import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import ta

## PART 1: Define Functions for Pulling, Processing, and Creating Indicators ##

# Fetch stock data based on the ticker, period, and interval
@st.cache_data
def fetch_stock_data(ticker, period, interval):
    try:
        end_date = datetime.now()
        if period == '1wk':
            start_date = end_date - timedelta(days=7)
            data = yf.download(ticker, start=start_date, end=end_date, interval=interval)
        else:
            data = yf.download(ticker, period=period, interval=interval)
        if data.empty:
            st.error(f"No data available for ticker '{ticker}' with period '{period}' and interval '{interval}'.")
            return pd.DataFrame()
        return data
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# Process data to ensure it is timezone-aware and correctly formatted
def process_data(data):
    if data.index.tzinfo is None:
        data.index = data.index.tz_localize('UTC')
    data.index = data.index.tz_convert('US/Eastern')
    data.reset_index(inplace=True)
    data.rename(columns={'Date': 'Datetime'}, inplace=True)
    
    # Flatten any multi-dimensional columns
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if data[col].ndim > 1:  # Check if column is multi-dimensional
            data[col] = data[col].iloc[:, 0]  # Convert to 1D Series
    
    return data

# Calculate basic metrics from the stock data
def calculate_metrics(data):
    # Convert Series values to native Python float types
    last_close = float(data['Close'].iloc[-1])
    prev_close = float(data['Close'].iloc[0])
    change = last_close - prev_close
    pct_change = (change / prev_close) * 100
    high = float(data['High'].max())
    low = float(data['Low'].min())
    volume = int(data['Volume'].sum())
    return last_close, change, pct_change, high, low, volume

# Add technical indicators (SMA and EMA)
def add_technical_indicators(data):
    # Ensure Close data is 1-dimensional and convert to pandas Series
    if data['Close'].ndim > 1:
        close_data = pd.Series(data['Close'].values.ravel(), index=data.index)
    else:
        close_data = data['Close']
    
    # Calculate indicators using the pandas Series
    data['SMA_20'] = ta.trend.sma_indicator(close=close_data, window=20)
    data['EMA_20'] = ta.trend.ema_indicator(close=close_data, window=20)
    return data

## PART 2: Creating the Dashboard App layout ##

# Set up Streamlit page layout
st.set_page_config(layout="wide")
st.title('Real-Time Stock Dashboard')

# 2A: SIDEBAR PARAMETERS
st.sidebar.header('Chart Parameters')
ticker = st.sidebar.text_input('Ticker', 'ADBE')
time_period = st.sidebar.selectbox('Time Period', ['1d', '1wk', '1mo', '1y', 'max'])
chart_type = st.sidebar.selectbox('Chart Type', ['Candlestick', 'Line'])
indicators = st.sidebar.multiselect('Technical Indicators', ['SMA 20', 'EMA 20'])

# Mapping of time periods to data intervals
interval_mapping = {
    '1d': '1m',
    '1wk': '30m',
    '1mo': '1d',
    '1y': '1wk',
    'max': '1wk'
}

# 2B: MAIN CONTENT AREA
if st.sidebar.button('Update'):
    data = fetch_stock_data(ticker, time_period, interval_mapping[time_period])
    if not data.empty:
        data = process_data(data)
        data = add_technical_indicators(data)

        last_close, change, pct_change, high, low, volume = calculate_metrics(data)

        # Display main metrics
        st.metric(label=f"{ticker} Last Price", value=f"{last_close:.2f} USD", delta=f"{change:.2f} ({pct_change:.2f}%)")

        col1, col2, col3 = st.columns(3)
        col1.metric("High", f"{high:.2f} USD")
        col2.metric("Low", f"{low:.2f} USD")
        col3.metric("Volume", f"{volume:,}")

        try:
            # Create figure with secondary y-axis
            fig = go.Figure()
            
            if chart_type == 'Candlestick':
                fig.add_trace(
                    go.Candlestick(
                        x=data['Datetime'],
                        open=data['Open'],
                        high=data['High'],
                        low=data['Low'],
                        close=data['Close'],
                        name='OHLC'
                    )
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=data['Datetime'],
                        y=data['Close'],
                        mode='lines',
                        name='Close'
                    )
                )
            
            # Add selected technical indicators
            for indicator in indicators:
                if indicator == 'SMA 20':
                    fig.add_trace(
                        go.Scatter(
                            x=data['Datetime'],
                            y=data['SMA_20'],
                            mode='lines',
                            name='SMA 20',
                            line=dict(color='orange')
                        )
                    )
                elif indicator == 'EMA 20':
                    fig.add_trace(
                        go.Scatter(
                            x=data['Datetime'],
                            y=data['EMA_20'],
                            mode='lines',
                            name='EMA 20',
                            line=dict(color='blue')
                        )
                    )
            
            # Update layout with better formatting
            fig.update_layout(
                title=f'{ticker} {time_period.upper()} Chart',
                yaxis_title='Price (USD)',
                xaxis_title='Date',
                height=600,
                template='plotly_white',
                hovermode='x unified',
                xaxis=dict(
                    rangeslider=dict(visible=True),
                    type='date'
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='lightgrey'
                )
            )
            
            # Display the chart
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error creating chart: {str(e)}")

        # Display historical data and technical indicators
        st.subheader('Historical Data')
        st.dataframe(data[['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']])

        st.subheader('Technical Indicators')
        st.dataframe(data[['Datetime', 'SMA_20', 'EMA_20']])

# 2C: SIDEBAR REAL-TIME PRICES
st.sidebar.header('Real-Time Stock Prices')
stock_symbols = ['AAPL', 'GOOGL', 'AMZN', 'MSFT']
for symbol in stock_symbols:
    real_time_data = fetch_stock_data(symbol, '1d', '1m')
    if not real_time_data.empty:
        real_time_data = process_data(real_time_data)
        last_price = float(real_time_data['Close'].iloc[-1])
        open_price = float(real_time_data['Open'].iloc[0])
        change = last_price - open_price
        pct_change = (change / open_price) * 100
        st.sidebar.metric(f"{symbol}", f"{last_price:.2f} USD", f"{change:.2f} ({pct_change:.2f}%)")

st.sidebar.subheader('About')
st.sidebar.info('This dashboard provides stock data and technical indicators for various time periods. Use the sidebar to customize your view.')
