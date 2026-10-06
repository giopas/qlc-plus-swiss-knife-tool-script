#!/usr/bin/env python3
"""tools/i18n_extract.py — the interface strings of Swiss Knife (v2.7.0).

The interface is translated by **the English text itself**: ``static/i18n/<lang>.json``
maps an English string to its translation, and ``static/js/i18n.js`` replaces
matching text, tooltips and placeholders as the page is drawn.  A string with
a changing part is a *pattern*: ``{0}``, ``{1}`` … stand for the parts in order
(``"{0} functions"``).  A string with no translation stays English.

This script lists every string the interface can show:

    python tools/i18n_extract.py                # how many, per source
    python tools/i18n_extract.py --keys         # one string per line
    python tools/i18n_extract.py --missing it   # what static/i18n/it.json lacks
    python tools/i18n_extract.py --json out.json  # {string: ""} to translate

Sources: the page (templates/index.html), the browser code (static/js/*.js:
HTML it builds, messages it shows) and the server messages (routes/*.py and
core/*.py: errors and messages that reach the screen).
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTRS = ("title", "placeholder", "data-tip", "data-desc", "data-tooltip", "aria-label", "alt")
_WORD = re.compile(r"[A-Za-zÀ-ÿ]{2}")


def norm(s: str) -> str:
    """The key of a text: whitespace collapsed (a string with a newline matches the same text on one line)."""
    return " ".join(s.replace(" ", " ").split())


_CODE = re.compile(r"""\)\.join|; return|\|\||&&|=>|\bfunction\b|\bconst\b|\bawait\b|\bnew \w+\(|querySelector|getElementById|\.map\(|\bnull\b.*\?|^\W+$|^[a-z]+(-[a-z0-9{}]+)+( [a-z0-9{}-]+)*$|^ ?--\w|^[A-Z][a-z]+[A-Z]\w+$|^[a-z][A-Za-z]+[A-Z]\w*$|^(Arrow|Key|Digit)\w+$|Content-Type|^application/|^text/|\bpx\b.*\{0\}|^\{0\}px|^\d[\d ]*\{0\}""")


_CODE_HTML = re.compile(r"^(<[\w.]+>[\w.]*|\.\w+|https?://\S+|[\w.-]+@[\w.-]+)$")


def worth(s: str) -> bool:
    s = norm(s)
    if _CODE.search(s):
        return False
    if len(s) < 2 or not _WORD.search(s):
        return False
    if re.fullmatch(r"[\w./:\\#%{}\-_@\[\]()=+*,;|<>$&?!'\"` ]*", s) and " " not in s and not s[0].isupper():
        return False                       # identifiers, paths, css classes, urls
    if re.match(r"^(https?://|/api/|/static/|[#.][\w-]+$|[a-z_]+\(.*\)$)", s):
        return False
    if re.fullmatch(r"[a-z0-9_.\-:/ ]+", s) and len(s.split()) <= 3 and not s[0].isupper() \
            and not re.fullmatch(r"[a-z]+( [a-z]+){1,2}", s):
        return False                       # css-ish lists, mime types, keys
    return True


# ── HTML ─────────────────────────────────────────────────────────────────────

class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        for k, v in attrs:
            if k in ATTRS and v:
                self.out.append(v)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def _placeholders(s: str, expr_names=None) -> str:
    """``${expr}`` → ``{0}``, ``{1}`` … in order."""
    n = [0]

    def sub(_m):
        i = n[0]
        n[0] += 1
        return "{%d}" % i
    return _expr_re.sub(sub, s)


def _strip_expr(s: str) -> str:
    """Replace every ``${…}`` (nested braces allowed) by ``\x00`` markers."""
    out, i = [], 0
    while i < len(s):
        if s.startswith("${", i):
            depth, j = 1, i + 2
            while j < len(s) and depth:
                depth += {"{": 1, "}": -1}.get(s[j], 0)
                j += 1
            out.append("\x00")
            i = j
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


_expr_re = re.compile(r"\x00")


def _from_html(text: str) -> list[str]:
    p = _P()
    try:
        p.feed(text)
    except Exception:  # noqa: BLE001
        pass
    return p.out


def html_strings() -> list[str]:
    s = open(os.path.join(ROOT, "templates", "index.html"), encoding="utf-8").read()
    s = re.sub(r"\{\{.*?\}\}", "", s)
    s = re.sub(r"\{%.*?%\}", "", s)
    return [norm(x) for x in _from_html(s) if _WORD.search(x) and len(norm(x)) >= 2 and not _CODE_HTML.search(norm(x))]


# ── JavaScript ───────────────────────────────────────────────────────────────

_JS_STR = re.compile(r"""'((?:\\.|[^'\\\n])*)'|"((?:\\.|[^"\\\n])*)"|`((?:\\.|[^`\\])*)`""", re.S)


def _unescape(s: str) -> str:
    return (s.replace("\\n", " ").replace("\\t", " ").replace("\\'", "'").replace('\\"', '"')
             .replace("\\`", "`").replace("\\u00a0", " ").replace("\\\\", "\\"))


def _js_literals(code: str):
    # drop comments (not inside strings: good enough for our own code)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    for m in _JS_STR.finditer(code):
        yield m.group(1) if m.group(1) is not None else m.group(2) if m.group(2) is not None else m.group(3)


_TAG = re.compile(r"</?[A-Za-z][^>]*>")


def js_strings() -> list[str]:
    out: list[str] = []
    d = os.path.join(ROOT, "static", "js")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".js") or fn == "i18n.js":
            continue
        code = open(os.path.join(d, fn), encoding="utf-8").read()
        for lit in _js_literals(code):
            raw = _unescape(lit)
            raw = _strip_expr(raw) if "${" in raw else raw
            if _TAG.search(raw):                       # HTML the code builds
                for piece in _from_html(raw):
                    piece = _placeholders(norm(piece))
                    if worth(piece.replace("\x00", "")):
                        out.append(piece)
            else:
                piece = _placeholders(norm(raw))
                if worth(piece):
                    out.append(piece)
    return out


# ── Python (server messages) ─────────────────────────────────────────────────

_PY_SKIP_CALLS = {"print", "add_argument", "getLogger", "debug", "info", "warning", "error", "exception",
                  "add_parser", "ArgumentParser", "compile", "match", "search", "sub", "fullmatch", "get", "pop",
                  "setdefault", "startswith", "endswith", "join", "split", "replace", "strip", "encode", "decode",
                  "open", "getenv", "environ", "find", "findall", "iter", "append_header", "add_header", "Blueprint",
                  "route", "setattr", "getattr", "hasattr", "isinstance", "writestr", "write", "exists", "isfile",
                  "isdir", "makedirs", "listdir", "walk", "normpath", "abspath", "expanduser", "SubElement",
                  "Element", "set", "attrib", "tag", "dumps", "loads", "mimetype", "send_file", "__import__",
                  "import_module", "run", "Popen", "check_output", "call", "which", "get_json", "args"}
_PY_LABEL_KEYS = {"label", "title", "name", "description", "hint", "text", "caption", "note", "warning",
                  "error", "message", "msg", "reason", "detail", "summary", "fix", "action"}


def _is_str(node) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)) or isinstance(node, ast.JoinedStr)


def _py_text(node, counter=None) -> str | None:
    """The text of a string expression, with ``{0}``, ``{1}`` … for the parts the program fills in
    (f-string fields, ``+ value``, ``% value``, ``.format(…)``).  None if it is not a string expression."""
    c = counter if counter is not None else [0]

    def ph():
        i = c[0]
        c[0] += 1
        return "{%d}" % i

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(str(v.value) if isinstance(v, ast.Constant) else ph() for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _py_text(node.left, c), _py_text(node.right, c)
        if a is None and b is None:
            return None
        if a is None:
            a = ph()
        if b is None:
            b = ph()
        return a + b
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) and _is_str(node.left):
        t = _py_text(node.left, c)
        return re.sub(r"%[-+ 0#]*\d*(?:\.\d+)?[sdif]", lambda _m: ph(), t) if t is not None else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format" \
            and isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str):
        return re.sub(r"\{[^{}]*\}", lambda _m: ph(), node.func.value.value)
    if isinstance(node, ast.IfExp):                              # "a" if x else "b": the first branch
        return _py_text(node.body, c) if _is_str(node.body) else None
    return None


class _PyVisitor(ast.NodeVisitor):
    def __init__(self):
        self.out: list[str] = []
        self.skip = 0

    def _take(self, node, label=False):
        t = _py_text(node)
        if t is None:
            return False
        n = norm(t)
        if len(n) < 2 or len(n) > 600 or not _WORD.search(n):
            return True
        words = len(n.replace("{", " ").replace("}", " ").split())
        if (words >= 2 or label) and worth(re.sub(r"\{\d+\}", "", n) or n) and not re.search(r"<[a-z]+[ >]|\\[dws]|\(\?", n):
            self.out.append(n)
        return True

    def generic_visit(self, node):
        if self.skip:
            return super().generic_visit(node)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body \
                and isinstance(node.body[0], ast.Expr) and _is_str(node.body[0].value):
            node.body = node.body[1:]                                # a docstring is not UI
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if name in _PY_SKIP_CALLS and not (name == "get" and False):
                return                                              # (arguments of these are code, not UI)
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                label = isinstance(k, ast.Constant) and k.value in _PY_LABEL_KEYS
                if not self._take(v, label=label):
                    self.visit(v)
                if k is not None:
                    pass                                            # keys are identifiers
            return
        if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.IfExp)) or (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format"):
            if self._take(node):
                return
        if isinstance(node, (ast.Subscript,)):
            self.visit(node.value)                                  # d["key"]: the key is code
            return
        if isinstance(node, ast.Compare):
            return                                                  # x == "word": code
        super().generic_visit(node)


def py_strings() -> list[str]:
    out: list[str] = []
    for sub in ("routes", "core"):
        for dp, dn, fns in os.walk(os.path.join(ROOT, sub)):
            dn[:] = [d for d in dn if d not in ("__pycache__",)]
            for fn in sorted(fns):
                if not fn.endswith(".py"):
                    continue
                try:
                    tree = ast.parse(open(os.path.join(dp, fn), encoding="utf-8").read())
                except SyntaxError:
                    continue
                v = _PyVisitor()
                v.visit(tree)
                out += v.out
    # labels kept in JSON data files (naming profiles, palettes, presets, VC styles)
    for dp, _dn, fns in os.walk(os.path.join(ROOT, "core")):
        for fn in fns:
            if fn.endswith(".json"):
                try:
                    data = json.load(open(os.path.join(dp, fn), encoding="utf-8"))
                except (OSError, ValueError):
                    continue

                def walk(o, key=""):
                    if isinstance(o, dict):
                        for k, vv in o.items():
                            walk(vv, k)
                    elif isinstance(o, list):
                        for vv in o:
                            walk(vv, key)
                    elif isinstance(o, str) and key in ("label", "description") and _WORD.search(o):
                        out.append(norm(o))
                walk(data)
    return out


# ── api ──────────────────────────────────────────────────────────────────────

def collect() -> dict:
    """``{"html": [...], "js": [...], "py": [...]}`` — every string once, in order."""
    res = {}
    seen = set()
    for k, fn in (("html", html_strings), ("js", js_strings), ("py", py_strings)):
        lst = []
        for s in fn():
            if s not in seen:
                seen.add(s)
                lst.append(s)
        res[k] = lst
    return res


def all_keys() -> list:
    c = collect()
    return c["html"] + c["js"] + c["py"]


def load_lang(lang: str) -> dict:
    p = os.path.join(ROOT, "static", "i18n", f"{lang}.json")
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else {}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    c = collect()
    keys = c["html"] + c["js"] + c["py"]
    if "--keys" in a:
        print("\n".join(keys))
    elif "--missing" in a:
        lang = a[a.index("--missing") + 1]
        have = load_lang(lang)
        miss = [k for k in keys if k not in have]
        print("\n".join(miss))
        print(f"-- {len(miss)} of {len(keys)} missing in {lang}", file=sys.stderr)
    elif "--json" in a:
        out = a[a.index("--json") + 1]
        json.dump({k: "" for k in keys}, open(out, "w", encoding="utf-8"), indent=0, ensure_ascii=False)
    else:
        for k in ("html", "js", "py"):
            print(f"{k:5} {len(c[k]):5} strings, {sum(len(s) for s in c[k]):7} characters")
        print(f"total {len(keys):5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
