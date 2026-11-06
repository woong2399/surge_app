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
.block-container{padding:4.5rem 1rem 4rem;max-width:720px}
header[data-testid="stHeader"]{background:transparent}
.hd{margin:0 0 .6rem}
.hd .t{font-size:26px;font-weight:800;letter-spacing:-.02em;line-height:1.3;margin:0}
.hd .s{color:var(--mute);font-size:14px;margin-top:2px}
.c{position:relative;border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:0 0 12px;background:var(--soft)}
.c-top{display:flex;justify-content:space-between;align-items:center;gap:10px}
.c-name a.sl{color:inherit;text-decoration:none}
.c-name a.sl::after{content:'';position:absolute;inset:0;border-radius:14px}
.c.go{cursor:pointer}.c.go:hover{border-color:var(--chip-fg)}
.c-news a,.chips{position:relative;z-index:2}
.c-name{font-size:18px;font-weight:700;letter-spacing:-.01em;min-width:0}
.c-code{font-size:12px;color:var(--mute);font-weight:500;margin-left:6px}
.pct{flex:none;font-size:16px;font-weight:800;color:var(--up);background:var(--up-bg);border-radius:999px;padding:3px 11px;font-variant-numeric:tabular-nums}
.c-meta{margin-top:3px;font-size:12.5px;color:var(--mute)}
.chips{margin-top:9px;display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:14.5px;font-weight:650;color:var(--chip-fg);background:var(--chip-bg);border-radius:999px;padding:4px 12px;line-height:1.35}
.trow{display:flex;gap:10px;align-items:flex-start;margin:6px 0}
.trow .d{flex:none;width:5.2em;font-size:13px;color:var(--mute);padding-top:6px;font-variant-numeric:tabular-nums}
.trow .chips{margin-top:0}
.chip.new{outline:2px solid var(--chip-fg);outline-offset:-2px}
.tag{display:inline-block;font-size:11px;font-weight:600;border:1px solid var(--line);border-radius:999px;padding:0 7px;color:var(--mute);margin-left:6px;vertical-align:2px}
.c-txt{margin-top:10px;font-size:15px;line-height:1.65}
.c-news{margin-top:8px;display:flex;flex-direction:column;gap:4px}
.c-news a, .c-news span{font-size:14px;line-height:1.5;text-decoration:none}
.c-news a{color:var(--chip-fg)}
.c-news a::before, .c-news span::before{content:"뉴스";font-size:10.5px;font-weight:700;color:var(--mute);border:1px solid var(--line);border-radius:4px;padding:0 4px;margin-right:6px}
.dh{margin:22px 0 8px;font-size:15px;font-weight:700;color:var(--mute)}
.box{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:6px 0 14px;font-size:15px;line-height:1.65;white-space:pre-wrap;background:var(--soft)}
.sec{margin:20px 0 6px;font-size:13px;font-weight:700;color:var(--mute);letter-spacing:.02em}
.empty{color:var(--mute);font-size:14.5px;margin:2px 0 8px}
section[data-testid="stSidebar"] label{font-size:14.5px}
</style>"""


def setup(title, sub=None):
    st.markdown(CSS, unsafe_allow_html=True)
    s = f"<div class='s'>{html.escape(sub)}</div>" if sub else ""
    st.markdown(f"<div class='hd'><div class='t'>{html.escape(title)}</div>{s}</div>", unsafe_allow_html=True)


def pct_html(pct):
    return f"<span class='pct'>+{pct:.2f}%</span>"


def amount_text(a):
    return "" if a is None else f"거래대금 {a:,.0f}백만 원"


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


def card(title, code=None, pct=None, meta="", tag=False, themes=(), text="", news="", href=None):
    """종목·이슈 한 칸."""
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
