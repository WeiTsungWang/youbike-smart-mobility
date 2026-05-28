import math

import streamlit as st
import pandas as pd
import pydeck as pdk
import altair as alt
import subprocess
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import get_station_data, get_realtime_info_batch

st.set_page_config(page_title="YouBike 智慧熱量估計系統", layout="wide")

def init_app():
    # 建立一個佔位容器
    placeholder = st.empty()
    
    if not os.path.exists('stations.db'):
        # 顯示初始化訊息
        with placeholder.container():
            st.info("偵測到尚未建立站點資料庫，正在執行初始化...")
            
        try:
            # 執行爬蟲
            subprocess.run(["python", "data_collector.py"], check=True)
            
            # 將內容替換為成功訊息
            with placeholder.container():
                st.success("初始化完成！")
            
            # 暫停 2 秒讓使用者看到成功訊息
            time.sleep(2)
            
        except subprocess.CalledProcessError as e:
            with placeholder.container():
                st.error(f"初始化失敗: {e}")
            time.sleep(2)
    
    # 清空容器，這會讓「初始化完成」的字樣消失
    placeholder.empty()

# 在頁面載入時執行一次
init_app()

st.title("🚲 全台 YouBike 2.0 即時查詢系統")

CITY_MAP = {
    "01": "臺北市", "02": "新北市", "03": "桃園市", "05": "新竹縣",
    "04": "新竹市", "82": "新竹科學園區", "07": "苗栗縣", "06": "臺中市",
    "11": "嘉義縣", "10": "嘉義市", "13": "臺南市", "12": "高雄市",
    "14": "屏東縣", "15": "臺東縣", "16": "光復鄉"
}

stations_df = get_station_data()
stations_df['city_name'] = stations_df['area_code_2'].map(CITY_MAP)

st.subheader("搜尋設定")
search_mode = st.radio("搜尋方式", ["依地區搜尋", "輸入站點名稱"], horizontal=True)

target_stations = stations_df.copy()

# --- 二階聯動選單 ---
# 1. 縣市 
# selected_city = st.sidebar.selectbox("請選擇縣市", list(CITY_MAP.values())) # 範例

# city_code = [k for k, v in CITY_MAP.items() if v == selected_city][0]
# target_stations = stations_df[stations_df['area_code_2'] == city_code]

# selected_dist = st.sidebar.selectbox("請選擇行政區", sorted(target_stations['district_tw'].unique()))
# target_stations = target_stations[target_stations['district_tw'] == selected_dist]
if search_mode == "依地區搜尋":
    col1, col2, col3 = st.columns([2, 2, 1], vertical_alignment="bottom")

    with col1:
        selected_city = st.selectbox("請選擇縣市", list(CITY_MAP.values()))

    city_code = [k for k, v in CITY_MAP.items() if v == selected_city][0]
    target_stations = stations_df[stations_df['area_code_2'] == city_code]

    with col2:
        selected_dist = st.selectbox("請選擇行政區", sorted(target_stations['district_tw'].unique()))

    target_stations = target_stations[target_stations['district_tw'] == selected_dist]

    with col3:
        query_btn = st.button("查詢該區即時資訊")
else: # 輸入站點名稱模式
    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    station_list = stations_df['name_tw'].tolist()

    with col1:
        search_query = st.selectbox("選擇站點", station_list, index=None, placeholder="請輸入站點名稱...")
    
    with col2:
        query_btn = st.button("查詢特定站點")
    
    if search_query:
        # 使用字串包含來搜尋
        target_stations = target_stations[target_stations['name_tw'].str.contains(search_query, na=False)]
    else:
        target_stations = pd.DataFrame() # 未輸入時為空

if query_btn:
    if target_stations.empty:
        st.warning("查無站點資料，請調整關鍵字。")
    else:
        with st.spinner(f'正在查詢即時資訊...'):
            # 一次取得該區所有站點 ID
            sno_list = target_stations['station_no'].tolist()
            
            # 批次呼叫
            realtime_data = get_realtime_info_batch(sno_list)
            
            if realtime_data:
                df_api = pd.DataFrame(realtime_data)
                df = pd.merge(df_api, target_stations, on='station_no', how='inner')
                # 在 merge 之後加上這段清理邏輯
                df = df.drop(columns=['lat_x', 'lng_x'])
                # 並將 lat_y, lng_y 重新命名為 lat, lng，這樣你原本的程式碼就不用再改 _y 了
                df = df.rename(columns={'lat_y': 'lat', 'lng_y': 'lng'})
                # st.write("目前表格的欄位:", df.columns.tolist())
                
                # 地圖顯示
                # 地圖顯示修正版：直接從 target_stations 獲取經緯度，確保不依賴 API 回傳的欄位
                # 1. 確保經緯度已經是 float 型態 (在 merge 之後執行)
                df['lat'] = df['lat'].astype(float)
                df['lng'] = df['lng'].astype(float)

                # --- 在 st.pydeck_chart 之前插入此段 ---
                # 1. 計算經緯度範圍 (Bounding Box)
                lat_range = df['lat'].max() - df['lat'].min()
                lon_range = df['lng'].max() - df['lng'].min()
                max_delta = max(lat_range, lon_range, 0.01) # 至少設為 0.01 避免單一點崩潰
                
                # 2. 自動計算 Zoom (範圍約 11~15)
                # 使用簡單的對數比例，讓範圍大的時候縮小，範圍小的時候放大
                zoom_level = 11.0 - math.log2(max_delta / 0.3)

                # 2. 地圖顯示區塊修正
                st.subheader(f"站點分佈")
                st.pydeck_chart(pdk.Deck(
                    initial_view_state=pdk.ViewState(
                        latitude=df['lat'].mean(), 
                        longitude=df['lng'].mean(), 
                        zoom=zoom_level
                    ),
                    layers=[pdk.Layer(
                        "ScatterplotLayer", 
                        df,
                        # 直接使用欄位名稱，不要再寫 .astype(float)
                        get_position='[lng, lat]', 
                        get_color='[200, 30, 0, 160]',
                        get_radius=40,
                        pickable=True
                    )],
                    tooltip={"text": "站點名稱: {name_tw}\n站點位置: {address_tw}\n可借: {available_spaces}\n可還: {empty_spaces}"}
                ))

                if search_mode == "依地區搜尋":
                # 橫向長條圖
                    st.subheader("前 10 名可借站點")
                    chart_data = df.nlargest(10, 'available_spaces')[['name_tw', 'available_spaces']]
                    chart = alt.Chart(chart_data).mark_bar(color='#76C8FF').encode(
                        x=alt.X('available_spaces', title='可借'),
                        y=alt.Y('name_tw', title=['站', '點', '名', '稱'], sort='-x', axis=alt.Axis(labelLimit=300, titleAngle=0))
                    ).properties(height=400)
                    st.altair_chart(chart.configure_axis(titleAngle=0), width='stretch')

                    st.subheader("前 10 名可還站點")
                    chart_data = df.nlargest(10, 'empty_spaces')[['name_tw', 'empty_spaces']]
                    chart = alt.Chart(chart_data).mark_bar(color='#76C8FF').encode(
                        x=alt.X('empty_spaces', title='可還'),
                        y=alt.Y('name_tw', title=['站', '點', '名', '稱'], sort='-x', axis=alt.Axis(labelLimit=300, titleAngle=0))
                    ).properties(height=400)
                    st.altair_chart(chart.configure_axis(titleAngle=0), width='stretch')

                # 表格顯示 (使用中文化設定)
                st.subheader("站點即時資訊")
                st.dataframe(df[['name_tw', 'address_tw', 'available_spaces', 'empty_spaces']].rename(columns={
                    'name_tw': '站點名稱', 'address_tw': '站點位置', 'available_spaces': '可借', 'empty_spaces': '可還'
                }), column_config={"站點名稱": st.column_config.TextColumn(width="large")}, hide_index=True)
            else:
                st.error(f"在找不到即時資料，請確認是否為 YouBike 2.0 營運範圍。")
