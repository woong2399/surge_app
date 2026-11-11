"""종목 — 맨 위 목록에서 종목을 고르면 테마, 종목 정보, 메모, 날짜별 기록(10%↑·거래대금 상위 30 합침)이 나온다."""
import html
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.need_token()

stocks = db.stocks()
if not stocks:
    ui.setup("종목")
    st.info("아직 올라온 종목이 없습니다.")
    st.stop()

def lab(s):
    """목록 글자: '이름  코드'."""
    return f"{s['name']}  {s['code']}"


# 카드를 눌러 들어오면 어느 화면에서 왔는지(from)와 그 화면의 날짜·테마를 기억해 둔다 → 나중에 그 화면으로 돌아간다.
BACK = {"issues": ("views/issues.py", "이슈"), "volume": ("views/volume.py", "거래대금"),
        "themes": ("views/themes.py", "테마"), "interest": ("views/interest.py", "내 종목")}
if st.query_params.get("from") in BACK:
    st.session_state["stk_back"] = (st.query_params["from"],
                                    {k: st.query_params[k] for k in ("day", "theme") if k in st.query_params})
for _k in ("from", "day", "theme"):
    st.query_params.pop(_k, None)

# 이슈·테마 화면의 카드를 누르면(?code=코드) 그 종목이 골라진 채로 열린다.
want = st.query_params.get("code")
if want:
    hit = next((s for s in stocks if s["code"] == want), None)
    if hit:
        st.session_state["stock_q"] = ""
        st.session_state["stock_pick"] = lab(hit)
    del st.query_params["code"]

# ── 종목 추가: 종목명을 고르고 테마를 정하면 바로 '내 종목'에 들어간다 (일지·거래대금에 나온 적 없는 종목도 됨) ──
def _do_add(items, code):
    try:
        names = edit._commit_names(items)
        edit.add_to_interest([code], ", ".join(names))
        st.session_state["stock_q"] = ""
        st.session_state["stock_pick"] = next(lab(s) for s in stocks if s["code"] == code)
        st.session_state.pop("add_pending", None)
        st.session_state["add_name"] = None
        st.session_state["add_themes"] = []
        st.toast("종목을 추가했습니다", icon="✅")
    except Exception as e:
        st.toast(f"추가하지 못했습니다: {str(e)[:100]}", icon="⚠️")


import edit  # noqa: E402

with st.expander("➕ 종목 추가"):
    if edit.unlocked():
        by_lab = {lab(s): s for s in stocks}
        ca, cb, cc = st.columns([1.1, 1.4, 0.45], vertical_alignment="center")
        pick = ca.selectbox("종목 추가", list(by_lab), index=None, key="add_name", placeholder="종목명",
                            label_visibility="collapsed")
        ths = cb.multiselect("테마", sorted(set(db.all_themes())), key="add_themes", accept_new_options=True,
                             placeholder="테마(고르거나 쓰기)", label_visibility="collapsed")
        fixed, ok = [], bool(pick)
        for r in edit.theme_resolve(", ".join(ths)):
            if isinstance(r, tuple):  # 오타 같은 테마: 후보 중에서 고르게 한다
                _, typed, cands = r
                ch = st.radio(f"‘{typed}’ 는 비슷한 테마가 있어요", cands + [f"새 테마 ‘{typed}’"], key=f"add_fix_{typed}", horizontal=True)
                fixed.append(typed if ch.startswith("새 테마") else ch)
            else:
                fixed.append(r)
        cc.button("추가", key="add_go", disabled=not ok, on_click=_do_add, args=(fixed, by_lab[pick]["code"] if pick else ""))

c1, c2 = st.columns([1, 1.4])
q = c2.text_input("검색", placeholder="🔍 종목명·코드 검색", label_visibility="collapsed", key="stock_q").strip().lower()
shown = [s for s in stocks if q in f"{s['name']} {s['code']}".lower()]
labels = {lab(s): s for s in shown}
choice = c1.selectbox("종목", list(labels), label_visibility="collapsed", key="stock_pick") if labels else None

if not choice:
    ui.setup("종목", "찾는 종목이 없습니다." if q else None)
    st.stop()

code, name = labels[choice]["code"], labels[choice]["name"]
card = db.stock_card(code)
tl = db.stock_timeline(code)
ui.setup(name, code if tl else f"{code} · 아직 일지·거래대금에 나온 적 없음")
WD = "월화수목금토일"
back = st.session_state.get("stk_back")
if back:
    st.page_link(BACK[back[0]][0], label=f"← {BACK[back[0]][1]} 화면으로", query_params=back[1])


def badges(e):
    h, v = e["hist"], e["vol"]
    out = []
    if h:
        out.append("🔺10%↑" if h["grp"] == "surge" else "텔레그램")
    if v:
        out.append(f"💰거래대금 {v['rank']:.0f}위" if v["rank"] is not None else "💰거래대금 상위")
    return out


def themes_of(e):
    out = []
    for r in (e["hist"], e["vol"]):
        for t in db.split_themes(r["theme"] if r else ""):
            if t not in out:
                out.append(t)
    return out


import edit  # noqa: E402

ktog = f"stk_edit_{code}"
on = st.toggle("✏️ 수정", key=ktog)
was = st.session_state.get(ktog + "_was", False)
st.session_state[ktog + "_was"] = on
if was and not on and back:  # 수정을 마치고 끄면 왔던 화면으로 돌아간다
    st.switch_page(BACK[back[0]][0], query_params=back[1])
if on:
    if edit.unlocked():
        edit.banner("고르거나 쓰고 Enter 를 누르면 바로 저장됩니다 · 수정할 수 있는 건 테마, 거래대금 이유, 한줄평입니다")
        edit.theme_ask_ui()  # 오타 같은 테마를 썼으면 여기서 '혹시 ○○?' 하고 묻는다
        mine = next((m for m in db.manual_stocks() if m["code"] == code), None)
        kf = f"fav_chk_{code}"
        st.checkbox("⭐ 내 종목", value=bool(mine), key=kf, on_change=edit.on_interest, args=(code, kf))
        if mine:
            kc, kt = f"cmt_{code}", f"mth_{code}"
            st.text_input("한줄평", value=mine["comment"], key=kc, on_change=edit.on_comment, args=(code, kc),
                          placeholder="📝 한줄평 (쓰고 Enter)", label_visibility="collapsed")
            edit.theme_select("테마", mine["theme"], kt, "manual", (code,))
        for e in tl:
            d = e["date"]
            st.markdown(f"<div class='ft'>{d} · {' '.join(badges(e))}</div>", unsafe_allow_html=True)
            ka, kb = f"th_{d}_{code}", f"rs_{d}_{code}"
            if e["vol"]:
                a, b = st.columns([1, 1.4])
                b.text_input("거래대금 이유", value=e["vol"]["reason"], key=kb, on_change=edit.on_reason, args=(d, code, kb),
                             placeholder="📌 거래대금 이유 (Enter)", label_visibility="collapsed")
            else:
                a = st
            edit.theme_select("테마", ", ".join(themes_of(e)), ka, "day", (d, code), container=a)
        if not tl and not mine:
            st.markdown("<div class='empty'>일지·거래대금에 나온 적 없는 종목이에요. ⭐ 내 종목에 넣으면 한줄평과 테마를 적을 수 있습니다.</div>",
                        unsafe_allow_html=True)
        st.stop()

if card["interest"]:
    st.markdown("<div class='sec'>⭐ 내 종목 · 한줄평</div>", unsafe_allow_html=True)
    if card["comment"]:
        st.markdown(f"<div class='box'>📝 {html.escape(card['comment'])}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='empty'>아직 한줄평이 없습니다. ✏️ 수정을 켜서 적어 보세요.</div>", unsafe_allow_html=True)

st.markdown("<div class='sec'>테마</div>", unsafe_allow_html=True)
if card["themes"]:
    st.markdown(ui.chips(card["themes"]).replace("class='chips'", "class='chips' style='margin-top:0'"), unsafe_allow_html=True)
else:
    st.markdown("<div class='empty'>아직 입력된 테마가 없습니다.</div>", unsafe_allow_html=True)

events = db.stock_events(code)
theme_tl = ui.theme_timeline(sorted(events, key=lambda e: e["date"]))
if theme_tl and len([e for e in events if e["theme"]]) > 1:
    st.markdown("<div class='sec'>테마 변화 · 윤곽선은 새로 나온 테마</div>", unsafe_allow_html=True)
    st.markdown(theme_tl, unsafe_allow_html=True)

st.markdown("<div class='sec'>종목 정보</div>", unsafe_allow_html=True)
if card["info"]:
    st.markdown(f"<div class='box'>{html.escape(card['info'])}</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='empty'>아직 입력된 정보가 없습니다. 시트 종목 탭 D열에 적으면 나옵니다.</div>", unsafe_allow_html=True)

if card["memo"]:
    st.markdown("<div class='sec'>메모</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='box'>{html.escape(card['memo'])}</div>", unsafe_allow_html=True)

# 일지(10%↑)와 거래대금 상위 30을 날짜 하나로 합쳐 보여 준다 (카드마다 표시가 붙어 있어 횟수 요약은 두지 않는다)
st.markdown("<div class='sec'>날짜별 기록 · 최신순</div>", unsafe_allow_html=True)
if not tl:
    st.markdown("<div class='empty'>일지나 거래대금 상위에 나온 적이 없습니다.</div>", unsafe_allow_html=True)
for e in tl:
    h, v = e["hist"], e["vol"]
    d = e["date"]
    wd = WD[datetime.strptime(d, "%Y-%m-%d").weekday()]
    size = f"거래대금 {ui.eok_text(v['amount'])}" if v else ui.amount_text(h["amount_est"])
    flow = ui.flow_line(v or h)
    if v and flow:
        flow = flow.split(" · ", 1)[1]  # 순위는 표시에 있으니 뺀다
    text = "\n".join(x for x in [f"💬 {h['telegram']}" if h and h["telegram"] else "",
                                 f"📌 {v['reason']}" if v and v["reason"] else ""] if x)  # 아이콘 하나로 출처 구분
    ui.card(
        ("👑 " if v and v["leader"] else "") + f"{d} ({wd})", pct=h["pct"] if h else v["pct"],
        meta=" · ".join(badges(e) + [x for x in [size, ui.cap_text(v) if v else ""] if x]),
        meta2=flow, themes=themes_of(e), text=text, news=h["news"] if h else "",
    )
