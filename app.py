import streamlit as st

pg = st.navigation([
    st.Page("pages/home.py", title="首頁", icon="🏠"),
    st.Page("pages/weather.py", title="天氣預報", icon="🌤️"),
    st.Page("pages/station_query.py", title="YouBike站點查詢", icon="🚲"),
    st.Page("pages/route_planner.py", title="路線規劃", icon="🗺️"),
])

pg.run()
