import pandas as pd
import yfinance as yf
import streamlit as st
from forecast import render_forecast_tab


def get_currency_symbol(currency_code):
    currency_map = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'INR': '₹',
        'AUD': 'A$',
        'CAD': 'C$',
        'CHF': 'CHF',
        'CNY': '¥',
        'SEK': 'kr',
        'NOK': 'kr',
        'DKK': 'kr',
        'ZAR': 'R',
        'HKD': 'HK$',
        'SGD': 'S$',
        'NZD': 'NZ$',
        'MXN': 'MX$',
        'BRL': 'R$',
        'RUB': '₽',
        'KRW': '₩',
        'TRY': '₺',
        'AED': 'د.إ',
        'SAR': '﷼',
    }
    return currency_map.get((currency_code or '').upper(), '$')


def format_number_with_commas(value, decimals=2):
    number = float(value)
    return f'{number:,.{decimals}f}'


def format_readable_number(value):
    number = float(value)
    absolute_number = abs(number)
    for divisor, suffix in (
        (1_000_000_000_000, 'T'),
        (1_000_000_000, 'B'),
        (1_000_000, 'M'),
        (1_000, 'K'),
    ):
        if absolute_number >= divisor:
            return f'{number / divisor:,.2f}{suffix}'
    return format_number_with_commas(number)


def format_stat_value(label, value, currency_code='USD'):
    if value is None:
        return 'N/A'

    symbol = get_currency_symbol(currency_code)

    if isinstance(value, (int, float)):
        if label in {'Market Cap', 'Enterprise Value'}:
            return f'{symbol}{format_readable_number(value)}'

        if label in {'Dividend Yield', 'Operating Margin', 'Profit Margin', 'Gross Margin', 'EBITDA Margin', 'Return on Assets', 'Return on Equity', 'ROA', 'ROE'}:
            return f'{format_number_with_commas(value * 100)}%'

        if label in {'PE Ratio', 'EPS', 'Beta', 'P/B Ratio', 'EV/Revenue', 'EV/EBITDA', 'Price to Book', 'P/E Ratio', 'Debt/Equity', 'Current Ratio', 'Quick Ratio'}:
            return format_number_with_commas(value)

        if label in {'52 Week High', '52 Week Low', 'Previous Close', 'Open', 'Day Low', 'Day High', 'Market Price', 'Target Price', 'Book Value', 'Cash per Share'}:
            return f'{symbol}{format_number_with_commas(value)}'

        if label in {'Volume', 'Average Volume', 'Shares Outstanding'}:
            return format_readable_number(value)

        if label in {'Total Debt', 'Total Cash', 'Cash & Equivalents', 'Free Cash Flow', 'Operating Cash Flow', 'Revenue', 'Net Income', 'EBITDA', 'Gross Profit', 'Enterprise Value'}:
            return f'{symbol}{format_readable_number(value)}'

        return f'{symbol}{format_readable_number(value)}'

    return str(value)


def render_stats_grid(stats_dict, currency_code='USD', percent_labels=None):
    percent_labels = percent_labels or set()
    stats_items = list(stats_dict.items())
    for i in range(0, len(stats_items), 6):
        cols = st.columns(6)
        for col, (label, value) in zip(cols, stats_items[i:i + 6]):
            with col:
                if value is None:
                    display_value = 'N/A'
                elif label in percent_labels and isinstance(value, (int, float)):
                    display_value = f'{format_number_with_commas(value * 100)}%'
                else:
                    display_value = format_stat_value(label, value, currency_code)
                st.metric(label=label, value=display_value)


def render_overview_section(info, stock):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.write('**Symbol**')
        st.write('**ISIN**')
        st.write('**Industry**')
        st.write('**Website**')
        st.write('**Currency**')
        st.write('**Outstanding Shares**')

    with col2:
        st.write(info.get('symbol'))
        st.write(stock.get_isin() or 'Not Available')
        st.write(info.get('industry'))
        st.write(info.get('website'))
        st.write(info.get('currency'))
        st.write(str(info.get('sharesOutstanding')) if info.get('sharesOutstanding') is not None else 'Not Available')

    with col3:
        st.write('**Long Name**')
        st.write('**Country**')
        st.write('**Sector**')
        st.write('**Total Employee**')
        st.write('**Exchange**')

    with col4:
        st.write(info.get('longName'))
        st.write(info.get('country'))
        st.write(info.get('sector'))
        st.write(str(info.get('fullTimeEmployees')) if info.get('fullTimeEmployees') is not None else 'Not Available')
        st.write(info.get('exchange', 'No description available.'))

    st.subheader('Description', divider=True)
    st.text(info.get('longBusinessSummary', 'No description available.'))

    st.subheader('Key Executives', divider=True)
    exec = info.get('companyOfficers', [])
    if exec:
        exec_df = pd.DataFrame(exec)
        exec_df = exec_df[['name', 'title', 'totalPay', 'exercisedValue', 'yearBorn']]
        exec_df.columns = ['Name', 'Title', 'Total Pay', 'Exercised Value', 'Year Born']
        st.dataframe(exec_df)
    else:
        st.info('No key executives information available.')

    st.subheader('Shareholders', divider=True)
    try:
        major_holders = stock.major_holders
    except Exception:
        major_holders = pd.DataFrame()

    if major_holders is not None and not major_holders.empty:
        major_holders_df = major_holders.copy()
        if major_holders_df.shape[1] >= 2:
            major_holders_df = major_holders_df.iloc[:, :2]
            major_holders_df.columns = ['Measure', 'Value']
            st.dataframe(major_holders_df, hide_index=True, use_container_width=True)
    else:
        st.info('No major holder information available.')

    try:
        institutional_holders = stock.institutional_holders
    except Exception:
        institutional_holders = pd.DataFrame()

    if institutional_holders is not None and not institutional_holders.empty:
        st.caption('Largest reported institutional holders')
        institutional_holders_df = institutional_holders.copy()
        if 'Date Reported' in institutional_holders_df.columns:
            institutional_holders_df['Date Reported'] = pd.to_datetime(
                institutional_holders_df['Date Reported'], errors='coerce'
            ).dt.strftime('%Y-%m-%d')
        for column in ['pctHeld', 'pctChange']:
            if column in institutional_holders_df.columns:
                institutional_holders_df[column] = (
                    pd.to_numeric(institutional_holders_df[column], errors='coerce') * 100
                ).map(lambda value: f'{value:,.2f}%' if pd.notna(value) else 'N/A')
        for column in ['Shares', 'Value']:
            if column in institutional_holders_df.columns:
                institutional_holders_df[column] = pd.to_numeric(
                    institutional_holders_df[column], errors='coerce'
                ).map(lambda value: f'{value:,.0f}' if pd.notna(value) else 'N/A')
        institutional_holders_df = institutional_holders_df.rename(columns={
            'pctHeld': '% Held',
            'pctChange': '% Change',
        })
        st.dataframe(institutional_holders_df, hide_index=True, use_container_width=True)
    else:
        st.info('No institutional holder information available.')


def get_fundamental_period_label(info, stock=None):
    periods = []
    annual_financials = getattr(stock, 'financials', None) if stock is not None else None
    if annual_financials is not None and hasattr(annual_financials, 'columns'):
        periods.extend(list(annual_financials.columns))

    periods.append(info.get('lastFiscalYearEnd'))
    for period in periods:
        if period is None:
            continue
        try:
            return f'FY {pd.to_datetime(period).year}'
        except Exception:
            continue

    return 'Latest available period'


def render_stats_section(info, stock=None):
    currency_code = (info.get('currency') or 'USD').upper()

    st.subheader('Trading Stats', divider=True)
    trading_stats = {
        'Market Cap': info.get('marketCap'),
        'Market Price': info.get('regularMarketPrice'),
        'Previous Close': info.get('previousClose'),
        'Open': info.get('open'),
        'Day High': info.get('dayHigh'),
        'Day Low': info.get('dayLow'),
        '52 Week High': info.get('fiftyTwoWeekHigh'),
        '52 Week Low': info.get('fiftyTwoWeekLow'),
        'Volume': info.get('volume'),
        'Average Volume': info.get('averageVolume'),
        'Dividend Yield': info.get('dividendYield')
    }
    render_stats_grid(
        trading_stats,
        currency_code,
        percent_labels={'Dividend Yield'}
    )

    fundamental_period = get_fundamental_period_label(info, stock)
    st.subheader(f'Fundamental Numbers ({fundamental_period})', divider=True)
    st.caption('Annual financial figures and key ratios for the latest reported fiscal year.')
    fundamental_stats = {
        'Revenue': info.get('totalRevenue'),
        'Gross Profit': info.get('grossProfits'),
        'EBITDA': info.get('ebitda'),
        'Operating Cash Flow': info.get('operatingCashflow'),
        'Free Cash Flow': info.get('freeCashflow'),
        'Net Income': info.get('netIncomeToCommon'),
        'Total Cash': info.get('totalCash'),
        'Total Debt': info.get('totalDebt'),
        'Cash per Share': info.get('totalCash') / info.get('sharesOutstanding') if info.get('totalCash') and info.get('sharesOutstanding') else None,
        'Book Value': info.get('bookValue'),
        'Shares Outstanding': info.get('sharesOutstanding'),
        'Debt/Equity': info.get('debtToEquity'),
        'Current Ratio': info.get('currentRatio'),
        'Quick Ratio': info.get('quickRatio'),
        'Gross Margin': info.get('grossMargins'),
        'Operating Margin': info.get('operatingMargins'),
        'Profit Margin': info.get('profitMargins'),
        'Revenue Growth': info.get('revenueGrowth'),
        'Earnings Growth': info.get('earningsGrowth'),
        'Return on Assets': info.get('returnOnAssets'),
        'Return on Equity': info.get('returnOnEquity'),
    }
    render_stats_grid(
        fundamental_stats,
        currency_code,
        percent_labels={
            'Gross Margin',
            'Operating Margin',
            'Profit Margin',
            'Revenue Growth',
            'Earnings Growth',
            'Return on Assets',
            'Return on Equity',
        }
    )

    st.subheader('Other Stats', divider=True)
    other_stats = {
        'Beta': info.get('beta'),
        'EPS': info.get('trailingEps'),
        'Forward P/E': info.get('forwardPE'),
        'P/B Ratio': info.get('priceToBook'),
        'P/S Ratio': info.get('priceToSalesTrailing12Months'),
        'P/E Ratio': info.get('trailingPE'),
        'EV/Revenue': info.get('enterpriseToRevenue'),
        'EV/EBITDA': info.get('enterpriseToEbitda'),
        'Return on Assets': info.get('returnOnAssets'),
        'Return on Equity': info.get('returnOnEquity'),
        'Target Price': info.get('targetMeanPrice'),
        'Recommendation': info.get('recommendationKey')
    }
    render_stats_grid(
        other_stats,
        currency_code,
        percent_labels={'Return on Assets', 'Return on Equity'}
    )


def format_statement_value(value, currency_code, metric=None):
    if value is None or pd.isna(value):
        return '-'

    metric_name = str(metric or '').lower()
    if 'rate' in metric_name or 'ratio' in metric_name or 'per share' in metric_name:
        return format_readable_number(value)

    return f'{get_currency_symbol(currency_code)}{format_readable_number(value)}'


def render_financial_summary_metrics(stock, info, currency_code):
    annual = stock.financials if getattr(stock, 'financials', None) is not None else pd.DataFrame()
    balance = stock.balance_sheet if getattr(stock, 'balance_sheet', None) is not None else pd.DataFrame()
    cashflow = stock.cashflow if getattr(stock, 'cashflow', None) is not None else pd.DataFrame()

    def get_first_value(df, metric_names):
        if df is None or df.empty:
            return None
        lookup = [name for name in metric_names if name in df.index]
        if not lookup:
            return None
        value = df.loc[lookup[0]]
        if isinstance(value, pd.Series):
            return value.iloc[0] if not value.empty else None
        return value

    summary = {
        'Revenue': get_first_value(annual, ['Total Revenue', 'Revenue']),
        'Gross Profit': get_first_value(annual, ['Gross Profit']),
        'Operating Income': get_first_value(annual, ['Operating Income', 'Operating Income/Income']),
        'Net Income': get_first_value(annual, ['Net Income', 'Net Income Common Stockholders']),
        'Free Cash Flow': get_first_value(cashflow, ['Free Cash Flow', 'Operating Cash Flow']),
        'Total Assets': get_first_value(balance, ['Total Assets', 'Total Assets / Total Assets']),
        'Total Liabilities': get_first_value(balance, ['Total Liabilities Net Minority Interest']),
        'Cash & Equivalents': get_first_value(balance, ['Cash And Cash Equivalents', 'Cash'])
    }

    summary = {key: value for key, value in summary.items() if value is not None}
    if not summary:
        st.info('No summary financial metrics available for this ticker.')
        return

    st.subheader('Financial Highlights', divider=True)
    chart_df = pd.DataFrame({
        'Metric': list(summary.keys()),
        'Value': [float(v) if pd.notna(v) and isinstance(v, (int, float)) else 0 for v in summary.values()]
    })

    chart_df = chart_df.sort_values('Value', ascending=False)
    st.bar_chart(
        chart_df.set_index('Metric')['Value'],
        use_container_width=True,
        height=260,
        x_label='Metric',
        y_label='Value'
    )

    st.caption('Revenue, profit, and cash metrics shown in the latest available period.')


def format_date_label(value):
    if value is None:
        return ''

    if isinstance(value, str):
        value = value.strip()
        if value == '':
            return ''
        if ' ' in value:
            value = value.split(' ')[0]
        return value

    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')

    return str(value)


def render_financial_statement_table(statement_df, currency_code, title):
    if statement_df is None or statement_df.empty:
        st.info(f'No {title.lower()} data available.')
        return

    table = statement_df.copy()
    if isinstance(table.index, pd.MultiIndex):
        table = table.reset_index()

    if isinstance(table, pd.DataFrame):
        table = table.rename_axis('Metric').reset_index()
        table.columns = [str(col) for col in table.columns]

    if table.empty:
        st.info(f'No {title.lower()} data available.')
        return

    columns = list(table.columns)
    if columns and columns[0].lower() == 'index':
        columns[0] = 'Metric'
        table.columns = columns

    if 'Metric' not in table.columns:
        table.insert(0, 'Metric', table.index)

    table.columns = [format_date_label(col) if col != 'Metric' else 'Metric' for col in table.columns]

    rename_map = {
        'Total Revenue': 'Revenue',
        'Revenue': 'Revenue',
        'Cost Of Revenue': 'Cost of revenue',
        'Cost of Revenue': 'Cost of revenue',
        'Gross Profit': 'Gross profit',
        'Operating Expense': 'Operating expenses',
        'Operating Expenses': 'Operating expenses',
        'Research And Development': 'Research & development',
        'Operating Income': 'Operating income',
        'Income Before Tax': 'Pretax income',
        'Income Before Income Tax Expense': 'Pretax income',
        'Income Tax Expense': 'Income tax expense',
        'Net Income': 'Net income',
        'Net Income Common Stockholders': 'Net income attributable to common shareholders',
        'Cash And Cash Equivalents': 'Cash & cash equivalents',
        'Cash and Cash Equivalents': 'Cash & cash equivalents',
        'Short Term Investments': 'Short-term investments',
        'Net Receivables': 'Accounts receivable',
        'Inventory': 'Inventory',
        'Total Current Assets': 'Total current assets',
        'Total Assets': 'Total assets',
        'Total Current Liabilities': 'Total current liabilities',
        'Total Liabilities': 'Total liabilities',
        'Total Debt': 'Total debt',
        'Long Term Debt': 'Long-term debt',
        'Net Cash Provided By Operating Activities': 'Operating cash flow',
        'Operating Cash Flow': 'Operating cash flow',
        'Capital Expenditure': 'Capital expenditure',
        'Free Cash Flow': 'Free cash flow',
        'Depreciation': 'Depreciation & amortization',
        'Change In Working Capital': 'Change in working capital',
        'Net Borrowings': 'Net borrowings',
    }
    table['Metric'] = table['Metric'].replace(rename_map)

    for col in [c for c in table.columns if c != 'Metric']:
        try:
            table[col] = [
                '-' if value is None or (isinstance(value, str) and value.strip().lower() in {'none', 'nan'})
                else value if isinstance(value, str)
                else format_statement_value(value, currency_code, table.at[index, 'Metric'])
                for index, value in table[col].items()
            ]
        except Exception:
            pass

    row_count = len(table)
    auto_height = max(420, min(1200, row_count * 36 + 80))

    st.dataframe(
        table,
        use_container_width=True,
        height=auto_height,
        hide_index=True,
        column_config={
            col: st.column_config.Column(
                label=str(col),
                width='medium' if col != 'Metric' else 'large'
            )
            for col in table.columns
        }
    )


def render_financials_section(stock, info):
    currency_code = (info.get('currency') or 'USD').upper()
    period_type = st.selectbox('Statement period', ['Quarterly', 'Annual'], index=1)

    if period_type == 'Quarterly':
        income = stock.quarterly_financials
        balance = stock.quarterly_balance_sheet
        cashflow = stock.quarterly_cashflow
    else:
        income = stock.financials
        balance = stock.balance_sheet
        cashflow = stock.cashflow

    render_financial_summary_metrics(stock, info, currency_code)

    statement_tabs = st.tabs(['Income statement', 'Balance sheet', 'Cash flow'])

    with statement_tabs[0]:
        st.subheader('Income statement', divider=True)
        st.caption('Revenue less cost of revenue = gross profit. Gross profit less operating expenses = operating income. Operating income less interest and taxes = net income.')
        if income is not None and not income.empty:
            income_df = income.copy()
            income_df = income_df.loc[~income_df.index.isin([''] + [None])]
            if income_df.empty:
                st.info('No standard income statement data available for this ticker.')
            else:
                render_financial_statement_table(income_df, currency_code, 'Income statement')
        else:
            st.info('No income statement data available.')

    with statement_tabs[1]:
        st.subheader('Balance sheet', divider=True)
        st.caption('Current assets are the resources held for short-term use: cash, receivables, inventory, and other short-term items. Total assets are the full asset base after all current and long-term assets are added.')
        if balance is not None and not balance.empty:
            balance_df = balance.copy()
            balance_df = balance_df.loc[~balance_df.index.isin([''] + [None])]
            if balance_df.empty:
                st.info('No standard balance sheet data available for this ticker.')
            else:
                render_financial_statement_table(balance_df, currency_code, 'Balance sheet')
        else:
            st.info('No balance sheet data available.')

    with statement_tabs[2]:
        st.subheader('Cash flow', divider=True)
        st.caption('Operating cash flow starts from net income and adjusts for non-cash items and working-capital changes. Free cash flow is operating cash flow minus capital expenditure.')
        if cashflow is not None and not cashflow.empty:
            cashflow_df = cashflow.copy()
            cashflow_df = cashflow_df.loc[~cashflow_df.index.isin([''] + [None])]
            if cashflow_df.empty:
                st.info('No standard cash flow data available for this ticker.')
            else:
                render_financial_statement_table(cashflow_df, currency_code, 'Cash flow')
        else:
            st.info('No cash flow data available.')


def get_chart_history(stock, period_label='Max', realtime=False):
    if realtime:
        return stock.history(period='1d', interval='1m', auto_adjust=False)

    period_map = {
        '1D': ('1d', '1m'),
        '5D': ('5d', '15m'),
        '1M': ('1mo', '1h'),
        '3M': ('3mo', '1d'),
        '6M': ('6mo', '1d'),
        '1Y': ('1y', '1d'),
        '2Y': ('2y', '1d'),
        '5Y': ('5y', '1d'),
        '10Y': ('10y', '1d'),
        'Max': ('max', '1d'),
        'All': ('max', '1d')
    }

    period, interval = period_map.get(period_label, ('max', '1d'))
    return stock.history(period=period, interval=interval, auto_adjust=False)


def get_historical_data(stock, start_date, end_date):
    if stock is None:
        return pd.DataFrame()

    try:
        adjusted_end = pd.Timestamp(end_date) + pd.Timedelta(days=1)
        return stock.history(start=start_date, end=adjusted_end, auto_adjust=False)
    except Exception:
        return pd.DataFrame()


def stream_single_ticker(ticker: str):
    ticker = ticker.strip().upper()
    if not ticker:
        st.error('Please enter a valid stock ticker.')
        return

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='5d')
        hist = hist.dropna(subset=['Close'])

        if len(hist) < 2:
            st.error(f'Could not fetch sufficient data for {ticker}. Make sure it is a valid symbol.')
            return

        prev_close = float(hist['Close'].iloc[-2])
        last_recorded_price = float(hist['Close'].iloc[-1])
        price_placeholder = st.empty()

        def render_price(price_value, is_live=False):
            change = price_value - prev_close
            pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
            label = f'{ticker} Live Price in {stock.info.get("currency", "USD")}' if is_live else f'{ticker} Recent Close in {stock.info.get("currency", "USD")}'
            price_placeholder.metric(
                label=label,
                value=f'{price_value:,.2f}',
                delta=f'{change:,.2f} ({pct_change:,.2f}%)'
            )

        render_price(last_recorded_price, is_live=False)

        if hasattr(yf, 'WebSocket'):
            try:
                with yf.WebSocket() as ws:
                    ws.subscribe([ticker])
                    ws.listen(lambda message: render_price(float(message['price']), is_live=True) if message and isinstance(message, dict) and message.get('price') else render_price(last_recorded_price, is_live=False))
            except Exception:
                st.caption('Market is closed or live websocket data is unavailable. Showing the latest closing price.')
                render_price(last_recorded_price, is_live=False)
        else:
            st.caption('Live streaming is not supported in this environment. Showing the recent closing price.')
            render_price(last_recorded_price, is_live=False)

    except Exception as e:
        st.error(f'An error occurred: {e}')


def render_data_section(stock, symbol):
    if 'historical_data' not in st.session_state:
        st.session_state.historical_data = pd.DataFrame()

    st.subheader('Historical Data', divider=True)

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input('Start date', value=pd.to_datetime('2020-01-01'), key='data_start_date')
    with col2:
        end_date = st.date_input('End date', value=pd.Timestamp.today(), key='data_end_date')

    if start_date > end_date:
        st.warning('Start date must be before end date.')
        return

    fetch_button = st.button('Fetch data', type='primary')

    if fetch_button:
        data = get_historical_data(stock, start_date, end_date)
        if data.empty:
            st.session_state.historical_data = pd.DataFrame()
            st.info('No historical data available for the selected range.')
        else:
            st.session_state.historical_data = data.reset_index()
            st.success(f'Loaded {len(st.session_state.historical_data)} rows for {symbol}.')

    data = st.session_state.get('historical_data')
    if data is None or data.empty:
        st.info('Choose a date range and click Fetch data to load the dataset.')
        return

    data_tabs = st.tabs(['View data', 'Download'])

    with data_tabs[0]:
        data_display = data.copy()
        if 'Date' not in data_display.columns and data_display.columns:
            data_display.rename(columns={data_display.columns[0]: 'Date'}, inplace=True)
        st.dataframe(data_display, use_container_width=True, height=420)

    with data_tabs[1]:
        csv_data = data.copy()
        if 'Date' not in csv_data.columns and csv_data.columns:
            csv_data.rename(columns={csv_data.columns[0]: 'Date'}, inplace=True)
        csv_bytes = csv_data.to_csv(index=False).encode('utf-8')
        st.download_button(
            'Download CSV',
            data=csv_bytes,
            file_name=f'{symbol}_historical_data.csv',
            mime='text/csv',
            use_container_width=True,
        )


def render_stock_dashboard(ticker):
    side_stock = ticker.strip().upper()
    stock = yf.Ticker(side_stock)
    info = stock.info

    left, right = st.columns([3, 1], vertical_alignment='bottom')
    with left:
        st.title(info.get('longName', side_stock))

    tab1, tab2, tab3, tab4, tab5 = st.tabs(['Overview', 'Chart', 'Quick Stats', 'Financials', 'Data'])

    with tab1:
        render_overview_section(info, stock)

    with tab2:
        chart_period = st.selectbox(
            'Chart period',
            ['Realtime', '1D', '5D', '1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', 'Max', 'All'],
            index=10
        )

        price_tab, forecast_tab = st.tabs(['Price Chart', 'Forecast & Volatility'])

        with price_tab:
            if chart_period == 'Realtime':
                live_df = get_chart_history(stock, realtime=True)
                if not live_df.empty:
                    st.caption('Live-ish data refreshes when the page reruns.')
                    st.line_chart(live_df['Close'], use_container_width=True)
                else:
                    st.info('No live data available for this ticker.')
            else:
                hist = get_chart_history(stock, chart_period)
                if not hist.empty:
                    st.line_chart(hist['Close'], use_container_width=True)
                else:
                    st.info('No historical data available for the selected period.')

        with forecast_tab:
            if chart_period == 'Realtime':
                st.info('Select a historical period to use the forecasting models.')
            else:
                render_forecast_tab(stock, chart_period, get_chart_history)

    with tab3:
        render_stats_section(info, stock)

    with tab4:
        render_financials_section(stock, info)

    with tab5:
        render_data_section(stock, side_stock)





    with right:
        stream_single_ticker(side_stock)