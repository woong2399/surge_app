"""리포트 — 날짜별 뉴스 리포트 (reports/날짜.json)."""
import html
import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import ui  # noqa: E402

CSS = """<style>
.k4{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:8px 0 6px}
.k{border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:var(--soft)}
.k .l{font-size:12.5px;color:var(--mute);font-weight:600}
.k .v{font-size:26px;font-weight:800;letter-spacing:-.02em;margin-top:2px}
.k .v.down{color:#2f6fe4}.k .v.up{color:var(--up)}
@media (prefers-color-scheme: dark){ .k .v.down{color:#7fa8ff} }
.k .s{font-size:12px;color:var(--mute);margin-top:2px;line-height:1.4}
.note{font-size:13.5px;color:var(--mute);margin:4px 2px 0;line-height:1.55}
.hero{border:1px solid var(--line);border-left:5px solid var(--chip-fg);border-radius:14px;padding:14px 16px;margin:8px 0 6px;background:var(--soft)}
.hero .h{font-size:19px;font-weight:800;letter-spacing:-.02em;line-height:1.4}
.hero .m{font-size:14.5px;line-height:1.6;margin-top:6px}
.li{border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:6px 0;background:var(--soft)}
.li .t{font-size:15px;font-weight:700;line-height:1.4}
.li .d{font-size:14px;line-height:1.55;margin-top:2px;color:var(--mute)}
.n{display:inline-block;width:20px;height:20px;line-height:20px;text-align:center;border-radius:999px;background:var(--chip-bg);color:var(--chip-fg);font-size:12px;font-weight:800;margin-right:8px}
.sr{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin:6px 0;background:var(--soft)}
.badge{flex:none;font-size:11.5px;font-weight:800;border-radius:999px;padding:2px 9px;margin-top:2px}
.badge.up{color:var(--up);background:var(--up-bg)}
.badge.down{color:#2f6fe4;background:rgba(47,111,228,.14)}
@media (prefers-color-scheme: dark){ .badge.down{color:#7fa8ff;background:rgba(127,168,255,.18)} }
.sr .nm{font-size:15px;font-weight:700;line-height:1.4}.sr .ds{font-size:13.5px;color:var(--mute);margin-top:1px;line-height:1.5}
.cv{font-size:12.5px;color:var(--mute);line-height:1.6;margin:18px 2px 0}
</style>"""

files = sorted(ROOT.glob("reports/*.json"), reverse=True)
if not files:
    st.info("아직 올라온 리포트가 없습니다.")
    st.stop()

days = [f.stem for f in files]
day = st.selectbox("날짜", days, label_visibility="collapsed")
r = json.loads((ROOT / "reports" / f"{day}.json").read_text(encoding="utf-8"))
d = datetime.strptime(r["date"], "%Y-%m-%d")
WD = "월화수목금토일"

ui.setup(f"{d.month}월 {d.day}일 {WD[d.weekday()]}요일 리포트", r.get("basis"))
st.markdown(CSS, unsafe_allow_html=True)
e = html.escape

st.markdown(
    f"<div class='hero'><div class='h'>{e(r['headline'])}</div><div class='m'>{e(r['summary'])}</div></div>",
    unsafe_allow_html=True,
)

st.markdown("<div class='sec'>시장</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='k4'>" + "".join(
        f"<div class='k'><div class='l'>{e(k['label'])}</div><div class='v {k['dir']}'>{e(k['value'])}</div><div class='s'>{e(k['sub'])}</div></div>"
        for k in r["kpis"]
    ) + "</div>" + (f"<div class='note'>{e(r['market_note'])}</div>" if r.get("market_note") else ""),
    unsafe_allow_html=True,
)

st.markdown("<div class='sec'>원인</div>", unsafe_allow_html=True)
st.markdown("".join(
    f"<div class='li'><div class='t'><span class='n'>{i}</span>{e(c['t'])}</div><div class='d'>{e(c['d'])}</div></div>"
    for i, c in enumerate(r["causes"], 1)), unsafe_allow_html=True)

st.markdown("<div class='sec'>정책 대응</div>", unsafe_allow_html=True)
st.markdown("".join(
    f"<div class='li'><div class='t'>{e(c['t'])}</div><div class='d'>{e(c['d'])}</div></div>" for c in r["policy"]),
    unsafe_allow_html=True)

st.markdown("<div class='sec'>종목·업종</div>", unsafe_allow_html=True)
rows = [("up", "호재", s) for s in r["stocks"]["up"]] + [("down", "악재", s) for s in r["stocks"]["down"]]
st.markdown("".join(
    f"<div class='sr'><span class='badge {k}'>{b}</span><div><div class='nm'>{e(s['name'])}</div><div class='ds'>{e(s['d'])}</div></div></div>"
    for k, b, s in rows), unsafe_allow_html=True)

st.markdown("<div class='sec'>다음에 확인할 것</div>", unsafe_allow_html=True)
st.markdown("".join(f"<div class='li'><div class='t'><span class='n'>{i}</span>{e(c)}</div></div>"
                    for i, c in enumerate(r["checks"], 1)), unsafe_allow_html=True)
st.markdown(f"<div class='cv'>{e(r['caveat'])}</div>", unsafe_allow_html=True)
