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
from utils import get_nearest_n_stations, get_osrm_distance, get_realtime_info_batch, get_station_data, get_weather_forecast, hide_streamlit_style

st.set_page_config(page_title="路線規劃 | YouBike 智慧出行系統", layout="wide", initial_sidebar_state="expanded")

st.markdown(hide_streamlit_style(), unsafe_allow_html=True)

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
if "confirmed_start" not in st.session_state:
    st.session_state.confirmed_start = None
if "confirmed_end" not in st.session_state:
    st.session_state.confirmed_end = None
if "zoom" in st.session_state:
    zoom_level = st.session_state["zoom"]

# ==========================================
# 2. 回呼函式 (Callback)
# ==========================================
def trigger_calc():
    st.session_state.run_calc = True

# 這是解決 Radio 不同步的終極武器，確保在畫面重繪前就改好狀態
def switch_to_walk():
    st.session_state.current_mode = "步行"

def search_address(searchterm: str):
    if not searchterm or len(searchterm) < 2:
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
st.button("計算路徑", on_click=trigger_calc)

if st.session_state.run_calc:
    st.session_state.confirmed_start = start_addr
    st.session_state.confirmed_end = end_addr
    st.session_state.run_calc = False  # 🔥 重置

    start_coords = st.session_state.address_map.get(st.session_state.confirmed_start)
    end_coords = st.session_state.address_map.get(st.session_state.confirmed_end)

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
                elif "晴" in status: st.success("☀️ 天氣理想，適合出行！")
                else: st.info("☁️ 天氣尚可，適合短途。")

            # YouBike 邏輯：找最近站點
            if st.session_state.current_mode == "YouBike":
                stations_df = get_station_data()

                candidate_starts = get_nearest_n_stations(
                                        start_lat,
                                        start_lon,
                                        stations_df,
                                        10
                                    )
                station_start_ids = candidate_starts["station_no"].tolist()

                start_realtime = get_realtime_info_batch(station_start_ids)
                df_rt = pd.DataFrame(start_realtime)

                candidate_starts = candidate_starts.merge(
                    df_rt,
                    on="station_no"
                )
                candidate_starts = candidate_starts.drop(columns=['lat_x', 'lng_x'])
                candidate_starts = candidate_starts.rename(columns={'lat_y': 'lat', 'lng_y': 'lng'})

                candidate_starts["distance_score"] = (
                    1 -
                    candidate_starts["dist"] /
                    candidate_starts["dist"].max()
                )

                candidate_starts["bike_score"] = (
                    candidate_starts["available_spaces"] /
                    candidate_starts["available_spaces"].max()
                )

                candidate_starts["final_score"] = (
                    0.6 * candidate_starts["bike_score"]
                    +
                    0.4 * candidate_starts["distance_score"]
                )

                best_start = candidate_starts.loc[candidate_starts["final_score"].idxmax()]

                candidate_ends = get_nearest_n_stations(
                                        end_lat,
                                        end_lon,
                                        stations_df,
                                        10
                                    )
                
                station_end_ids = candidate_ends["station_no"].tolist()
                end_realtime = get_realtime_info_batch(station_end_ids)
                df_rt_end = pd.DataFrame(end_realtime)
                candidate_ends = candidate_ends.merge(  
                    df_rt_end,
                    on="station_no"
                )

                candidate_ends = candidate_ends.drop(columns=['lat_x', 'lng_x'])
                candidate_ends = candidate_ends.rename(columns={'lat_y': 'lat', 'lng_y': 'lng'})

                candidate_ends["slot_score"] = (
                    candidate_ends["empty_spaces"] /
                    candidate_ends["empty_spaces"].max()
                )

                candidate_ends["distance_score"] = (
                    1 -
                    candidate_ends["dist"] /
                    candidate_ends["dist"].max()
                )

                candidate_ends["final_score"] = (
                    0.6 * candidate_ends["slot_score"]
                    +
                    0.4 * candidate_ends["distance_score"]
                )

                best_end = candidate_ends.loc[candidate_ends["final_score"].idxmax()]

                top3_start = candidate_starts.nlargest(
                                3,
                                "final_score"
                            )
                top3_end = candidate_ends.nlargest(
                                3,
                                "final_score"
                            )

                start_node = best_start
                end_node = best_end

                # st.write(f"DEBUG: start_node 的類型是 {type(start_node)}, 內容是: {start_node}")
                # st.write(f"DEBUG: end_node 的類型是 {(end_node)}, 內容是: {end_node}")
                

                # 更新座標為站點座標
                s_lat, s_lon = float(start_node['lat']), float(start_node['lng'])
                e_lat, e_lon = float(end_node['lat']), float(end_node['lng'])

                # --- 時間判斷邏輯 ---
                # 1. 計算純步行時間 (時速 5 km/h)
                walk_only_dist = get_osrm_distance(start_lat, start_lon, end_lat, end_lon, "foot")
                walk_only_time = (walk_only_dist / 5) * 60
                
                # 2. 計算 YouBike 方案時間 (步行段 5km/h, 騎乘段 12km/h)
                walk_dist1 = get_osrm_distance(start_lat, start_lon, s_lat, s_lon, "foot")
                walk_dist2 = get_osrm_distance(e_lat, e_lon, end_lat, end_lon, "foot")
                walk_dist = walk_dist1 + walk_dist2
                ride_dist = get_osrm_distance(s_lat, s_lon, e_lat, e_lon, "bicycle")
                
                yb_time = (walk_dist / 5) * 60 + (ride_dist / 12) * 60
                st.subheader("🏆 智慧借還站推薦")
                col1, col2 = st.columns(2)

                with col1:
                    st.warning(
                        f"""
                        🚲 推薦借車站

                        {best_start['name_tw']}

                        距離： {walk_dist1*1000:.0f} m

                        可借車輛：
                        {best_start['available_spaces']} 台

                        綜合評分：
                        {best_start['final_score']*100:.0f}
                        """
                    )

                with col2:
                    st.success(
                        f"""
                        🅿️ 推薦還車站

                        {best_end['name_tw']}

                        距離：{walk_dist2*1000:.0f} m

                        可還空位：
                        {best_end['empty_spaces']} 格

                        綜合評分：
                        {best_end['final_score']*100:.0f}
                        """
                    )

                if yb_time > walk_only_time:
                    st.warning(f"💡 建議直接步行：步行約 {int(walk_only_time)} 分鐘！")

                    col_a, col_b = st.columns([1, 4])
                                        
                    # 這是最關鍵的修正：利用 on_click 觸發狀態改變！
                    col_a.button("切換至步行模式", on_click=switch_to_walk)
                                    
                st.write(f"🚗 幫您導航推薦路線：起點({start_addr}) -> 借車點({start_node['name_tw']}) -> 還車點({end_node['name_tw']}) -> 終點({end_addr})")
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
                        walk_dist_km1 = get_osrm_distance(start_lat, start_lon, s_lat, s_lon, "foot")
                        walk_dist_km2 = get_osrm_distance(e_lat, e_lon, end_lat, end_lon, "foot")
                        walk_dist_km = walk_dist_km1 + walk_dist_km2
                        
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

                    # 🔥 改良點 1：確保 YouBike 模式下的「原始起終點」也被包覆在視角內
                    if st.session_state.current_mode == "YouBike":
                        min_lat = min(min_lat, start_lat, end_lat, s_lat, e_lat)
                        max_lat = max(max_lat, start_lat, end_lat, s_lat, e_lat)
                        min_lon = min(min_lon, start_lon, end_lon, s_lon, e_lon)
                        max_lon = max(max_lon, start_lon, end_lon, s_lon, e_lon)

                    # # 2. 自動計算 Zoom (改良版算法)
                    # max_delta = max(max_lat - min_lat, max_lon - min_lon)
                    # # 透過對數計算合適的縮放比例，並限制在 11~16 之間，避免單點過度放大或跨縣市過度縮小
                    # zoom_level = 11.5 - math.log2(max_delta / 0.1) if max_delta > 0 else 15
                    # zoom_level = max(11, min(16, zoom_level)) 

                    # --- 這裡計算所有的座標點，包含起終點與路徑 ---
                    # 確保這些點都存在
                    all_lats = df_route['lat'].tolist() + [start_lat, end_lat]
                    all_lons = df_route['lon'].tolist() + [start_lon, end_lon]

                    # 計算中心點與極值
                    mid_lat = (max(all_lats) + min(all_lats)) / 2
                    mid_lon = (max(all_lons) + min(all_lons)) / 2

                    # 動態計算 Zoom (參考之前的 get_dynamic_zoom)
                    max_delta = max(max(all_lats) - min(all_lats), max(all_lons) - min(all_lons))
                    zoom_level = 11.5 - math.log2(max_delta / 0.1) if max_delta > 0 else 13

                    # 🔥 關鍵：建立一個 ViewState 物件
                    view_state = pdk.ViewState(
                        latitude=mid_lat,
                        longitude=mid_lon,
                        zoom=zoom_level,
                        pitch=0,
                        bearing=0
                    )

                    layers = []

                    if st.session_state.current_mode == "YouBike":
                        def get_route_geometry(from_lat, from_lon, to_lat, to_lon, profile):
                            url = f"http://router.project-osrm.org/route/v1/{profile}/{from_lon},{from_lat};{to_lon},{to_lat}?overview=full"
                            res = requests.get(url).json()
                            if res['code'] == 'Ok':
                                return polyline.decode(res['routes'][0]['geometry'])
                            return []

                        walk_path1 = get_route_geometry(start_lat, start_lon, s_lat, s_lon, "foot")
                        bike_path = get_route_geometry(s_lat, s_lon, e_lat, e_lon, "bicycle")
                        walk_path2 = get_route_geometry(e_lat, e_lon, end_lat, end_lon, "foot")

                        walk_data1 = [[p[1], p[0]] for p in walk_path1]
                        bike_data = [[p[1], p[0]] for p in bike_path]
                        walk_data2 = [[p[1], p[0]] for p in walk_path2]

                        # 🔥 改良點 2：加入 width_min_pixels 與 width_max_pixels
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[{"path": walk_data1, "name": "步行路段"}],
                            get_path="path",
                            get_color=[0, 255, 255, 200],
                            get_width=5,          # 真實世界寬度 (公尺)
                            width_min_pixels=3,   # 縮到最小時，依然保有 3 像素寬度
                            width_max_pixels=8,   # 放到最大時，不超過 8 像素寬度
                            get_dash_array=[10, 5],
                            pickable=True,
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[{"path": walk_data2, "name": "步行路段"}],
                            get_path="path",
                            get_color=[0, 255, 255, 200],
                            get_width=5,
                            width_min_pixels=3,
                            width_max_pixels=8,
                            get_dash_array=[10, 5],
                            pickable=True,
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[{"path": bike_data, "name": "YouBike騎乘路段"}],
                            get_path="path",
                            get_color=[255, 69, 0, 200],
                            get_width=5,
                            width_min_pixels=4,
                            width_max_pixels=12,
                            pickable=True,
                        ))
                        
                        # 🔥 改良點 3：加入 radius_min_pixels 與 radius_max_pixels
                        layers.append(pdk.Layer(
                            "ScatterplotLayer",
                            data=[
                                {"name": f"起點: {start_addr}", "pos": [start_lon, start_lat], "color": [255, 165, 0]},
                                {"name": f"借車站: {start_node['name_tw']}\n距離: {walk_dist_km1*1000:.0f} m\n可借: {start_node['available_spaces']}", "pos": [s_lon, s_lat], "color": [255, 255, 0]},
                                {"name": f"還車站: {end_node['name_tw']}\n距離: {walk_dist_km2*1000:.0f} m\n可還: {end_node['empty_spaces']}", "pos": [e_lon, e_lat], "color": [0, 255, 0]},
                                {"name": f"終點: {end_addr}", "pos": [end_lon, end_lat], "color": [150, 0, 150]}
                            ],
                            get_position="pos",
                            get_color="color",
                            get_radius=50,          # 真實世界半徑 (公尺)
                            radius_min_pixels=8,    # 縮小地圖時，點不會消失
                            radius_max_pixels=30,   # 放心地圖時，點不會蓋住整個螢幕
                            pickable=True,
                        ))
                    else:
                        layers.append(pdk.Layer(
                            "ScatterplotLayer",
                            data=[
                                {"name": f"起點: {start_addr}", "pos": [start_lon, start_lat], "color": [255, 165, 0]},
                                {"name": f"終點: {end_addr}", "pos": [end_lon, end_lat], "color": [150, 0, 150]}
                            ],
                            get_position="pos",
                            get_color="color",
                            get_radius=50,
                            radius_min_pixels=8,
                            radius_max_pixels=30,
                            pickable=True,
                        ))
                        layers.append(pdk.Layer(
                            "PathLayer",
                            data=[{"path": path_data, "name": "路線"}],
                            get_path="path",
                            get_color=[255, 69, 0, 200],
                            get_width=5,
                            width_min_pixels=4,
                            width_max_pixels=12,
                            pickable=True,
                        ))

                    # st.pydeck_chart(
                    #     pdk.Deck(
                    #         initial_view_state=pdk.ViewState(
                    #             latitude=(min_lat + max_lat) / 2,
                    #             longitude=(min_lon + max_lon) / 2,
                    #             zoom=zoom_level,
                    #             pitch=0
                    #         ),
                    #         layers=layers,
                    #         tooltip={"text": "{name}"}
                    #     ),
                    #     use_container_width=True
                    # )

                    st.pydeck_chart(
                        pdk.Deck(
                            initial_view_state=view_state,
                            layers=layers,
                            tooltip={"text": "{name}"}
                        ),
                        use_container_width=True
                    )

                    if st.session_state.current_mode == "YouBike":
                        col1, col2 = st.columns(2)

                        with col1:
                            st.subheader("🚲 借車站 Top3")

                            start_dist = []

                            for i in range(len(top3_start)):
                                dist = get_osrm_distance(
                                    start_lat, 
                                    start_lon, 
                                    top3_start.iloc[i]['lat'], 
                                    top3_start.iloc[i]['lng'], 
                                    "foot"
                                )
                                start_dist.append(dist)

                            start_data = pd.DataFrame({
                                "站點名稱": top3_start["name_tw"],
                                "距離(m)": [dist * 1000 for dist in start_dist],
                                "可借車輛": top3_start["available_spaces"],
                                "綜合評分": [f"{score*100:.2f}" for score in top3_start["final_score"]]
                            })

                            st.dataframe(
                                start_data,
                                use_container_width=True, 
                                hide_index=True
                            )
                        with col2:
                            st.subheader("🅿️ 還車站 Top3")

                            end_dist = []

                            for i in range(len(top3_end)):
                                dist = get_osrm_distance(
                                    end_lat, 
                                    end_lon, 
                                    top3_end.iloc[i]['lat'], 
                                    top3_end.iloc[i]['lng'], 
                                    "foot"
                                )
                                end_dist.append(dist)

                            end_data = pd.DataFrame({
                                "站點名稱": top3_end["name_tw"],
                                "距離(m)": [dist * 1000 for dist in end_dist],
                                "可還空位": top3_end["empty_spaces"],
                                "綜合評分": [f"{score*100:.2f}" for score in top3_end["final_score"]]
                            })

                            st.dataframe(
                                end_data,
                                use_container_width=True, 
                                hide_index=True
                            )

                    
                else:
                    st.error("無法計算路徑。")
            except Exception as e:
                st.error(f"路徑繪製失敗: {e}")
else:
    st.info("請先選擇起點與終點後按下「計算路徑」按鈕以進行計算。")
