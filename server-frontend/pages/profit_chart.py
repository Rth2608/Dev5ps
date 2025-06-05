import streamlit as st
import requests
import altair as alt

API_URL = st.secrets.get("API_URL", "http://localhost:8080")

st.set_page_config(layout="wide")
st.title("백테스트 승률 시각화")
st.markdown("현재까지 실행한 백테스트의 결과를 한 눈에 확인할 수 있습니다.")


st.header("📈 누적 수익률 그래프")
filtered_res = requests.get(f"{API_URL}/filtered-profit-rate")
if filtered_res.status_code != 200:
    st.error(f"전략 목록 불러오기 실패: {filtered_res.status_code}")
    st.stop()

filtered_data = filtered_res.json()
if not filtered_data:
    st.warning("저장된 전략 결과가 없습니다.")
    st.stop()

chart = alt.Chart(alt.Data(values=filtered_data)).mark_line(
    color='#FF4B4B', strokeWidth=2
).encode(
    x=alt.X('entry_time:T', axis=alt.Axis(title='진입 시간')),
    y=alt.Y('cum_profit_rate:Q', axis=alt.Axis(format='.2f'), title='누적 수익률 (%)')
).properties(
    width='container',
    height=400
)

st.altair_chart(chart, use_container_width=True)

st.header("핵심 통계 요약")

filtered_tp_res = requests.get(f"{API_URL}/filtered-tp-sl-rate")
if filtered_tp_res.status_code != 200:
    st.error(f"전략 목록 불러오기 실패: {filtered_tp_res.status_code}")
    st.stop()

filtered_tp_data = filtered_tp_res.json()
if not filtered_tp_data:
    st.warning("통계 데이터가 없습니다.")
    st.stop()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("총 실행 횟수", filtered_tp_data.get("total_count", 0))
    st.metric("수익 발생 횟수", filtered_tp_data.get("tp_count", 0))
    st.metric("누적 승률", f"{filtered_tp_data.get('tp_rate', 0):.2f}%")

with col2:
    st.metric("최종 수익률", f"{filtered_tp_data.get('final_profit_rate', 0):+.2f}%")
    st.metric("기대 수익률", f"{filtered_tp_data.get('expectancy', 0):+.2f}%")

with col3:
    st.metric("MDD (최대 낙폭)", f"{filtered_tp_data.get('mdd', 0):+.2f}%")
    st.metric("MDD 고점 시점", filtered_tp_data.get("high_time", "N/A"))
    st.metric("MDD 저점 시점", filtered_tp_data.get("low_time", "N/A"))
with st.expander("📊 세부 통계량 보기"):

    st.subheader(" 전체 수익률 통계")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("평균 수익률", f"{filtered_tp_data.get('profit_rate_mean', 0):+.2f}%")
        st.metric("표준편차", f"{filtered_tp_data.get('profit_rate_std', 0):.2f}")
    with col2:
        st.metric("최소 수익률", f"{filtered_tp_data.get('profit_rate_min', 0):+.2f}%")
        st.metric("최대 수익률", f"{filtered_tp_data.get('profit_rate_max', 0):+.2f}%")

    st.subheader("🔺 수익 구간 통계")
    col3, col4 = st.columns(2)
    with col3:
        st.metric("수익 평균", f"{filtered_tp_data.get('profit_mean', 0):+.2f}%")
        st.metric("수익 표준편차", f"{filtered_tp_data.get('profit_std', 0):.2f}")
    with col4:
        st.metric("최소 수익", f"{filtered_tp_data.get('profit_min', 0):+.2f}%")
        st.metric("최대 수익", f"{filtered_tp_data.get('profit_max', 0):+.2f}%")

    st.subheader("🔻 손실 구간 통계")
    col5, col6 = st.columns(2)
    with col5:
        st.metric("손실 평균", f"{filtered_tp_data.get('loss_mean', 0):+.2f}%")
        st.metric("손실 표준편차", f"{filtered_tp_data.get('loss_std', 0):.2f}")
    with col6:
        st.metric("최소 손실", f"{filtered_tp_data.get('loss_max', 0):+.2f}%")
        st.metric("최대 손실", f"{filtered_tp_data.get('loss_min', 0):+.2f}%")
