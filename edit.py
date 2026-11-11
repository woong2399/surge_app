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


def banner(text):
    """수정 중임을 눈에 띄게 알리는 띠."""
    import html
    st.markdown(f"<div class='editbar'>✏️ <b>수정 중</b> · {html.escape(text)}</div>", unsafe_allow_html=True)


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


# ── 테마 목록(고유값) ─────────────────────────────────────────────────────────────


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


# ── 종목 화면 수정: 테마(이미 있는 테마로 연결·오타 확인)·거래대금 이유·한줄평·관심종목 ───────────────────
# 모두 '쓰고 Enter' 로 바로 저장된다(저장 버튼 없음). 콜백(on_*)은 위젯의 on_change 로 건다.

def _norm(t):
    """테마 이름 비교값: 글자·숫자만 남기고 소문자로. 공백·괄호·가운뎃점만 다른 이름은 같은 테마로 본다."""
    import re
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t or "").casefold()


_theme_key = _norm


def _lev(a, b):
    """두 글자열의 편집 거리(글자 하나 바꾸기·넣기·빼기 횟수)."""
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def theme_resolve(text):
    """입력한 테마 글을 이미 있는 테마와 맞춘다. 쉼표로 나눠 하나씩:
      · 이미 있는 테마(공백·괄호·대소문자만 달라도) → 그 이름 (문자열)
      · 비슷한 테마가 있음(오타 같음: 반도채→반도체, 앞부분만 쓴 반도→반도체…) → ("?", 입력, [후보…]) 로 물어봐야 함
      · 없는 이름 → 새 테마 (문자열, 저장할 때 테마목록에 등록)"""
    by = {}
    for t in db.all_themes():
        by.setdefault(_norm(t), t)
    out = []
    for t in db.split_themes(_clean(text)):
        k = _norm(t)
        if not k:
            continue
        if k in by:
            out.append(by[k])
            continue
        lim = 1 if len(k) <= 4 else 2
        cands = [n for kk, n in by.items() if abs(len(kk) - len(k)) <= lim and _lev(k, kk) <= lim]
        cands += [n for kk, n in by.items() if len(k) >= 2 and kk.startswith(k) and n not in cands]
        out.append(("?", t, cands[:3]) if cands else t)
    return out


def _commit_names(items):
    """정해진 이름들(문자열)을 돌려준다. 테마목록에 없는 새 이름은 여기서 등록한다."""
    known = {_norm(t) for t in db.all_themes()}
    names = []
    for t in items:
        if _norm(t) not in known:
            add_theme(t)
            known.add(_norm(t))
        if t not in names:
            names.append(t)
    return names


def save_day_theme(date, code, text):
    """그날 그 종목의 테마를, 그 줄이 있는 시트(거래대금상위·일지 이력)마다 쓴다. 쓴 칸 수를 돌려준다."""
    ae = {(date, code): {"theme": text}} if any(r["date"] == date and r["code"] == code for r in db.volume()) else {}
    he = {(date, code): {"theme": text}} if any(r["date"] == date and r["code"] == code for r in db.history()) else {}
    return save(amount_edits=ae, hist_edits=he)


def _apply_theme(kind, args, key, items):
    try:
        text = ", ".join(_commit_names(items))
        if kind == "day":
            save_day_theme(args[0], args[1], text)
        else:
            save_manual(args[0], theme=text)
        st.session_state[key] = db.split_themes(text)  # 칸에는 연결된(고쳐진) 이름을 보여 준다
        st.toast("저장했습니다", icon="✅")
    except Exception as e:
        st.toast(f"저장하지 못했습니다: {str(e)[:100]}", icon="⚠️")


def on_theme(kind, args, key):
    """테마 칸에서 Enter. kind: 'day'(날짜별, args=(날짜, 코드)) 또는 'manual'(관심종목, args=(코드,))."""
    raw = st.session_state.get(key, "")
    items = theme_resolve(", ".join(raw) if isinstance(raw, list) else raw)
    if any(isinstance(i, tuple) for i in items):  # 오타 같은 게 있으면 저장하지 않고 먼저 물어본다
        st.session_state["theme_pending"] = {"kind": kind, "args": args, "key": key, "items": items}
        return
    _apply_theme(kind, args, key, items)


def _ask_pick(i, name):
    p = st.session_state.get("theme_pending")
    if not p:
        return
    p["items"][i] = name
    if not any(isinstance(it, tuple) for it in p["items"]):
        st.session_state.pop("theme_pending")
        _apply_theme(p["kind"], p["args"], p["key"], p["items"])


def _ask_cancel():
    p = st.session_state.pop("theme_pending", None)
    if p:
        st.session_state.pop(p["key"], None)  # 칸을 원래 값으로 되돌린다


def theme_ask_ui():
    """오타 같은 테마가 있으면 '혹시 ○○?' 하고 묻는다. 고르면 이어서 저장한다."""
    import html
    p = st.session_state.get("theme_pending")
    if not p:
        return
    i = next(n for n, it in enumerate(p["items"]) if isinstance(it, tuple))
    _, typed, cands = p["items"][i]
    st.markdown(f"<div class='editbar'>‘{html.escape(typed)}’ 는 목록에 없는 테마예요. 혹시 "
                f"<b>{html.escape(' / '.join(cands))}</b> 인가요?</div>", unsafe_allow_html=True)
    cols = st.columns(len(cands) + 2)
    for c, cand in zip(cols, cands):
        c.button(cand, key=f"ta_{i}_{cand}", on_click=_ask_pick, args=(i, cand))
    cols[-2].button(f"새 테마 ‘{typed}’", key=f"ta_new_{i}", on_click=_ask_pick, args=(i, typed))
    cols[-1].button("취소", key=f"ta_cancel_{i}", on_click=_ask_cancel)


def theme_select(label, value, key, kind, args, container=None):
    """테마 칸: 스크롤·검색으로 고르거나 새로 쓸 수 있는 선택 목록(여러 개). 바꾸면 바로 저장한다(오타 같으면 먼저 물어봄).
    value 는 지금 값(쉼표로 이은 글), kind·args 는 on_theme 참고."""
    cur = db.split_themes(value)
    (container or st).multiselect(label, sorted(set(db.all_themes()) | set(cur)), default=cur, key=key,
                                  on_change=on_theme, args=(kind, args, key), accept_new_options=True,
                                  placeholder="테마 고르기(스크롤·검색) 또는 새로 쓰기", label_visibility="collapsed")


# ── 테마 정리: 이름 바꾸기·합치기 (테마 화면) ─────────────────────────────────────────────

def _final_name(old, new):
    """새 이름을 정리한다. 이미 있는 다른 테마와 같은 이름(공백·괄호·대소문자만 달라도)이면 그 이름으로 합친다.
    (정리된 이름, 이미 있는 다른 테마와 합치는지). 쓸 수 없는 이름이면 ValueError."""
    new = " ".join((new or "").split())
    if not new:
        raise ValueError("새 이름이 비었습니다.")
    if "," in new:
        raise ValueError("새 이름에는 쉼표를 쓸 수 없습니다. 테마 하나의 이름만 쓰세요.")
    if new.lower() == "null":
        raise ValueError("null 은 테마 이름으로 쓸 수 없습니다.")
    if _norm(new) == _norm(old):  # 띄어쓰기·대소문자만 고치는 경우
        if new == old:
            raise ValueError("이름이 그대로입니다.")
        return new, False
    by = {_norm(t): t for t in db.all_themes() if t != old}
    if _norm(new) in by:
        return by[_norm(new)], True
    return new, False


def rename_preview(old, new):
    """바꾸면 어떻게 되는지 미리 본다(시트에는 쓰지 않는다). {"final", "merged", "이력", "거래대금상위", "관심종목", "similar"}.
    쓸 수 없는 이름이면 ValueError."""
    final, merged = _final_name(old, new)
    n = lambda rows: sum(1 for r in rows if old in db.split_themes(r["theme"]))
    others = [t for t in db.all_themes() if t != old]
    k = _norm(final)
    lim = 1 if len(k) <= 4 else 2
    similar = [] if merged else [t for t in others if abs(len(_norm(t)) - len(k)) <= lim and _lev(k, _norm(t)) <= lim][:3]
    return {"final": final, "merged": merged, "이력": n(db.history()), "거래대금상위": n(db.volume()),
            "관심종목": n(db.manual_stocks()), "similar": similar}


def _replace_tokens(cell, old, to):
    ts = db.split_themes(cell)
    if old not in ts:
        return None
    out = []
    for t in ts:
        t = to if t == old else t
        if t not in out:  # 이미 있으면 한 번만
            out.append(t)
    return ", ".join(out)


def rename_theme(old, new):
    """모든 탭(이력·거래대금상위·관심종목)의 테마 old 를 새 이름으로 바꾸고 테마목록도 맞춘다. 쉼표로 나뉜 테마를 하나씩
    정확히 비교하므로 다른 이름(반도체(장비) 등)은 건드리지 않는다. (바뀐 칸 수, 최종 이름)을 돌려준다."""
    final, _ = _final_name(old, new)
    jobs = []
    for sid, tab in ((db.AMOUNT_SHEET_ID, "거래대금상위"), (db.sheet_id(), "이력")):
        ws, vals, h = _load(sid, tab)
        jobs.append((ws, h, {(i, "theme"): x for i, r in enumerate(vals[1:], start=2)
                             if (x := _replace_tokens(_cell(r, h, "theme"), old, final)) is not None}))
    ws, vals, h = _manual()
    if ws is not None:
        jobs.append((ws, h, {(i, "theme"): x for i, r in enumerate(vals[1:], start=2)
                             if (x := _replace_tokens(_cell(r, h, "theme"), old, final)) is not None}))
    for ws, h, upd in jobs:
        _write(ws, h, upd)
    tws, tvals, _h = _tab(THEME_TAB, THEME_HEAD, create=True)  # 테마목록: old 줄을 지우고 새 이름이 없으면 더한다
    have = {_norm(r[0]) for r in tvals[1:] if r and r[0].strip() and r[0].strip() != old}
    for i in range(len(tvals) - 1, 0, -1):  # 아래에서부터 지워야 줄 번호가 안 밀린다
        if tvals[i] and tvals[i][0].strip() == old:
            tws.delete_rows(i + 1)
    if _norm(final) not in have:
        tws.append_rows([[final, _today()]], value_input_option="RAW")
    st.cache_data.clear()
    return sum(len(u) for _, _, u in jobs), final


def on_reason(date, code, key):
    """거래대금 이유 칸에서 Enter."""
    try:
        save(amount_edits={(date, code): {"reason": st.session_state.get(key, "")}})
        st.toast("저장했습니다", icon="✅")
    except Exception as e:
        st.toast(f"저장하지 못했습니다: {str(e)[:100]}", icon="⚠️")


def on_comment(code, key):
    """관심종목 한줄평 칸에서 Enter."""
    try:
        save_manual(code, comment=st.session_state.get(key, ""))
        st.toast("저장했습니다", icon="✅")
    except Exception as e:
        st.toast(f"저장하지 못했습니다: {str(e)[:100]}", icon="⚠️")


def on_interest(code, key):
    """'⭐ 내 종목' 체크: 켜면 넣고, 끄면 뺀다(한줄평·테마도 함께 지워진다)."""
    try:
        if st.session_state.get(key):
            add_to_interest([code])
            st.toast("내 종목에 넣었습니다", icon="⭐")
        else:
            remove_manual(code)
            st.toast("내 종목에서 뺐습니다", icon="✅")
    except Exception as e:
        st.toast(f"처리하지 못했습니다: {str(e)[:100]}", icon="⚠️")


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
