import streamlit as st
from streamlit_searchbox import st_searchbox
import requests
import polyline
import pandas as pd
import pydeck as pdk
import sys
import os
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import get_osrm_distance, get_station_data, find_nearest_station, get_weather_forecast

st.set_page_config(page_title="路線規劃 | YouBike 智慧出行系統", layout="wide")

st.title("🚲 路線規劃與熱量估算")

# ==========================================
# 1. 狀態初始化 (State Management)
# ==========================================
if 'address_map' not in st.session_state:
    st.session_state.address_map = {}
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = "步行"
if 'run_calc' not in st.session_state:
    st.session_state.run_calc = False # 紀錄是否已經按過「計算路徑」

# ==========================================
# 2. 回呼函式 (Callback)
# ==========================================
# 這是解決 Radio 不同步的終極武器，確保在畫面重繪前就改好狀態
def switch_to_walk():
    st.session_state.current_mode = "步行"

def search_address(searchterm: str):
    if not searchterm or len(searchterm) < 3:
        return []
    
    url = f"https://nominatim.openstreetmap.org/search?q={searchterm}&format=json&limit=5&countrycodes=tw"
    headers = {'User-Agent': 'YouBikeApp/1.0'}
    
    try:
        response = requests.get(url, headers=headers).json()
        results = {res['display_name']: [float(res['lat']), float(res['lon'])] for res in response}
        # 更新全域的查詢紀錄
        st.session_state.address_map.update(results)
        return list(results.keys()) # searchbox 選單只需要顯示 Key
    except:
        return []

# ==========================================
# 3. UI 元件
# ==========================================
# 最簡潔的寫法，直接讓 key 控制
st.radio(
    "選擇交通方式", 
    ["步行", "自己的腳踏車", "YouBike"], 
    key="current_mode",
    horizontal=True
)

col1, col2, col3 = st.columns(3)
with col1:
    start_addr = st_searchbox(search_address, label="輸入起點 (例如：台北車站)", key="start_addr_box")
with col2:
    end_addr = st_searchbox(search_address, label="輸入終點 (例如：新北市政府)", key="end_addr_box")
with col3:
    weight = st.number_input("體重 (kg)", value=65)

# ==========================================
# 4. 核心邏輯區塊
# ==========================================
# 按下按鈕只負責改變狀態，不包攬所有計算邏輯
if st.button("計算路徑"):
    st.session_state.run_calc = True

# 只要 run_calc 是 True，就維持顯示計算結果
if st.session_state.run_calc:
    start_coords = st.session_state.address_map.get(start_addr)
    end_coords = st.session_state.address_map.get(end_addr)

    if not start_addr and not end_addr:
        st.warning("請先輸入起點與終點！")
    elif not start_addr:
        st.warning("請先輸入起點！")
    elif not end_addr:
        st.warning("請先輸入終點！")
    elif not start_coords or not end_coords:
        st.error("找不到座標！請確保您是從選單中選取地點的。")
    else:
        start_lat, start_lon = start_coords
        end_lat, end_lon = end_coords
        
        if not (start_lat and end_lat):
            st.error("找不到地址，請輸入更明確的地點。")
        else:
            # --- 查詢天氣 ---
            avg_lat, avg_lon = (start_lat + end_lat) / 2, (start_lon + end_lon) / 2
            weather_data = get_weather_forecast(avg_lat, avg_lon)
            if weather_data:
                prob = weather_data['daily']['precipitation_probability_max'][0]
                status = "晴天" if weather_data['current']['weather_code'] < 2 else "雨天/多雲"
                if prob > 50: st.error(f"☔ 降雨機率 {prob}%，建議攜帶雨具。")
                elif "晴" in status: st.success("☀️ 天氣理想，適合騎乘！")
                else: st.info("☁️ 天氣尚可，適合短途騎行。")

            # YouBike 邏輯：找最近站點
            if st.session_state.current_mode == "YouBike":
                stations_df = get_station_data()
                start_node = find_nearest_station(start_lat, start_lon, stations_df)
                end_node = find_nearest_station(end_lat, end_lon, stations_df)
                
                # 更新座標為站點座標
                s_lat, s_lon = start_node['lat'], start_node['lng']
                e_lat, e_lon = end_node['lat'], end_node['lng']

                # --- 時間判斷邏輯 ---
                # 1. 計算純步行時間 (時速 5 km/h)
                walk_only_dist = get_osrm_distance(start_lat, start_lon, end_lat, end_lon, "foot")
                walk_only_time = (walk_only_dist / 5) * 60
                
                # 2. 計算 YouBike 方案時間 (步行段 5km/h, 騎乘段 12km/h)
                walk_dist = (get_osrm_distance(start_lat, start_lon, s_lat, s_lon, "foot") + 
                             get_osrm_distance(e_lat, e_lon, end_lat, end_lon, "foot"))
                ride_dist = get_osrm_distance(s_lat, s_lon, e_lat, e_lon, "bicycle")
                
                yb_time = (walk_dist / 5) * 60 + (ride_dist / 12) * 60

                if yb_time > walk_only_time:
                    st.warning(f"💡 建議直接步行：步行約 {int(walk_only_time)} 分鐘！")

                    col_a, col_b = st.columns([1, 4])
                                        
                    # 這是最關鍵的修正：利用 on_click 觸發狀態改變！
                    col_a.button("切換至步行模式", on_click=switch_to_walk)
                                    
                st.write(f"🚗 幫您導航至最近站點：\n起點({start_addr})\n -> 借車點({start_node['name_tw']})\n -> 終點({end_node['name_tw']})\n -> 終點({end_addr})")
            else:
                s_lat, s_lon = start_lat, start_lon
                e_lat, e_lon = end_lat, end_lon

            # 呼叫 OSRM (步行用 'foot', 自行車用 'bicycle')
            profile = "foot" if st.session_state.current_mode == "步行" else "bicycle"
            url = f"http://router.project-osrm.org/route/v1/{profile}/{s_lon},{s_lat};{e_lon},{e_lat}?overview=full"
            
            try:
                response = requests.get(url).json()
                if response['code'] == 'Ok':
                    route = response['routes'][0]
                    dist_km = route['distance'] / 1000
                    
                    # --- 解碼 Polyline ---
                    coords = polyline.decode(route['geometry'])
                    df_route = pd.DataFrame(coords, columns=['lat', 'lon'])
                    
                    if st.session_state.current_mode == "YouBike":
                        # 計算步行段 (起點->借車站, 還車站->終點)
                        walk_dist_km = (get_osrm_distance(start_lat, start_lon, s_lat, s_lon, "foot") + 
                                        get_osrm_distance(e_lat, e_lon, end_lat, end_lon, "foot"))
                        
                        # 計算騎乘段 (借車站->還車站)
                        ride_dist_km = get_osrm_distance(s_lat, s_lon, e_lat, e_lon, "bicycle")

                        total_dist_km = walk_dist_km + ride_dist_km
                        
                        # 熱量公式：步行 METs 約 3.5, 自行車 METs 約 5.0
                        walk_calories = (3.5 * weight * (walk_dist_km / 5) )
                        ride_calories = (5.0 * weight * (ride_dist_km / 12))
                        calories = walk_calories + ride_calories

                        walk_time_min = (walk_dist_km / 5) * 60
                        ride_time_min = (ride_dist_km / 12) * 60
                        time_min = walk_time_min + ride_time_min
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("總距離", f"{total_dist_km:.2f} km")
                        m1.write(f"包含步行 {walk_dist_km:.2f}km 與 騎乘 {ride_dist_km:.2f}km")
                        m2.metric("總時間", f"{int(time_min)} 分鐘")
                        m2.write(f"包含步行 {int(walk_time_min)}分鐘 與 騎乘 {int(ride_time_min)}分鐘")
                        m3.metric("總消耗熱量", f"{int(calories)} 大卡")
                        m3.write(f"包含步行 {walk_calories:.1f}大卡 與 騎乘 {ride_calories:.1f}大卡")
                        
                    elif st.session_state.current_mode == "步行":
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
                    padding = 0.02 # 這個 padding 確保起終點不會剛好卡在畫面邊緣
                    search_radius = max_delta + padding

                    zoom_level = 13.0 - math.log10(search_radius + 0.001)

                    layers = []

                    if st.session_state.current_mode == "YouBike":
                        # 1. 取得三段路由的路徑幾何資料
                        def get_route_geometry(from_lat, from_lon, to_lat, to_lon, profile):
                            url = f"http://router.project-osrm.org/route/v1/{profile}/{from_lon},{from_lat};{to_lon},{to_lat}?overview=full"
                            res = requests.get(url).json()
                            if res['code'] == 'Ok':
                                return polyline.decode(res['routes'][0]['geometry'])
                            return []

                        walk_path1 = get_route_geometry(start_lat, start_lon, s_lat, s_lon, "foot")
                        bike_path = get_route_geometry(s_lat, s_lon, e_lat, e_lon, "bicycle")
                        walk_path2 = get_route_geometry(e_lat, e_lon, end_lat, end_lon, "foot")

                        # 2. 將路徑資料轉換為 PyDeck 需要的格式
                        # 注意：OSRM 回傳的是 (lat, lon)，PyDeck 需要 [lon, lat]
                        walk_data1 = [[p[1], p[0]] for p in walk_path1]
                        bike_data = [[p[1], p[0]] for p in bike_path]
                        walk_data2 = [[p[1], p[0]] for p in walk_path2]

                        # 3. 繪製圖層
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[{"path": walk_data1, "name": "步行路段"}],
                            get_path="path",
                            get_color=[0, 255, 255, 200],
                            get_width=8,
                            get_dash_array=[10, 5],
                            pickable=True,
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[{"path": walk_data2, "name": "步行路段"}],
                            get_path="path",
                            get_color=[0, 255, 255, 200],
                            get_width=8,
                            get_dash_array=[10, 5],
                            pickable=True,
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[{"path": bike_data, "name": "YouBike騎乘路段"}],
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