"""관심종목 — 공부하려고 넣어 둔 종목. 보기만 한다. 넣고 빼기·한줄평·테마는 종목 화면의 ✏️ 수정에서 한다. 카드를 누르면 그 종목 화면으로 간다."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db  # noqa: E402
import ui  # noqa: E402

ui.need_token()

items = db.manual_stocks()  # 최근에 넣은 종목이 앞
ui.setup("관심종목", f"{len(items)}종목 · 최근에 넣은 순" if items else "공부하고 싶은 종목을 넣어 두는 곳")

if not items:
    st.markdown("<div class='empty'>아직 없습니다. 종목 화면에서 종목을 고르고 ✏️ 수정을 켠 뒤 ⭐ 관심종목을 체크하세요.</div>",
                unsafe_allow_html=True)

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
        text=f"📝 {m['comment']}" if m["comment"] else "", href=f"stocks?code={code}",
    )
