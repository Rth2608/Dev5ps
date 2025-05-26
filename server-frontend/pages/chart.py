import streamlit as st
import requests
import base64
import json
from datetime import datetime

API_URL = st.secrets.get("API_URL", "http://localhost:8080")

st.set_page_config(layout="wide")
st.title("전략 기반 캔들 차트 시각화")
st.write("저장된 전략별 백테스트 결과를 캔들 차트로 시각화합니다.")
# 전략 결과 불러오기
filtered_res = requests.get(f"{API_URL}/filtered-ohlcv")
if filtered_res.status_code != 200:
    st.error(f"전략 목록 불러오기 실패: {filtered_res.status_code}")
    st.stop()

filtered_data = filtered_res.json()
if not filtered_data:
    st.warning("저장된 전략 결과가 없습니다.")
    st.stop()

# 전략 선택 UI
options = [
    f"{row['symbol']} [{row['interval']}] | {row['entry_time']} ~ {row['exit_time']}"
    for row in filtered_data
]
selected_idx = st.selectbox(
    "전략 선택", range(len(options)), format_func=lambda i: options[i]
)
selected = filtered_data[selected_idx]

# 원본 캔들 데이터 요청
candle_res = requests.get(
    f"{API_URL}/filtered-candle-data",
    params={
        "entry_time": selected["entry_time"],
        "exit_time": selected["exit_time"],
        "symbol": selected["symbol"],
        "interval": selected["interval"],
    },
)
if candle_res.status_code != 200:
    st.error("원본 캔들 데이터 요청 실패")
    st.stop()

ohlcv = candle_res.json()
if not ohlcv:
    st.warning("해당 구간에 원본 캔들 데이터가 없습니다.")
    st.stop()

# 데이터 전처리
from datetime import datetime

ohlc_data = [
    {
        "time": int(datetime.fromisoformat(row["timestamp"]).timestamp()),
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
    }
    for row in ohlcv
]

volume_data = [
    {
        "time": int(datetime.fromisoformat(row["timestamp"]).timestamp()),
        "value": round(__import__("math").log(row["volume"] + 1) * 100, 2),
        "color": "green" if row["close"] >= row["open"] else "red",
    }
    for row in ohlcv
]

# base64 encode
ohlc_b64 = base64.b64encode(json.dumps(ohlc_data).encode()).decode()
vol_b64 = base64.b64encode(json.dumps(volume_data).encode()).decode()

# lightweight-charts HTML 삽입
html = f"""
<!DOCTYPE html>
<html><head><meta charset='UTF-8'>
<script src='https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js'></script>
<style>
html, body, #container, #candleChart, #volumeChart {{
    margin: 0;
    padding: 0;
    overflow: hidden;
    background-color: #000000 !important;
    color: #ffffff;
}}
#container {{
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100vw;
}}
#candleChart {{ flex: 2; }}
#volumeChart {{ flex: 1; }}
</style></head>
<body>
<div id='container'>
  <div id='candleChart'></div>
  <div id='volumeChart'></div>
</div>
<script>
const ohlcData = JSON.parse(atob("{ohlc_b64}"));
const volumeData = JSON.parse(atob("{vol_b64}"));

function createChart(containerId) {{
    return LightweightCharts.createChart(document.getElementById(containerId), {{
        layout: {{ backgroundColor: '#000000', textColor: '#ffffff' }},
        grid: {{ vertLines: {{ color: 'transparent' }}, horzLines: {{ color: 'transparent' }} }},
        rightPriceScale: {{ visible: false }},
        timeScale: {{ visible: false }},
        crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }}
    }});
}}

const mainChart = createChart('candleChart');
const volumeChart = createChart('volumeChart');

mainChart.addCandlestickSeries({{
    upColor: '#26a69a', downColor: '#ef5350',
    borderUpColor: '#26a69a', borderDownColor: '#ef5350',
    wickUpColor: '#26a69a', wickDownColor: '#ef5350'
}}).setData(ohlcData);

volumeChart.addHistogramSeries({{
    upColor: '#26a69a', downColor: '#ef5350',
    borderVisible: false, priceFormat: {{ type: 'volume' }}, overlay: true
}}).setData(volumeData);
</script>
</body></html>
"""

st.components.v1.html(html, height=700, scrolling=False)
