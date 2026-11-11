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
    last = max(evs, key=lambda e: e["date"])  # 날짜 없는 줄(관심종목에 직접 넣은 것)은 가장 뒤
    dated = {e["date"] for e in evs if e["date"]}  # 두 시트에 같은 날이 있어도 하루로
    cards.append((last["date"], last["pct"] or 0, code, last, len(dated)))
cards.sort(key=lambda c: (c[0], c[1]), reverse=True)

ui.setup(theme, f"종목 {len(cards)}개 · 최근에 나온 순")
if st.toggle("✏️ 입력", key="thm_edit"):
    import edit
    if edit.unlocked():
        edit.theme_box()
        if st.session_state.get("thm_msg"):
            st.success(st.session_state.pop("thm_msg"))
        if not db.universe():
            st.info("종목 목록(amount 시트 종목목록 탭)을 읽지 못했습니다. 컴퓨터에서 lists_sync.py 가 한 번 돌아야 합니다.")
        else:
            with st.form(f"thm_add_{theme}"):
                picked = edit.stock_picker("이 테마에 종목 추가 (DB 종목만)", "thm_pick")
                st.caption("추가한 종목은 관심종목에도 나옵니다.")
                add = st.form_submit_button("추가", type="primary", use_container_width=True)
            if add and picked:
                try:
                    n_new, n_th = edit.add_to_interest(picked, theme)
                    st.session_state["thm_msg"] = f"추가했습니다 · 새 종목 {n_new}개, 테마만 더한 종목 {n_th}개"
                    edit.reset_picker("thm_pick")
                    st.rerun()  # 아래 '빼기' 목록에 방금 넣은 종목이 바로 나오게
                except Exception as e:
                    if type(e).__name__ not in ("RerunException", "StopException"):
                        st.error(f"추가하지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
                    else:
                        raise
        mine = {m["code"]: m["name"] for m in db.manual_stocks() if theme in db.split_themes(m["theme"])}
        if mine:
            with st.form(f"thm_del_{theme}"):
                out = st.multiselect("이 테마에서 빼기 (직접 추가한 종목만)", list(mine), key=f"thm_del_names_{theme}",
                                     format_func=lambda c: f"{mine[c]}  {c}")
                st.caption("테마만 빠지고 종목은 관심종목에 남습니다. 관심종목에서 아예 빼려면 관심종목 화면에서 하세요.")
                rm = st.form_submit_button("빼기", use_container_width=True)
            if rm and out:
                try:
                    st.session_state["thm_msg"] = f"뺐습니다 · {edit.remove_theme(out, theme)}개"
                except Exception as e:
                    st.error(f"빼지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
                else:
                    st.session_state.pop(f"thm_del_names_{theme}", None)
                    st.rerun()
        with st.form(f"thm_rename_{theme}"):
            new = st.text_input("테마 이름 바꾸기", value=theme, key=f"thm_new_{theme}")
            st.caption("일지·거래대금·관심종목의 모든 칸과 테마목록에서 바뀝니다. 쉼표로 적으면 여러 테마로 나뉩니다 (예: 반도체, HBM).")
            go = st.form_submit_button("이름 바꾸기", use_container_width=True)
        if go:
            if not new.strip():
                st.error("이름을 비울 수는 없습니다. 칸 하나에서 빼려면 종목·이슈·거래대금 화면에서 그 칸의 테마를 빼세요.")
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
        if not cards:  # 쓰는 종목이 하나도 없는 테마(목록에만 있는 테마)는 지울 수 있다
            with st.form(f"thm_delete_{theme}"):
                st.caption("이 테마를 쓰는 종목이 없습니다. 테마목록에서 지울 수 있습니다.")
                dele = st.form_submit_button("이 테마 지우기", use_container_width=True)
            if dele:
                try:
                    edit.delete_theme(theme)
                    st.session_state["thm_msg"] = f"테마를 지웠습니다: {theme}"
                    st.session_state.pop("theme_pick", None)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    if type(e).__name__ not in ("RerunException", "StopException"):
                        st.error(f"지우지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
                    else:
                        raise
    st.stop()
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
