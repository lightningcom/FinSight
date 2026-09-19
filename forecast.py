import numpy as np
import pandas as pd
import sys
try:
    import streamlit as st
except ImportError:
    st = None

try:
    from arch import arch_model
    from xgboost import XGBRegressor
except ImportError:
    arch_model = None
    XGBRegressor = None
    dependency_error = 'xgboost or arch could not be imported.'
else:
    dependency_error = ''


FEATURE_COLUMNS = [
    'Return Lag 1',
    'Return Lag 2',
    'Return Lag 3',
    'Return Lag 5',
    'Return Lag 10',
    'Return Lag 20',
    'Return Mean 5',
    'Return Mean 20',
    'Return Volatility 20',
]

ACTUAL_COLOR = '#0F766E'
FORECAST_COLOR = '#D97706'
VOLATILITY_COLOR = '#C2410C'
LOWER_RANGE_COLOR = '#7C3AED'
UPPER_RANGE_COLOR = '#BE123C'


def load_forecasting_dependencies():
    global arch_model, XGBRegressor, dependency_error

    if arch_model is not None and XGBRegressor is not None:
        return True

    try:
        from arch import arch_model as installed_arch_model
        from xgboost import XGBRegressor as installed_xgb_regressor
    except Exception as error:
        dependency_error = f'{type(error).__name__}: {error}'
        return False

    arch_model = installed_arch_model
    XGBRegressor = installed_xgb_regressor
    dependency_error = ''
    return True


def create_return_features(prices):
    data = pd.DataFrame({'Close': prices.astype(float)})
    data['Return'] = np.log(data['Close'] / data['Close'].shift(1))

    for lag in [1, 2, 3, 5, 10, 20]:
        data[f'Return Lag {lag}'] = data['Return'].shift(lag)

    data['Return Mean 5'] = data['Return'].rolling(5).mean()
    data['Return Mean 20'] = data['Return'].rolling(20).mean()
    data['Return Volatility 20'] = data['Return'].rolling(20).std()
    data['Target'] = data['Return'].shift(-1)
    return data


def build_xgboost_model():
    return XGBRegressor(
        n_estimators=300,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='reg:squarederror',
        random_state=42,
    )


def fit_xgboost_model(feature_data):
    model = build_xgboost_model()
    model.fit(feature_data[FEATURE_COLUMNS], feature_data['Target'], verbose=False)
    return model


def predict_next_return(model, feature_row):
    input_data = pd.DataFrame([feature_row[FEATURE_COLUMNS].to_dict()], columns=FEATURE_COLUMNS)
    return float(model.predict(input_data)[0])


def forecast_xgboost(prices, forecast_days):
    feature_data = create_return_features(prices).dropna()
    model = fit_xgboost_model(feature_data)
    working_data = create_return_features(prices).copy()
    predictions = []

    for _ in range(forecast_days):
        feature_row = working_data.iloc[-1]
        predicted_return = predict_next_return(model, feature_row)
        next_price = float(working_data['Close'].iloc[-1]) * np.exp(predicted_return)
        next_date = working_data.index[-1] + pd.offsets.BDay(1)

        new_row = pd.Series(index=working_data.columns, dtype=float)
        new_row['Close'] = next_price
        new_row['Return'] = predicted_return
        for lag in [1, 2, 3, 5, 10, 20]:
            new_row[f'Return Lag {lag}'] = working_data['Return'].iloc[-lag + 1]
        new_row['Return Mean 5'] = working_data['Return'].tail(5).mean()
        new_row['Return Mean 20'] = working_data['Return'].tail(20).mean()
        new_row['Return Volatility 20'] = working_data['Return'].tail(20).std()
        new_row['Target'] = np.nan
        working_data.loc[next_date] = new_row
        predictions.append(next_price)

    dates = pd.bdate_range(start=prices.index[-1] + pd.offsets.BDay(1), periods=forecast_days)
    return pd.Series(predictions, index=dates, name='XGBoost Forecast')


def validate_xgboost(prices, train_size):
    feature_data = create_return_features(prices).dropna()
    train_end = min(train_size, len(feature_data) - 1)
    training_data = feature_data.iloc[:train_end]
    validation_data = feature_data.iloc[train_end:]

    if len(training_data) < 40 or validation_data.empty:
        return None

    model = fit_xgboost_model(training_data)
    predicted_returns = model.predict(validation_data[FEATURE_COLUMNS])
    current_prices = prices.loc[validation_data.index]
    predicted_prices = current_prices * np.exp(predicted_returns)
    actual_prices = current_prices * np.exp(validation_data['Target'])

    errors = actual_prices - predicted_prices
    direction_actual = np.sign(validation_data['Target'].to_numpy())
    direction_predicted = np.sign(predicted_returns)
    directional_accuracy = float((direction_actual == direction_predicted).mean() * 100)
    mae = float(np.abs(errors).mean())
    average_validation_price = float(actual_prices.mean())

    return {
        'MAE': mae,
        'MAE Percentage': (mae / average_validation_price) * 100 if average_validation_price else None,
        'Directional Accuracy': directional_accuracy,
        'Predicted': pd.Series(predicted_prices.to_numpy(), index=validation_data.index, name='Validation Forecast'),
    }


def forecast_garch_volatility(prices, forecast_days, train_size):
    if arch_model is None:
        return None

    returns = np.log(prices / prices.shift(1)).dropna() * 100
    training_returns = returns.iloc[:max(train_size - 1, 1)]
    if len(training_returns) < 40:
        return None

    model = arch_model(training_returns, mean='Zero', vol='GARCH', p=1, q=1, dist='t')
    fitted_model = model.fit(disp='off')
    variance = fitted_model.forecast(horizon=forecast_days).variance.iloc[-1].to_numpy()
    volatility = np.sqrt(np.maximum(variance, 0)) / 100
    dates = pd.bdate_range(start=prices.index[-1] + pd.offsets.BDay(1), periods=forecast_days)
    return pd.Series(volatility, index=dates, name='GARCH Volatility')


def render_forecast_tab(stock, chart_period, get_chart_history):
    dependencies_available = load_forecasting_dependencies()
    st.subheader('XGBoost Forecast and GARCH Volatility', divider=True)
    st.caption('The selected period is split chronologically: 85% for training and 15% for validation.')

    forecast_days = st.selectbox(
        'Forecast horizon (trading days)',
        [5, 10, 20, 30],
        index=0,
        key='forecast_horizon',
    )
    history = get_chart_history(stock, chart_period)
    prices = history['Close'].dropna() if not history.empty and 'Close' in history else pd.Series(dtype=float)

    if not dependencies_available:
        st.error(
            'Forecasting packages are unavailable. '
            f'Python: {sys.executable}. Error: {dependency_error}'
        )
        return
    if len(prices) < 100:
        st.warning('Choose at least 3 months of history. At least 100 trading observations are required.')
        return

    train_size = int(len(prices) * 0.85)
    validation_size = len(prices) - train_size
    st.caption(
        f'Historical window: {chart_period} | '
        f'{len(prices):,} trading days | '
        f'{train_size:,} training observations | '
        f'{validation_size:,} validation observations.'
    )
    validation = validate_xgboost(prices, train_size)
    forecast = forecast_xgboost(prices, forecast_days)
    volatility = forecast_garch_volatility(prices, forecast_days, train_size)

    if validation is not None:
        st.subheader('Validation Results', divider=True)
        st.caption(
            'Actual prices compared with one-step-ahead XGBoost estimates '
            'on the held-out final 15% of the selected historical window.'
        )
        validation_chart = pd.concat([
            prices.rename('Actual Price'),
            validation['Predicted'],
        ], axis=1)
        st.line_chart(
            validation_chart,
            color=[ACTUAL_COLOR, FORECAST_COLOR],
            use_container_width=True,
        )
        metric_col1, metric_col2 = st.columns(2)
        metric_col1.metric('Validation MAE', f'{validation["MAE"]:,.2f}')
        metric_col2.metric('Directional Accuracy', f'{validation["Directional Accuracy"]:.1f}%')

        mae_percentage = validation['MAE Percentage']
        if mae_percentage is not None:
            if mae_percentage <= 1:
                mae_assessment = 'Good: average error is below 1% of the stock price.'
            elif mae_percentage <= 2:
                mae_assessment = 'Reasonable: average error is between 1% and 2%.'
            elif mae_percentage <= 5:
                mae_assessment = 'Moderate: predictions have noticeable price error.'
            else:
                mae_assessment = 'High error: predictions are not close to the actual price.'
        else:
            mae_assessment = 'Unavailable: the validation price scale could not be calculated.'

        directional_accuracy = validation['Directional Accuracy']
        if directional_accuracy >= 60:
            direction_assessment = 'Good: direction was correct at least 60% of the time.'
        elif directional_accuracy >= 55:
            direction_assessment = 'Modest: direction is somewhat better than random.'
        elif directional_accuracy >= 45:
            direction_assessment = 'Weak: direction is close to random guessing.'
        else:
            direction_assessment = 'Poor: direction was usually predicted incorrectly.'

        assessment_col1, assessment_col2 = st.columns(2)
        assessment_col1.caption(f'MAE assessment: {mae_assessment}')
        assessment_col2.caption(f'Direction assessment: {direction_assessment}')

    st.subheader('Share Price Forecast', divider=True)
    st.caption(
        f'XGBoost forecast for the next {forecast_days} trading days, '
        'trained on the complete selected historical window after validation.'
    )
    forecast_chart = pd.concat([prices.tail(120).rename('Actual Price'), forecast], axis=1)
    st.line_chart(
        forecast_chart,
        color=[ACTUAL_COLOR, FORECAST_COLOR],
        use_container_width=True,
    )

    if volatility is not None:
        st.subheader('Expected Volatility', divider=True)
        st.caption(
            'GARCH-estimated daily volatility for the forecast horizon. '
            'Higher percentages indicate a wider expected range of price movement.'
        )
        volatility_chart = (volatility * 100).rename('Expected Daily Volatility (%)')
        st.line_chart(
            volatility_chart,
            color=VOLATILITY_COLOR,
            use_container_width=True,
        )
        cumulative_volatility = np.sqrt((volatility ** 2).cumsum())
        confidence = pd.DataFrame({
            'Forecast': forecast,
            'Lower 95% Range': forecast * np.exp(-1.96 * cumulative_volatility),
            'Upper 95% Range': forecast * np.exp(1.96 * cumulative_volatility),
        })
        st.subheader('Forecast Confidence Range', divider=True)
        st.caption(
            'The shaded-equivalent upper and lower lines show an approximate '
            '95% statistical range based on GARCH volatility, not a guarantee.'
        )
        st.line_chart(
            confidence,
            color=[FORECAST_COLOR, LOWER_RANGE_COLOR, UPPER_RANGE_COLOR],
            use_container_width=True,
        )

    st.caption('XGBoost estimates returns and GARCH estimates volatility. This is not investment advice.')
    st.markdown('---')
    st.subheader('Methodology and Calculations', divider=True)
    st.markdown(
        '**Historical split:** The selected historical window is ordered by date and split chronologically. '
        'The first 85% trains the models and the final 15% is held out for validation.\n\n'
        '**XGBoost forecast:** The model learns from daily log returns, calculated as '
        '`ln(today close / previous close)`, plus lagged returns, 5-day and 20-day average returns, '
        'and 20-day rolling volatility. The predicted return is converted back to price using '
        '`next price = current price x exp(predicted return)`.\n\n'
        '**Validation MAE:** Mean Absolute Error is calculated as '
        '`average(abs(actual next-day price - predicted next-day price))`. Lower values are better, '
        'and the result is expressed in the stock currency.\n\n'
        '**Directional accuracy:** For every validation day, the predicted return sign is compared '
        'with the actual return sign. The percentage of matching directions is shown. A result near '
        '50% is similar to random direction guessing.\n\n'
        '**GARCH volatility:** GARCH models the changing variance of historical returns. Its output is '
        'shown as expected daily volatility. Higher volatility means a wider range of possible price movement.\n\n'
        '**95% confidence range:** The forecast is expanded using cumulative GARCH volatility: '
        '`forecast x exp(+/- 1.96 x cumulative volatility)`. This is an approximate statistical range, '
        'not a guaranteed high and low.\n\n'
        '**Important:** These are statistical estimates based only on historical market data. News, '
        'earnings, market conditions, and unexpected events can cause actual prices to differ substantially.'
    )
