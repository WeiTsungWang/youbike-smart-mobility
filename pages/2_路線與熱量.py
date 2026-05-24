import streamlit as st
import requests
import polyline  # 需要先 pip install polyline
import pandas as pd
import pydeck as pdk
import sys
import os
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import get_station_data

st.set_page_config(page_title="YouBike 智慧熱量估計系統", layout="wide")
st.title("🚲 路線規劃與熱量估算")

stations_df = get_station_data()
station_list = stations_df['name_tw'].tolist()

col1, col2, col3 = st.columns(3)
with col1:
    start_name = st.selectbox("選擇起點", station_list, index=None, placeholder="請輸入起點...")
with col2:
    end_name = st.selectbox("選擇終點", station_list, index=None, placeholder="請輸入終點...")
with col3:
    weight = st.number_input("體重 (kg)", value=65)

if start_name and end_name:
    if st.button("計算並繪製路徑"):
        start_node = stations_df[stations_df['name_tw'] == start_name].iloc[0]
        end_node = stations_df[stations_df['name_tw'] == end_name].iloc[0]
        
        start_coords = f"{start_node['lng']},{start_node['lat']}"
        end_coords = f"{end_node['lng']},{end_node['lat']}"
        
        # 改為 overview=full 以獲取路徑 geometry
        url = f"http://router.project-osrm.org/route/v1/bicycle/{start_coords};{end_coords}?overview=full"
        
        try:
            response = requests.get(url).json()
            if response['code'] == 'Ok':
                route = response['routes'][0]
                dist_km = route['distance'] / 1000
                
                # --- 解碼 Polyline ---
                coords = polyline.decode(route['geometry'])
                df_route = pd.DataFrame(coords, columns=['lat', 'lon'])
                
                # 顯示統計數據
                time_min = (dist_km / 12) * 60
                calories = (4.0 * weight * time_min / 60)
                
                m1, m2, m3 = st.columns(3)
                m1.metric("騎乘距離", f"{dist_km:.2f} km")
                m2.metric("騎乘時間", f"{int(time_min)} 分鐘")
                m3.metric("消耗熱量", f"{int(calories)} 大卡")
                
                # 顯示地圖
                path_data = [[row['lon'], row['lat']] for _, row in df_route.iterrows()]

                # 1. 計算邊界 (Bounding Box)
                min_lat, max_lat = df_route['lat'].min(), df_route['lat'].max()
                min_lon, max_lon = df_route['lon'].min(), df_route['lon'].max()

                # 2. 自動計算 Zoom
                # 邏輯：經度差值 (delta_lon) 越大，zoom 需要越小
                delta_lat = max_lat - min_lat
                delta_lon = max_lon - min_lon
                max_delta = max(delta_lat, delta_lon)

                # 這是一個基於 Mercator 投影的縮放經驗公式
                # 根據經驗，zoom 14 對應的經緯度跨度約為 0.05 度左右
                # zoom_level = 14 - math.log2(max_delta / 0.05 + 0.001)

                # 限制 zoom 範圍在 11 到 17 之間，避免太過極端
                # zoom_level = max(11, min(17, zoom_level))

                zoom_level = 14 - math.log2(max_delta / 0.08 + 0.001)
                zoom_level = max(13, min(16, zoom_level))

                st.pydeck_chart(pdk.Deck(
                    initial_view_state=pdk.ViewState(
                        latitude=(min_lat + max_lat) / 2,
                        longitude=(min_lon + max_lon) / 2,
                        zoom=zoom_level,
                        pitch=0
                    ),
                    layers=[
                        pdk.Layer(
                            "PathLayer",
                            data=[{"path": path_data}],
                            get_path="path",
                            get_color=[255, 69, 0, 200],
                            get_width=8,
                            pickable=True,
                        )
                    ]
                ))
                
            else:
                st.error("無法計算路徑。")
        except Exception as e:
            st.error(f"路徑繪製失敗: {e}")
else:
    st.info("請先選擇起點與終點以進行計算。")