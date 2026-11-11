"""관심종목 — 공부하고 싶은 종목을 종목명만으로 넣어 두고, 카드마다 한줄평을 적는다. 일지·거래대금에 나온 종목이면 최근 기록이 같이 보인다."""
import sys
from pathlib import Path
from urllib.parse import quote

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.need_token()

items = db.manual_stocks()  # 최근에 넣은 종목이 앞
ui.setup("관심종목", f"{len(items)}종목 · 최근에 넣은 순" if items else "공부하고 싶은 종목을 넣어 두는 곳")

if st.toggle("✏️ 입력 (추가·한줄평)", key="fav_edit"):
    import edit
    if edit.unlocked():
        if st.session_state.get("fav_msg"):  # 추가·빼기 뒤 화면을 새로 그리면서 남긴 안내
            st.success(st.session_state.pop("fav_msg"))
        with st.form("fav_add"):
            names = st.text_input("종목 추가", key="fav_add_names", placeholder="종목명 (쉼표로 여러 개, 코드는 안 적어도 됩니다)")
            st.caption("종목명은 정확히 적어야 일지·거래대금의 같은 종목과 합쳐집니다.")
            add = st.form_submit_button("추가", type="primary", use_container_width=True)
        if add:
            try:
                n_new, _ = edit.add_to_interest(names.split(","))
                if n_new:
                    st.session_state["fav_msg"] = f"추가했습니다 · 새 종목 {n_new}개"
                    st.rerun()  # 아래 한줄평·빼기 목록에 방금 넣은 종목이 바로 나오게
                st.info("넣을 종목명이 없거나 이미 있는 종목입니다.")
            except Exception as e:
                st.error(f"추가하지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
        if items:
            edit.form("fav_comments", [("한줄평", [
                {"id": m["name"], "title": m["name"], "fields": [("comment", "📝 한줄평", m["comment"])]} for m in items])],
                lambda ch: sum(bool(edit.save_manual(n, comment=f["comment"])) for n, f in ch.items()))
            with st.form("fav_del"):
                out = st.multiselect("관심종목에서 빼기", [m["name"] for m in items], key="fav_del_names")
                rm = st.form_submit_button("빼기", use_container_width=True)
            if rm and out:
                try:
                    st.session_state["fav_msg"] = f"뺐습니다 · {sum(bool(edit.remove_manual(n)) for n in out)}개"
                except Exception as e:
                    st.error(f"빼지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
                else:
                    st.session_state.pop("fav_del_names", None)  # 빠진 종목이 선택으로 남아 오류가 나지 않게
                    st.rerun()
    st.stop()

if not items:
    st.markdown("<div class='empty'>아직 없습니다. ✏️ 입력을 켜서 종목명을 넣어 보세요. "
                "종목 화면에서 ⭐ 관심종목에 추가를 눌러도 됩니다.</div>", unsafe_allow_html=True)

for m in items:
    code = db.manual_code(m["name"])
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
        m["name"], code="" if code.startswith("@") else code, pct=row["pct"] if row else None, meta=meta,
        themes=card["themes"], text=f"📝 {m['comment']}" if m["comment"] else "", href=f"stocks?code={quote(code)}",
    )
