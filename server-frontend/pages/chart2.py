# chart2.py
import streamlit as st
import requests
import base64
import json
from datetime import datetime

API_URL = st.secrets.get("API_URL", "http://localhost:8082")

st.set_page_config(layout="wide")
st.title("전략 기반 캔들 차트 시각화")

# 전략 목록 불러오기
filtered_res = requests.get(f"{API_URL}/filtered-ohlcv")
filtered_data = filtered_res.json()

options = [
    f"{row['symbol']} [{row['interval']}] | {row['entry_time']} ~ {row['exit_time']}"
    for row in filtered_data
]
selected_idx = st.selectbox(
    "전략 선택", range(len(options)), format_func=lambda i: options[i]
)
selected = filtered_data[selected_idx]

# what_indicators 추출
raw_ind = selected.get("what_indicators", "")
if raw_ind and raw_ind.lower() != "none":
    indicators = [ind.strip() for ind in raw_ind.lower().split("and")]
else:
    indicators = []

# OHLCV 데이터 가져오기
candle_res = requests.get(
    f"{API_URL}/filtered-candle-data",
    params={
        "entry_time": selected["entry_time"],
        "exit_time": selected["exit_time"],
        "symbol": selected["symbol"],
        "interval": selected["interval"],
    },
)
ohlcv = candle_res.json()

# 기본 시계열 구성
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

# 보조지표 시계열
indicator_series = {
    ind: [
        {
            "time": int(datetime.fromisoformat(row["timestamp"]).timestamp()),
            "value": row[ind] if row.get(ind) is not None else None,
        }
        for row in ohlcv
        if ind in row and row[ind] is not None
    ]
    for ind in indicators
}

# HTML용 base64 인코딩
ohlc_b64 = base64.b64encode(json.dumps(ohlc_data).encode()).decode()
vol_b64 = base64.b64encode(json.dumps(volume_data).encode()).decode()
ind_b64_map = {
    k: base64.b64encode(json.dumps(v).encode()).decode()
    for k, v in indicator_series.items()
}

# JS로 표시할 보조지표 시리즈 코드
indicator_js = ""
for name, b64 in ind_b64_map.items():
    indicator_js += f"""
    mainChart.addLineSeries({{
        title: '{name}', color: '#fbc02d', lineWidth: 2
    }}).setData(JSON.parse(atob('{b64}')));
    """

# 전체 HTML/JS 차트 생성
html = f"""
<!DOCTYPE html><html><head><meta charset='UTF-8'>
<script src='https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js'></script>
<style>
  html, body, #container, #candleChart, #volumeChart {{
    margin: 0; padding: 0; background-color: black; height: 100%;
  }}
  #container {{ display: flex; flex-direction: column; height: 700px; }}
  #candleChart {{ flex: 2; }}
  #volumeChart {{ flex: 1; }}
</style></head><body>
<div id="container">
  <div id="candleChart"></div>
  <div id="volumeChart"></div>
</div>
<script>
const ohlc = JSON.parse(atob("{ohlc_b64}"));
const volume = JSON.parse(atob("{vol_b64}"));

const mainChart = LightweightCharts.createChart(document.getElementById('candleChart'), {{
  layout: {{ backgroundColor: '#000', textColor: '#fff' }},
  grid: {{ vertLines: {{ color: '#444' }}, horzLines: {{ color: '#444' }} }},
  timeScale: {{ timeVisible: true }},
}});
mainChart.addCandlestickSeries().setData(ohlc);

{indicator_js}

const volumeChart = LightweightCharts.createChart(document.getElementById('volumeChart'), {{
  layout: {{ backgroundColor: '#000', textColor: '#fff' }},
}});
volumeChart.addHistogramSeries({{
  color: '#888', priceFormat: {{ type: 'volume' }}, overlay: true
}}).setData(volume);
</script></body></html>
"""

# Streamlit에 차트 렌더링
st.components.v1.html(html, height=750, scrolling=False)
