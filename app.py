"""Surge 종목 창고 — 이슈 / 종목 / 테마 / 리포트 네 장. 화면 코드는 views/ 에 있다."""
import streamlit as st

st.set_page_config(page_title="Surge 종목 창고", layout="centered")

pg = st.navigation([
    st.Page("views/issues.py", title="이슈", default=True),
    st.Page("views/stocks.py", title="종목"),
    st.Page("views/themes.py", title="테마"),
    st.Page("views/report.py", title="리포트"),
])
pg.run()
