"""테마 — 옆 목록에서 테마를 고르면 그 테마의 종목과 날짜별 이슈가 나온다."""
import html
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.need_token()

themes = db.all_themes()
if not themes:
    ui.setup("테마")
    st.info("아직 입력된 테마가 없습니다. 시트 이력 탭의 테마 열을 채우면 여기에 나옵니다.")
    st.stop()

with st.sidebar:
    q = st.text_input("테마 찾기", placeholder="테마 이름").strip().lower()
    shown = [t for t in themes if q in t.lower()]
    if not shown:
        st.caption("찾는 테마가 없습니다.")
    theme = st.radio("테마 목록", shown, label_visibility="collapsed") if shown else None

if not theme:
    ui.setup("테마", "옆 목록에서 테마를 고르세요. 폰에서는 왼쪽 위 » 를 누르면 목록이 열립니다.")
    st.stop()

events = db.theme_events(theme)
stocks = []
for e in events:
    if e["name"] not in stocks:
        stocks.append(e["name"])

ui.setup(theme, f"종목 {len(stocks)}개")
st.markdown("<div class='sec'>이 테마의 종목</div>", unsafe_allow_html=True)
st.markdown(ui.chips(stocks).replace("class='chips'", "class='chips' style='margin-top:0'"), unsafe_allow_html=True)

last = None
for e in events:
    if e["date"] != last:
        st.markdown(f"<div class='dh'>{e['date']}</div>", unsafe_allow_html=True)
        last = e["date"]
    ui.card(
        e["name"], code=e["code"], pct=e["pct"], tag=e["grp"] == "telegram",
        themes=[t for t in db.split_themes(e["theme"]) if t != theme],
        text=e["telegram"], news=e["news"],
    )
