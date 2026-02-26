import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta
from plotly.subplots import make_subplots
import os
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Global Trading Hub", layout="wide", initial_sidebar_state="expanded")

# --- AUTO UPDATE SERVER ---
# Refreshes the entire app every 30 seconds
count = st_autorefresh(interval=30000, limit=10000, key="fizzbuzzcounter")

# Dark Theme + Custom CSS
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #161b22; border-radius: 10px; padding: 15px; border: 1px solid #30363d; }
    [data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌐 Global Trading Agent Hub")

# Sidebar - Multi-Agent Control
st.sidebar.header("🕹️ Agent Control")
st.sidebar.info(f"Refreshed: {datetime.now().strftime('%H:%M:%S')} (Cycle #{count})")

def load_trades():
    if os.path.exists("data/trades.json"):
        with open("data/trades.json", "r") as f:
            try:
                data = json.load(f)
                if not data: return pd.DataFrame()
                df = pd.DataFrame(data)
                df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
                return df
            except:
                return pd.DataFrame()
    return pd.DataFrame()

df = load_trades()

if not df.empty:
    available_agents = df['agent'].unique().tolist()
    selected_agents = st.sidebar.multiselect("Active Agents", available_agents, default=available_agents)
    chart_type = st.sidebar.radio("Market Chart Type", ["Candlestick", "Line", "Area"])
    pair = st.sidebar.selectbox("Market View", ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"])
else:
    st.sidebar.info("Awaiting first agent data...")
    selected_agents = []
    pair = "EURUSD=X"
    chart_type = "Candlestick"

# Filter data
filtered_df = df[df['agent'].isin(selected_agents)] if not df.empty and selected_agents else df

# --- Market View Section ---
st.subheader(f"📊 Live Market: {pair}")

@st.cache_data(ttl=30) # Cache for only 30s to match auto-refresh
def get_chart_data(symbol):
    data = yf.download(symbol, period="7d", interval="1h", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    # Calculate Indicators
    data['EMA20'] = data['Close'].ewm(span=20, adjust=False).mean()
    data['EMA50'] = data['Close'].ewm(span=50, adjust=False).mean()
    
    # RSI
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))
    
    return data

hist = get_chart_data(pair)

if not hist.empty:
    # Create Subplots: Main Chart + RSI
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])
    
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="Price"), row=1, col=1)
    elif chart_type == "Line":
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], mode='lines', line=dict(color='#00ff00'), name="Price"), row=1, col=1)
    else: # Area
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], fill='tozeroy', line=dict(color='#00ff00'), name="Price"), row=1, col=1)
    
    # Indicators
    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA20'], line=dict(color='yellow', width=1), name="EMA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA50'], line=dict(color='orange', width=1), name="EMA 50"), row=1, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], line=dict(color='cyan', width=1), name="RSI"), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    # Overlay Trades
    pair_name = pair.replace("=X", "")
    current_trades = filtered_df[filtered_df['pair'] == pair_name].tail(10) if not filtered_df.empty else pd.DataFrame()
    
    for i, t in current_trades.iterrows():
        color = "green" if t['type'] == "BUY" else "red"
        fig.add_hline(y=t['entry'], line_dash="dot", line_color=color, annotation_text=f"{t['agent']} {t['type']}", row=1, col=1)
    
    fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=600, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error(f"Failed to retrieve market data for {pair}.")

# --- Comparison Section ---
st.divider()
st.subheader("⚔️ Agent Comparison")

if not filtered_df.empty:
    c1, c2, c3, c4 = st.columns(4)
    total_p = filtered_df['profit'].sum()
    c1.metric("Total Profit", f"${total_p:.2f}")
    c2.metric("Total Trades", len(filtered_df))
    win_p = (len(filtered_df[filtered_df['profit'] > 0]) / len(filtered_df)) * 100 if len(filtered_df) > 0 else 0
    c3.metric("Global Win Rate", f"{win_p:.1f}%")
    c4.metric("Last Signal", filtered_df['timestamp'].iloc[-1].strftime('%H:%M:%S'))

    st.write("#### Equity Growth Comparison")
    filtered_df = filtered_df.sort_values('timestamp')
    filtered_df['cumulative_profit'] = filtered_df.groupby('agent')['profit'].transform(pd.Series.cumsum)
    fig_comp = px.line(filtered_df, x='timestamp', y='cumulative_profit', color='agent', markers=True, template="plotly_dark")
    st.plotly_chart(fig_comp, use_container_width=True)

    st.write("#### 📑 Unified Trade Ledger")
    st.dataframe(filtered_df.sort_values('timestamp', ascending=False), use_container_width=True)
else:
    st.info("Select agents in the sidebar to view comparison.")

st.sidebar.divider()
if st.sidebar.button("🗑️ Clear Cache"):
    st.cache_data.clear()
    st.rerun()
