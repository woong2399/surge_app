"""관심종목 — 공부하고 싶은 종목을 DB 종목목록에서 골라 넣고, 카드마다 테마와 한줄평을 적는다. 카드를 누르면 그 종목 화면으로 간다.
수정 모드에서는 고르거나 쓰고 Enter 만 하면 바로 저장된다(저장 버튼 없음)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.need_token()

items = db.manual_stocks()  # 최근에 넣은 종목이 앞
ui.setup("관심종목", f"{len(items)}종목 · 최근에 넣은 순" if items else "공부하고 싶은 종목을 넣어 두는 곳")

editing = False
if st.toggle("✏️ 수정 (종목 추가·테마·한줄평)", key="fav_edit"):
    import edit
    editing = edit.unlocked()
    if editing:
        edit.pick_stock("fav_pick")
        edit.theme_box()


def _do(fn, *a, ok="저장했습니다"):
    """바로 저장하는 동작. 결과는 말풍선(toast)으로 알린다."""
    import edit
    try:
        fn(*a)
        st.toast(ok, icon="✅")
    except Exception as e:
        st.toast(f"저장하지 못했습니다: {str(e)[:100]}", icon="⚠️")


def _save_theme(code, k):
    import edit
    _do(lambda: edit.save_manual(code, theme=", ".join(st.session_state[k])))


def _save_comment(code, k):
    import edit
    _do(lambda: edit.save_manual(code, comment=st.session_state[k]))


def _remove(code):
    import edit
    _do(edit.remove_manual, code, ok="관심종목에서 뺐습니다")


if not items:
    st.markdown("<div class='empty'>아직 없습니다. ✏️ 수정을 켜고 종목을 골라 넣어 보세요. "
                "종목 화면에서 ⭐ 관심종목에 추가를 눌러도 됩니다.</div>", unsafe_allow_html=True)

all_themes = db.all_themes() if editing else []
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
        m["name"], code=code, pct=row["pct"] if row else None, meta=meta, themes=card["themes"],
        text="" if editing else (f"📝 {m['comment']}" if m["comment"] else ""), href=f"stocks?code={code}",
    )
    if editing:
        cur = db.split_themes(m["theme"])
        kt, kc = f"fav_t_{code}", f"fav_c_{code}"
        st.multiselect("테마", sorted(set(all_themes) | set(cur)), default=cur, key=kt, on_change=_save_theme,
                       args=(code, kt), placeholder="테마 선택", label_visibility="collapsed")
        c1, c2 = st.columns([4, 1])
        c1.text_input("한줄평", value=m["comment"], key=kc, on_change=_save_comment, args=(code, kc),
                      placeholder="📝 한줄평 (쓰고 Enter)", label_visibility="collapsed")
        c2.button("빼기", key=f"fav_x_{code}", on_click=_remove, args=(code,), use_container_width=True)
