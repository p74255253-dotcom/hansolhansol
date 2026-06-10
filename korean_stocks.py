import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

st.set_page_config(
    page_title="국내 주식 대시보드",
    page_icon="📈",
    layout="wide"
)

STOCKS = {
    "삼성전자":       "005930.KS",
    "SK하이닉스":     "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차":         "005380.KS",
    "셀트리온":       "068270.KS",
    "POSCO홀딩스":    "005490.KS",
    "KB금융":         "105560.KS",
    "신한지주":       "055550.KS",
    "카카오":         "035720.KS",
}

def get_series(df, col):
    """yfinance 버전 무관하게 1차원 Series 반환"""
    s = df[col]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.squeeze()

# ── 사이드바 ─────────────────────────────────────────────
st.sidebar.title("⚙️ 설정")

period_map = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo", "1년": "1y", "2년": "2y"}
selected_period_label = st.sidebar.selectbox("조회 기간", list(period_map.keys()), index=2)
selected_period = period_map[selected_period_label]

selected_stocks = st.sidebar.multiselect(
    "종목 선택",
    list(STOCKS.keys()),
    default=list(STOCKS.keys())[:5]
)

# ── 데이터 로딩 ───────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data(ticker_pairs: list, period: str) -> dict:
    result = {}
    for name, ticker in ticker_pairs:
        try:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
            if not df.empty:
                result[name] = df
        except Exception:
            pass
    return result

@st.cache_data(ttl=600)
def load_info(ticker_pairs: list) -> dict:
    info_map = {}
    for name, ticker in ticker_pairs:
        try:
            info_map[name] = yf.Ticker(ticker).info
        except Exception:
            info_map[name] = {}
    return info_map

# ── 메인 ─────────────────────────────────────────────────
st.title("📈 국내 주식 대시보드")
st.caption(f"데이터 출처: Yahoo Finance  |  기준일: {datetime.today().strftime('%Y-%m-%d')}")

if not selected_stocks:
    st.warning("왼쪽 사이드바에서 종목을 하나 이상 선택하세요.")
    st.stop()

ticker_pairs = [(name, STOCKS[name]) for name in selected_stocks]

with st.spinner("데이터 수집 중..."):
    data  = load_data(ticker_pairs, selected_period)
    infos = load_info(ticker_pairs)

if not data:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도하세요.")
    st.stop()

# ── 요약 카드 ─────────────────────────────────────────────
st.subheader("📊 종목 요약")

cols = st.columns(min(len(data), 5))
for i, (name, df) in enumerate(data.items()):
    col = cols[i % 5]
    close = get_series(df, "Close")
    latest = float(close.iloc[-1])
    prev   = float(close.iloc[-2]) if len(close) > 1 else latest
    change = latest - prev
    pct    = (change / prev * 100) if prev else 0
    arrow  = "▲" if change >= 0 else "▼"
    col.metric(
        label=name,
        value=f"{latest:,.0f}원",
        delta=f"{arrow} {abs(pct):.2f}%",
        delta_color="normal" if change >= 0 else "inverse"
    )

st.divider()

# ── 주가 추이 차트 ────────────────────────────────────────
st.subheader("📉 주가 추이 (종가 기준)")

fig = go.Figure()
for name, df in data.items():
    close = get_series(df, "Close")
    fig.add_trace(go.Scatter(
        x=df.index, y=close,
        mode="lines", name=name,
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f}원<extra>" + name + "</extra>"
    ))

fig.update_layout(
    xaxis_title="날짜", yaxis_title="종가 (원)",
    hovermode="x unified",
    legend=dict(orientation="h", y=-0.2),
    height=450, margin=dict(t=20)
)
st.plotly_chart(fig, width="stretch")

# ── 정규화 수익률 비교 ────────────────────────────────────
st.subheader("📐 수익률 비교 (기간 시작 = 100)")

fig2 = go.Figure()
for name, df in data.items():
    close = get_series(df, "Close")
    normalized = close / float(close.iloc[0]) * 100
    fig2.add_trace(go.Scatter(
        x=df.index, y=normalized,
        mode="lines", name=name,
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.1f}<extra>" + name + "</extra>"
    ))

fig2.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.5)
fig2.update_layout(
    xaxis_title="날짜", yaxis_title="지수 (시작=100)",
    hovermode="x unified",
    legend=dict(orientation="h", y=-0.2),
    height=400, margin=dict(t=20)
)
st.plotly_chart(fig2, width="stretch")

# ── 거래량 바 차트 ───────────────────────────────────────
st.subheader("📦 최근 20일 평균 거래량")

vol_data = []
for name, df in data.items():
    vol = get_series(df, "Volume")
    vol_data.append({"종목": name, "평균 거래량 (20일)": float(vol.tail(20).mean())})

vol_df = pd.DataFrame(vol_data).sort_values("평균 거래량 (20일)", ascending=True)
fig3 = px.bar(
    vol_df, x="평균 거래량 (20일)", y="종목",
    orientation="h", color="평균 거래량 (20일)",
    color_continuous_scale="Blues", text_auto=".3s"
)
fig3.update_layout(showlegend=False, height=350, margin=dict(t=20), coloraxis_showscale=False)
st.plotly_chart(fig3, width="stretch")

# ── 상세 데이터 테이블 ────────────────────────────────────
st.subheader("📋 종목별 상세 정보")

rows = []
for name, df in data.items():
    close = get_series(df, "Close")
    high  = get_series(df, "High")
    low   = get_series(df, "Low")
    vol   = get_series(df, "Volume")

    latest      = float(close.iloc[-1])
    pct_change  = (float(close.iloc[-1]) / float(close.iloc[0]) - 1) * 100
    period_high = float(high.max())
    period_low  = float(low.min())
    avg_vol     = float(vol.tail(20).mean())

    mkt_cap = infos.get(name, {}).get("marketCap", None)
    mkt_cap_str = f"{mkt_cap/1e12:.2f}조" if mkt_cap else "-"

    rows.append({
        "종목":           name,
        "현재가 (원)":    f"{latest:,.0f}",
        "기간 수익률":    f"{pct_change:+.2f}%",
        "기간 최고가":    f"{period_high:,.0f}",
        "기간 최저가":    f"{period_low:,.0f}",
        "20일 평균거래량": f"{avg_vol:,.0f}",
        "시가총액":       mkt_cap_str,
    })

st.dataframe(pd.DataFrame(rows).set_index("종목"), width="stretch")

# ── 캔들스틱 (단일 종목) ──────────────────────────────────
st.subheader("🕯️ 캔들스틱 차트")

candle_stock = st.selectbox("종목 선택", list(data.keys()))
df_c = data[candle_stock]

fig4 = go.Figure(go.Candlestick(
    x=df_c.index,
    open=get_series(df_c, "Open"),
    high=get_series(df_c, "High"),
    low=get_series(df_c, "Low"),
    close=get_series(df_c, "Close"),
    name=candle_stock,
    increasing_line_color="red",
    decreasing_line_color="blue"
))
fig4.update_layout(
    xaxis_rangeslider_visible=True,
    xaxis_title="날짜", yaxis_title="가격 (원)",
    height=500, margin=dict(t=20)
)
st.plotly_chart(fig4, width="stretch")

st.caption("※ 본 대시보드는 투자 권유가 아닙니다. 투자 판단은 본인 책임하에 하시기 바랍니다.")
