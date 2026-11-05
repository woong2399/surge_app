"""세 화면이 같이 쓰는 모양: 스타일, 등락률·뉴스 표시."""
import html
import re

import streamlit as st

UP, MUTED = "#d6372b", "#6a6a6a"  # 한국식: 상승 빨강

CSS = """<style>
.block-container{padding:5.5rem 1rem 3rem;max-width:720px}
h1{font-size:24px!important;line-height:1.35!important;padding-top:.2rem!important}h2{font-size:16px!important;margin-top:1.2rem!important}
.it{margin:18px 0 4px;font-size:17px}.it small{color:#6a6a6a;font-size:12px;margin-left:4px}
.tag{font-size:10px;border:1px solid #ccc;border-radius:4px;padding:0 4px;color:#6a6a6a;margin-left:4px}
.chip{display:inline-block;font-size:15px;font-weight:600;background:#e3ebfb;color:#1d3a78;border-radius:14px;padding:3px 12px;margin:4px 6px 2px 0;line-height:1.4}
.sub{margin:4px 0 0 14px;font-size:15px;line-height:1.6}.sub a{text-decoration:none}
.th{margin:6px 0 0 14px}
.box{background:rgba(128,128,128,.08);border:1px solid #ddd;border-radius:8px;padding:10px 12px;margin:8px 0;font-size:14px;line-height:1.55;white-space:pre-wrap}
</style>"""


def setup(title):
    st.markdown(CSS, unsafe_allow_html=True)
    a, b, c = st.columns(3)  # 폰에서는 옆 메뉴가 접혀 있어서 장 이동 링크를 위에 둔다
    a.page_link("views/issues.py", label="이슈")
    b.page_link("views/stocks.py", label="종목")
    c.page_link("views/themes.py", label="테마")
    st.title(title)


def pct_html(pct):
    return f"<span style='color:{UP};font-weight:600'>+{pct:.2f}%</span>"


def amount_text(a):
    return "" if a is None else f"{a:,.0f}백만"


def chips(themes):
    return "".join(f"<span class='chip'>{html.escape(t)}</span>" for t in themes)


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
                out.append(f"<div class='sub'>📰 <a href='{html.escape(url)}' target='_blank'>{html.escape(head)}</a></div>")
                continue
        if re.match(r"https?://", line):
            out.append(f"<div class='sub'>📰 <a href='{html.escape(line)}' target='_blank'>{html.escape(line)}</a></div>")
        else:
            out.append(f"<div class='sub'>📰 {html.escape(line)}</div>")
    return "".join(out)


def need_token():
    """시트를 못 읽으면 안내하고 멈춘다 (이름은 예전 그대로 둔다)."""
    import db
    try:
        db.history()
    except Exception as e:  # 시트 공유가 꺼졌거나 이름이 바뀐 경우
        st.error("시트를 읽지 못했습니다. 시트가 '링크가 있는 누구나 보기'인지, 탭 이름이 이력·종목인지 확인하세요.")
        st.caption(str(e)[:200])
        st.stop()
