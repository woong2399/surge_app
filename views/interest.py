"""관심종목 — 공부하고 싶은 종목을 DB 종목목록에서 골라 넣고, 카드마다 테마와 한줄평을 적는다. 카드를 누르면 그 종목 화면으로 간다."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.need_token()

items = db.manual_stocks()  # 최근에 넣은 종목이 앞
ui.setup("관심종목", f"{len(items)}종목 · 최근에 넣은 순" if items else "공부하고 싶은 종목을 넣어 두는 곳")

if st.toggle("✏️ 입력 (추가·테마·한줄평)", key="fav_edit"):
    import edit
    if edit.unlocked():
        edit.theme_box()
        if st.session_state.get("fav_msg"):  # 추가·빼기 뒤 화면을 새로 그리면서 남긴 안내
            st.success(st.session_state.pop("fav_msg"))
        if not db.universe():
            st.info("종목 목록(amount 시트 종목목록 탭)을 읽지 못했습니다. 컴퓨터에서 lists_sync.py 가 한 번 돌아야 합니다.")
        else:
            with st.form("fav_add"):
                picked = edit.stock_picker("종목 추가 (DB 종목만)", "fav_pick", exclude={m["code"] for m in items})
                add = st.form_submit_button("추가", type="primary", use_container_width=True)
            if add and picked:
                try:
                    n_new, _ = edit.add_to_interest(picked)
                    st.session_state["fav_msg"] = f"추가했습니다 · 새 종목 {n_new}개"
                    edit.reset_picker("fav_pick")
                    st.rerun()  # 아래 테마·한줄평·빼기 목록에 방금 넣은 종목이 바로 나오게
                except Exception as e:
                    if type(e).__name__ not in ("RerunException", "StopException"):
                        st.error(f"추가하지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
                    else:
                        raise
        if items:
            edit.form("fav_comments", [("테마와 한줄평", [
                {"id": m["code"], "title": f"{m['name']}  {m['code']}",
                 "fields": [("theme", "테마", m["theme"], "theme"), ("comment", "📝 한줄평", m["comment"])]}
                for m in items])],
                lambda ch: sum(bool(edit.save_manual(c, **f)) for c, f in ch.items()))
            names = {m["code"]: m["name"] for m in items}
            with st.form("fav_del"):
                out = st.multiselect("관심종목에서 빼기", list(names), key="fav_del_names",
                                     format_func=lambda c: f"{names[c]}  {c}")
                rm = st.form_submit_button("빼기", use_container_width=True)
            if rm and out:
                try:
                    st.session_state["fav_msg"] = f"뺐습니다 · {sum(bool(edit.remove_manual(c)) for c in out)}개"
                except Exception as e:
                    st.error(f"빼지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
                else:
                    st.session_state.pop("fav_del_names", None)  # 빠진 종목이 선택으로 남지 않게
                    st.rerun()
    st.stop()

if not items:
    st.markdown("<div class='empty'>아직 없습니다. ✏️ 입력을 켜서 종목을 골라 넣어 보세요. "
                "종목 화면에서 ⭐ 관심종목에 추가를 눌러도 됩니다.</div>", unsafe_allow_html=True)

for m in items:
    code = m["code"]
    card = db.stock_card(code)
    rec = db.latest_record(code)
    h, v = (rec["hist"], rec["vol"]) if rec else (None, None)
    row = h or v
    if rec:
        badges = (["🔺10%↑" if h["grp"] == "surge" else "텔레그램"] if h else []) + (
            [f"💰거래대금 {v['rank']:.0f}위" if v["rank"] is not None else "💰거래대금 상위"] if v else [])
        meta = " · ".join([f"최근 {rec['date'][5:]}"] + badges)
    else:
        meta = "아직 일지·거래대금에 나온 적 없음"
    ui.card(
        m["name"], code=code, pct=row["pct"] if row else None, meta=meta,
        themes=card["themes"], text=f"📝 {m['comment']}" if m["comment"] else "", href=f"stocks?code={code}",
    )
