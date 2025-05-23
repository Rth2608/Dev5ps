import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import datetime
from shared.symbols_intervals import SYMBOLS, INTERVALS
import os

# fastapi 설정
API_URL = os.getenv("API_URL", "http://localhost:8000")

# UI
st.set_page_config(page_title="캔들차트", layout="wide")
st.title("암호화폐 실시간 차트")



# UI ( 사용자 입력 )
symbol = st.selectbox("코인", SYMBOLS)
interval = st.selectbox("시간 간격(h)", INTERVALS, index=0)
volume_threshold = st.number_input("최소 거래량", min_value=0.0, value=0.0, step=1000.0)

# /ohlcv/{symbol}/{interval} 호출 함수 ( 호출 주기 60초로 제한 )
@st.cache_data(ttl=60)
def fetch_ohlcv(symbol: str, interval: str):
    url = f"{API_URL}/ohlcv/{symbol.upper()}/{interval}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Seoul")
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"/ohlcv/{symbol}/{interval} 호출 실패: {e}")
        return pd.DataFrame()

# 데이터 호출
df = fetch_ohlcv(symbol, interval)

if df.empty or "timestamp" not in df.columns:
    st.error("데이터를 로딩 실패")
    st.write("응답 내용:", df)
    st.stop()

# 정렬 및 슬라이더용 변수 설정
df = df.sort_values("timestamp").reset_index(drop=True)
latest = df["timestamp"].max()
earliest = df["timestamp"].min()
max_len = min(300, len(df))

# 차트에 표시할 캔들 개수
length = st.slider("표시할 캔들 개수", 10, max_len, value=min(100, max_len))

# 슬라이더: 종료 시점 선택
def interval_to_minutes(interval: str) -> int:
    if interval.endswith("m"):
        return int(interval.replace("m", ""))
    elif interval.endswith("h"):
        return int(interval.replace("h", "")) * 60
    elif interval.endswith("d"):
        return int(interval.replace("d", "")) * 1440
    else:
        return 15
    
step_minutes = interval_to_minutes(interval)

end_date = st.slider(
    "종료 시점 선택",
    min_value=earliest.to_pydatetime(),
    max_value=latest.to_pydatetime(),
    value=latest.to_pydatetime(),
    step=datetime.timedelta(minutes=step_minutes),
    format="YYYY-MM-DD HH:mm"
)

# 데이터 필터링: 종료 시점 이전 데이터 중 최근 length개를 표시할 예정이다
df_filtered = df[(df["timestamp"] <= pd.to_datetime(end_date)) & (df["volume"] >= volume_threshold)]
df_filtered = df_filtered.iloc[-length:]

# 캔들차트 출력
fig = go.Figure(data=[
    go.Candlestick(
        x=df_filtered["timestamp"],
        open=df_filtered["open"],
        high=df_filtered["high"],
        low=df_filtered["low"],
        close=df_filtered["close"]
    )
])
fig.update_layout(
    title=f"{symbol} {interval} 캔들차트",
    xaxis_rangeslider_visible=False
)
st.plotly_chart(fig, use_container_width=True)