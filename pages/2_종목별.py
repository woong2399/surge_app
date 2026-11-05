"""2장 — 종목별 화면: 테마, 종목 정보·메모, 관련 이슈."""
import html
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.setup("종목별")
ui.need_token()


def _stocks():
    return db.stocks()


def _card(code):
    return db.stock_card(code)


def _events(code):
    return db.stock_events(code)


stocks = _stocks()
if not stocks:
    st.info("아직 올라온 종목이 없습니다.")
    st.stop()

labels = {f"{s['name']} ({s['code']})": s["code"] for s in stocks}
choice = st.selectbox("종목 (이름이나 코드를 입력해 찾기)", list(labels), index=None, placeholder="종목 선택")
if not choice:
    st.stop()
code = labels[choice]
name = choice.rsplit(" (", 1)[0]

card = _card(code)
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
for e in _events(code):
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
