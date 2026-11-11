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


def _tok():
    """비밀번호에서 만든 확인값(비밀번호 자체가 아니다). 비밀번호를 바꾸면 예전 확인값은 저절로 못 쓰게 된다."""
    import hashlib
    import hmac
    return hmac.new(str(_secret("EDIT_PASSWORD")).encode(), b"surge-edit-v1", hashlib.sha256).hexdigest()


_BRIDGE_JS = """<script>
// 로그인 기억: 이 기기(브라우저)의 localStorage 에 확인값을 두고, 새 화면이 열리면 숨은 입력 칸으로 서버에 보낸다.
// (Streamlit Cloud 는 쿠키를 앱에 전달하지 않아서 localStorage 를 쓴다. 주소에는 아무것도 남기지 않는다.)
const KEY = 'surge_edit_tok';
const SAVE = %s;
try {
  if (SAVE) { localStorage.setItem(KEY, SAVE); }
  const saved = localStorage.getItem(KEY);
  const doc = window.parent.document;
  const send = () => {
    const inp = doc.querySelector('input[aria-label="edit_tok_bridge"]');
    if (!inp || !saved || inp.value === saved) return !!inp;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(inp, saved);
    inp.dispatchEvent(new Event('input', {bubbles: true}));
    inp.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
    inp.blur();
    return true;
  };
  if (!SAVE && saved) { let n = 0; const t = setInterval(() => { if (send() || ++n > 20) clearInterval(t); }, 250); }
} catch (e) {}
</script>"""


def unlocked():
    """비밀번호를 맞게 넣었으면 True. 아니면 입력 칸을 보여 주고 False.
    한 번 맞게 넣으면 이 기기가 기억해서(localStorage), 화면이 새로 열리거나 폰이 다시 연결돼도 다시 묻지 않는다.
    비밀번호(EDIT_PASSWORD)를 바꾸면 기억된 값은 저절로 못 쓰게 된다."""
    import hmac
    import streamlit.components.v1 as components
    if not available():
        st.info("입력 기능이 아직 켜지지 않았습니다. 앱 Secrets 에 서비스 계정 키와 EDIT_PASSWORD 를 넣어야 합니다.")
        return False
    got = st.session_state.get("edit_tok_bridge", "")
    if st.session_state.get("edit_ok") or (got and hmac.compare_digest(got, _tok())):
        st.session_state["edit_ok"] = True
        if st.session_state.pop("edit_remember", False):  # 방금 로그인했으면 이 기기에 기억을 남긴다
            components.html(_BRIDGE_JS % repr(_tok()), height=0)
        return True
    pw = st.text_input("비밀번호 (한 번 넣으면 이 기기가 기억합니다)", type="password", key="edit_pw")
    st.text_input("edit_tok_bridge", key="edit_tok_bridge", label_visibility="collapsed")  # 숨은 칸: 기억된 값이 들어온다
    components.html(_BRIDGE_JS % "''", height=0)
    if st.query_params.get("dbg"):
        st.caption(f"기기 기억 수신: {'있음' if got else '없음'}")
    if pw:
        if pw == str(_secret("EDIT_PASSWORD")):
            st.session_state["edit_ok"] = True
            st.session_state["edit_remember"] = True
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
    ws, vals, h = _manual()  # 관심종목의 테마도
    if ws is not None:
        upd = {}
        for i, r in enumerate(vals[1:], start=2):
            ts = db.split_themes(_cell(r, h, "theme"))
            if old in ts:
                out = []
                for t in ts:
                    for x in (to if t == old else [t]):
                        if x not in out:
                            out.append(x)
                upd[(i, "theme")] = ", ".join(out)
        _write(ws, h, upd)
        n += len(upd)
    _registry_replace(old, to)  # 테마목록도
    st.cache_data.clear()
    return n


def form(key, sections, on_save):
    """입력 칸 묶음. sections = [(제목, [{"id", "title", "fields": [(칸, 안내 글자, 지금 값[, "theme"])]}])].
    네 번째 값이 "theme" 인 칸은 테마목록에서 고르는 선택 목록(스크롤·검색, 여러 개)이고, 나머지는 글자 칸이다.
    저장을 누르면 바뀐 칸만 on_save({id: {칸: 새 값}}) 로 넘기고, 돌려받은 쓴 칸 수를 보여 준다."""
    import html
    all_themes = db.all_themes()
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
                for col, fld in zip(cols, fs):
                    f, ph, v = fld[:3]
                    k = f"{key}|{it['id']}|{f}"
                    if len(fld) > 3 and fld[3] == "theme":
                        cur = db.split_themes(v)  # 목록에 없는 옛 테마도 보이게 한다(잃어버리지 않게)
                        col.multiselect(ph, sorted(set(all_themes) | set(cur)), default=cur, key=k,
                                        placeholder="테마 선택", label_visibility="collapsed")
                    else:
                        col.text_input(ph, value=v or "", key=k, placeholder=ph, label_visibility="collapsed")
        if not st.form_submit_button("저장", type="primary", use_container_width=True):
            return
    ch = {}
    for _, items in sections:
        for it in items:
            for fld in it["fields"]:
                f, _ph, v = fld[:3]
                raw = st.session_state.get(f"{key}|{it['id']}|{f}")
                if len(fld) > 3 and fld[3] == "theme":
                    cur = db.split_themes(v)
                    new = list(raw) if raw is not None else cur
                    if set(new) != set(cur):  # 순서만 다른 건 바뀐 게 아니다
                        ch.setdefault(it["id"], {})[f] = ", ".join(new)
                else:
                    new = raw if raw is not None else (v or "")
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


MANUAL_TAB = "관심종목"  # code, name, theme, comment(한줄평), added — 사용자가 고른 관심종목. 다른 스크립트는 이 탭을 쓰지 않는다.
MANUAL_HEAD = ["code", "name", "theme", "comment", "added"]
THEME_TAB = "테마목록"  # theme, added — 테마를 고를 때 쓰는 목록(고유값). lists_sync.py 가 시트에 이미 적힌 테마를 더한다.
THEME_HEAD = ["theme", "added"]


def _tab(title, header, create=False):
    """amount 시트의 탭과 (전체 값, 칸 제목→번호). 없으면 create 일 때만 header 와 함께 만든다. 없으면 (None, [], {})."""
    import gspread
    ss = _client().open_by_key(db.AMOUNT_SHEET_ID)
    try:
        ws = ss.worksheet(title)
    except gspread.WorksheetNotFound:
        if not create:
            return None, [], {}
        ws = ss.add_worksheet(title, rows=200, cols=len(header))
        ws.update(range_name=f"A1:{chr(64 + len(header))}1", values=[header])
    vals = ws.get_all_values()
    return ws, vals, {n: i for i, n in enumerate(vals[0])}


def _migrate_manual(ws, vals, h):
    """예전 형식(코드 칸 없이 종목명만)의 관심종목 탭을 새 형식으로 옮긴다. 이름은 DB 종목목록에서 찾고(대소문자 무시),
    같은 종목은 합친다. 찾지 못한 이름이 있으면 아무것도 바꾸지 않고 ValueError."""
    by = {}
    for u in db.universe():
        by.setdefault(u["name"].casefold(), []).append(u["code"])
    names = db.universe_names()
    out, lost = {}, []
    for r in vals[1:]:
        g = lambda f: r[h[f]].strip() if f in h and h[f] < len(r) else ""
        if not g("name"):
            continue
        codes = by.get(g("name").casefold(), [])
        if len(codes) != 1:
            lost.append(g("name"))
            continue
        cur = out.setdefault(codes[0], {"theme": [], "comment": [], "added": g("added")})
        cur["theme"] += [t for t in db.split_themes(g("theme")) if t not in cur["theme"]]
        if g("comment") and g("comment") not in cur["comment"]:
            cur["comment"].append(g("comment"))
        cur["added"] = min(x for x in (cur["added"], g("added")) if x) if (cur["added"] or g("added")) else ""
    if lost:
        raise ValueError(f"관심종목 탭의 옛 항목을 DB 종목에서 찾지 못했습니다: {', '.join(lost[:5])}")
    new = [MANUAL_HEAD] + [[c, names[c], ", ".join(d["theme"]), " / ".join(d["comment"]), d["added"]]
                           for c, d in out.items()]
    ws.clear()
    ws.update(range_name=f"A1:E{len(new)}", values=new, value_input_option="RAW")


def _manual(create=False):
    ws, vals, h = _tab(MANUAL_TAB, MANUAL_HEAD, create)
    if ws is not None and vals and "code" not in h and "name" in h:  # 예전 형식이면 새 형식으로 옮기고 다시 읽는다
        _migrate_manual(ws, vals, h)
        vals = ws.get_all_values()
        h = {n: i for i, n in enumerate(vals[0])}
    return ws, vals, h


def _cell(r, h, f):
    return r[h[f]].strip() if f in h and h[f] < len(r) else ""


def _today():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def add_to_interest(codes, theme=""):
    """DB 종목목록에 있는 종목(코드)만 관심종목에 넣는다. 이미 있으면 theme 이 있을 때 테마만 더한다.
    (새로 만든 종목 수, 테마를 더한 종목 수)를 돌려준다. 목록에 없는 코드가 있으면 ValueError."""
    uni = db.universe_names()
    codes = list(dict.fromkeys(c.strip() for c in codes if c and c.strip()))
    bad = [c for c in codes if c not in uni]
    if bad:
        raise ValueError(f"DB 종목목록에 없는 종목입니다: {', '.join(bad[:5])}")
    ws, vals, h = _manual(create=True)
    have = {_cell(r, h, "code"): (i, r) for i, r in enumerate(vals[1:], start=2) if _cell(r, h, "code")}
    th = db.split_themes(_clean(theme))
    new_rows, upd = [], {}
    for code in codes:
        if code in have:
            i, r = have[code]
            cur = db.split_themes(_cell(r, h, "theme"))
            merged = cur + [t for t in th if t not in cur]
            if merged != cur:
                upd[(i, "theme")] = ", ".join(merged)
        else:
            row = [""] * len(vals[0])
            for f, x in (("code", code), ("name", uni[code]), ("theme", ", ".join(th)), ("added", _today())):
                if f in h:
                    row[h[f]] = x
            new_rows.append(row)
    _write(ws, h, upd)
    if new_rows:
        ws.append_rows(new_rows, value_input_option="RAW")
    if upd or new_rows:
        st.cache_data.clear()
    return len(new_rows), len(upd)


def save_manual(code, theme=None, comment=None):
    """관심종목의 테마·한줄평을 고친다(None 이면 그 칸은 그대로). 줄이 없으면 False."""
    ws, vals, h = _manual()
    for i, r in enumerate(vals[1:], start=2):
        if _cell(r, h, "code") == code:
            upd = {}
            if theme is not None:
                upd[(i, "theme")] = ", ".join(db.split_themes(_clean(theme)))
            if comment is not None:
                upd[(i, "comment")] = " ".join(comment.split())  # 한줄평은 한 줄로
            _write(ws, h, upd)
            st.cache_data.clear()
            return True
    return False


def remove_manual(code):
    """관심종목에서 종목을 뺀다(줄 삭제). 지운 줄이 있으면 True."""
    ws, vals, h = _manual()
    for i, r in enumerate(vals[1:], start=2):
        if _cell(r, h, "code") == code:
            ws.delete_rows(i)
            st.cache_data.clear()
            return True
    return False


def remove_theme(codes, theme):
    """관심종목 줄들에서 테마 하나만 뺀다(종목은 관심종목에 남는다). 바뀐 줄 수를 돌려준다."""
    ws, vals, h = _manual()
    upd = {}
    for i, r in enumerate(vals[1:], start=2):
        if _cell(r, h, "code") in codes:
            cur = db.split_themes(_cell(r, h, "theme"))
            if theme in cur:
                upd[(i, "theme")] = ", ".join(t for t in cur if t != theme)
    _write(ws, h, upd)
    if upd:
        st.cache_data.clear()
    return len(upd)


# ── 테마 목록(고유값) ─────────────────────────────────────────────────────────────

def _theme_key(t):
    """같은 이름인지 볼 때 쓰는 값: 공백을 없애고 소문자로."""
    import re
    return re.sub(r"\s+", "", t or "").casefold()


def add_theme(name):
    """테마목록에 새 테마를 넣는다. 같은 이름(공백·대소문자만 다른 것 포함)·쉼표가 든 이름·null 은 ValueError.
    넣은 이름을 돌려준다."""
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("테마 이름이 비었습니다.")
    if "," in name:
        raise ValueError("테마 이름에는 쉼표를 쓸 수 없습니다. 쉼표는 여러 테마를 나누는 글자입니다.")
    if name.lower() == "null":
        raise ValueError("null 은 테마 이름으로 쓸 수 없습니다.")
    ws, vals, h = _tab(THEME_TAB, THEME_HEAD, create=True)
    key = _theme_key(name)
    same = next((t for t in list(db.all_themes()) + [r[0] for r in vals[1:] if r] if _theme_key(t) == key), None)
    if same:
        raise ValueError(f"이미 있는 테마입니다: {same}")
    ws.append_rows([[name, _today()]], value_input_option="RAW")
    st.cache_data.clear()
    return name


def _uses(theme):
    """그 테마를 쓰는 칸 수(일지 이력·거래대금상위·관심종목)."""
    n = 0
    for rows in (db.history(), db.volume(), db.manual_stocks()):
        n += sum(1 for r in rows if theme in db.split_themes(r["theme"]))
    return n


def delete_theme(theme):
    """테마목록에서 테마를 지운다. 쓰는 칸이 하나라도 있으면 ValueError(먼저 다른 테마로 바꾸거나 빼야 한다)."""
    n = _uses(theme)
    if n:
        raise ValueError(f"{n}개 칸에서 쓰고 있어서 지울 수 없습니다.")
    ws, vals, h = _tab(THEME_TAB, THEME_HEAD)
    if ws is None:
        return 0
    gone = 0
    for i in range(len(vals) - 1, 0, -1):  # 아래에서부터 지워야 줄 번호가 안 밀린다
        if vals[i] and vals[i][0].strip() == theme:
            ws.delete_rows(i + 1)
            gone += 1
    if gone:
        st.cache_data.clear()
    return gone


def _registry_replace(old, to):
    """이름을 바꿀 때 테마목록도 맞춘다: old 줄을 지우고, to 의 이름 중 목록에 없는 것을 더한다."""
    ws, vals, h = _tab(THEME_TAB, THEME_HEAD, create=True)
    have = {_theme_key(r[0]) for r in vals[1:] if r and r[0].strip() and r[0].strip() != old}
    for i in range(len(vals) - 1, 0, -1):
        if vals[i] and vals[i][0].strip() == old:
            ws.delete_rows(i + 1)
    add = [[t, _today()] for t in to if _theme_key(t) not in have]
    if add:
        ws.append_rows(add, value_input_option="RAW")


def theme_box(key="new_theme"):
    """'➕ 새 테마' 입력 칸. 이름을 쓰고 Enter 를 누르면 바로 테마목록에 들어가고, 선택 목록에 바로 나온다."""
    def done():
        name = st.session_state.get(key, "")
        if not name.strip():
            return
        try:
            st.toast(f"테마를 추가했습니다: {add_theme(name)}", icon="✅")
            st.session_state[key] = ""
        except ValueError as e:
            st.toast(str(e), icon="⚠️")
        except Exception as e:
            st.toast(f"추가하지 못했습니다: {type(e).__name__}: {str(e)[:100]}", icon="⚠️")

    st.text_input("➕ 새 테마 (이름을 쓰고 Enter)", key=key, on_change=done, placeholder="새 테마 이름")


def pick_stock(key, theme="", label="➕ 종목 추가"):
    """DB 종목목록에서 이름·코드를 검색해 고르면 바로 관심종목에 넣는다(theme 이 있으면 그 테마도 붙인다). 추가 버튼은 없다."""
    uni = {u["code"]: u for u in db.universe()}
    if not uni:
        st.info("종목 목록(amount 시트 종목목록 탭)을 읽지 못했습니다. 컴퓨터에서 lists_sync.py 가 한 번 돌아야 합니다.")
        return
    have = {m["code"] for m in db.manual_stocks() if not theme or theme in db.split_themes(m["theme"])}

    def done():
        code = st.session_state.get(key)
        if not code:
            return
        try:
            add_to_interest([code], theme)
            st.toast(f"{uni[code]['name']} 추가했습니다" + (f" → {theme}" if theme else " → 관심종목"), icon="✅")
        except Exception as e:
            st.toast(f"추가하지 못했습니다: {str(e)[:100]}", icon="⚠️")
        st.session_state[key] = None  # 다음 종목을 바로 고를 수 있게 비운다

    st.selectbox(label, [c for c in uni if c not in have], index=None, key=key, on_change=done,
                 format_func=lambda c: f"{uni[c]['name']}  {c}  {uni[c]['market']}",
                 placeholder="이름이나 코드로 검색해서 고르면 바로 추가됩니다")


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
