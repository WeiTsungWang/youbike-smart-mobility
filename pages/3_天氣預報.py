import pandas as pd
import streamlit as st
import sys
import os

# 加入根目錄以匯入 utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import get_weather_forecast

st.title("🌤️ 全台各地天氣預報")

# 建立縣市與其中心點經緯度對照表
CITY_COORDS = {
    "基隆市": (25.132, 121.745), "臺北市": (25.033, 121.565), 
    "新北市": (25.017, 121.463), "桃園市": (24.993, 121.301),
    "新竹市": (24.813, 120.967), "新竹縣": (24.825, 121.011),
    "苗栗縣": (24.558, 120.821), "臺中市": (24.147, 120.673),
    "彰化縣": (24.051, 120.516), "南投縣": (23.916, 120.896),
    "雲林縣": (23.697, 120.522), "嘉義市": (23.475, 120.447),
    "嘉義縣": (23.451, 120.252), "臺南市": (22.999, 120.227),
    "高雄市": (22.627, 120.301), "屏東縣": (22.683, 120.494),
    "宜蘭縣": (24.702, 121.755), "花蓮縣": (23.975, 121.603),
    "臺東縣": (22.751, 121.144), "澎湖縣": (23.568, 119.579),
    "金門縣": (24.432, 118.326), "連江縣": (26.155, 119.957)
}

# 選擇城市
selected_city = st.selectbox("請選擇要查詢的縣市", list(CITY_COORDS.keys()))
lat, lon = CITY_COORDS[selected_city]

if st.button("查詢天氣"):
    with st.spinner(f'正在為您查詢 {selected_city} 的天氣資訊...'):
        # 只呼叫一次 API
        data = get_weather_forecast(lat, lon)
        prob = data['daily']['precipitation_probability_max'][0]
        
        if data:
            curr = data['current']
            
            # 1. 頂部摘要 (只顯示關鍵指標，避開溫度重複)
            st.subheader(f"{selected_city} 當前概況")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("即時溫度", f"{curr['temperature_2m']}°C")
            col2.metric("濕度", f"{curr['relative_humidity_2m']}%")
            col3.metric("降雨機率", f"{prob}%")
            col4.metric("風速", f"{curr['wind_speed_10m']} km/h")
            # 這裡我們利用 weather_code 簡單轉譯狀態
            w_code = curr['weather_code']
            status = "晴天" if w_code < 2 else "陰天/多雲"
            if 50 <= w_code <= 67: status = "雨天"
            col4.metric("天氣狀態", status)
            
            # 2. 動態建議 (邏輯改為從 data 中讀取降雨機率)
            prob = data['daily']['precipitation_probability_max'][0] # 當日預報機率
            if prob > 50:
                st.error("☔ 降雨機率高，建議攜帶雨具。")
            elif "晴" in status:
                st.success("☀️ 天氣理想，適合騎乘 YouBike！")
            else:
                st.info("☁️ 天氣尚可，適合短途騎行。")

            # 一週預報 (表格化)
            st.subheader("🗓️ 一週天氣預報")
            daily = data['daily']
            df_forecast = pd.DataFrame({
                "日期": daily['time'],
                "最高溫": daily['temperature_2m_max'],
                "最低溫": daily['temperature_2m_min'],
                "降雨機率 (%)": daily['precipitation_probability_max']
            })
