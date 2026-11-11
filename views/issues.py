"""이슈 — 날짜별 종목과 이슈."""
import html
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.need_token()

dates = db.dates()
if not dates:
    st.info("아직 올라온 날짜가 없습니다.")
    st.stop()

WD = "월화수목금토일"
c1, c2 = st.columns([1, 1.4])
day = c1.selectbox("날짜", dates, label_visibility="collapsed")
q = c2.text_input("검색", placeholder="🔍 종목·테마·이슈 검색", label_visibility="collapsed").strip().lower()

d = datetime.strptime(day, "%Y-%m-%d")
rows = db.day_rows(day)
if q:
    rows = [r for r in rows if q in f"{r['name']} {r['code']} {r['telegram']} {r['theme']}".lower()]

ui.setup(f"{d.month}월 {d.day}일 {WD[d.weekday()]}요일", f"{len(rows)}종목 · 등락률 높은 순")
if st.toggle("✏️ 테마·이슈 입력", key="iss_edit"):
    import edit
    if edit.unlocked():
        edit.form(f"iss_form_{day}", [("", [
            {"id": (day, r["code"]), "title": f"{r['name']} · {r['pct']:+.2f}%",
             "fields": [("theme", "테마 (쉼표로 여러 개)", r["theme"]), ("telegram", "이슈", r["telegram"])]}
            for r in rows])], lambda ch: edit.save(hist_edits=ch))
        st.caption("같은 날 거래대금 상위에 같은 종목이 있고 그쪽 테마가 비어 있으면 같이 채워집니다.")
    st.stop()
if not rows:
    st.markdown("<div class='empty'>조건에 맞는 종목이 없습니다.</div>", unsafe_allow_html=True)

for r in rows:
    ui.card(
        r["name"], code=r["code"], pct=r["pct"], meta=ui.amount_text(r["amount_est"]),
        tag=r["grp"] == "telegram", themes=db.split_themes(r["theme"]),
        text=r["telegram"], news=r["news"], href=f"stocks?code={r['code']}", meta2=ui.flow_line(r),
    )
