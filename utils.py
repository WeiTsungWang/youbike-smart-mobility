import math
import pandas as pd
import sqlite3
import requests

def get_station_data():
    conn = sqlite3.connect('stations.db')
    df = pd.read_sql("SELECT * FROM stations", conn)
    df['lat'] = pd.to_numeric(df['lat'])
    df['lng'] = pd.to_numeric(df['lng'])
    conn.close()
    return df

# utils.py
def get_weather_forecast(lat, lon):
    # 請確認 URL 包含 weather_code
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia/Taipei&forecast_days=7"
    try:
        response = requests.get(url, timeout=5).json()
        return response
    except:
        return None
    
def get_coords(address):
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
    headers = {'User-Agent': 'YouBikeApp/1.0'} # Nominatim 需要自訂 User-Agent
    try:
        res = requests.get(url, headers=headers).json()
        if res:
            return float(res[0]['lat']), float(res[0]['lon'])
    except:
        return None, None
    return None, None

def get_osrm_distance(lat1, lon1, lat2, lon2, profile):
    url = f"http://router.project-osrm.org/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}"
    res = requests.get(url).json()
    return res['routes'][0]['distance'] / 1000 # 回傳 km
