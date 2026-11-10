"""amount 시트에 쓰기 — 거래대금상위의 theme·reason, 종목 탭의 memo.

필요한 것 (Streamlit Cloud → 앱 Settings → Secrets 에 사용자가 직접 넣는다. 코드·GitHub 에는 없다):
  EDIT_PASSWORD = "..."            # 입력 화면을 여는 비밀번호
  [gcp_service_account]            # 서비스 계정 키 JSON 의 항목들 (type, project_id, private_key, client_email, …)
이 컴퓨터에서 시험할 때는 환경변수 SURGE_KEY_FILE 에 키 파일 경로를, EDIT_PASSWORD 에 비밀번호를 준다.
칸은 첫 줄 제목(date, code, theme, reason / code, memo)으로 찾는다.
"""
import os

import streamlit as st

import db


def _secret(name):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


@st.cache_resource(show_spinner=False)
def _client():
    import gspread
    info = _secret("gcp_service_account")
    if info:
        return gspread.service_account_from_dict(dict(info))
    path = os.environ.get("SURGE_KEY_FILE")
    if path:
        return gspread.service_account(filename=path)
    return None


def available():
    try:
        return _client() is not None and bool(_secret("EDIT_PASSWORD"))
    except Exception:
        return False


def unlocked():
    """비밀번호를 맞게 넣었으면 True. 아니면 입력 칸을 보여 주고 False."""
    if not available():
        st.info("입력 기능이 아직 켜지지 않았습니다. 앱 Secrets 에 서비스 계정 키와 EDIT_PASSWORD 를 넣어야 합니다.")
        return False
    if st.session_state.get("edit_ok"):
        return True
    pw = st.text_input("비밀번호", type="password", key="edit_pw")
    if pw:
        if pw == str(_secret("EDIT_PASSWORD")):
            st.session_state["edit_ok"] = True
            st.rerun()
        st.error("비밀번호가 맞지 않습니다.")
    return False


def _ws(tab):
    return _client().open_by_key(db.AMOUNT_SHEET_ID).worksheet(tab)


def save_day(day, edits):
    """edits = {code: {"theme": .., "reason": ..}}. 바뀐 칸만 쓴다. 같은 종목의 다른 날짜 빈 테마는,
    그 종목 테마가 한 가지뿐이면 그 값으로 채운다(시트·옵시디언과 같은 규칙). 쓴 칸 수를 돌려준다."""
    from gspread.utils import rowcol_to_a1
    ws = _ws("거래대금상위")
    vals = ws.get_all_values()
    h = {n: i for i, n in enumerate(vals[0])}
    upd = {}
    for i, r in enumerate(vals[1:], start=2):
        e = edits.get(r[h["code"]]) if r[h["date"]] == day else None
        if not e:
            continue
        for f in ("theme", "reason"):
            new = " ".join((e.get(f) or "").split())
            if new.lower() == "null":
                new = ""
            if new != r[h[f]].strip():
                upd[(i, f)] = new
                r[h[f]] = new
    known = {}
    for r in vals[1:]:
        if r[h["theme"]].strip():
            known.setdefault(r[h["code"]], set()).add(r[h["theme"]].strip())
    for i, r in enumerate(vals[1:], start=2):
        c = r[h["code"]]
        if r[h["code"]] in edits and not r[h["theme"]].strip() and len(known.get(c, ())) == 1:
            upd[(i, "theme")] = next(iter(known[c]))
    if upd:
        ws.batch_update([{"range": rowcol_to_a1(i, h[f] + 1), "values": [[v]]} for (i, f), v in upd.items()],
                        value_input_option="RAW")
    # 일지(surge 시트 이력)의 같은 날·같은 종목 테마가 비어 있으면 같이 채운다 (빈 칸만, 사용자 결정 2026-11-11)
    themes = {r[h["code"]]: r[h["theme"]].strip() for r in vals[1:] if r[h["date"]] == day and r[h["code"]] in edits}
    hws = _client().open_by_key(db.sheet_id()).worksheet("이력")
    hv = hws.get_all_values()
    hh = {n: i for i, n in enumerate(hv[0])}
    hist = [{"range": rowcol_to_a1(j, hh["theme"] + 1), "values": [[themes[r[hh["code"]]]]]}
            for j, r in enumerate(hv[1:], start=2)
            if r[hh["date"]] == day and themes.get(r[hh["code"]]) and not r[hh["theme"]].strip()]
    if hist:
        hws.batch_update(hist, value_input_option="RAW")
    if upd or hist:
        st.cache_data.clear()
    return len(upd) + len(hist)


def save_memo(code, memo):
    """amount 종목 탭에서 code 줄의 memo 칸을 바꾼다. 줄이 없으면 False."""
    ws = _ws("종목")
    vals = ws.get_all_values()
    h = {n: i for i, n in enumerate(vals[0])}
    for i, r in enumerate(vals[1:], start=2):
        if r[h["code"]] == code:
            ws.update_cell(i, h["memo"] + 1, memo.strip())
            st.cache_data.clear()
            return True
    return False


def read_values(tab):
    """서비스 계정으로 amount 시트 탭 읽기(링크 공개가 꺼져 있어도 됨). 쓸 수 없으면 None."""
    global last_error
    try:
        cl = _client()
        if cl is None:
            last_error = "서비스 계정 키가 Secrets 에 없습니다 (gcp_service_account)."
            return None
        return cl.open_by_key(db.AMOUNT_SHEET_ID).worksheet(tab).get_all_values()
    except Exception as e:
        last_error = f"{type(e).__name__}: {str(e)[:200]}"
        return None


last_error = ""  # 화면에 원인을 보여 주기 위한 마지막 읽기 오류 (키 내용은 담지 않는다)
