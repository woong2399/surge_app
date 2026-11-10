"""거래대금 — 날짜별 거래대금 상위 30을 테마로 묶어 보여 준다. 테마·대장(leader)·이유는 시트에 직접 적는다."""
import html
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.need_token()

NO_THEME = "테마 미입력"
WD = "월화수목금토일"

dates = db.volume_dates()
if not dates:
    ui.setup("거래대금 상위")
    st.info("아직 올라온 날짜가 없습니다. 시트 거래대금상위 탭이 채워지면 여기에 나옵니다.")
    st.stop()

c1, c2 = st.columns([1, 1.4])
day = c1.selectbox("날짜", dates, label_visibility="collapsed", key="vol_day")
q = c2.text_input("검색", placeholder="🔍 종목·테마·이유 검색", label_visibility="collapsed", key="vol_q").strip().lower()

rows = db.volume_day(day)
if q:
    rows = [r for r in rows if q in f"{r['name']} {r['code']} {r['theme']} {r['reason']}".lower()]

# 테마 묶음: 테마를 여러 개 쓴 종목은 묶음마다 나오고, 맨 위 합계에서는 한 번만 센다.
groups = {}
for r in rows:
    for t in db.split_themes(r["theme"]) or [NO_THEME]:
        groups.setdefault(t, []).append(r)


def total(rs):
    return sum(r["amount"] or 0 for r in rs) if any(r["amount"] is not None for r in rs) else None


order = sorted(groups, key=lambda t: (t == NO_THEME, -(total(groups[t]) or 0)))

d = datetime.strptime(day, "%Y-%m-%d")
ui.setup(f"{d.month}월 {d.day}일 {WD[d.weekday()]}요일",
         f"상위 {len(rows)}종목 · 합계 {ui.eok_text(total(rows))} · 테마 합계 큰 순")
if not rows:
    st.markdown("<div class='empty'>조건에 맞는 종목이 없습니다.</div>", unsafe_allow_html=True)

for t in order:
    rs = sorted(groups[t], key=lambda r: (not r["leader"], -(r["amount"] or 0), r["rank"] or 999))
    st.markdown(
        f"<div class='grp'><div class='gt'>{html.escape(t)}</div>"
        f"<div class='gs'>{len(rs)}종목 · 합계 {ui.eok_text(total(rs))}</div></div>",
        unsafe_allow_html=True,
    )
    for r in rs:
        meta = [f"{r['rank']:.0f}위" if r["rank"] is not None else "-위", f"거래대금 {ui.eok_text(r['amount'])}"]
        if ui.cap_text(r):
            meta.append(ui.cap_text(r))
        if r["in_diary"]:
            meta.append("일지 ✓")
        flow = ui.flow_line(r)
        ui.card(
            ("👑 " if r["leader"] else "") + r["name"], code=r["code"], pct=r["pct"], meta=" · ".join(meta),
            meta2=flow.split(" · ", 1)[1] if flow else "",  # 순위는 위 줄에 있으니 뺀다
            themes=[x for x in db.split_themes(r["theme"]) if x != t],
            text=r["reason"], href=f"stocks?code={r['code']}",
        )
