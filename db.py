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


def _csv(tab):
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id()}/gviz/tq?tqx=out:csv&sheet="
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


@st.cache_data(ttl=TTL, show_spinner="시트를 읽는 중…")
def history():
    """이력 탭 전체 → [{date, code, name, pct, amount_est, grp, theme, telegram, news}]"""
    df = _csv("이력")
    rows = []
    for r in df.iloc[:, :8].itertuples(index=False):
        date, code, name, pct, amount, theme, telegram, news = [str(x).strip() for x in r]
        if not code or not date:
            continue
        p, a = _num(pct), _num(amount)
        if p is None:
            continue
        telegram_only = a is None or p < 10  # 10%↑ 목록(Surge)에 없던 종목
        rows.append({"date": date, "code": code, "name": name, "pct": p, "amount_est": a,
                     "grp": "telegram" if telegram_only else "surge",
                     "theme": theme, "telegram": telegram.removeprefix("* "), "news": news})
    return rows


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


def dates():
    return sorted({r["date"] for r in history()}, reverse=True)


def day_rows(day):
    return sorted((r for r in history() if r["date"] == day), key=lambda r: -r["pct"])


def stocks():
    names = {}
    for r in history():
        names[r["code"]] = r["name"]
    return sorted(({"code": c, "name": n} for c, n in names.items()), key=lambda s: s["name"])


def stock_card(code):
    note = stock_notes().get(code, {"info": "", "memo": ""})
    themes = []
    for r in sorted((r for r in history() if r["code"] == code), key=lambda r: r["date"]):
        for t in split_themes(r["theme"]):
            if t not in themes:
                themes.append(t)
    return {"info": note["info"], "memo": note["memo"], "themes": themes}


def stock_events(code):
    return sorted((r for r in history() if r["code"] == code), key=lambda r: r["date"], reverse=True)


def all_themes():
    seen = set()
    for r in history():
        seen.update(split_themes(r["theme"]))
    return sorted(seen)


def theme_events(theme):
    rows = [r for r in history() if theme in split_themes(r["theme"])]
    return sorted(rows, key=lambda r: (r["date"], r["pct"]), reverse=True)
