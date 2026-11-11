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

goto = st.session_state.pop("thm_goto", None)  # 이름을 바꾼 뒤엔 새 이름, 지운 뒤엔 처음 상태로
if goto is not None:
    st.session_state.pop("theme_pick", None)
    st.session_state.pop("theme_q", None)
    if goto:
        st.session_state["theme_pick"] = goto

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
    last = max(evs, key=lambda e: e["date"])  # 날짜 없는 줄(관심종목에 직접 넣은 것)은 가장 뒤
    dated = {e["date"] for e in evs if e["date"]}  # 두 시트에 같은 날이 있어도 하루로
    cards.append((last["date"], last["pct"] or 0, code, last, len(dated)))
cards.sort(key=lambda c: (c[0], c[1]), reverse=True)

ui.setup(theme, f"종목 {len(cards)}개 · 최근에 나온 순")
if st.session_state.get("thm_msg"):  # 이름 바꾸기·지우기 뒤 화면을 새로 그리면서 남긴 안내
    st.success(st.session_state.pop("thm_msg"))

editing = False
if st.toggle("✏️ 수정 (종목 추가·테마 관리)", key="thm_edit"):
    import edit
    editing = edit.unlocked()
    if editing:
        edit.pick_stock("thm_pick", theme=theme, label=f"➕ {theme} 에 종목 추가")
        edit.theme_box()
        with st.expander("⚙️ 이 테마 관리 (이름 바꾸기·지우기·종목 이슈)"):
            with st.form(f"thm_rename_{theme}"):
                new = st.text_input("테마 이름 바꾸기", value=theme, key=f"thm_new_{theme}")
                st.caption("일지·거래대금·관심종목의 모든 칸과 테마목록에서 바뀝니다. 쉼표로 적으면 여러 테마로 나뉩니다 (예: 반도체, HBM).")
                go = st.form_submit_button("이름 바꾸기", use_container_width=True)
            if go:
                if not new.strip():
                    st.error("이름을 비울 수는 없습니다.")
                elif " ".join(new.split()) == theme:
                    st.info("이름이 그대로입니다.")
                else:
                    try:
                        n = edit.rename_theme(theme, new)
                        st.session_state["thm_msg"] = f"바꿨습니다 · 바뀐 칸 {n}개"
                        st.session_state["thm_goto"] = db.split_themes(new)[0]
                        st.rerun()
                    except Exception as e:
                        if type(e).__name__ not in ("RerunException", "StopException"):
                            st.error(f"바꾸지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
                        else:
                            raise
            if not cards:  # 쓰는 종목이 하나도 없는 테마(목록에만 있는 테마)는 지울 수 있다
                with st.form(f"thm_delete_{theme}"):
                    st.caption("이 테마를 쓰는 종목이 없습니다. 테마목록에서 지울 수 있습니다.")
                    dele = st.form_submit_button("이 테마 지우기", use_container_width=True)
                if dele:
                    try:
                        edit.delete_theme(theme)
                        st.session_state["thm_msg"] = f"테마를 지웠습니다: {theme}"
                        st.session_state["thm_goto"] = ""
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        if type(e).__name__ not in ("RerunException", "StopException"):
                            st.error(f"지우지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
                        else:
                            raise
            notes = db.amount_notes()
            edit.form(f"thm_memo_{theme}", [("종목 이슈 (종목 화면의 종목 이슈와 같은 칸)", [
                {"id": code, "title": last["name"], "fields": [("memo", "종목 이슈", notes[code]["memo"])]}
                for _, _, code, last, _ in cards if code in notes])],
                lambda ch: sum(bool(edit.save_memo(c, f["memo"])) for c, f in ch.items()))


def _drop(code):
    """이 테마에서 빼기(관심종목에 직접 넣은 종목만). 종목은 관심종목에 남는다."""
    import edit
    try:
        edit.remove_theme([code], theme)
        st.toast("이 테마에서 뺐습니다", icon="✅")
    except Exception as e:
        st.toast(f"빼지 못했습니다: {str(e)[:100]}", icon="⚠️")


st.markdown("<div class='sec'>이 테마의 종목</div>", unsafe_allow_html=True)
for date_, pct_, code, last, n in cards:
    card = db.stock_card(code)
    if date_:
        pct, meta = last["pct"], f"최근 {date_[5:]} · 이 테마로 {n}일 나옴"
    else:  # 관심종목에 직접 넣은 종목: 이 테마로 나온 날은 없다. 다른 이유로 나온 최근 기록이 있으면 같이 보여 준다.
        rec = db.latest_record(code)
        row = (rec["hist"] or rec["vol"]) if rec else None
        pct = row["pct"] if row else None
        meta = "관심종목에서 추가" + (f" · 최근 기록 {rec['date'][5:]}" if rec else " · 아직 일지·거래대금에 나온 적 없음")
    ui.card(
        last["name"], code=code, pct=pct, meta=meta,
        tag=last.get("grp") == "telegram", themes=card["themes"],
        text=card["comment"] and f"📝 {card['comment']}" or card["info"], href=f"stocks?code={code}",
    )
    if editing and not date_:  # 직접 넣은 종목만 이 테마에서 뺄 수 있다
        st.button("이 테마에서 빼기", key=f"thm_rm_{code}", on_click=_drop, args=(code,))
