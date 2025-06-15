import streamlit as st
import requests
import base64
import json
from datetime import datetime
import math

API_URL = st.secrets.get("API_URL", "http://localhost:8082")
st.set_page_config(layout="wide")
st.title("전략 기반 캔들 차트 시각화")

# 전략 목록 가져오기
res = requests.get(f"{API_URL}/filtered-ohlcv")
filtered_data = res.json() if res.status_code == 200 else []
if not filtered_data:
    st.info("전략 데이터가 없습니다.")
    st.stop()

# 전략 선택
options = [
    f"{row['symbol']} [{row['interval']}] | {row['entry_time']} ~ {row['exit_time']}"
    for row in filtered_data
]
selected_idx = st.selectbox(
    "전략 선택", range(len(options)), format_func=lambda i: options[i]
)
selected = filtered_data[selected_idx]

# 사용된 보조지표
res = requests.get(
    f"{API_URL}/filtered-indicators",
    params={"entry_time": selected["entry_time"], "exit_time": selected["exit_time"]},
)
what_indicators_raw = (
    res.json().get("what_indicators", "") if res.status_code == 200 else ""
)
st.markdown(f"**사용된 보조지표:** `{what_indicators_raw or '없음'}`")


# 보조지표 확장
def expand(ind):
    return {
        "boll": ["boll_upper", "boll_lower", "boll_ma"],
        "rsi": ["rsi", "rsi_signal"],
        "macd": ["macd", "macd_signal"],
    }.get(ind, [ind])


indicators = []
if what_indicators_raw:
    for base in what_indicators_raw.split("and"):
        indicators.extend(expand(base.strip()))

# 색상 매핑
color_map = {
    "ema_7": "#F39C12",
    "ema_25": "#3498DB",
    "ema_99": "#9B59B6",
    "rsi": "#2ECC71",
    "rsi_signal": "#27AE60",
    "macd": "#E74C3C",
    "macd_signal": "#C0392B",
    "boll_upper": "#1ABC9C",
    "boll_lower": "#1ABC9C",
    "boll_ma": "#BDC3C7",
}

# 캔들 데이터
res = requests.get(
    f"{API_URL}/filtered-candle-data",
    params={
        "entry_time": selected["entry_time"],
        "exit_time": selected["exit_time"],
        "symbol": selected["symbol"],
        "interval": selected["interval"],
    },
)
ohlcv = res.json() if res.status_code == 200 else []
if not ohlcv:
    st.stop()

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
        "value": round(math.log(row["volume"] + 1) * 100, 2),
        "color": "green" if row["close"] >= row["open"] else "red",
    }
    for row in ohlcv
]

# 보조지표 데이터
indicator_data = {}
for ind in indicators:
    res = requests.get(
        f"{API_URL}/indicator-data",
        params={
            "symbol": selected["symbol"],
            "interval": selected["interval"],
            "indicator": ind,
            "entry_time": selected["entry_time"],
            "exit_time": selected["exit_time"],
        },
    )
    if res.status_code == 200:
        indicator_data[ind] = res.json()

# main/sub 분리
main_series = []
sub_charts = {}
for name, rows in indicator_data.items():
    base = name.split("_")[0]
    points = [
        {
            "time": int(datetime.fromisoformat(r["timestamp"]).timestamp()),
            "value": r["value"],
        }
        for r in rows
        if r.get("name") == name
    ]
    encoded = base64.b64encode(json.dumps(points).encode()).decode()
    if base in ["rsi", "macd"]:
        sub_charts.setdefault(base, []).append((name, encoded))
    else:
        main_series.append((name, encoded))

# HTML 생성
ohlc_b64 = base64.b64encode(json.dumps(ohlc_data).encode()).decode()
vol_b64 = base64.b64encode(json.dumps(volume_data).encode()).decode()
main_js = "\n".join(
    f'mainChart.addLineSeries({{ color: "{color_map.get(name, "white")}" }}).setData(JSON.parse(atob("{data}")));'
    for name, data in main_series
)
sub_html = "\n".join(f'<div id="{k}Chart" class="chartArea"></div>' for k in sub_charts)
sub_js = "\n".join(
    f"""
const {k}Chart = createChart("{k}Chart");
syncCharts.push({k}Chart);
"""
    + "\n".join(
        f'{k}Chart.addLineSeries({{ color: "{color_map.get(name, "white")}" }}).setData(JSON.parse(atob("{data}")));'
        for name, data in lines
    )
    for k, lines in sub_charts.items()
)

html = f"""
<!DOCTYPE html>
<html><head><meta charset='UTF-8'>
<script src='https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js'></script>
<style>
html, body, #container {{ margin: 0; padding: 0; overflow: hidden; background-color: #000; color: #fff; }}
#container {{ display: grid; grid-template-rows: repeat({2 + len(sub_charts)}, 1fr); height: 100vh; width: 100vw; }}
.chartArea {{ position: relative; }}
</style></head>
<body>
<div id="container">
  <div id="mainChart" class="chartArea"></div>
  <div id="volumeChart" class="chartArea"></div>
  {sub_html}
</div>
<script>
const syncCharts = [];
function createChart(id) {{
    return LightweightCharts.createChart(document.getElementById(id), {{
        layout: {{ backgroundColor: '#000', textColor: '#fff' }},
        grid: {{ vertLines: {{ color: 'transparent' }}, horzLines: {{ color: 'transparent' }} }},
        rightPriceScale: {{ visible: false }},
        timeScale: {{ visible: true }},
        crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }}
    }});
}}

const ohlcData = JSON.parse(atob("{ohlc_b64}"));
const volumeData = JSON.parse(atob("{vol_b64}"));
const mainChart = createChart("mainChart");
syncCharts.push(mainChart);
mainChart.addCandlestickSeries({{
    upColor: '#26a69a', downColor: '#ef5350',
    borderUpColor: '#26a69a', borderDownColor: '#ef5350',
    wickUpColor: '#26a69a', wickDownColor: '#ef5350'
}}).setData(ohlcData);
{main_js}

const volumeChart = createChart("volumeChart");
syncCharts.push(volumeChart);
volumeChart.addHistogramSeries({{
    upColor: '#26a69a', downColor: '#ef5350',
    borderVisible: false, priceFormat: {{ type: 'volume' }},
    overlay: true
}}).setData(volumeData);

{sub_js}

// 동기화: 줌/스크롤
syncCharts.forEach(source => {{
    source.timeScale().subscribeVisibleLogicalRangeChange(range => {{
        if (!range) return;
        syncCharts.forEach(target => {{
            if (target !== source) {{
                target.timeScale().setVisibleLogicalRange(range);
            }}
        }});
    }});
}});
</script>
</body></html>
"""

st.components.v1.html(html, height=1000, scrolling=False)
