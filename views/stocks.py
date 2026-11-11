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
tl = db.stock_timeline(code)
WD = "월화수목금토일"


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


if st.toggle("✏️ 테마·이슈 입력", key=f"stk_edit_{code}"):
    import edit
    if not edit.unlocked():
        st.stop()
    if code in db.amount_notes():
        with st.form(f"memo_form_{code}"):
            memo = st.text_area("종목 이슈", value=card["amount_memo"], height=120,
                                placeholder="이 종목의 이슈를 적어 두세요 (amount 시트 종목 탭 memo 칸)")
            if st.form_submit_button("종목 이슈 저장", type="primary", use_container_width=True):
                try:
                    st.success("저장했습니다." if edit.save_memo(code, memo) else "amount 종목 탭에 이 종목 줄이 없습니다.")
                except Exception as e:
                    st.error(f"저장하지 못했습니다: {type(e).__name__}: {str(e)[:200]}")
    items = []
    for e in tl:
        fs = [("theme", "테마 (쉼표로 여러 개)", ", ".join(themes_of(e)))]
        if e["hist"]:
            fs.append(("telegram", "일지 이슈", e["hist"]["telegram"]))
        if e["vol"]:
            fs.append(("reason", "거래대금 이유", e["vol"]["reason"]))
        items.append({"id": e["date"], "title": " · ".join([e["date"]] + badges(e)), "fields": fs})
    has = {e["date"]: e for e in tl}

    def on_save(ch):
        he, ae = {}, {}
        for d, fs in ch.items():
            for f, v in fs.items():  # 테마는 그날 있는 시트 모두에, 이슈는 제 칸에
                if f in ("theme", "telegram") and has[d]["hist"]:
                    he.setdefault((d, code), {})[f] = v
                if f in ("theme", "reason") and has[d]["vol"]:
                    ae.setdefault((d, code), {})[f] = v
        return edit.save(amount_edits=ae, hist_edits=he)

    edit.form(f"stk_form_{code}", [("날짜별 테마·이슈 · 최신순", items)], on_save)
    st.stop()

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

if card["amount_info"] or card["amount_memo"]:
    st.markdown("<div class='sec'>종목 이슈</div>", unsafe_allow_html=True)
    body = "\n\n".join(x for x in [card["amount_info"], card["amount_memo"]] if x)
    st.markdown(f"<div class='box'>{html.escape(body)}</div>", unsafe_allow_html=True)

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
    text = "\n".join(x for x in [h["telegram"] if h else "", f"거래대금 이유: {v['reason']}" if v and v["reason"] else ""] if x)
    ui.card(
        ("👑 " if v and v["leader"] else "") + f"{d} ({wd})", pct=h["pct"] if h else v["pct"],
        meta=" · ".join(badges(e) + [x for x in [size, ui.cap_text(v) if v else ""] if x]),
        meta2=flow, themes=themes_of(e), text=text, news=h["news"] if h else "",
    )
