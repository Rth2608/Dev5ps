import streamlit as st
from shared.symbols_intervals import SYMBOLS, INTERVALS
import requests
from datetime import datetime

API_URL = st.secrets.get("API_URL", "http://localhost:8082")

st.set_page_config(page_title="암호화폐 차트 분석 플랫폼", layout="wide")
st.title("투자 전략 백테스트")
st.write(
    "선택한 코인에 대해 전략을 수립하고 백테스트를 실행합니다. 차트 기능을 통해 시각화된 결과를 확인할 수 있습니다."
)

# 상태 초기화
if "conditions" not in st.session_state:
    st.session_state.conditions = []
if "condition_id_counter" not in st.session_state:
    st.session_state.condition_id_counter = 0

# 코인/간격 선택
col1, col2 = st.columns(2)
with col1:
    symbol = st.selectbox("코인", SYMBOLS, key="symbol")
with col2:
    interval = st.selectbox("시간 간격(h)", INTERVALS, key="interval")

# 🔄 테이블에서 시작/종료 시간 가져오기
default_start = datetime.now()
default_end = datetime.now()
if symbol and interval:
    try:
        time_range_url = f"{API_URL}/time-range?symbol={symbol}&interval={interval}"
        resp = requests.get(time_range_url)
        if resp.status_code == 200:
            data = resp.json()
            default_start = datetime.fromisoformat(data["start_time"])
            default_end = datetime.fromisoformat(data["end_time"])
    except Exception as e:
        st.warning(f"기간 정보를 불러오는 중 오류: {e}")

# 📅 기간 선택 UI
st.subheader("백테스트 기간 설정")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("시작 날짜", value=default_start.date())
    start_time = st.time_input("시작 시간", value=default_start.time())
with col2:
    end_date = st.date_input("종료 날짜", value=default_end.date())
    end_time = st.time_input("종료 시간", value=default_end.time())

# ⚙️ 조건 설정 UI
st.subheader("조건 설정")
all_fields = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "rsi",
    "rsi_signal",
    "ema_7",
    "ema_25",
    "ema_99",
    "macd",
    "macd_signal",
    "boll_ma",
    "boll_upper",
    "boll_lower",
    "volume_ma_20",
]
operators = [">", ">=", "<", "<=", "==", "!="]

# ➕ 조건 추가
if st.button("➕ 조건 추가"):
    cid = st.session_state.condition_id_counter
    st.session_state.conditions.append(
        {
            "id": cid,
            "left": "open",
            "op": ">",
            "mode": "값",
            "value": "0",
            "right": "close",
        }
    )
    st.session_state.condition_id_counter += 1
    st.rerun()

# 조건 리스트 UI
to_delete = None
for cond in st.session_state.conditions:
    col1, col2, col3, col4, _, col6 = st.columns([1.2, 1, 1.5, 1.5, 1.5, 0.3])
    with col1:
        cond["left"] = st.selectbox(
            "지표",
            all_fields,
            key=f"left_{cond['id']}",
            index=all_fields.index(cond["left"]),
        )
    with col2:
        cond["op"] = st.selectbox(
            "연산자",
            operators,
            key=f"op_{cond['id']}",
            index=operators.index(cond["op"]),
        )
    with col3:
        cond["mode"] = st.selectbox(
            "기준",
            ["값", "지표"],
            key=f"mode_{cond['id']}",
            index=["값", "지표"].index(cond["mode"]),
        )
    with col4:
        if cond["mode"] == "값":
            cond["value"] = st.text_input(
                "값 입력", value=cond["value"], key=f"value_{cond['id']}"
            )
        else:
            cond["right"] = st.selectbox(
                "비교 지표",
                all_fields,
                key=f"right_{cond['id']}",
                index=all_fields.index(cond["right"]),
            )
    with col6:
        if st.button("❌", key=f"delete_{cond['id']}"):
            to_delete = cond["id"]

# 조건 삭제 반영
if to_delete is not None:
    st.session_state.conditions = [
        c for c in st.session_state.conditions if c["id"] != to_delete
    ]
    st.rerun()

# 손익비 입력
rr_ratio = st.text_input("손익비 (예: 2.0)", value="2.0")

# ✅ 전략 실행 버튼
if st.button("전략 실행 및 저장"):
    if not st.session_state.conditions:
        st.error("최소 1개의 조건이 필요합니다.")
    else:
        # 전략 SQL 구성
        conditions_str = []
        for cond in st.session_state.conditions:
            left = cond["left"]
            op = cond["op"]
            if cond["mode"] == "값":
                try:
                    float(cond["value"])
                except ValueError:
                    st.error(f"올바르지 않은 값: {cond['value']}")
                    st.stop()
                right = cond["value"]
            else:
                right = cond["right"]
            conditions_str.append(f"{left} {op} {right}")
        strategy_sql = " and ".join(conditions_str)

        start_dt_str = datetime.combine(start_date, start_time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        end_dt_str = datetime.combine(end_date, end_time).strftime("%Y-%m-%d %H:%M:%S")

        # 요청 JSON 구성
        strategy_data = {
            "symbol": symbol,
            "interval": interval,
            "strategy_sql": strategy_sql,
            "risk_reward_ratio": rr_ratio,
            "start_time": start_dt_str,
            "end_time": end_dt_str,
        }

        # 확인용 출력
        st.success("전략 실행 준비 완료 (요청 JSON)")
        st.json(strategy_data)

        # API 요청
        api_url = f"{API_URL}/save_strategy"
        try:
            response = requests.post(api_url, json=strategy_data)
            if response.status_code == 200:
                st.success("전략 데이터 저장 완료!")
            else:
                st.error(f"전략 저장 실패: {response.text}")
        except Exception as e:
            st.error(f"전략 저장 중 오류 발생: {e}")
