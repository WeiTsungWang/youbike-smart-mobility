import pandas as pd
import sqlite3
import requests
from urllib.parse import quote

def get_station_data():
    conn = sqlite3.connect('stations.db')
    df = pd.read_sql("SELECT * FROM stations", conn)
    df['lat'] = pd.to_numeric(df['lat'])
    df['lng'] = pd.to_numeric(df['lng'])
    conn.close()
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

def get_weather_forecast(lat, lon):
    # 請確認 URL 包含 weather_code
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia/Taipei&forecast_days=7"
    try:
        response = requests.get(url, timeout=5).json()
        return response
    except:
        return None

def get_osrm_distance(lat1, lon1, lat2, lon2, profile):
    url = f"http://router.project-osrm.org/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}"
    res = requests.get(url).json()
    return res['routes'][0]['distance'] / 1000 # 回傳 km

def find_nearest_station(lat, lon, df):
    df['dist'] = ((df['lat'] - lat)**2 + (df['lng'] - lon)**2)
    return df.loc[df['dist'].idxmin()]
