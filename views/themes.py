"""테마 — 옆 목록에서 테마를 고르면 그 테마의 종목과 날짜별 이슈가 나온다."""
import html
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.setup("테마")
ui.need_token()

themes = db.all_themes()
if not themes:
    st.info("아직 입력된 테마가 없습니다. 시트 이력 탭의 테마 열을 채우면 여기에 나옵니다.")
    st.stop()

with st.sidebar:
    q = st.text_input("테마 찾기", placeholder="테마 이름").strip().lower()
    shown = [t for t in themes if q in t.lower()]
    if not shown:
        st.caption("찾는 테마가 없습니다.")
    theme = st.radio("테마 목록", shown, label_visibility="collapsed") if shown else None

if not theme:
    st.write("옆 목록에서 테마를 고르세요. 폰에서는 왼쪽 위 `>>` 를 누르면 목록이 열립니다.")
    st.stop()

events = db.theme_events(theme)
stocks = []
for e in events:
    if e["name"] not in stocks:
        stocks.append(e["name"])

st.subheader(theme)
st.markdown("**종목**")
st.markdown("".join(f"<span class='chip'>{html.escape(s)}</span>" for s in stocks), unsafe_allow_html=True)

st.markdown("**날짜별 이슈** (최신순)")
last = None
for e in events:
    if e["date"] != last:
        st.markdown(f"<h2>{e['date']}</h2>", unsafe_allow_html=True)
        last = e["date"]
    tag = "<span class='tag'>텔레그램만</span>" if e["grp"] == "telegram" else ""
    st.markdown(
        f"<div class='it'><b>{html.escape(e['name'])}</b><small>{e['code']}</small> "
        f"{ui.pct_html(e['pct'])}{tag}</div>",
        unsafe_allow_html=True,
    )
    others = [t for t in db.split_themes(e["theme"]) if t != theme]
    if others:
        st.markdown(f"<div class='th'>{ui.chips(others)}</div>", unsafe_allow_html=True)
    if e["telegram"]:
        st.markdown(f"<div class='sub'>{html.escape(e['telegram'])}</div>", unsafe_allow_html=True)
    if e["news"]:
        st.markdown(ui.news_html(e["news"]), unsafe_allow_html=True)
