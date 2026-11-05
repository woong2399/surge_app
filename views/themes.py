"""테마 — 맨 위 목록에서 테마를 고르면 그 테마의 종목과 날짜별 이슈가 나온다. 검색은 목록을 좁힌다."""
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

c1, c2 = st.columns([1, 1.4])
q = c2.text_input("검색", placeholder="🔍 테마 검색", label_visibility="collapsed", key="theme_q").strip().lower()
shown = [t for t in themes if q in t.lower()]
theme = c1.selectbox("테마", shown, label_visibility="collapsed", key="theme_pick") if shown else None

if not theme:
    ui.setup("테마", "찾는 테마가 없습니다." if q else None)
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
