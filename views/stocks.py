"""종목 — 맨 위 목록에서 종목을 고르면 테마, 종목 정보, 메모, 관련 이슈가 나온다. 검색은 목록을 좁힌다."""
import html
import sys
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

# 이슈·테마 화면의 카드를 누르면(?code=코드) 그 종목이 골라진 채로 열린다.
want = st.query_params.get("code")
if want:
    hit = next((s for s in stocks if s["code"] == want), None)
    if hit:
        st.session_state["stock_q"] = ""
        st.session_state["stock_pick"] = f"{hit['name']}  {hit['code']}"
    del st.query_params["code"]

c1, c2 = st.columns([1, 1.4])
q = c2.text_input("검색", placeholder="🔍 종목명·코드 검색", label_visibility="collapsed", key="stock_q").strip().lower()
shown = [s for s in stocks if q in f"{s['name']} {s['code']}".lower()]
labels = {f"{s['name']}  {s['code']}": s for s in shown}
choice = c1.selectbox("종목", list(labels), label_visibility="collapsed", key="stock_pick") if labels else None

if not choice:
    ui.setup("종목", "찾는 종목이 없습니다." if q else None)
    st.stop()

code, name = labels[choice]["code"], labels[choice]["name"]
card = db.stock_card(code)
ui.setup(name, code)

st.markdown("<div class='sec'>테마</div>", unsafe_allow_html=True)
if card["themes"]:
    st.markdown(ui.chips(card["themes"]).replace("class='chips'", "class='chips' style='margin-top:0'"), unsafe_allow_html=True)
else:
    st.markdown("<div class='empty'>아직 입력된 테마가 없습니다.</div>", unsafe_allow_html=True)

events = db.stock_events(code)
tl = ui.theme_timeline(sorted(events, key=lambda e: e["date"]))
if tl and len([e for e in events if e["theme"]]) > 1:
    st.markdown("<div class='sec'>테마 변화 · 윤곽선은 새로 나온 테마</div>", unsafe_allow_html=True)
    st.markdown(tl, unsafe_allow_html=True)

st.markdown("<div class='sec'>종목 정보</div>", unsafe_allow_html=True)
if card["info"]:
    st.markdown(f"<div class='box'>{html.escape(card['info'])}</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='empty'>아직 입력된 정보가 없습니다. 시트 종목 탭 D열에 적으면 나옵니다.</div>", unsafe_allow_html=True)

if card["memo"]:
    st.markdown("<div class='sec'>메모</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='box'>{html.escape(card['memo'])}</div>", unsafe_allow_html=True)

st.markdown("<div class='sec'>관련 이슈(일지) · 최신순</div>", unsafe_allow_html=True)
if not events:
    st.markdown("<div class='empty'>일지에 나온 적이 없습니다.</div>", unsafe_allow_html=True)
for e in events:
    ui.card(
        e["date"], pct=e["pct"], meta=ui.amount_text(e["amount_est"]),
        tag=e["grp"] == "telegram", themes=db.split_themes(e["theme"]),
        text=e["telegram"], news=e["news"], meta2=ui.flow_line(e),
    )

if card["amount_info"] or card["amount_memo"]:
    st.markdown("<div class='sec'>거래대금 메모 (amount 시트)</div>", unsafe_allow_html=True)
    body = "\n\n".join(x for x in [card["amount_info"], card["amount_memo"]] if x)
    st.markdown(f"<div class='box'>{html.escape(body)}</div>", unsafe_allow_html=True)

if code in db.amount_notes() and st.toggle("✏️ 종목 이슈 입력", key=f"memo_edit_{code}"):
    import edit
    if edit.unlocked():
        with st.form(f"memo_form_{code}"):
            memo = st.text_area("종목 이슈", value=card["amount_memo"], height=180,
                                placeholder="이 종목의 이슈를 적어 두세요 (amount 시트 종목 탭 memo 칸)")
            if st.form_submit_button("저장", type="primary", use_container_width=True):
                try:
                    st.success("저장했습니다." if edit.save_memo(code, memo) else "amount 종목 탭에 이 종목 줄이 없습니다.")
                except Exception as e:
                    st.error(f"저장하지 못했습니다: {type(e).__name__}: {str(e)[:200]}")

vols = db.stock_volume_events(code)
st.markdown(f"<div class='sec'>거래대금 상위 기록 · {len(vols)}번 · 최신순</div>", unsafe_allow_html=True)
if not vols:
    st.markdown("<div class='empty'>거래대금 상위 30에 든 적이 없습니다.</div>", unsafe_allow_html=True)
for v in vols:
    flow = ui.flow_line(v)
    ui.card(
        ("👑 " if v["leader"] else "") + v["date"], pct=v["pct"],
        meta=" · ".join(x for x in [f"{v['rank']:.0f}위" if v["rank"] is not None else "",
                                     f"거래대금 {ui.eok_text(v['amount'])}", ui.cap_text(v)] if x),
        meta2=flow.split(" · ", 1)[1] if flow else "", themes=db.split_themes(v["theme"]), text=v["reason"],
    )
