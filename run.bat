@echo off
echo 正在為您檢查環境...
conda env create -f environment.yml -n youbike_app
echo 正在啟動應用程式...
call conda activate youbike_app
streamlit run 0_首頁.py
pause