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

# 최신순 정렬
filtered_data.sort(key=lambda x: x["entry_time"], reverse=True)

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
    "ema_7": "#FFCC00",
    "ema_25": "#05FD05",
    "ema_99": "#AF02F9",
    "rsi": "#FFCC00",
    "rsi_signal": "#09F96D",
    "macd": "#F61D05",
    "macd_signal": "#FF7700",
    "boll_upper": "#15A2DA",
    "boll_lower": "#15A2DA",
    "boll_ma": "#15A2DA",
}

# 전체 OHLCV 데이터 가져오기
res_all = requests.get(f"{API_URL}/ohlcv/{selected['symbol']}/{selected['interval']}")
all_ohlcv = res_all.json() if res_all.status_code == 200 else []

# entry/exit 기준으로 앞뒤 10개 캔들 포함
all_ohlcv.sort(key=lambda x: x["timestamp"])
entry_dt = selected["entry_time"]
exit_dt = selected["exit_time"]

entry_idx = next((i for i, x in enumerate(all_ohlcv) if x["timestamp"] >= entry_dt), 0)
exit_idx = next(
    (i for i, x in enumerate(all_ohlcv) if x["timestamp"] > exit_dt), len(all_ohlcv)
)

sliced_ohlcv = all_ohlcv[max(0, entry_idx - 10) : min(len(all_ohlcv), exit_idx + 10)]

ohlc_data = [
    {
        "time": int(datetime.fromisoformat(row["timestamp"]).timestamp()),
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "color": (
            "#999"
            if row["timestamp"] < entry_dt or row["timestamp"] > exit_dt
            else None
        ),
    }
    for row in sliced_ohlcv
]

volume_data = [
    {
        "time": int(datetime.fromisoformat(row["timestamp"]).timestamp()),
        "value": round(math.log(row["volume"] + 1) * 100, 2),
        "color": (
            "#999"
            if row["timestamp"] < entry_dt or row["timestamp"] > exit_dt
            else ("green" if row["close"] >= row["open"] else "red")
        ),
    }
    for row in sliced_ohlcv
]

# 보조지표 데이터 요청 (entry-10 ~ exit+10 구간)
indicator_data = {}
for ind in indicators:
    res = requests.get(
        f"{API_URL}/indicator-data",
        params={
            "symbol": selected["symbol"],
            "interval": selected["interval"],
            "indicator": ind,
            "entry_time": sliced_ohlcv[0]["timestamp"],
            "exit_time": sliced_ohlcv[-1]["timestamp"],
        },
    )
    if res.status_code == 200:
        rows = res.json()
        base = ind.split("_")[0]
        for row in rows:
            row_time = datetime.fromisoformat(row["timestamp"])
            row["color"] = (
                "#999"
                if row_time < datetime.fromisoformat(entry_dt)
                or row_time > datetime.fromisoformat(exit_dt)
                else None
            )
        indicator_data[ind] = rows

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

# HTML 삽입
ohlc_b64 = base64.b64encode(json.dumps(ohlc_data).encode()).decode()
vol_b64 = base64.b64encode(json.dumps(volume_data).encode()).decode()
main_js = "\n".join(
    f'mainChart.addLineSeries({{ color: "{color_map.get(name, "white")}", lineWidth: 1.5 }}).setData(JSON.parse(atob("{data}")));'
    for name, data in main_series
)
sub_html = "\n".join(f'<div id="{k}Chart" class="chartArea"></div>' for k in sub_charts)
sub_js = "\n".join(
    f"""
const {k}Chart = createChart("{k}Chart");
syncCharts.push({k}Chart);
"""
    + "\n".join(
        f'{k}Chart.addLineSeries({{ color: "{color_map.get(name, "white")}", lineWidth: 2 }}).setData(JSON.parse(atob("{data}")));'
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
