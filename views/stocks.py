"""종목 — 옆 목록에서 종목을 고르면 테마, 종목 정보, 메모, 관련 이슈가 나온다."""
import html
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.setup("종목")
ui.need_token()

stocks = db.stocks()
if not stocks:
    st.info("아직 올라온 종목이 없습니다.")
    st.stop()

with st.sidebar:
    q = st.text_input("종목 찾기", placeholder="이름·코드").strip().lower()
    shown = [s for s in stocks if q in f"{s['name']} {s['code']}".lower()]
    labels = {f"{s['name']}  {s['code']}": s for s in shown}
    if not labels:
        st.caption("찾는 종목이 없습니다.")
    choice = st.radio("종목 목록", list(labels), label_visibility="collapsed") if labels else None

if not choice:
    st.write("옆 목록에서 종목을 고르세요. 폰에서는 왼쪽 위 `>>` 를 누르면 목록이 열립니다.")
    st.stop()

code, name = labels[choice]["code"], labels[choice]["name"]
card = db.stock_card(code)
st.subheader(name)
st.caption(code)

st.markdown("**테마**")
if card["themes"]:
    st.markdown(f"<div>{ui.chips(card['themes'])}</div>", unsafe_allow_html=True)
else:
    st.write("아직 입력된 테마가 없습니다.")

st.markdown("**종목 정보**")
if card["info"]:
    st.markdown(f"<div class='box'>{html.escape(card['info'])}</div>", unsafe_allow_html=True)
else:
    st.write("아직 입력된 정보가 없습니다.")

if card["memo"]:
    st.markdown("**메모**")
    st.markdown(f"<div class='box'>{html.escape(card['memo'])}</div>", unsafe_allow_html=True)

st.markdown("**관련 이슈** (최신순)")
for e in db.stock_events(code):
    tag = "<span class='tag'>텔레그램만</span>" if e["grp"] == "telegram" else ""
    st.markdown(
        f"<div class='it'><b>{e['date']}</b> {ui.pct_html(e['pct'])}"
        f"<small>{ui.amount_text(e['amount_est'])}</small>{tag}</div>",
        unsafe_allow_html=True,
    )
    themes = db.split_themes(e["theme"])
    if themes:
        st.markdown(f"<div class='th'>{ui.chips(themes)}</div>", unsafe_allow_html=True)
    if e["telegram"]:
        st.markdown(f"<div class='sub'>{html.escape(e['telegram'])}</div>", unsafe_allow_html=True)
    if e["news"]:
        st.markdown(ui.news_html(e["news"]), unsafe_allow_html=True)
