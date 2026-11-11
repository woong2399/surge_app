"""세 화면이 같이 쓰는 모양: 스타일, 카드, 등락률·뉴스 표시."""
import html
import re

import streamlit as st

CSS = """<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
.stApp, .stApp *:not([data-testid="stIconMaterial"]):not([class*="material"]) {
  font-family: 'Pretendard', -apple-system, 'Segoe UI', 'Noto Sans KR', sans-serif !important;
}
:root{
  --up:#e5483c; --up-bg:rgba(229,72,60,.13);
  --chip-fg:#2f5fc4; --chip-bg:rgba(66,133,244,.14);
  --line:rgba(128,128,128,.28); --soft:rgba(128,128,128,.07); --mute:rgba(128,128,128,.95);
}
@media (prefers-color-scheme: dark){ :root{ --up:#ff6b5e; --up-bg:rgba(255,107,94,.16); --chip-fg:#8db4ff; --chip-bg:rgba(110,160,255,.18); } }
.block-container{padding:3.2rem .75rem 3rem;max-width:760px}
header[data-testid="stHeader"]{background:transparent}
/* 한 화면에 많이 보이게: 글씨·간격을 작게 (사용자 요청 2026-11-11) */
.stApp [data-testid="stVerticalBlock"]{gap:.45rem}
.stApp [data-testid="stMarkdownContainer"] p,.stApp label,.stApp input,.stApp textarea,.stApp [data-baseweb="select"] *{font-size:13px}
.stApp [data-testid="stTextInput"] input{padding:5px 9px}
.stApp [data-baseweb="select"] > div{min-height:34px}
.stApp [data-testid="stFormSubmitButton"] button,.stApp .stButton button{min-height:34px;padding:2px 12px}
.hd{margin:0 0 .3rem}
.hd .t{font-size:19px;font-weight:800;letter-spacing:-.02em;line-height:1.3;margin:0}
.hd .s{color:var(--mute);font-size:12px;margin-top:1px}
.c{position:relative;border:1px solid var(--line);border-radius:10px;padding:7px 11px;margin:0 0 6px;background:var(--soft)}
.c-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.c-name a.sl{color:inherit;text-decoration:none}
.c-name a.sl::after{content:'';position:absolute;inset:0;border-radius:10px}
.c.go{cursor:pointer}.c.go:hover{border-color:var(--chip-fg)}
.c-news a,.chips{position:relative;z-index:2}
.c-name{font-size:14.5px;font-weight:700;letter-spacing:-.01em;min-width:0}
.c-code{font-size:11px;color:var(--mute);font-weight:500;margin-left:5px}
.pct{flex:none;font-size:12.5px;font-weight:800;color:var(--up);background:var(--up-bg);border-radius:999px;padding:1px 8px;font-variant-numeric:tabular-nums}
.c-meta{margin-top:1px;font-size:11.5px;line-height:1.45;color:var(--mute);white-space:pre-line}
.pct.dn{color:#2f6fe0;background:rgba(47,111,224,.13)}
.grp{margin:14px 0 5px;padding:5px 10px;border-radius:8px;background:var(--chip-bg);display:flex;align-items:baseline;gap:8px}
.grp .gt{font-size:14px;font-weight:800;color:var(--chip-fg)}
.grp .gs{font-size:11.5px;color:var(--mute)}
.chips{margin-top:4px;display:flex;flex-wrap:wrap;gap:4px}
.chip{font-size:11.5px;font-weight:650;color:var(--chip-fg);background:var(--chip-bg);border-radius:999px;padding:1px 8px;line-height:1.4}
.trow{display:flex;gap:8px;align-items:flex-start;margin:3px 0}
.trow .d{flex:none;width:4.6em;font-size:11.5px;color:var(--mute);padding-top:2px;font-variant-numeric:tabular-nums}
.trow .chips{margin-top:0}
.chip.new{outline:1.5px solid var(--chip-fg);outline-offset:-1.5px}
.tag{display:inline-block;font-size:10px;font-weight:600;border:1px solid var(--line);border-radius:999px;padding:0 6px;color:var(--mute);margin-left:5px;vertical-align:1px}
.c-txt{margin-top:4px;font-size:12.5px;line-height:1.5;white-space:pre-line}
.c-news{margin-top:3px;display:flex;flex-direction:column;gap:2px}
.c-news a, .c-news span{font-size:12px;line-height:1.45;text-decoration:none}
.c-news a{color:var(--chip-fg)}
.c-news a::before, .c-news span::before{content:"뉴스";font-size:9.5px;font-weight:700;color:var(--mute);border:1px solid var(--line);border-radius:4px;padding:0 3px;margin-right:5px}
.dh{margin:14px 0 5px;font-size:13px;font-weight:700;color:var(--mute)}
.box{border:1px solid var(--line);border-radius:9px;padding:7px 10px;margin:3px 0 8px;font-size:12.5px;line-height:1.5;white-space:pre-wrap;background:var(--soft)}
.sec{margin:12px 0 3px;font-size:11.5px;font-weight:700;color:var(--mute);letter-spacing:.02em}
.sum{font-size:12px;margin:0 0 6px}
.ft{font-size:12.5px;font-weight:650;line-height:1.4;margin:6px 0 0}
.stApp [data-testid="stMarkdownContainer"]:has(> .ft){margin-bottom:0}
.empty{color:var(--mute);font-size:12.5px;margin:2px 0 6px}
section[data-testid="stSidebar"] label{font-size:13px}
</style>"""


def setup(title, sub=None):
    st.markdown(CSS, unsafe_allow_html=True)
    s = f"<div class='s'>{html.escape(sub)}</div>" if sub else ""
    st.markdown(f"<div class='hd'><div class='t'>{html.escape(title)}</div>{s}</div>", unsafe_allow_html=True)


def pct_html(pct):
    return f"<span class='pct{' dn' if pct < 0 else ''}'>{pct:+.2f}%</span>"


def amount_text(a):
    return "" if a is None else f"거래대금 {a:,.0f}백만 원"


def eok_text(a):
    """억 원 → '9,836억', '1조 2,340억'. 빈 값이면 '-'."""
    if a is None:
        return "-"
    jo, eok = divmod(round(a), 10000)
    return f"{jo}조 {eok:,}억" if jo else f"{eok:,}억"


def cap_text(r):
    """'시총 2조 4,986억 · 회전율 10.6%'. 시총이 없으면 ''."""
    if r.get("mktcap") is None:
        return ""
    t = r.get("turnover")
    return f"시총 {eok_text(r['mktcap'])}" + (f" · 회전율 {t:.2f}%" if t is not None and t < 1 else f" · 회전율 {t:.1f}%" if t is not None else "")


def _signed(label, v):
    """억 원. 10억 미만은 소수 첫째 자리까지(+0.3), 0 은 0."""
    if v is None:
        return f"{label} -"
    if round(v, 1) == 0:
        return f"{label} 0"
    return f"{label} {v:+,.1f}" if abs(v) < 10 else f"{label} {v:+,.0f}"


def flow_line(r):
    """'거래대금 12위 · 52주 신고가 · 외 +305 · 기 +810 · 프 -20 · 상위30 5회' (억 원). 값이 모두 비면 ''."""
    keys = ("rank", "new_high", "foreign", "inst", "program", "top30")
    if all(r.get(k) in (None, "") for k in keys):
        return ""
    parts = [f"거래대금 {r['rank']:.0f}위" if r.get("rank") is not None else "거래대금 -위"]
    if r.get("new_high"):
        parts.append(f"{r['new_high']} 신고가")
    parts += [_signed("외", r.get("foreign")), _signed("기", r.get("inst")), _signed("프", r.get("program"))]
    parts.append(f"상위30 {r['top30']:.0f}회" if r.get("top30") is not None else "상위30 -회")
    return " · ".join(parts)


def chips(themes):
    if not themes:
        return ""
    return "<div class='chips'>" + "".join(f"<span class='chip'>{html.escape(t)}</span>" for t in themes) + "</div>"


def news_html(text):
    """뉴스 칸: 한 줄에 하나. '헤드라인 | 주소' 는 링크로, 주소만 있으면 주소 글자로 링크를 만든다."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            head, url = [x.strip() for x in line.rsplit("|", 1)]
            if re.match(r"https?://", url):
                out.append(f"<a href='{html.escape(url)}' target='_blank' rel='noopener'>{html.escape(head)}</a>")
                continue
        if re.match(r"https?://", line):
            out.append(f"<a href='{html.escape(line)}' target='_blank' rel='noopener'>{html.escape(line)}</a>")
        else:
            out.append(f"<span>{html.escape(line)}</span>")
    return "<div class='c-news'>" + "".join(out) + "</div>" if out else ""


def card(title, code=None, pct=None, meta="", tag=False, themes=(), text="", news="", href=None, meta2=""):
    """종목·이슈 한 칸. meta2 는 meta 아래 한 줄 더(수급 등)."""
    if meta2:
        meta = f"{meta}\n{meta2}" if meta else meta2
    code_html = f"<span class='c-code'>{html.escape(code)}</span>" if code else ""
    title_html = html.escape(title)
    if href:  # 카드를 누르면 href 로 이동
        title_html = f"<a class='sl' href='{html.escape(href)}' target='_self'>{title_html}</a>"
    tag_html = "<span class='tag'>텔레그램만</span>" if tag else ""
    pct_part = pct_html(pct) if pct is not None else ""
    meta_html = f"<div class='c-meta'>{html.escape(meta)}</div>" if meta else ""
    text_html = f"<div class='c-txt'>{html.escape(text)}</div>" if text else ""
    st.markdown(
        f"<div class='c{' go' if href else ''}'><div class='c-top'><div class='c-name'>{title_html}{code_html}{tag_html}</div>{pct_part}</div>"
        f"{meta_html}{chips(themes)}{text_html}{news_html(news)}</div>",
        unsafe_allow_html=True,
    )


def need_token():
    """시트를 못 읽으면 안내하고 멈춘다 (이름은 예전 그대로 둔다)."""
    import db
    try:
        db.history()
    except Exception as e:  # 시트 공유가 꺼졌거나 이름이 바뀐 경우
        st.error("시트를 읽지 못했습니다. 시트가 '링크가 있는 누구나 보기'인지, 탭 이름이 이력·종목인지 확인하세요.")
        st.caption(str(e)[:200])
        st.stop()


def theme_timeline(events):
    """날짜별 테마 변화. events 는 날짜 오름차순 [{date, theme}]. 전날까지 없던 테마는 윤곽선으로 표시한다."""
    import db
    seen, rows = set(), []
    for e in events:
        ts = db.split_themes(e["theme"])
        if not ts:
            continue
        chips_html = "".join(
            f"<span class='chip{'' if t in seen else ' new'}'>{html.escape(t)}</span>" for t in ts
        )
        seen.update(ts)
        rows.append(f"<div class='trow'><div class='d'>{e['date'][5:]}</div><div class='chips'>{chips_html}</div></div>")
    return "".join(rows)
