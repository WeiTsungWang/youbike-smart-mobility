import streamlit as st
from streamlit_searchbox import st_searchbox
import requests
import polyline  # 需要先 pip install polyline
import pandas as pd
import pydeck as pdk
import sys
import os
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import calculate_dist, get_osrm_distance, get_station_data, get_coords

def find_nearest_station(lat, lon, df):
    df['dist'] = ((df['lat'] - lat)**2 + (df['lng'] - lon)**2)
    return df.loc[df['dist'].idxmin()]

def search_address(searchterm: str):
    if not searchterm or len(searchterm) < 3:
        return []
    
    # 限制搜尋範圍在台灣 (countrycodes='tw')
    url = f"https://nominatim.openstreetmap.org/search?q={searchterm}&format=json&limit=5&countrycodes=tw"
    headers = {'User-Agent': 'YouBikeApp/1.0'}
    
    try:
        response = requests.get(url, headers=headers).json()
        # 回傳一個列表，格式為 [顯示文字, 原始資料]
        return [res['display_name'] for res in response]
    except:
        return []

st.title("🚲 路線規劃與熱量估算")

# stations_df = get_station_data()
# station_list = stations_df['name_tw'].tolist()

mode = st.radio("選擇交通方式", ["步行", "自己的腳踏車", "YouBike"], horizontal=True)

col1, col2, col3 = st.columns(3)
with col1:
    start_addr = st_searchbox(search_address, label="輸入起點 (例如：台北車站)", key="start_addr_box")
with col2:
    end_addr = st_searchbox(search_address, label="輸入終點 (例如：新北市政府)", key="end_addr_box")
with col3:
    weight = st.number_input("體重 (kg)", value=65)

if st.button("計算路徑"):
    if not start_addr and not end_addr:
        st.warning("請先輸入起點與終點地址！")
    elif not start_addr:
        st.warning("請先輸入起點地址！")
    elif not end_addr:
        st.warning("請先輸入終點地址！")
    else:
        start_lat, start_lon = get_coords(start_addr)
        end_lat, end_lon = get_coords(end_addr)
        profile = "foot" if mode == "步行" else "bicycle"
        
        if not (start_lat and end_lat):
            st.error("找不到地址，請輸入更明確的地點。")
        else:
            # YouBike 邏輯：找最近站點
            if mode == "YouBike":
                stations_df = get_station_data()
                start_node = find_nearest_station(start_lat, start_lon, stations_df)
                end_node = find_nearest_station(end_lat, end_lon, stations_df)
                
                # 更新座標為站點座標
                s_lat, s_lon = start_node['lat'], start_node['lng']
                e_lat, e_lon = end_node['lat'], end_node['lng']
                st.write(f"🚗 幫您導航至最近站點：起點({start_node['name_tw']}) -> 終點({end_node['name_tw']})")
            else:
                s_lat, s_lon = start_lat, start_lon
                e_lat, e_lon = end_lat, end_lon

            # 呼叫 OSRM (步行用 'foot', 自行車用 'bicycle')
            profile = "foot" if mode == "步行" else "bicycle"
            url = f"http://router.project-osrm.org/route/v1/{profile}/{s_lon},{s_lat};{e_lon},{e_lat}?overview=full"
            
            try:
                response = requests.get(url).json()
                if response['code'] == 'Ok':
                    route = response['routes'][0]
                    dist_km = route['distance'] / 1000
                    
                    # --- 解碼 Polyline ---
                    coords = polyline.decode(route['geometry'])
                    df_route = pd.DataFrame(coords, columns=['lat', 'lon'])
                    
                    if mode == "YouBike":
                        # 計算步行段 (起點->借車站, 還車站->終點)
                        # 這裡建議使用簡單的直線距離 (Haversine) 或再呼叫兩次 foot API
                        walk_dist_km = (get_osrm_distance(start_lat, start_lon, s_lat, s_lon, "foot") + 
                                        get_osrm_distance(e_lat, e_lon, end_lat, end_lon, "foot"))
                        
                        # 計算騎乘段 (借車站->還車站)
                        ride_dist_km = get_osrm_distance(s_lat, s_lon, e_lat, e_lon, "bicycle")
                        
                        # 熱量公式：步行 METs 約 3.5, 自行車 METs 約 6.0 - 8.0
                        walk_calories = (3.5 * weight * (walk_dist_km / 5) )
                        ride_calories = (5.0 * weight * (ride_dist_km / 12))
                        calories = walk_calories + ride_calories

                        walk_time_min = (walk_dist_km / 5) * 60
                        ride_time_min = (ride_dist_km / 12) * 60
                        time_min = walk_time_min + ride_time_min
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("總距離", f"{dist_km:.2f} km")
                        m1.write(f"包含步行 {walk_dist_km:.2f}km 與 騎乘 {ride_dist_km:.2f}km")
                        m2.metric("總時間", f"{int(time_min)} 分鐘")
                        m2.write(f"包含步行 {int(walk_time_min)}分鐘 與 騎乘 {int(ride_time_min)}分鐘")
                        m3.metric("總消耗熱量", f"{int(calories)} 大卡")
                        m3.write(f"包含步行 {walk_calories:.1f}大卡 與 騎乘 {ride_calories:.1f}大卡")
                        
                    elif mode == "步行":
                        dist_km = get_osrm_distance(start_lat, start_lon, end_lat, end_lon, "foot")
                        calories = (3.5 * weight * (dist_km / 5)) # 步行時速約 5km/h

                        time_min = (dist_km / 5) * 60

                        m1, m2, m3 = st.columns(3)

                        m1.metric("步行距離", f"{dist_km:.2f} km")
                        m2.metric("步行時間", f"{int(time_min)} 分鐘")
                        m3.metric("總消耗熱量", f"{int(calories)} 大卡")
                        
                    else: # 自己的腳踏車
                        dist_km = get_osrm_distance(start_lat, start_lon, end_lat, end_lon, "bicycle")
                        calories = (7.0 * weight * (dist_km / 12)) # 騎乘時速約 12km/h
                        time_min = (dist_km / 12) * 60

                        m1, m2, m3 = st.columns(3)
                        m1.metric("騎乘距離", f"{dist_km:.2f} km")
                        m2.metric("騎乘時間", f"{int(time_min)} 分鐘")
                        m3.metric("總消耗熱量", f"{int(calories)} 大卡")


                    
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

                    zoom_level = 14 - math.log2(max_delta / 0.08 + 0.001)
                    zoom_level = max(13, min(16, zoom_level))

                    layers = []

                    if mode == "YouBike":
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[
                                {"path": [[start_lon, start_lat], [s_lon, s_lat]], "name": "步行路段"}, # 起點到借車
                                {"path": [[e_lon, e_lat], [end_lon, end_lat]], "name": "步行路段"}      # 還車到終點
                            ],
                            get_path="path",
                            get_color=[0, 255, 255, 200], # 亮青色 (Cyan)
                            get_width=8,
                            get_dash_array=[10, 5],      # [線長, 間隔] - 這就是虛線的關鍵！
                            pickable=True,
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[{"path": path_data, "name": "YouBike騎乘路段"}],
                            get_path="path",
                            get_color=[255, 69, 0, 200],
                            get_width=8,
                            pickable=True,
                        ))
                        # YouBike 模式：顯示起終點 + 借還站點
                        layers.append(pdk.Layer(
                            "ScatterplotLayer",
                            data=[
                                {"name": f"起點: {start_addr}", "pos": [start_lon, start_lat], "color": [0, 255, 0]},
                                {"name": f"借車站: {start_node['name_tw']}", "pos": [s_lon, s_lat], "color": [255, 255, 0]},
                                {"name": f"還車站: {end_node['name_tw']}", "pos": [e_lon, e_lat], "color": [255, 165, 0]},
                                {"name": f"終點: {end_addr}", "pos": [end_lon, end_lat], "color": [0, 0, 255]}
                            ],
                            get_position="pos",
                            get_color="color",
                            get_radius=50,
                            pickable=True,
                        ))
                    else:
                        # 步行/自行車模式：只顯示起終點
                        layers.append(pdk.Layer(
                            "ScatterplotLayer",
                            data=[
                                {"name": f"起點: {start_addr}", "pos": [start_lon, start_lat], "color": [0, 255, 0]},
                                {"name": f"終點: {end_addr}", "pos": [end_lon, end_lat], "color": [0, 0, 255]}
                            ],
                            get_position="pos",
                            get_color="color",
                            get_radius=50,
                            pickable=True,
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[{"path": path_data, "name": "路線"}],
                            get_path="path",
                            get_color=[255, 69, 0, 200],
                            get_width=8,
                            pickable=True,
                        ))

                    st.pydeck_chart(pdk.Deck(
                        initial_view_state=pdk.ViewState(
                            latitude=(min_lat + max_lat) / 2,
                            longitude=(min_lon + max_lon) / 2,
                            zoom=zoom_level,
                            pitch=0
                        ),
                        layers=layers,
                        tooltip={"text": "{name}"}
                    ))
                    
                else:
                    st.error("無法計算路徑。")
            except Exception as e:
                st.error(f"路徑繪製失敗: {e}")
else:
    st.info("請先選擇起點與終點以進行計算。")