"""core/retarget.py — the recipe's calls by *meaning*, so they can be replayed
on another show (WORKPLAN 3.1, v2.1.0).

A recorded call names things by their ID in the show it was made on: function
``2328``, fixture ``7``, VC widget ``33``…  Another show has other IDs.  Here a
call is turned into a **symbolic** call — every ID it names replaced by what
it is (*the Scene "Song 22"*, *the fixture "DR: Drums" at 1.17*, *the CueList
"Setlist" on the page "1. SETLIST"*) — and bound back to IDs on any show.

* :func:`index` — the identity of everything a call can name, in one show.
* :func:`symbolize` — a call with its IDs replaced by ``@ref:`` strings
  (done before each recorded call, while the show is as the call saw it).
* :func:`bind` — the symbolic call with the IDs of the show it is replayed on;
  :class:`Unbound` when something it names is not in that show.

Which fields of which call hold which kind of ID is declared in :data:`RULES`.
A value that is not an ID (``"all"``, ``"__new__"``, ``""``) is left alone.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from core.vc_ops import WIDGET_TYPES

REF = "@ref:"
KEEP = {"", "all", "__new__", "-1", "4294967295", "none", "None"}


class Unbound(LookupError):
    """Something the call names is not in this show."""


# ── identity of a show ───────────────────────────────────────────────────────

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kids(el, name):
    return [c for c in el if _local(c.tag) == name]


def _find(el, name):
    return next((c for c in el if _local(c.tag) == name), None)


def index(root) -> Dict[str, Dict[str, tuple]]:
    """``{kind: {id: key}}`` for functions, fixtures, groups, VC widgets and
    meshes.  A key is what the thing *is*; the *n*-th of equal keys gets *n*."""
    out = {"fn": {}, "fx": {}, "grp": {}, "w": {}, "mesh": {}}
    if root is None:
        return out
    if hasattr(root, "getroot"):
        root = root.getroot()
    eng = _find(root, "Engine")
    if eng is not None:
        seen: Dict[tuple, int] = {}

        def add(kind, i, base, extra=()):
            k = seen.get((kind,) + base, 0)
            seen[(kind,) + base] = k + 1
            out[kind][i] = base + (k,) + tuple(extra)

        def num(e):
            try:
                return int(e.get("ID", ""))
            except ValueError:
                return 1 << 30
        for f in sorted(_kids(eng, "Function"), key=num):
            add("fn", f.get("ID", ""), (f.get("Type", ""), f.get("Name", "")))
        def fxnum(e):
            i = _find(e, "ID")
            try:
                return int((i.text or "").strip()) if i is not None else 1 << 30
            except ValueError:
                return 1 << 30
        for f in sorted(_kids(eng, "Fixture"), key=fxnum):
            fid = (_find(f, "ID").text or "").strip() if _find(f, "ID") is not None else ""
            nm = (_find(f, "Name").text or "") if _find(f, "Name") is not None else ""
            uni = (_find(f, "Universe").text or "0") if _find(f, "Universe") is not None else "0"
            adr = (_find(f, "Address").text or "0") if _find(f, "Address") is not None else "0"
            add("fx", fid, (nm,), (uni.strip(), adr.strip()))
        for g in _kids(eng, "FixtureGroup"):
            nm = (_find(g, "Name").text or "") if _find(g, "Name") is not None else ""
            add("grp", g.get("ID", ""), (nm,))
        mon = _find(eng, "Monitor")
        for m in (_kids(mon, "MeshItem") if mon is not None else []):
            add("mesh", m.get("ID", ""), (m.get("Name") or m.get("Res") or "",))
    vc = _find(root, "VirtualConsole")
    if vc is not None:
        def walk(el, path):
            seen: Dict[tuple, int] = {}
            for c in el:
                t = _local(c.tag)
                if c.get("ID") is None or t not in WIDGET_TYPES:
                    continue
                base = (t, (c.get("Caption") or "").strip())
                k = seen.get(base, 0)
                seen[base] = k + 1
                p = path + (base + (k,),)
                out["w"][c.get("ID")] = p
                walk(c, p)
        walk(vc, ())
    return out


def _reverse(idx: dict) -> dict:
    return {kind: {v: k for k, v in m.items()} for kind, m in idx.items()}


# ── symbolic values ──────────────────────────────────────────────────────────

def _sym(kind: str, i: str, idx: dict) -> str:
    if str(i) in KEEP or str(i).startswith("new:"):
        return i
    key = idx[kind].get(str(i))
    if key is None:
        return i                       # not in the show (e.g. made by this call)
    return REF + json.dumps([kind, list(key) if kind != "w" else [list(x) for x in key]],
                            ensure_ascii=False)


def _bind_value(s: Any, rev: dict, idx: dict, missing: list, notes: Optional[list] = None) -> Any:
    if not isinstance(s, str) or not s.startswith(REF):
        return s
    kind, key = json.loads(s[len(REF):])
    if kind == "w":
        key = tuple(tuple(x) for x in key)
        hit = rev["w"].get(key)
        if hit is None and key:        # the same widget elsewhere, if only one
            last = key[-1][:2]
            cands = [i for i, p in idx["w"].items() if p and p[-1][:2] == tuple(last)]
            hit = cands[0] if len(cands) == 1 else None
            if hit is not None and notes is not None:
                notes.append(f"{last[0]} '{last[1]}' found elsewhere on the console")
        if hit is None:
            missing.append(f"VC {key[-1][0]} '{key[-1][1]}'" if key else "VC root")
        return hit if hit is not None else s
    if kind == "fx":
        name, k, uni, adr = key[0], key[1], key[2], key[3]
        hit = next((i for i, v in idx["fx"].items() if v[:2] == (name, k)), None)
        if hit is None:                # another rig: the fixture at the same address
            hit = next((i for i, v in idx["fx"].items() if v[2:] == (uni, adr)), None)
            if hit is not None and notes is not None:
                notes.append(f"'{name}' → '{idx['fx'][hit][0]}' (same address {int(uni) + 1}.{int(adr) + 1})")
        if hit is None:
            missing.append(f"fixture '{name}' ({int(uni) + 1}.{int(adr) + 1})")
        return hit if hit is not None else s
    hit = rev[kind].get(tuple(key))
    if hit is None:
        what = {"fn": f"{key[0]} '{key[1]}'", "grp": f"group '{key[0]}'",
                "mesh": f"mesh '{key[0]}'"}.get(kind, kind)
        missing.append(what)
    return hit if hit is not None else s


# ── which fields hold IDs ────────────────────────────────────────────────────
#
# A rule is (field path, kind).  Path steps: a key, ``*`` (every list item),
# ``{}`` (every dict key), ``{*}`` (every dict value).  ``@seg<n>`` is the
# n-th segment of the URL.  The kind may be a function of the body
# (stage ops: ``f:7`` is a fixture, ``27`` a mesh).

def _stage_kind(body: dict, value: str) -> str:
    if isinstance(value, str) and value.startswith("f:"):
        return "fx:f:"
    return "fx" if (body or {}).get("op") == "move_fixture" else "mesh"


_W = "w"
RULES: List[Tuple[str, str, list]] = [
    ("POST", r"^/api/brightness/apply-show$", [("scales.{}", "fx"),
                                                ("manual_dimmer_offsets.{}", "fx")]),
    ("POST", r"^/api/looks/(apply|check)$", [("looks.*.group", "grp"), ("chasers.*.group", "grp")]),
    ("POST", r"^/api/reducer/apply$", [("keep.*", "fx"), ("repatch.{}", "fx")]),
    ("POST", r"^/api/porter/(apply|validate)$", [("fixture_mapping.{*}.*", "fx"),
                                                 ("vc.target_page", _W), ("vc.remove.*", _W)]),
    ("POST", r"^/api/setlist/[^/]+/", [("@seg3", _W), ("rows.*.qxw_id", "fn"),
                                       ("target_chaser_id", "fn")]),
    ("PATCH", r"^/api/setlist/[^/]+/details/", [("@seg3", _W), ("qxw_id", "fn")]),
    ("POST", r"^/api/stage/op$", [("id", _stage_kind), ("ids.*", _stage_kind),
                                  ("fixtures.*", "fx"), ("gid", "grp")]),
    ("PATCH", r"^/api/triggers/[^/]+$", [("@seg3", "trigger")]),
    ("POST", r"^/api/vc/op$", [("ids.*", _W), ("target_id", _W), ("page_id", _W),
                               ("parent_id", _W), ("widget_id", _W), ("cuelist_id", _W),
                               ("frame_id", _W), ("page_ids.*", _W), ("func_id", "fn"),
                               ("chaser_id", "fn")]),
    ("POST", r"^/api/vc/patch$", [("changes.*.id", _W)]),
    ("POST", r"^/api/vc/template$", [("page_id", _W)]),
]
_RULES = [(m, re.compile(p), r) for m, p, r in RULES]

# Calls that name nothing in the show (replayed as they are).
PLAIN = [r"^/api/show/(undo|redo)$", r"^/api/vc/undo$", r"^/api/setlist/(apply-all|auto-match|load|purge-workspace-clones|notes)$",
         r"^/api/porter/(source/load|target/show|target/load|clear|resolve|auto-map|fixture-candidates|vc/seeds|wire/options)$",
         r"^/api/triggers/midi-shift$", r"^/api/stage/mesh-info$", r"^/api/brightness/assign-qxf$"]
_PLAIN = [re.compile(p) for p in PLAIN]
_TRIGGER = re.compile(r"^([a-z]+)_(\d+)(.*)$")


def _rules(method: str, path: str) -> Optional[list]:
    rules = [r for m, p, rr in _RULES if m == method and p.search(path) for r in rr]
    if rules:
        return rules
    if path == "/api/doctor/apply":
        return []
    if any(p.search(path) for p in _PLAIN):
        return []
    return None


def known(method: str, path: str) -> bool:
    """True when the call can be replayed on another show."""
    return _rules(method, path) is not None


def _apply(body: Any, steps: List[str], fn: Callable[[str], Any], kind_of) -> Any:
    if not steps:
        return fn(body, kind_of)
    s, rest = steps[0], steps[1:]
    if isinstance(body, dict):
        if s == "{}":
            return {fn(k, kind_of) if isinstance(k, str) else k: _apply(v, rest, fn, kind_of) if rest else v
                    for k, v in body.items()}
        if s == "{*}":
            return {k: _apply(v, rest, fn, kind_of) for k, v in body.items()}
        if s in body:
            out = dict(body)
            out[s] = _apply(body[s], rest, fn, kind_of)
            return out
        return body
    if isinstance(body, list) and s == "*":
        return [_apply(v, rest, fn, kind_of) for v in body]
    return body


def _map_call(method: str, path: str, body: Any, conv: Callable[[str, str], Any]) -> Tuple[str, Any]:
    """Run *conv(value, kind)* over every ID field of the call."""
    rules = _rules(method, path) or []
    body = copy.deepcopy(body)
    segs = path.split("/")
    for field, kind in rules:
        def one(v, _k=kind):
            if not isinstance(v, (str, int)) or isinstance(v, bool):
                return v
            v = str(v)
            k = _k(body, v) if callable(_k) else _k
            if k == "fx:f:":                       # stage: "f:<fixture id>"
                return "f:" + str(conv(v[2:], "fx"))
            if k == "trigger":                     # "btn_<widget>", "cl_<widget>_<action>"
                if "~" in v:
                    pre, rest = v.split("~", 1)
                    mid, suf = rest.rsplit("~", 1)
                else:
                    m = _TRIGGER.match(v)
                    if not m:
                        return v
                    pre, mid, suf = m.group(1), m.group(2), m.group(3)
                w = str(conv(mid, "w"))
                return f"{pre}~{w}~{suf}" if REF in w else f"{pre}_{w}{suf}"
            return conv(v, k)
        if field.startswith("@seg"):
            n = int(field[4:])
            if n < len(segs):
                r = str(one(unquote(segs[n])))
                segs[n] = quote(r, safe="") if REF in r else r
            continue
        body = _apply(body, field.split("."), lambda v, _: one(v), None)
    return "/".join(segs), body


def symbolize(method: str, path: str, body: Any, root) -> Optional[dict]:
    """``{"path", "body"}`` with IDs replaced by what they are, or ``None``
    when the call names nothing (or is not known)."""
    if _rules(method, path) is None:
        return None
    idx = index(root)
    if path == "/api/doctor/apply":
        keys = [str(k) for k in ((body or {}).get("keys") or [])]
        return {"path": path, "body": {"@doctor": {"codes": sorted({k.split("|", 1)[0] for k in keys}),
                                                   "keys": keys}}}

    p, b = _map_call(method, path, body, lambda v, kind: _sym(kind, v, idx))
    if p == path and b == body:
        return None
    return {"path": p, "body": b}


def bind(method: str, sym: dict, root, doctor_findings: Optional[Callable[[], list]] = None) -> dict:
    """The symbolic call with this show's IDs.  Raises :class:`Unbound`."""
    path, body = sym["path"], sym.get("body")
    if isinstance(body, dict) and "@doctor" in body:
        d = body["@doctor"]
        fs = doctor_findings() if doctor_findings else []
        want = set(d.get("keys") or [])
        codes = set(d.get("codes") or [])
        keys = [f["key"] for f in fs if f["key"] in want or (f.get("default") and f["code"] in codes)]
        return {"path": path, "body": {"keys": keys},
                "note": f"the same kinds of fixes ({', '.join(sorted(codes))}): {len(keys)} in this show"}
    idx = index(root)
    rev = _reverse(idx)
    missing: list = []
    notes: list = []
    p, b = _map_call(method, path, body, lambda v, kind: _bind_value(v, rev, idx, missing, notes))
    # values in plain fields that are still symbolic (e.g. "f:@ref…")
    leftover = [s for s in _strings(b) + p.split("/") if isinstance(s, str) and REF in s]
    if missing or leftover:
        raise Unbound(", ".join(sorted(set(missing))) or "something this call names")
    out = {"path": p, "body": b}
    if notes:
        out["note"] = "matched by place: " + "; ".join(dict.fromkeys(notes))
    return out


def _strings(o) -> list:
    if isinstance(o, dict):
        return [s for k, v in o.items() for s in ([k] + _strings(v))]
    if isinstance(o, list):
        return [s for v in o for s in _strings(v)]
    return [o]
