# FinanceSight

FinanceSight is a Streamlit dashboard for exploring market data, company fundamentals, financial statements, and model-based price forecasts for a ticker symbol.

## Features

- Trading statistics, company information, key executives, and financial highlights from Yahoo Finance through `yfinance`.
- Current valuation measures including market capitalization, enterprise value, and common valuation ratios.
- Interactive historical price charts and a forecast tab.
- XGBoost return forecasting with GARCH volatility estimates and an approximate 95% statistical range.

The valuation table intentionally shows only current values. Historical valuation values are not displayed because the data source does not provide a reliable historical series for these measures in this app.

## Forecasting method

The selected price history is ordered chronologically and split into 85% training data and 15% held-out validation data. The XGBoost regressor uses daily log returns, lagged returns, rolling mean returns, and 20-day rolling volatility to estimate the next return. The estimated return is converted back to a price forecast.

A GARCH(1,1) model estimates expected daily volatility from historical returns. The dashboard uses cumulative volatility to show an approximate 95% range around the forecast. This range is statistical context, not a guarantee.

Validation reports Mean Absolute Error and directional accuracy. Directional accuracy near 50% is treated as close to random direction guessing, so this project is intended as a forecasting methods and validation exercise rather than investment advice.

## Run locally

1. Create and activate a Python environment.
2. Install the dependencies:

   ```text
   pip install -r requirements.txt
   ```

3. Start the dashboard:

   ```text
   streamlit run landing.py
   ```

4. Enter a ticker symbol such as `AAPL` in the sidebar.

The app needs an internet connection to retrieve market data from Yahoo Finance. At least 100 trading observations are required for the forecasting tab.

## Project files

- `landing.py` starts the Streamlit interface.
- `caller.py` loads company data and renders the dashboard sections.
- `forecast.py` contains feature engineering, XGBoost forecasting, validation, and GARCH volatility estimation.
- `requirements.txt` lists the Python dependencies.

## Disclaimer

FinanceSight is an educational software project. Its estimates are based on historical market data and are not financial advice.