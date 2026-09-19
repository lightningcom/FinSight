import streamlit as st

from caller import render_stock_dashboard


st.set_page_config(
    page_title='FinanceSight',
    layout='wide'
)

st.sidebar.title("Search")
ticker = st.sidebar.text_input('Your Ticker is:', key='ticker_input')

if ticker:
    render_stock_dashboard(ticker)
