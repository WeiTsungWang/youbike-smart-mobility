import streamlit as st

from utils import hide_streamlit_style

st.set_page_config(page_title="首頁 | YouBike 智慧出行系統", layout="wide", initial_sidebar_state="expanded")

st.title("🚲 YouBike 智慧出行系統")

st.markdown(hide_streamlit_style(), unsafe_allow_html=True)
st.markdown("歡迎使用本系統，請從左側選單選擇功能：")
st.info("👈 點選左側選單進入『即時查詢』或『路線與熱量計算』。")
