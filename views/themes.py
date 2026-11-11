"""테마 — 맨 위 목록에서 테마를 고르면 그 테마의 종목이 나온다(일지·거래대금 두 시트의 테마). 검색은 목록을 좁힌다."""
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
by = {}  # 종목 코드 → 그 테마로 나온 날짜들 (종목마다 카드는 한 장)
for e in events:
    by.setdefault(e["code"], []).append(e)
cards = []
for code, evs in by.items():
    last = max(evs, key=lambda e: e["date"])
    cards.append((last["date"], last["pct"] or 0, code, last, len({e["date"] for e in evs})))  # 두 시트에 같은 날이 있어도 하루로
cards.sort(key=lambda c: (c[0], c[1]), reverse=True)

ui.setup(theme, f"종목 {len(cards)}개 · 최근에 나온 순")
if st.toggle("✏️ 입력", key="thm_edit"):
    import edit
    if edit.unlocked():
        with st.form(f"thm_rename_{theme}"):
            new = st.text_input("테마 이름 바꾸기", value=theme, key=f"thm_new_{theme}")
            st.caption("일지·거래대금 두 시트의 모든 칸에서 바뀝니다. 쉼표로 적으면 여러 테마로 나뉩니다 (예: 반도체, HBM).")
            go = st.form_submit_button("이름 바꾸기", use_container_width=True)
        if go:
            if not new.strip():
                st.error("이름을 비울 수는 없습니다. 칸 하나에서 빼려면 그 날짜 칸에 null 을 적으세요.")
            elif " ".join(new.split()) == theme:
                st.info("이름이 그대로입니다.")
            else:
                try:
                    st.success(f"바꿨습니다 · 바뀐 칸 {edit.rename_theme(theme, new)}개. 테마 목록에서 새 이름을 고르세요.")
                except Exception as e:
                    st.error(f"바꾸지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
        notes = db.amount_notes()
        edit.form(f"thm_memo_{theme}", [("종목 이슈 (종목 화면의 종목 이슈와 같은 칸)", [
            {"id": code, "title": last["name"], "fields": [("memo", "종목 이슈", notes[code]["memo"])]}
            for _, _, code, last, _ in cards if code in notes])],
            lambda ch: sum(bool(edit.save_memo(c, f["memo"])) for c, f in ch.items()))
    st.stop()
st.markdown("<div class='sec'>이 테마의 종목</div>", unsafe_allow_html=True)
for date_, pct_, code, last, n in cards:
    card = db.stock_card(code)
    ui.card(
        last["name"], code=code, pct=last["pct"], meta=f"최근 {date_[5:]} · 이 테마로 {n}일 나옴",
        tag=last.get("grp") == "telegram", themes=[t for t in card["themes"] if t != theme],
        text=card["info"], href=f"stocks?code={code}",
    )
