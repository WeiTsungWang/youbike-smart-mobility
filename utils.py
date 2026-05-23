import pandas as pd
import sqlite3

def get_station_data():
    conn = sqlite3.connect('stations.db')
    df = pd.read_sql("SELECT * FROM stations", conn)
    conn.close()
    return df