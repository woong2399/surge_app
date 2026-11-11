"""시트에 쓰기 — amount 시트 거래대금상위의 theme·reason, 종목 탭의 memo, surge 시트(일지) 이력의 theme·telegram.

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
def _make_client():
    """키가 있을 때만 접속을 만들어 기억한다. 키가 없으면 오류를 내서 '없음'은 기억하지 않는다
    (Secrets 를 나중에 넣어도 앱을 다시 켜지 않고 바로 쓰이게)."""
    import gspread
    info = _secret("gcp_service_account")
    if info:
        return gspread.service_account_from_dict(dict(info))
    path = os.environ.get("SURGE_KEY_FILE")
    if path:
        return gspread.service_account(filename=path)
    raise LookupError("no key")


def _client():
    try:
        return _make_client()
    except LookupError:
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


def _clean(v):
    """칸에 넣을 글자: 공백 정리, 'null' 은 빈 칸."""
    v = " ".join((v or "").split())
    return "" if v.lower() == "null" else v


def _same(f, old):
    """비교용 원래 값. 이력 telegram 칸은 앞의 '* ' 표시를 떼고 본다(화면도 떼고 보여 준다)."""
    old = old.strip()
    return old.removeprefix("* ") if f == "telegram" else old


def _load(sid, tab):
    ws = _client().open_by_key(sid).worksheet(tab)
    vals = ws.get_all_values()
    return ws, vals, {n: i for i, n in enumerate(vals[0])}


def _write(ws, h, upd):
    from gspread.utils import rowcol_to_a1
    if upd:
        ws.batch_update([{"range": rowcol_to_a1(i, h[f] + 1), "values": [[v]]} for (i, f), v in upd.items()],
                        value_input_option="RAW")


def _apply(vals, h, edits, upd):
    """edits = {(date, code): {칸 제목: 값}}. 바뀐 칸만 upd[(줄, 칸)] 에 넣고 vals 도 고친다."""
    for i, r in enumerate(vals[1:], start=2):
        e = edits.get((r[h["date"]], r[h["code"]]))
        for f, v in (e or {}).items():
            if f not in h:
                continue
            new = _clean(v)
            if new == _same(f, r[h[f]]):
                continue
            if f == "telegram" and new and r[h[f]].strip().startswith("* "):
                new = "* " + new  # 원래 있던 표시는 그대로 둔다
            upd[(i, f)] = r[h[f]] = new


def save(amount_edits=None, hist_edits=None):
    """amount_edits: 거래대금상위 {(date, code): {"theme", "reason"}}, hist_edits: 일지 이력 {(date, code): {"theme", "telegram"}}.
    바뀐 칸만 쓰고, 빈 테마 칸은 이렇게 채운다(사용자 결정 2026-11-11, 빈 칸만):
      · 거래대금상위: 고친 종목의 테마가 한 가지뿐이면 그 종목의 다른 날짜 빈 칸
      · 같은 날·같은 종목: 거래대금상위 ↔ 일지 이력 서로
    방금 직접 고친 칸은 채우기로 덮지 않는다(null 로 비운 칸이 다시 차지 않게). 쓴 칸 수를 돌려준다."""
    amount_edits, hist_edits = amount_edits or {}, hist_edits or {}
    aws, av, ah = _load(db.AMOUNT_SHEET_ID, "거래대금상위")
    hws, hv, hh = _load(db.sheet_id(), "이력")
    au, hu = {}, {}
    _apply(av, ah, amount_edits, au)
    _apply(hv, hh, hist_edits, hu)
    mine_a, mine_h = set(au), set(hu)
    keys = set(amount_edits) | set(hist_edits)
    codes = {c for _, c in keys}

    known = {}
    for r in av[1:]:
        if r[ah["theme"]].strip():
            known.setdefault(r[ah["code"]], set()).add(r[ah["theme"]].strip())
    for i, r in enumerate(av[1:], start=2):
        c = r[ah["code"]]
        if c in codes and not r[ah["theme"]].strip() and len(known.get(c, ())) == 1 and (i, "theme") not in mine_a:
            au[(i, "theme")] = r[ah["theme"]] = next(iter(known[c]))

    arow = {(r[ah["date"]], r[ah["code"]]): (i, r) for i, r in enumerate(av[1:], start=2)}
    hrow = {(r[hh["date"]], r[hh["code"]]): (i, r) for i, r in enumerate(hv[1:], start=2)}
    for k in keys:
        if k in arow and k in hrow:
            (ai, ar), (hi, hr) = arow[k], hrow[k]
            a, b = ar[ah["theme"]].strip(), hr[hh["theme"]].strip()
            if a and not b and (hi, "theme") not in mine_h:
                hu[(hi, "theme")] = hr[hh["theme"]] = a
            elif b and not a and (ai, "theme") not in mine_a:
                au[(ai, "theme")] = ar[ah["theme"]] = b

    _write(aws, ah, au)
    _write(hws, hh, hu)
    if au or hu:
        st.cache_data.clear()
    return len(au) + len(hu)


def rename_theme(old, new):
    """두 시트(거래대금상위·일지 이력)의 모든 칸에서 테마 old 를 new 로 바꾼다. new 는 쉼표로 여러 개도 된다.
    이미 같은 테마가 있는 칸은 겹치지 않게 한 번만 둔다. 쓴 칸 수를 돌려준다."""
    to = db.split_themes(_clean(new))
    if not to:
        raise ValueError("새 테마 이름이 비었습니다")
    n = 0
    for sid, tab in ((db.AMOUNT_SHEET_ID, "거래대금상위"), (db.sheet_id(), "이력")):
        ws, vals, h = _load(sid, tab)
        upd = {}
        for i, r in enumerate(vals[1:], start=2):
            ts = db.split_themes(r[h["theme"]])
            if old not in ts:
                continue
            out = []
            for t in ts:
                for x in (to if t == old else [t]):
                    if x not in out:
                        out.append(x)
            v = ", ".join(out)
            if v != r[h["theme"]].strip():
                upd[(i, "theme")] = v
        _write(ws, h, upd)
        n += len(upd)
    if n:
        st.cache_data.clear()
    return n


def form(key, sections, on_save):
    """입력 칸 묶음. sections = [(제목, [{"id", "title", "fields": [(칸, 안내 글자, 지금 값)]}])].
    저장을 누르면 바뀐 칸만 on_save({id: {칸: 새 값}}) 로 넘기고, 돌려받은 쓴 칸 수를 보여 준다."""
    import html
    with st.form(key):
        for title, items in sections:
            if not items:
                continue
            if title:
                st.markdown(f"<div class='sec'>{html.escape(title)}</div>", unsafe_allow_html=True)
            for it in items:
                st.markdown(f"<div class='ft'>{html.escape(it['title'])}</div>", unsafe_allow_html=True)
                fs = it["fields"]
                cols = st.columns([1] + [1.4] * (len(fs) - 1)) if len(fs) > 1 else [st]
                for col, (f, ph, v) in zip(cols, fs):
                    col.text_input(ph, value=v or "", key=f"{key}|{it['id']}|{f}", placeholder=ph,
                                   label_visibility="collapsed")
        if not st.form_submit_button("저장", type="primary", use_container_width=True):
            return
    ch = {}
    for _, items in sections:
        for it in items:
            for f, _ph, v in it["fields"]:
                new = st.session_state.get(f"{key}|{it['id']}|{f}", v or "")
                if " ".join(new.split()) != " ".join((v or "").split()):
                    ch.setdefault(it["id"], {})[f] = new
    if not ch:
        st.info("바뀐 칸이 없습니다.")
        return
    try:
        n = on_save(ch)
        st.success(f"저장했습니다 · 바뀐 칸 {n}개" if n else "바뀐 칸이 없습니다.")
    except Exception as e:
        st.error(f"저장하지 못했습니다: {type(e).__name__}: {str(e)[:200]}")


MANUAL_TAB = "관심종목"  # 사용자가 직접 넣은 종목 (name, theme, comment=한줄평, added). 다른 스크립트는 이 탭을 쓰지 않는다.


def _manual(create=False):
    """관심종목 탭과 (전체 값, 칸 제목→번호). 탭이 없으면 create 일 때만 만든다."""
    import gspread
    ss = _client().open_by_key(db.AMOUNT_SHEET_ID)
    try:
        ws = ss.worksheet(MANUAL_TAB)
    except gspread.WorksheetNotFound:
        if not create:
            return None, [], {}
        ws = ss.add_worksheet(MANUAL_TAB, rows=200, cols=4)
        ws.update(range_name="A1:D1", values=[["name", "theme", "comment", "added"]])
    vals = ws.get_all_values()
    return ws, vals, {n: i for i, n in enumerate(vals[0])}


def _cell(r, h, f):
    return r[h[f]].strip() if h[f] < len(r) else ""


def add_to_interest(names, theme=""):
    """종목명(코드 없이)을 관심종목에 넣는다. 이미 있으면 theme 이 있을 때 테마만 더한다.
    (새로 만든 종목 수, 테마를 더한 종목 수)를 돌려준다."""
    from datetime import datetime
    ws, vals, h = _manual(create=True)
    have = {_cell(r, h, "name"): (i, r) for i, r in enumerate(vals[1:], start=2) if _cell(r, h, "name")}
    th = db.split_themes(_clean(theme))
    new_rows, upd, seen = [], {}, set()
    for name in names:
        name = " ".join((name or "").split())
        if not name or name in seen:
            continue
        seen.add(name)
        if name in have:
            i, r = have[name]
            cur = db.split_themes(_cell(r, h, "theme"))
            merged = cur + [t for t in th if t not in cur]
            if merged != cur:
                upd[(i, "theme")] = ", ".join(merged)
        else:
            row = [""] * len(vals[0])
            row[h["name"]], row[h["theme"]] = name, ", ".join(th)
            if "added" in h:
                row[h["added"]] = datetime.now().strftime("%Y-%m-%d")
            new_rows.append(row)
    _write(ws, h, upd)
    if new_rows:
        ws.append_rows(new_rows, value_input_option="RAW")
    if upd or new_rows:
        st.cache_data.clear()
    return len(new_rows), len(upd)


def save_manual(name, theme=None, comment=None):
    """관심종목의 테마·한줄평을 고친다(None 이면 그 칸은 그대로). 줄이 없으면 False."""
    ws, vals, h = _manual()
    for i, r in enumerate(vals[1:], start=2):
        if _cell(r, h, "name") == name:
            upd = {}
            if theme is not None:
                upd[(i, "theme")] = ", ".join(db.split_themes(_clean(theme)))
            if comment is not None:
                upd[(i, "comment")] = " ".join(comment.split())  # 한줄평은 한 줄로
            _write(ws, h, upd)
            st.cache_data.clear()
            return True
    return False


def remove_manual(name):
    """관심종목에서 종목을 뺀다(줄 삭제). 지운 줄이 있으면 True."""
    ws, vals, h = _manual()
    for i, r in enumerate(vals[1:], start=2):
        if _cell(r, h, "name") == name:
            ws.delete_rows(i)
            st.cache_data.clear()
            return True
    return False


def remove_theme(names, theme):
    """관심종목 줄들에서 테마 하나만 뺀다(종목은 관심종목에 남는다). 바뀐 줄 수를 돌려준다."""
    ws, vals, h = _manual()
    upd = {}
    for i, r in enumerate(vals[1:], start=2):
        if _cell(r, h, "name") in names:
            cur = db.split_themes(_cell(r, h, "theme"))
            if theme in cur:
                upd[(i, "theme")] = ", ".join(t for t in cur if t != theme)
    _write(ws, h, upd)
    if upd:
        st.cache_data.clear()
    return len(upd)


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
