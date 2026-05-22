import streamlit as st
import pandas as pd
import sqlite3
import requests
import pydeck as pdk
import altair as alt

st.set_page_config(page_title="全台 YouBike 即時監控", layout="wide")

@st.cache_data
def get_stations():
    conn = sqlite3.connect('stations.db')
    df = pd.read_sql("SELECT * FROM stations", conn)
    conn.close()
    # 假設你需要將 district_tw 對應到縣市，這裡為了範例簡化
    # 如果 stations.db 沒有縣市欄位，可以手動建立一個簡易對照表
    return df

def get_realtime_info_batch(station_nos):
    """改為 POST 請求，符合 API 規範"""
    url = "https://apis.youbike.com.tw/tw2/parkingInfo"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://youbike.com.tw/",
    }
    
    all_data = []
    chunk_size = 20
    for i in range(0, len(station_nos), chunk_size):
        chunk = station_nos[i:i + chunk_size]
        # POST 的參數應該放在 'data' 或 'json' 中
        payload = {'station_no[]': chunk}
        try:
            # 關鍵：改用 requests.post
            response = requests.post(url, data=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['retCode'] == 1:
                    all_data.extend(data['retVal']['data'])
            else:
                print(f"請求失敗，狀態碼: {response.status_code}")
                # 印出回應內容以便除錯
                print(response.text)
        except Exception as e:
            print(f"API 連線錯誤: {e}")
            
    return all_data

st.title("🚲 全台 YouBike 2.0 即時查詢系統")

CITY_MAP = {
    "01": "臺北市", "02": "新北市", "03": "桃園市", "05": "新竹縣",
    "04": "新竹市", "82": "新竹科學園區", "07": "苗栗縣", "06": "臺中市",
    "11": "嘉義縣", "10": "嘉義市", "13": "臺南市", "12": "高雄市",
    "14": "屏東縣", "15": "臺東縣", "16": "光復鄉"
}

stations_df = get_stations()
stations_df['city_name'] = stations_df['area_code_2'].map(CITY_MAP)

# --- 二階聯動選單 ---
# 1. 縣市 (這裡假設 stations.db 有縣市資訊，若無請用 district_tw 代替或手動分組)
selected_city = st.sidebar.selectbox("請選擇縣市", list(CITY_MAP.values())) # 範例

city_code = [k for k, v in CITY_MAP.items() if v == selected_city][0]
target_stations = stations_df[stations_df['area_code_2'] == city_code]

selected_dist = st.sidebar.selectbox("請選擇行政區", sorted(target_stations['district_tw'].unique()))
target_stations = target_stations[target_stations['district_tw'] == selected_dist]

# --- 2. 欄位中文化對應字典 ---
column_mapping = {
    'sna_clean': '站點名稱',
    'Quantity': '總車數',
    'available_rent_bikes': '可借車數',
    'mday': '更新時間'
}

if st.sidebar.button("查詢該區即時資訊"):
    with st.spinner(f'正在查詢 {selected_dist} 的站點資訊...'):
        realtime_list = []
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
            st.write("目前表格的欄位:", df.columns.tolist())
            
            # 地圖顯示
            # 地圖顯示修正版：直接從 target_stations 獲取經緯度，確保不依賴 API 回傳的欄位
            # 1. 確保經緯度已經是 float 型態 (在 merge 之後執行)
            df['lat'] = df['lat'].astype(float)
            df['lng'] = df['lng'].astype(float)

            # 2. 地圖顯示區塊修正
            st.subheader(f"{selected_dist} 站點分佈")
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(
                    latitude=df['lat'].mean(), 
                    longitude=df['lng'].mean(), 
                    zoom=14
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
                tooltip={"text": "站點: {name_tw}\n可借車數: {available_spaces}"}
            ))

            # 橫向長條圖
            st.subheader("前 10 名可借站點")
            chart_data = df.nlargest(10, 'available_spaces')[['name_tw', 'available_spaces']]
            chart = alt.Chart(chart_data).mark_bar(color='#76C8FF').encode(
                x=alt.X('available_spaces', title='可借車數'),
                y=alt.Y('name_tw', title='站點名稱', sort='-x', axis=alt.Axis(labelLimit=300))
            ).properties(height=400)
            st.altair_chart(chart.configure_axis(titleAngle=0), width='stretch')

            # 表格顯示 (使用中文化設定)
            st.subheader("原始資料明細")
            st.dataframe(df[['name_tw', 'available_spaces', 'empty_spaces']].rename(columns={
                'name_tw': '站點名稱', 'available_spaces': '可借車數', 'empty_spaces': '空位數'
            }), column_config={"站點名稱": st.column_config.TextColumn(width="large")}, hide_index=True)
        else:
            st.error(f"在 {selected_dist} 找不到即時資料，請確認該區是否為 YouBike 2.0 營運範圍。")
