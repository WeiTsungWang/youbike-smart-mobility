import requests
import sqlite3
import pandas as pd

# 全台站點 API
STATION_URL = "https://apis.youbike.com.tw/json/station-min-yb2.json"

def fetch_and_save_stations():
    """抓取全台站點清單並存入 SQLite"""
    try:
        print("正在從 API 抓取全台站點清單...")
        response = requests.get(STATION_URL)
        response.raise_for_status()
        stations = response.json()
        
        # 轉換成 DataFrame
        df = pd.DataFrame(stations)
        
        # 選取我們要的欄位
        # station_no: 站點ID, name_tw: 站點名稱, district_tw: 行政區, lat/lng: 經緯度, area_code_2: 縣市代碼, address_tw: 地址
        df_clean = df[['station_no', 'name_tw', 'district_tw', 'lat', 'lng', 'area_code_2', 'address_tw']]

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, 'stations.db')
        
        # 存入 stations.db
        conn = sqlite3.connect(DB_PATH)
        df_clean.to_sql('stations', conn, if_exists='replace', index=False)
        conn.close()
        
        print(f"成功儲存 {len(df_clean)} 個站點至 stations.db")
        
    except Exception as e:
        print(f"發生錯誤: {e}")

if __name__ == "__main__":
    fetch_and_save_stations()
