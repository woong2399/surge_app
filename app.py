"""1장 — 날짜별 종목과 이슈."""
import html
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.setup("날짜별 종목·이슈")
ui.need_token()


def _dates():
    return db.dates()


def _rows(day):
    return db.day_rows(day)


dates = _dates()
if not dates:
    st.info("아직 올라온 날짜가 없습니다.")
    st.stop()

c1, c2 = st.columns([1, 2])
day = c1.selectbox("날짜", dates)
q = c2.text_input("검색", placeholder="종목명·코드·이슈·테마").strip().lower()

rows = _rows(day)
if q:
    rows = [r for r in rows if q in f"{r['name']} {r['code']} {r['telegram']} {r['theme']}".lower()]

st.caption(f"{day} · {len(rows)}종목 · 등락률 큰 순")
if not rows:
    st.write("조건에 맞는 종목이 없습니다.")

for r in rows:
    tag = "<span class='tag'>텔레그램만</span>" if r["grp"] == "telegram" else ""
    st.markdown(
        f"<div class='it'><b>{html.escape(r['name'])}</b><small>{r['code']}</small> "
        f"{ui.pct_html(r['pct'])}<small>{ui.amount_text(r['amount_est'])}</small>{tag}</div>",
        unsafe_allow_html=True,
    )
    themes = db.split_themes(r["theme"])
    if themes:
        st.markdown(f"<div class='th'>{ui.chips(themes)}</div>", unsafe_allow_html=True)
    if r["telegram"]:
        st.markdown(f"<div class='sub'>{html.escape(r['telegram'])}</div>", unsafe_allow_html=True)
    if r["news"]:
        st.markdown(ui.news_html(r["news"]), unsafe_allow_html=True)
