"""
Global Macro Engine — single-file version with extra features.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Deploy on Streamlit Community Cloud:
    Put this app.py and requirements.txt in the ROOT of your GitHub repo
    (no subfolders), then set "Main file path" to: app.py
"""

from datetime import date, datetime, timedelta

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
    "Industrial Production Index": {"id": "INDPRO", "yoy": True, "unit": "%"},
    "Consumer Sentiment (U. Michigan)": {"id": "UMCSENT", "yoy": False, "unit": ""},
    "Housing Starts (thousands, SAAR)": {"id": "HOUST", "yoy": False, "unit": "K"},
}

FX_TICKERS = {
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "GBP/USD": "GBPUSD=X",
    "US Dollar Index (DXY)": "DX-Y.NYB",
    "Gold (USD/oz)": "GC=F",
    "WTI Crude Oil": "CL=F",
    "S&P 500": "^GSPC",
}

RECESSION_SERIES_ID = "USREC"  # FRED: NBER-based recession indicator (0/1)
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

HEADLINE_KPIS = [
    "US CPI Inflation (YoY %)",
    "US Unemployment Rate",
    "US 10Y-2Y Yield Spread",
    "Fed Funds Rate",
]


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
    """Fetch daily FX/equity/commodity prices from Yahoo Finance — no API key needed."""
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


@st.cache_data(ttl=3600, show_spinner=False)
def get_recession_periods() -> list:
    """Return list of (start, end) date ranges where NBER recession flag == 1."""
    try:
        df = get_fred_series(RECESSION_SERIES_ID)
    except Exception:  # noqa: BLE001
        return []
    df = df.sort_values("date").reset_index(drop=True)
    periods, in_recession, start = [], False, None
    for _, row in df.iterrows():
        if row["value"] >= 1 and not in_recession:
            in_recession, start = True, row["date"]
        elif row["value"] < 1 and in_recession:
            in_recession = False
            periods.append((start, row["date"]))
    if in_recession:
        periods.append((start, df["date"].iloc[-1]))
    return periods


def filter_range(df: pd.DataFrame, start, end) -> pd.DataFrame:
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    return df.loc[mask]


def zscore(df: pd.DataFrame) -> float:
    """Z-score of the latest value vs. the series' full available history."""
    if len(df) < 5 or df["value"].std() == 0:
        return 0.0
    return (df["value"].iloc[-1] - df["value"].mean()) / df["value"].std()


def plot(df: pd.DataFrame, title: str, unit: str = "", shade_recessions: bool = False) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["value"], mode="lines", name=title))
    if shade_recessions and not df.empty:
        for r_start, r_end in get_recession_periods():
            if r_end >= df["date"].min() and r_start <= df["date"].max():
                fig.add_vrect(x0=r_start, x1=r_end, fillcolor="gray", opacity=0.15, line_width=0)
    fig.update_layout(title=title, height=320, yaxis_title=unit,
                       template="plotly_white", margin=dict(l=10, r=10, t=40, b=10))
    return fig


def download_button(df: pd.DataFrame, label: str, key: str):
    st.download_button(
        "⬇️ Download CSV", df.to_csv(index=False).encode("utf-8"),
        file_name=f"{label.replace(' ', '_').replace('/', '-')}.csv",
        mime="text/csv", key=key, use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("🌍 Global Macro Engine")
start_date = st.sidebar.date_input("Start date", date.today() - timedelta(days=365 * 10))
end_date = st.sidebar.date_input("End date", date.today())
shade_recessions = st.sidebar.checkbox("Shade US recessions on charts", value=True)

st.sidebar.markdown("---")
picked_macro = st.sidebar.multiselect(
    "Macro indicators to show", list(FRED_SERIES.keys()), default=list(FRED_SERIES.keys())
)
picked_fx = st.sidebar.multiselect(
    "FX / market series to show", list(FX_TICKERS.keys()), default=list(FX_TICKERS.keys())
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh data (clear cache)"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption(f"Last loaded: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.sidebar.caption("Data: FRED + Yahoo Finance (both free, no API key required).")

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
st.title("Global Macro Engine")
st.caption("Growth, inflation, rates, and FX — all in one dashboard.")

# --- Headline KPI row -------------------------------------------------------
st.subheader("Headline snapshot")
kpi_cols = st.columns(len(HEADLINE_KPIS))
for col, label in zip(kpi_cols, HEADLINE_KPIS):
    cfg = FRED_SERIES[label]
    try:
        df = load_indicator(cfg)
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
        z = zscore(df)
        tag = "⚠️ extreme" if abs(z) > 2 else ("↑ high" if z > 1 else ("↓ low" if z < -1 else "normal"))
        col.metric(label, f"{latest['value']:.2f}{cfg['unit']}", f"{latest['value'] - prev['value']:.2f}")
        col.caption(f"z-score: {z:.2f} ({tag})")
    except Exception as e:  # noqa: BLE001
        col.error(f"Error: {e}")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Macro Indicators", "💱 FX & Markets", "🔄 Compare & Correlate"])

with tab1:
    cols = st.columns(2)
    for i, label in enumerate(picked_macro):
        cfg = FRED_SERIES[label]
        with cols[i % 2]:
            try:
                df = filter_range(load_indicator(cfg), start_date, end_date)
                if df.empty:
                    st.warning(f"No data in range for {label}")
                    continue
                st.plotly_chart(plot(df, label, cfg["unit"], shade_recessions), use_container_width=True)
                latest = df.iloc[-1]
                st.caption(f"Latest: {latest['value']:.2f}{cfg['unit']} on {latest['date'].date()} · z-score: {zscore(df):.2f}")
                download_button(df, label, key=f"dl_macro_{i}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Couldn't load {label}: {e}")

with tab2:
    cols = st.columns(2)
    for i, label in enumerate(picked_fx):
        ticker = FX_TICKERS[label]
        with cols[i % 2]:
            try:
                df = filter_range(get_fx_series(ticker), start_date, end_date)
                if df.empty:
                    st.warning(f"No data in range for {label}")
                    continue
                st.plotly_chart(plot(df, label, shade_recessions=shade_recessions), use_container_width=True)
                latest = df.iloc[-1]
                st.caption(f"Latest: {latest['value']:.4f} on {latest['date'].date()} · z-score: {zscore(df):.2f}")
                download_button(df, label, key=f"dl_fx_{i}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Couldn't load {label}: {e}")

with tab3:
    st.write("Overlay series on one rebased (start = 100) chart, and see how they correlate.")
    all_options = {f"[Macro] {k}": ("macro", v) for k, v in FRED_SERIES.items()}
    all_options.update({f"[FX] {k}": ("fx", v) for k, v in FX_TICKERS.items()})
    picks = st.multiselect("Series to compare", list(all_options.keys()), default=list(all_options.keys())[:3])

    if picks:
        fig = go.Figure()
        series_for_corr = {}
        for pick in picks:
            kind, payload = all_options[pick]
            try:
                df = load_indicator(payload) if kind == "macro" else get_fx_series(payload)
                df = filter_range(df, start_date, end_date)
                if df.empty:
                    continue
                rebased = df.copy()
                rebased["value"] = rebased["value"] / rebased["value"].iloc[0] * 100
                fig.add_trace(go.Scatter(x=rebased["date"], y=rebased["value"], mode="lines", name=pick))
                series_for_corr[pick] = df.set_index("date")["value"]
            except Exception as e:  # noqa: BLE001
                st.error(f"Couldn't load {pick}: {e}")

        fig.update_layout(title="Rebased comparison (start = 100)", height=480,
                           template="plotly_white", margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

        if len(series_for_corr) >= 2:
            st.subheader("Correlation matrix (monthly, forward-filled)")
            merged = pd.DataFrame(series_for_corr).resample("ME").last().ffill()
            corr = merged.corr()
            st.dataframe(corr.style.background_gradient(cmap="RdBu", vmin=-1, vmax=1).format("{:.2f}"),
                         use_container_width=True)
    else:
        st.info("Select at least one series above.")
