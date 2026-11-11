"""일지(Surge 종목 창고) — 이슈 / 거래대금 / 종목 / 테마 / 관심종목 다섯 장. 화면 코드는 views/ 에 있다."""
import importlib

import streamlit as st

import db
import ui

# GitHub 에 새 코드를 올려도 서버가 예전 db·ui 모듈을 메모리에 들고 있으면 오류가 난다 → 매번 새로 읽는다.
importlib.reload(db)
importlib.reload(ui)
import edit  # noqa: E402
importlib.reload(edit)

st.set_page_config(page_title="Surge 종목 창고", layout="centered")

pg = st.navigation([
    st.Page("views/issues.py", title="이슈", default=True),
    st.Page("views/volume.py", title="거래대금"),
    st.Page("views/stocks.py", title="종목"),
    st.Page("views/themes.py", title="테마"),
    st.Page("views/interest.py", title="내 종목"),
])
pg.run()
