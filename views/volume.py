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
    import edit
    if edit.read_values("거래대금상위") is None:  # 왜 비었는지 다시 읽어 보고 원인을 보여 준다
        st.caption(f"amount 시트 읽기 오류: {edit.last_error}")
    else:
        st.caption("서비스 계정으로는 읽힙니다. 잠시 뒤(1분) 새로 고침해 보세요.")
        st.cache_data.clear()
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

if st.toggle("✏️ 테마·이슈 입력", key="vol_edit"):
    import edit
    if not edit.unlocked():
        st.stop()
    # 옵시디언 날짜 노트와 같은 순서: 전 거래일 상위 30에 없던 종목(신규 진입) 먼저, 등락률 없는 종목(신규 상장) 맨 위
    all_rows = db.volume_day(day)
    older = [x for x in dates if x < day]
    prev_codes = {r["code"] for r in db.volume_day(older[0])} if older else set()
    order = lambda r: (r["pct"] is not None, -(r["pct"] or 0))
    new = sorted([r for r in all_rows if r["code"] not in prev_codes], key=order)
    cont = sorted([r for r in all_rows if r["code"] in prev_codes], key=order)
    def item(r):
        pct = "신규" if r["pct"] is None else f"{r['pct']:+.2f}%"
        return {"id": (day, r["code"]), "title": f"{r['name']} · {pct}",
                "fields": [("theme", "테마 (쉼표로 여러 개)", r["theme"]), ("reason", "이슈", r["reason"])]}
    edit.form(f"vol_form_{day}",
              [(f"신규 진입 · {len(new)}종목", [item(r) for r in new]),
               (f"이어서 든 종목 · {len(cont)}종목", [item(r) for r in cont])],
              lambda ch: edit.save(amount_edits=ch))
    st.caption("같은 종목의 다른 날짜와 일지(이력)의 같은 날 빈 테마 칸도 같이 채워집니다. 옵시디언 노트에는 이 컴퓨터에서 동기화가 돌 때 들어갑니다.")
    st.stop()
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
