"""테마 — 맨 위 목록에서 테마를 고르면 그 테마의 종목이 나온다(일지·거래대금·관심종목의 테마). 보기만 한다. 검색은 목록을 좁힌다.
테마는 종목 화면의 ✏️ 수정에서 적는다."""
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
    st.info("아직 입력된 테마가 없습니다. 종목 화면에서 테마를 적으면 여기에 나옵니다.")
    st.stop()

if st.query_params.get("theme") in themes:  # 종목 화면에서 돌아왔으면 보던 테마로
    st.session_state["theme_pick"] = st.query_params["theme"]
    st.session_state["theme_q"] = ""
st.query_params.pop("theme", None)
c1, c2 = st.columns([1, 1.4])
q = c2.text_input("검색", placeholder="🔍 테마 검색", label_visibility="collapsed", key="theme_q").strip().lower()
shown = [t for t in themes if q in t.lower()]
theme = c1.selectbox("테마", shown, label_visibility="collapsed", key="theme_pick") if shown else None

if not theme:
    ui.setup("테마", "찾는 테마가 없습니다." if q else None)
    st.stop()

events = db.theme_events(theme)
by = {}  # 종목 코드 → 그 테마로 나온 날짜들 (종목마다 카드는 한 장)
for e in events:
    by.setdefault(e["code"], []).append(e)
cards = []
for code, evs in by.items():
    last = max(evs, key=lambda e: e["date"])  # 날짜 없는 줄(관심종목에만 있는 것)은 가장 뒤
    dated = {e["date"] for e in evs if e["date"]}  # 두 시트에 같은 날이 있어도 하루로
    cards.append((last["date"], last["pct"] or 0, code, last, len(dated)))
cards.sort(key=lambda c: (c[0], c[1]), reverse=True)

ui.setup(theme, f"종목 {len(cards)}개 · 최근에 나온 순")
if not cards:
    st.markdown("<div class='empty'>이 테마를 쓰는 종목이 아직 없습니다.</div>", unsafe_allow_html=True)

for date_, pct_, code, last, n in cards:
    card = db.stock_card(code)
    if date_:
        pct, meta = last["pct"], f"최근 {date_[5:]} · 이 테마로 {n}일 나옴"
    else:  # 관심종목에만 있는 종목: 이 테마로 나온 날은 없다. 다른 이유로 나온 최근 기록이 있으면 같이 보여 준다.
        rec = db.latest_record(code)
        row = (rec["hist"] or rec["vol"]) if rec else None
        pct = row["pct"] if row else None
        meta = "관심종목" + (f" · 최근 기록 {rec['date'][5:]}" if rec else " · 아직 일지·거래대금에 나온 적 없음")
    ui.card(
        last["name"], code=code, pct=pct, meta=meta,
        tag=last.get("grp") == "telegram", themes=card["themes"],
        text=card["comment"] and f"📝 {card['comment']}" or card["info"], href=f"stocks?code={code}&from=themes&theme={theme}",
    )
