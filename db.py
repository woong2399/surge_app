"""구글 시트 surge 를 직접 읽는다. 시트에서 고치면 1분 안에 화면에 반영된다.

읽는 곳: 시트의 `이력` 탭(date, code, name, pct, amount_est, theme, telegram, news)과 `종목` 탭(code, name, …, D열 종목 정보, E열 메모).
시트는 '링크가 있는 누구나 보기'로 열려 있어야 한다(CSV 로 읽는다). 쓰지는 않는다.
시트 id 는 환경변수·Streamlit secrets 의 SURGE_SHEET_ID 로 바꿀 수 있다(없으면 아래 기본값).
"""
import os
import re
import urllib.parse

import pandas as pd
import streamlit as st

DEFAULT_SHEET_ID = "1SpHykeusHQ9PjYCu2W46DJrbgDKmcdmWfjfcaLkgOkM"
TTL = 60  # 초: 시트를 고친 뒤 화면에 반영되기까지 최대 시간


def sheet_id():
    t = os.environ.get("SURGE_SHEET_ID")
    if t:
        return t
    try:
        if "SURGE_SHEET_ID" in st.secrets:
            return st.secrets["SURGE_SHEET_ID"]
    except Exception:
        pass
    return DEFAULT_SHEET_ID


AMOUNT_SHEET_ID = "16G7kVUSJokomw7tq42VVBjelgFoW1mQmA34_Nh2HnC0"  # 거래대금상위 탭이 있는 amount 시트


def _csv(tab, sid=None):
    if sid == AMOUNT_SHEET_ID:  # 서비스 계정 키가 있으면 그걸로 읽는다(링크 공개가 꺼져 있어도 됨)
        import edit
        vals = edit.read_values(tab)
        if vals:
            n = len(vals[0])
            return pd.DataFrame([r + [""] * (n - len(r)) for r in vals[1:]], columns=vals[0], dtype=str)
    url = (f"https://docs.google.com/spreadsheets/d/{sid or sheet_id()}/gviz/tq?tqx=out:csv&headers=1&sheet="
           + urllib.parse.quote(tab))
    return pd.read_csv(url, dtype=str, keep_default_na=False)


def split_themes(text):
    """'a, b,c' → ['a', 'b', 'c'] (빈 값 제거, 순서 유지)"""
    out = []
    for t in re.split(r"\s*,\s*", text or ""):
        t = t.strip()
        if t and t not in out:
            out.append(t)
    return out


def _num(s):
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def _cells(df, n):
    """표의 각 줄을 n 칸 글자 목록으로 (칸이 모자라면 빈 글자로 채움)."""
    for r in df.itertuples(index=False):
        vals = [str(x).strip() for x in r][:n]
        yield vals + [""] * (n - len(vals))


def _flow(rank, new_high, foreign, inst, program, top30):
    """이력 I~N 칸, 거래대금상위 탭이 같이 쓰는 수급 칸."""
    return {"rank": _num(rank), "new_high": new_high, "foreign": _num(foreign), "inst": _num(inst),
            "program": _num(program), "top30": _num(top30)}


@st.cache_data(ttl=TTL, show_spinner="시트를 읽는 중…")
def history():
    """이력 탭 전체 → [{date, code, name, pct, amount_est, grp, theme, telegram, news, rank, new_high, …}]"""
    df = _csv("이력")
    rows = []
    for vals in _cells(df, 14):
        date, code, name, pct, amount, theme, telegram, news = vals[:8]
        if not code or not date:
            continue
        p, a = _num(pct), _num(amount)
        if p is None:
            continue
        telegram_only = a is None or p < 10  # 10%↑ 목록(Surge)에 없던 종목
        rows.append({"date": date, "code": code, "name": name, "pct": p, "amount_est": a,
                     "grp": "telegram" if telegram_only else "surge",
                     "theme": theme, "telegram": telegram.removeprefix("* "), "news": news,
                     **_flow(*vals[8:14])})
    return rows


def _named(df):
    """첫 줄 제목 이름으로 읽기: 줄마다 {제목: 글자}. 사용자가 칸 순서를 바꿔도 된다."""
    cols = [str(c).strip() for c in df.columns]
    for r in df.itertuples(index=False):
        yield {c: str(x).strip() for c, x in zip(cols, r)}


@st.cache_data(ttl=TTL, show_spinner=False)
def volume():
    """amount 시트 거래대금상위 탭 → [{date, rank, code, name, pct, amount(억), mktcap(억), turnover(%), new_high,
    foreign, inst, program, top30, in_diary, theme, leader, reason}]. 탭이 없거나 비어 있으면 []."""
    try:
        df = _csv("거래대금상위", AMOUNT_SHEET_ID)
    except Exception:
        return []
    rows = []
    for v in _named(df):
        g = lambda k: v.get(k, "")
        if not g("date") or not g("code") or g("date") == "date":
            continue
        rows.append({"date": g("date"), "code": g("code"), "name": g("name"), "pct": _num(g("pct")),
                     "amount": _num(g("amount")), "mktcap": _num(g("mktcap")), "turnover": _num(g("turnover")),
                     **_flow(g("rank"), g("new_high"), g("foreign"), g("inst"), g("program"), g("top30_cnt")),
                     "in_diary": bool(g("in_diary")), "theme": g("theme"), "leader": bool(g("leader")),
                     "reason": g("reason")})
    return rows


def volume_dates():
    return sorted({r["date"] for r in volume()}, reverse=True)


def volume_day(day):
    return sorted((r for r in volume() if r["date"] == day), key=lambda r: r["rank"] or 999)


def stock_volume_events(code):
    return sorted((r for r in volume() if r["code"] == code), key=lambda r: r["date"], reverse=True)


@st.cache_data(ttl=TTL, show_spinner=False)
def stock_notes():
    """종목 탭 → {code: {info, memo}}"""
    df = _csv("종목")
    out = {}
    for r in df.iloc[:, :5].itertuples(index=False):
        code = str(r[0]).strip()
        if code:
            out[code] = {"info": str(r[3]).strip(), "memo": str(r[4]).strip()}
    return out


@st.cache_data(ttl=TTL, show_spinner=False)
def amount_notes():
    """amount 시트 종목 탭 → {code: {info, memo}} (surge 시트 종목 탭과 따로 관리)."""
    try:
        df = _csv("종목", AMOUNT_SHEET_ID)
    except Exception:
        return {}
    return {v["code"]: {"info": v.get("info", ""), "memo": v.get("memo", "")}
            for v in _named(df) if v.get("code")}


def dates():
    return sorted({r["date"] for r in history()}, reverse=True)


def day_rows(day):
    return sorted((r for r in history() if r["date"] == day), key=lambda r: -r["pct"])


@st.cache_data(ttl=TTL, show_spinner=False)
def universe():
    """amount 시트 종목목록 탭(lists_sync.py 가 DB stocks 에서 내보낸 상장 종목) → [{code, name, market}].
    탭이 없거나 읽을 수 없으면 []."""
    import edit
    vals = edit.read_values("종목목록")
    if not vals or not {"code", "name", "market"} <= set(vals[0]):
        return []
    h = {n: i for i, n in enumerate(vals[0])}
    out = []
    for r in vals[1:]:
        g = lambda f: r[h[f]].strip() if h[f] < len(r) else ""
        if g("code"):
            out.append({"code": g("code"), "name": g("name"), "market": g("market")})
    return out


def universe_names():
    return {u["code"]: u["name"] for u in universe()}


@st.cache_data(ttl=TTL, show_spinner=False)
def theme_registry():
    """amount 시트 테마목록 탭 → 테마 이름 목록(고유값). 탭이 없으면 []."""
    import edit
    vals = edit.read_values("테마목록")
    if not vals or "theme" not in vals[0]:
        return []
    i = vals[0].index("theme")
    return [r[i].strip() for r in vals[1:] if i < len(r) and r[i].strip()]


@st.cache_data(ttl=TTL, show_spinner=False)
def manual_stocks():
    """amount 시트 관심종목 탭 → [{code, name, theme, comment}] (최근에 넣은 것이 앞). 탭이 없거나 읽을 수 없으면 []."""
    import edit
    vals = edit.read_values("관심종목")
    if not vals or not {"code", "name", "theme", "comment"} <= set(vals[0]):  # 탭이 없을 때 엉뚱한 시트를 읽지 않게 제목도 확인
        return []
    h = {n: i for i, n in enumerate(vals[0])}
    names = universe_names()
    out = []
    for r in vals[1:]:
        g = lambda f: r[h[f]].strip() if h[f] < len(r) else ""
        if g("code"):
            out.append({"code": g("code"), "name": names.get(g("code")) or g("name"), "theme": g("theme"),
                        "comment": g("comment")})
    return out[::-1]


def name_of(code):
    return (next((r["name"] for r in history() + volume() if r["code"] == code and r["name"]), "")
            or universe_names().get(code, ""))


def stocks():
    """일지(이력) 종목 + 거래대금상위 종목 + (그 둘에 없는) 관심종목."""
    names = {}
    for r in volume() + history():
        if r["name"]:
            names[r["code"]] = r["name"]
    for m in manual_stocks():
        names.setdefault(m["code"], m["name"])
    return sorted(({"code": c, "name": n} for c, n in names.items()), key=lambda s: s["name"])


def stock_card(code):
    note = stock_notes().get(code, {"info": "", "memo": ""})
    themes = []
    for r in sorted((r for r in history() + volume() if r["code"] == code), key=lambda r: r["date"]):
        for t in split_themes(r["theme"]):
            if t not in themes:
                themes.append(t)
    mine = next((m for m in manual_stocks() if m["code"] == code), None)
    for t in split_themes(mine["theme"] if mine else ""):
        if t not in themes:
            themes.append(t)
    an = amount_notes().get(code, {"info": "", "memo": ""})
    return {"info": note["info"], "memo": note["memo"], "themes": themes,
            "amount_info": an["info"], "amount_memo": an["memo"],
            "interest": mine is not None, "comment": mine["comment"] if mine else ""}


def stock_events(code):
    return sorted((r for r in history() if r["code"] == code), key=lambda r: r["date"], reverse=True)


def stock_timeline(code):
    """한 종목의 날짜별 기록: 일지(10%↑·텔레그램)와 거래대금 상위 30을 날짜 하나로 합친다.
    [{date, hist: 이력 줄 또는 None, vol: 거래대금상위 줄 또는 None}] 최신순."""
    by = {}
    for r in history():
        if r["code"] == code:
            by.setdefault(r["date"], {})["hist"] = r
    for r in volume():
        if r["code"] == code:
            by.setdefault(r["date"], {})["vol"] = r
    return [{"date": d, "hist": v.get("hist"), "vol": v.get("vol")} for d, v in sorted(by.items(), reverse=True)]


def all_themes():
    """일지 이력·거래대금상위·관심종목에 적힌 테마 + 테마목록(고유값)."""
    seen = set()
    for r in history() + volume():
        seen.update(split_themes(r["theme"]))
    for m in manual_stocks():
        seen.update(split_themes(m["theme"]))
    seen.update(theme_registry())
    return sorted(seen)


def latest_record(code):
    """그 종목의 가장 최근 기록(일지·거래대금 날짜를 합친 것) = stock_timeline 의 첫 줄, 없으면 None."""
    tl = stock_timeline(code)
    return tl[0] if tl else None


def theme_events(theme):
    """그 테마가 적힌 줄들. 관심종목에 직접 넣은 종목은 날짜 없는 줄(date '', manual True)로 더한다."""
    rows = [r for r in history() + volume() if theme in split_themes(r["theme"])]
    for m in manual_stocks():
        if theme in split_themes(m["theme"]):
            rows.append({"date": "", "code": m["code"], "name": m["name"], "pct": None,
                         "grp": "surge", "manual": True})
    return sorted(rows, key=lambda r: (r["date"], r["pct"] or 0), reverse=True)
