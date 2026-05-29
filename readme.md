# 🚲 全台 YouBike 2.0 智慧出行系統

本系統為個人開發之 YouBike 2.0 智慧查詢與路線規劃工具。透過整合開放數據與地理資訊引擎，提供使用者即時站點狀態查詢、天氣防護建議，以及包含熱量估算的動態路線規劃服務。

## 🚀 系統功能
- **即時站點查詢**：支援依行政區篩選，或透過站點名稱搜尋，即時顯示可借/可還車輛。
- **動態路徑規劃**：整合 OSRM 路由引擎，提供步行、自備單車、YouBike 三種模式規劃。
- **熱量估算**：依據使用者體重、距離與交通方式，即時計算運動消耗卡路里。
- **氣象整合**：自動偵測查詢地區之即時天氣狀態與降雨機率，提供出行建議。
- **視覺化地圖**：利用 PyDeck 繪製動態路徑與站點分佈，提供最佳視覺化體驗。

## 🛠 安裝與執行說明

請確保您的電腦已安裝 **Anaconda** 環境。

### 1. 開啟終端機
請開啟 `Anaconda Prompt`，並切換至本專案目錄：
```bash
cd [本專案資料夾]
```
例如
```bash
cd C:\Users\Jason\Desktop\Big-Data-Final
```

### 2. 安裝必要套件

執行以下指令，系統將自動安裝所有依賴套件：

```bash
pip install -r requirements.txt
```

*(若遇到執行原則錯誤，請先執行：`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`)*

### 3. 啟動系統

執行以下指令即可開啟瀏覽器操作介面：

```bash
streamlit run 0_首頁.py
```

## 📂 專案結構

* `0_首頁.py`: 主程式入口。
* `pages/`: 包含各功能分頁 (路線規劃、即時查詢)。
* `utils.py`: 封裝 API 請求邏輯 (OSRM, Weather, YouBike API)。
* `data_collector.py`: 資料庫初始化與站點資料爬蟲腳本。
* `requirements.txt`: 專案相依套件清單。

## 💡 技術棧

* **Frontend/Framework**: Streamlit
* **Data Visualization**: PyDeck, Altair
* **Routing Engine**: OSRM API
* **Data Processing**: Pandas, NumPy
* **Weather API**: Open-Meteo

---

*Developed by Wang Wei-Tsung (Jason) - NTUST CSIE B11330046*