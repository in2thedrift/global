"""
Global Macro Engine — simple single-file version.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Deploy on Streamlit Community Cloud:
    Put this app.py and requirements.txt in the ROOT of your GitHub repo
    (no subfolders), then set "Main file path" to: app.py
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Global Macro Engine", page_icon="🌍", layout="wide")

# ---------------------------------------------------------------------------
# Indicator config — edit these dicts to add/remove series
# ---------------------------------------------------------------------------
FRED_SERIES = {
    "US CPI Inflation (YoY %)": {"id": "CPIAUCSL", "yoy": True, "unit": "%"},
    "US Core PCE Inflation (YoY %)": {"id": "PCEPILFE", "yoy": True, "unit": "%"},
    "US Unemployment Rate": {"id": "UNRATE", "yoy": False, "unit": "%"},
    "US Real GDP Growth (QoQ, SAAR %)": {"id": "A191RL1Q225SBEA", "yoy": False, "unit": "%"},
    "Fed Funds Rate": {"id": "FEDFUNDS", "yoy": False, "unit": "%"},
    "US 10Y Treasury Yield": {"id": "DGS10", "yoy": False, "unit": "%"},
    "US 2Y Treasury Yield": {"id": "DGS2", "yoy": False, "unit": "%"},
    "US 10Y-2Y Yield Spread": {"id": "T10Y2Y", "yoy": False, "unit": "%"},
}

FX_TICKERS = {
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "GBP/USD": "GBPUSD=X",
    "US Dollar Index (DXY)": "DX-Y.NYB",
    "Gold (USD/oz)": "GC=F",
    "WTI Crude Oil": "CL=F",
}

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


# ---------------------------------------------------------------------------
# Data fetching (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_fred_series(series_id: str) -> pd.DataFrame:
    """Fetch a FRED series — no API key needed."""
    df = pd.read_csv(f"{FRED_CSV_URL}?id={series_id}")
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def get_fx_series(ticker: str) -> pd.DataFrame:
    """Fetch daily FX/commodity prices from Yahoo Finance — no API key needed."""
    data = yf.Ticker(ticker).history(period="10y").reset_index()[["Date", "Close"]]
    data.columns = ["date", "value"]
    data["date"] = pd.to_datetime(data["date"]).dt.tz_localize(None)
    return data


def load_indicator(cfg: dict) -> pd.DataFrame:
    df = get_fred_series(cfg["id"])
    if cfg.get("yoy"):
        df = df.copy()
        df["value"] = df["value"].pct_change(12) * 100
        df = df.dropna()
    return df


def filter_range(df: pd.DataFrame, start, end) -> pd.DataFrame:
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    return df.loc[mask]


def plot(df: pd.DataFrame, title: str, unit: str = "") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["value"], mode="lines", name=title))
    fig.update_layout(title=title, height=320, yaxis_title=unit,
                       template="plotly_white", margin=dict(l=10, r=10, t=40, b=10))
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("🌍 Global Macro Engine")
start_date = st.sidebar.date_input("Start date", date.today() - timedelta(days=365 * 10))
end_date = st.sidebar.date_input("End date", date.today())
st.sidebar.caption("Data: FRED + Yahoo Finance (both free, no API key required).")

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
st.title("Global Macro Engine")
st.caption("Growth, inflation, rates, and FX — all in one dashboard.")

tab1, tab2 = st.tabs(["📊 Macro Indicators", "💱 FX & Markets"])

with tab1:
    cols = st.columns(2)
    for i, (label, cfg) in enumerate(FRED_SERIES.items()):
        with cols[i % 2]:
            try:
                df = filter_range(load_indicator(cfg), start_date, end_date)
                if df.empty:
                    st.warning(f"No data in range for {label}")
                    continue
                st.plotly_chart(plot(df, label, cfg["unit"]), use_container_width=True)
                latest = df.iloc[-1]
                st.caption(f"Latest: {latest['value']:.2f}{cfg['unit']} on {latest['date'].date()}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Couldn't load {label}: {e}")

with tab2:
    cols = st.columns(2)
    for i, (label, ticker) in enumerate(FX_TICKERS.items()):
        with cols[i % 2]:
            try:
                df = filter_range(get_fx_series(ticker), start_date, end_date)
                if df.empty:
                    st.warning(f"No data in range for {label}")
                    continue
                st.plotly_chart(plot(df, label), use_container_width=True)
                latest = df.iloc[-1]
                st.caption(f"Latest: {latest['value']:.4f} on {latest['date'].date()}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Couldn't load {label}: {e}")
