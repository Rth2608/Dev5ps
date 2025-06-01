import streamlit as st
import requests
import json


API_URL = st.secrets.get("API_URL", "http://localhost:8080")

st.set_page_config(layout="wide")
st.title("백테스트 승률 시각화")
st.write("현재까지 실행한 백테스트의 결과를 한 눈에 확인합니다.")

filtered_res = requests.get(f"{API_URL}/filtered-profit-rate")
if filtered_res.status_code != 200:
    st.error(f"전략 목록 불러오기 실패: {filtered_res.status_code}")
    st.stop()

filtered_data = filtered_res.json()
if not filtered_data:
    st.warning("저장된 전략 결과가 없습니다.")
    st.stop()

st.line_chart(filtered_data, x = "entry_time", y = "cum_profit_rate",color="#FF0000")

filtered_tp_res = requests.get(f"{API_URL}/filtered-tp-sl-rate")
if filtered_res.status_code != 200:
    st.error(f"전략 목록 불러오기 실패: {filtered_res.status_code}")
    st.stop()

filtered_tp_data = filtered_tp_res.json()
if not filtered_data:
    st.warning("저장된 전략 결과가 없습니다.")
    st.stop()

a, b = st.columns(2)
a.matric(label = "총 실행 횟수", value = filtered_tp_data["total_count"])
b.matric(label = "누적 승률", value = filtered_tp_data["tp_rate"])
