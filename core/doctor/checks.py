"""
Workspace Doctor — read-only checks (WORKPLAN Phase 1.0).

``check(root, qxf_defs)`` never mutates *root*: it works on a
namespace-stripped deep copy.  Findings are emitted check by check in code
order, and inside each check in document order, so the report is
deterministic for a given file.
"""

from __future__ import annotations

import copy
import glob
import os
import re
import xml.etree.ElementTree as ET  # nosec B405
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from core import qxw_io
from core.doctor.report import ERROR, INFO, WARNING, Finding, Report, make_report

NONE_ID = "4294967295"          # QLC+ "no function" sentinel

VC_WIDGET_TAGS = {
    "Frame", "SoloFrame", "Button", "Slider", "XYPad", "CueList", "Label",
    "SpeedDial", "AudioTriggers", "Clock", "Matrix", "Animation", "Knob",
}
CONTAINER_TAGS = {"Frame", "SoloFrame"}

# A scene is intentional FX when its own name, or the name of any function
# that (transitively) contains it, matches this (WORKPLAN §3, 2026-09-23).
# "macro" / "program" / "audio" mark scenes that deliberately run a fixture's
# internal programs or sound-active mode.  Anything else: use allow_fx.
FX_NAME_RE = re.compile(
    r"strob|flash|\*|punk|macro|program|audio|(?<![a-z])fx(?![a-z])", re.I)
PANIC_RE = re.compile(r"panic\s*reset", re.I)
UNNAMED_RE = re.compile(r"^\[\d+\]\s+\S+\s+-\s+Unassigned$")
SCRIPT_FUNC_RE = re.compile(r"(?:start|stop)function:(\d+)", re.I)

# Channel groups whose non-neutral values run strobe / internal programs.
RISKY_GROUPS = ("Shutter", "Effect")
SAFE_CAP_RE = re.compile(
    r"no function|no flash|no effect|shutter open|\bopen\b|\boff\b|"
    r"dmx mode|manual|^none$", re.I)
SAFE_PRESETS = {"ShutterOpen"}
# Words that make a capability "active" (a program, a strobe, a macro …).
# At DMX 0, a capability whose label has none of these is the fixture's
# plain operating mode (e.g. SlimPAR 56 "Mode = 0 (RGB)") and is safe.
ACTIVE_CAP_RE = re.compile(
    r"strob|flash|pulse|program|auto|macro|sound|music|chase|jump|fade|"
    r"random|effect|rotat|shake|blackout|close|reset|lamp", re.I)


# ═════════════════════════════════════════════════════════════════════════════
# Fixture definitions
# ═════════════════════════════════════════════════════════════════════════════

def _def_key(manufacturer: str, model: str) -> Tuple[str, str]:
    return ((manufacturer or "").strip().lower(), (model or "").strip().lower())


def load_qxf_defs(paths: Iterable[str]) -> Dict[Tuple[str, str], dict]:
    """Parse every ``.qxf`` in *paths* (files or folders, non-recursive).

    Returns ``{(manufacturer, model) (lower-case): parse_qxf() dict}``.
    Unreadable files are skipped.
    """
    from core.qxf_parser import parse_qxf
    files: List[str] = []
    for p in paths or ():
        if os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, "*.qxf"))))
        elif os.path.isfile(p):
            files.append(p)
    defs: Dict[Tuple[str, str], dict] = {}
    for f in files:
        try:
            d = parse_qxf(f)
        except Exception:  # noqa: BLE001 — a bad QXF must not stop Doctor
            continue
        defs.setdefault(_def_key(d["manufacturer"], d["model"]), d)
    return defs


def _normalise_defs(qxf_defs) -> Dict[Tuple[str, str], dict]:
    if not qxf_defs:
        return {}
    if isinstance(qxf_defs, dict):
        items = qxf_defs.values()
    else:
        items = qxf_defs
    out = {}
    for d in items:
        if isinstance(d, dict) and "model" in d:
            out.setdefault(_def_key(d.get("manufacturer", ""), d["model"]), d)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Workspace model
# ═════════════════════════════════════════════════════════════════════════════

def _int(s, default=None):
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return default


class _Workspace:
    """Indexed, read-only view of a namespace-stripped workspace."""

    def __init__(self, root: ET.Element, defs):
        self.root = root
        self.engine = root.find("Engine")
        if self.engine is None:
            self.engine = ET.Element("Engine")
        self.defs = defs

        # fixtures
        self.fixtures: Dict[str, dict] = {}
        self.fixture_els: List[ET.Element] = self.engine.findall("Fixture")
        for el in self.fixture_els:
            fid = (el.findtext("ID") or "").strip()
            info = {
                "id": fid,
                "name": el.findtext("Name") or "",
                "manufacturer": el.findtext("Manufacturer") or "",
                "model": el.findtext("Model") or "",
                "mode": el.findtext("Mode") or "",
                "universe": _int(el.findtext("Universe"), 0),
                "address": _int(el.findtext("Address"), 0),
                "channels": _int(el.findtext("Channels"), 0),
            }
            d = defs.get(_def_key(info["manufacturer"], info["model"]))
            names = (d or {}).get("mode_channels", {}).get(info["mode"])
            info["def"] = d if names else None
            info["channel_names"] = names or []
            self.fixtures.setdefault(fid, info)

        self.group_els = self.engine.findall("FixtureGroup")
        self.groups = {g.get("ID"): g for g in self.group_els}

        # functions
        self.function_els: List[ET.Element] = self.engine.findall("Function")
        self.functions: Dict[str, ET.Element] = {}
        for f in self.function_els:
            self.functions.setdefault(f.get("ID"), f)
        self.children: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.parents: Dict[str, set] = defaultdict(set)
        for f in self.function_els:
            fid = f.get("ID")
            for kind, ref in self._function_refs(f):
                self.children[fid].append((kind, ref))
                if ref:
                    self.parents[ref].add(fid)

        # virtual console
        self.vc = root.find("VirtualConsole")
        self.widgets: List[Tuple[ET.Element, str]] = []   # (el, page caption)
        self.pages: List[ET.Element] = []
        if self.vc is not None:
            for top in self.vc:
                if top.tag in CONTAINER_TAGS:
                    self.pages.append(top)
                    self._walk_vc(top, top.get("Caption", ""))
                elif top.tag in VC_WIDGET_TAGS:
                    self._walk_vc(top, "")
        self.vc_refs: Dict[str, List[ET.Element]] = defaultdict(list)
        for w, _page in self.widgets:
            for fid in self.widget_function_refs(w):
                self.vc_refs[fid].append(w)

    # ── helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _function_refs(f: ET.Element):
        """Yield ``(kind, function_id)`` for every function *f* references."""
        for step in f.findall("Step"):
            yield "step", (step.text or "").strip()
        for el in f.iter():
            if el is not f and el.get("BoundScene"):
                yield "bound", el.get("BoundScene")
            if el.tag == "ShowFunction" and el.get("ID"):
                yield "show", el.get("ID")
            if el.tag == "Track" and el.get("SceneID") not in (None, "", NONE_ID):
                yield "show", el.get("SceneID")
        if f.get("BoundScene"):
            yield "bound", f.get("BoundScene")
        if f.get("Type") == "Script":
            for cmd in f.findall("Command"):
                for m in SCRIPT_FUNC_RE.finditer(cmd.text or ""):
                    yield "script", m.group(1)

    def _walk_vc(self, el: ET.Element, page: str):
        self.widgets.append((el, page))
        for child in el:
            if child.tag in VC_WIDGET_TAGS:
                self._walk_vc(child, page)

    @staticmethod
    def widget_function_refs(w: ET.Element) -> List[str]:
        refs = []
        if w.tag == "CueList":
            refs.append((w.findtext("Chaser") or NONE_ID).strip())
            return refs
        for el in list(w) + list(w.findall("Playback")):
            if el.tag == "Function":
                fid = el.get("ID") or (el.text or "").strip()
                if fid and fid != NONE_ID:
                    refs.append(fid)
        return refs

    # ── labels ──────────────────────────────────────────────────────────
    def fn_loc(self, fid: str) -> str:
        f = self.functions.get(fid)
        name = f.get("Name", "") if f is not None else "?"
        return f"Function {fid} '{name}'"

    @staticmethod
    def widget_loc(w: ET.Element, page: str) -> str:
        cap = (w.get("Caption") or "").replace("\n", " ")
        where = f" on page '{page}'" if page and w.get("Caption") != page else ""
        return f"VC {w.tag} {w.get('ID', '?')} '{cap}'{where}"

    def page_of(self, w: ET.Element) -> str:
        for el, page in self.widgets:
            if el is w:
                return page
        return ""

    def ancestors(self, fid: str) -> set:
        seen, stack = set(), [fid]
        while stack:
            for p in self.parents.get(stack.pop(), ()):
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        return seen


# ═════════════════════════════════════════════════════════════════════════════
# Checks
# ═════════════════════════════════════════════════════════════════════════════

def _d002_duplicates(ws: _Workspace):
    def dups(items, kind, loc):
        seen: Dict[str, int] = defaultdict(int)
        for i in items:
            seen[i] += 1
        for i, n in seen.items():
            if n > 1:
                yield Finding("D002", ERROR, loc(i),
                              f"{kind} ID {i} is used {n} times", {kind: i})
    yield from dups([(el.findtext("ID") or "").strip() for el in ws.fixture_els],
                    "fixture", lambda i: f"Fixture {i}")
    yield from dups([g.get("ID") for g in ws.group_els],
                    "fixture group", lambda i: f"Fixture group {i}")
    yield from dups([f.get("ID") for f in ws.function_els],
                    "function", lambda i: f"Function {i}")
    by_wid: Dict[str, List[str]] = defaultdict(list)
    for w, page in ws.widgets:
        if w.get("ID") is not None:
            by_wid[w.get("ID")].append(ws.widget_loc(w, page))
    for wid, locs in by_wid.items():
        if len(locs) > 1:
            yield Finding("D002", ERROR, f"VC widget ID {wid}",
                          f"used by {len(locs)} widgets: " + "; ".join(locs),
                          {"widget": wid})


def _d003_dangling(ws: _Workspace):
    for f in ws.function_els:
        fid, ftype = f.get("ID"), f.get("Type")
        for kind, ref in ws.children.get(fid, ()):
            if not ref:
                yield Finding("D003", ERROR, ws.fn_loc(fid),
                              f"{kind} without a function ID", {"function": fid})
            elif ref not in ws.functions:
                yield Finding("D003", ERROR, ws.fn_loc(fid),
                              f"{kind} → missing function {ref}",
                              {"function": fid, "target": ref})
        if ftype == "Scene":
            for v in f.findall("FixtureVal"):
                if v.get("ID") not in ws.fixtures:
                    yield Finding("D003", ERROR, ws.fn_loc(fid),
                                  f"values for missing fixture {v.get('ID')}",
                                  {"function": fid, "fixture": v.get("ID")})
        if ftype == "RGBMatrix":
            g = (f.findtext("FixtureGroup") or "").strip()
            if g and g not in ws.groups:
                yield Finding("D003", ERROR, ws.fn_loc(fid),
                              f"uses missing fixture group {g}",
                              {"function": fid, "group": g})
        if ftype == "EFX":
            for fx in f.findall("Fixture"):
                x = (fx.findtext("ID") or "").strip()
                if x and x not in ws.fixtures:
                    yield Finding("D003", ERROR, ws.fn_loc(fid),
                                  f"EFX uses missing fixture {x}",
                                  {"function": fid, "fixture": x})
    for w, page in ws.widgets:
        loc = ws.widget_loc(w, page)
        if w.tag == "CueList":
            c = (w.findtext("Chaser") or NONE_ID).strip()
            if c == NONE_ID:
                yield Finding("D003", ERROR, loc, "CueList has no chaser attached",
                              {"widget": w.get("ID")})
            elif c not in ws.functions:
                yield Finding("D003", ERROR, loc, f"CueList → missing chaser {c}",
                              {"widget": w.get("ID"), "target": c})
            elif ws.functions[c].get("Type") != "Chaser":
                yield Finding("D003", ERROR, loc,
                              f"CueList → function {c} is a "
                              f"{ws.functions[c].get('Type')}, not a Chaser",
                              {"widget": w.get("ID"), "target": c})
            continue
        for ref in ws.widget_function_refs(w):
            if ref not in ws.functions:
                yield Finding("D003", ERROR, loc, f"→ missing function {ref}",
                              {"widget": w.get("ID"), "target": ref})
        if w.tag == "Slider":
            for ch in w.iter("Channel"):
                fx = ch.get("Fixture")
                if fx is not None and fx not in ws.fixtures:
                    yield Finding("D003", ERROR, loc,
                                  f"level channel on missing fixture {fx}",
                                  {"widget": w.get("ID"), "fixture": fx})


def _d004_empty(ws: _Workspace):
    for f in ws.function_els:
        fid, ftype = f.get("ID"), f.get("Type")
        if ftype == "Scene":
            if not any((v.text or "").strip() for v in f.findall("FixtureVal")):
                yield Finding("D004", WARNING, ws.fn_loc(fid), "empty scene (no channel values)",
                              {"function": fid})
        elif ftype == "Chaser" and f.find("Sequence") is None and not f.get("BoundScene"):
            n = len([s for s in f.findall("Step") if (s.text or "").strip()])
            if n <= 1:
                yield Finding("D004", WARNING, ws.fn_loc(fid),
                              f"degenerate chaser ({n} step{'s' if n != 1 else ''})",
                              {"function": fid, "steps": n})
        elif ftype == "Collection" and not f.findall("Step"):
            yield Finding("D004", WARNING, ws.fn_loc(fid), "empty collection", {"function": fid})


def _scene_pairs(v: ET.Element) -> Dict[int, int]:
    nums = [x.strip() for x in (v.text or "").split(",") if x.strip()]
    out: Dict[int, int] = {}
    for ch, val in zip(nums[0::2], nums[1::2]):
        c, x = _int(ch), _int(val)
        if c is not None and x is not None:
            out[c] = x
    return out


def _ch_label(fx: dict, ch: int) -> str:
    names = fx["channel_names"]
    return f"{ch + 1} {names[ch]}" if ch < len(names) else f"{ch + 1}"


def _d005_incomplete(ws: _Workspace):
    for f in ws.function_els:
        if f.get("Type") != "Scene":
            continue
        fid = f.get("ID")
        for v in f.findall("FixtureVal"):
            fx = ws.fixtures.get(v.get("ID"))
            pairs = _scene_pairs(v)
            if fx is None or not pairs or fx["channels"] <= 0:
                continue
            missing = [c for c in range(fx["channels"]) if c not in pairs]
            if missing:
                labels = ", ".join(_ch_label(fx, c) for c in missing)
                yield Finding(
                    "D005", WARNING, ws.fn_loc(fid),
                    f"{fx['name']}: declares {fx['channels'] - len(missing)}/"
                    f"{fx['channels']} channels (missing: {labels})",
                    {"function": fid, "fixture": fx["id"],
                     "missing": [c for c in missing]})


def _is_safe_value(chdef: dict, val: int) -> bool:
    caps = chdef.get("capabilities") or []
    for cap in caps:
        if cap["min"] <= val <= cap["max"]:
            label = cap.get("label") or ""
            if cap.get("preset") in SAFE_PRESETS or SAFE_CAP_RE.search(label):
                return True
            return (val == 0 and not cap.get("preset")
                    and not ACTIVE_CAP_RE.search(label))
    return val == 0


def _cap_label(chdef: dict, val: int) -> str:
    for cap in chdef.get("capabilities") or []:
        if cap["min"] <= val <= cap["max"]:
            return cap.get("label") or ""
    return ""


def _d006_strobe(ws: _Workspace, allow_fx: set):
    fx_cache: Dict[str, bool] = {}

    def is_fx(fid: str) -> bool:
        if fid not in fx_cache:
            ids = {fid} | ws.ancestors(fid)
            fx_cache[fid] = bool(ids & allow_fx) or any(
                FX_NAME_RE.search(ws.functions[i].get("Name", ""))
                for i in ids if i in ws.functions)
        return fx_cache[fid]

    for f in ws.function_els:
        if f.get("Type") != "Scene":
            continue
        fid = f.get("ID")
        for v in f.findall("FixtureVal"):
            fx = ws.fixtures.get(v.get("ID"))
            if fx is None or fx["def"] is None:
                continue
            chdefs = fx["def"]["channel_defs"]
            for ch, val in sorted(_scene_pairs(v).items()):
                if ch >= len(fx["channel_names"]):
                    continue
                cname = fx["channel_names"][ch]
                cd = chdefs.get(cname) or {}
                if cd.get("group") not in RISKY_GROUPS or _is_safe_value(cd, val):
                    continue
                if is_fx(fid):
                    continue
                label = _cap_label(cd, val)
                yield Finding(
                    "D006", WARNING, ws.fn_loc(fid),
                    f"{fx['name']}: {cname} = {val}"
                    + (f" ({label})" if label else "")
                    + " — not marked as FX",
                    {"function": fid, "fixture": fx["id"], "channel": ch, "value": val})


def _d007_shared_scene(ws: _Workspace):
    step_of: Dict[str, List[str]] = defaultdict(list)
    for f in ws.function_els:
        if f.get("Type") == "Chaser":
            for kind, ref in ws.children.get(f.get("ID"), ()):
                if kind == "step" and ref:
                    step_of[ref].append(f.get("ID"))
    for fid, widgets in ws.vc_refs.items():
        f = ws.functions.get(fid)
        if f is None or f.get("Type") != "Scene" or fid not in step_of:
            continue
        buttons = [w for w in widgets if w.tag == "Button"]
        if not buttons:
            continue
        chasers = ", ".join(sorted(set(step_of[fid]), key=lambda x: _int(x, 0)))
        yield Finding("D007", WARNING, ws.fn_loc(fid),
                      f"used by VC button '{(buttons[0].get('Caption') or '').strip()}' "
                      f"and by chaser {chasers}",
                      {"function": fid})


def _d008_panic(ws: _Workspace):
    panic = [f for f in ws.function_els if PANIC_RE.search(f.get("Name", ""))]
    if not panic:
        yield Finding("D008", WARNING, "Workspace", "no PANIC RESET function", {})
        return
    on_button = [f for f in panic
                 if any(w.tag == "Button" for w in ws.vc_refs.get(f.get("ID"), ()))]
    if not on_button:
        yield Finding("D008", WARNING, ws.fn_loc(panic[0].get("ID")),
                      "PANIC RESET is not on a VC button",
                      {"function": panic[0].get("ID")})


def _d009_overlap(ws: _Workspace):
    owner: Dict[Tuple[int, int], str] = {}
    reported = set()
    for fid, fx in ws.fixtures.items():
        for c in range(fx["address"], fx["address"] + max(fx["channels"], 0)):
            key = (fx["universe"], c)
            other = owner.get(key)
            if other is not None and (other, fid) not in reported:
                reported.add((other, fid))
                o = ws.fixtures[other]
                yield Finding("D009", WARNING, f"Fixture {fid} '{fx['name']}'",
                              f"overlaps fixture {other} '{o['name']}' from "
                              f"U{fx['universe'] + 1}.{c + 1}",
                              {"fixture": fid, "other": other})
            owner.setdefault(key, fid)


def _d012_inputs(ws: _Workspace):
    if ws.vc is None:
        return
    bound: Dict[str, int] = defaultdict(int)
    for inp in ws.vc.iter("Input"):
        u = inp.get("Universe")
        if u is not None:
            bound[u] += 1
    patched = set()
    iom = ws.engine.find("InputOutputMap")
    if iom is not None:
        for u in iom.findall("Universe"):
            for i in u.findall("Input"):
                if (i.get("Name") or "None") not in ("None", "") and i.get("Plugin") not in (None, "None"):
                    patched.add(u.get("ID"))
    for u in sorted(bound, key=lambda x: _int(x, 0)):
        if u not in patched:
            yield Finding("D012", WARNING, f"Universe {(_int(u, 0) or 0) + 1}",
                          f"{bound[u]} VC input binding(s) but no input device patched "
                          f"(saved as None) — they will not respond",
                          {"universe": u, "bindings": bound[u]})


def _d015_unnamed(ws: _Workspace):
    for f in ws.function_els:
        if UNNAMED_RE.match(f.get("Name", "")):
            yield Finding("D015", INFO, ws.fn_loc(f.get("ID")),
                          "unnamed function — give it a meaningful name",
                          {"function": f.get("ID")})


def _d016_unreferenced(ws: _Workspace):
    for f in ws.function_els:
        fid = f.get("ID")
        if not ws.parents.get(fid) and not ws.vc_refs.get(fid):
            yield Finding("D016", WARNING, ws.fn_loc(fid),
                          f"{f.get('Type')} not used by any function or VC widget",
                          {"function": fid})


def _i001_caption_buttons(ws: _Workspace):
    for w, page in ws.widgets:
        if w.tag != "Button":
            continue
        fe = w.find("Function")
        fid = fe.get("ID") if fe is not None else NONE_ID
        action = (w.findtext("Action") or "").strip()
        if fid == NONE_ID and action not in ("StopAll", "Blackout"):
            yield Finding("I001", INFO, ws.widget_loc(w, page),
                          "button has no function (label use?)",
                          {"widget": w.get("ID")})


def _i002_pages(ws: _Workspace):
    if ws.pages:
        caps = [p.get("Caption", "") for p in ws.pages]
        yield Finding("I002", INFO, "Virtual Console",
                      f"{len(caps)} page(s): " + " | ".join(caps),
                      {"pages": caps})


def _i003_missing_defs(ws: _Workspace):
    seen = set()
    for fid, fx in ws.fixtures.items():
        key = (fx["manufacturer"], fx["model"], fx["mode"])
        if fx["def"] is None and key not in seen:
            seen.add(key)
            yield Finding("I003", INFO, f"Fixture {fid} '{fx['name']}'",
                          f"no definition loaded for {fx['manufacturer']} {fx['model']} "
                          f"({fx['mode']}) — D006 skipped for it",
                          {"fixture": fid})


# ═════════════════════════════════════════════════════════════════════════════
# Public API
# ═════════════════════════════════════════════════════════════════════════════

def check(root, qxf_defs=None, *, allow_fx: Iterable[str] = (),
          source: str = "") -> Report:
    """Run every read-only check on a workspace tree and return a Report.

    *root*      ``ET.Element`` / ``ET.ElementTree`` (namespaced or stripped)
    *qxf_defs*  ``load_qxf_defs()`` result, or any iterable of
                ``parse_qxf()`` dicts; needed for channel-aware checks (D006)
    *allow_fx*  function IDs that are intentional FX (with everything they contain)
    """
    if isinstance(root, ET.ElementTree):
        root = root.getroot()
    root = qxw_io.strip_ns(copy.deepcopy(root))
    ws = _Workspace(root, _normalise_defs(qxf_defs))
    allow = {str(a) for a in allow_fx}
    findings: List[Finding] = []
    for gen in (_d002_duplicates(ws), _d003_dangling(ws), _d004_empty(ws),
                _d005_incomplete(ws), _d006_strobe(ws, allow),
                _d007_shared_scene(ws), _d008_panic(ws), _d009_overlap(ws),
                _d012_inputs(ws), _d015_unnamed(ws), _d016_unreferenced(ws),
                _i001_caption_buttons(ws), _i002_pages(ws), _i003_missing_defs(ws)):
        findings.extend(gen)
    stats = {"fixtures": len(ws.fixture_els), "functions": len(ws.function_els),
             "vc_widgets": len(ws.widgets), "vc_pages": len(ws.pages)}
    return make_report(source, findings, stats)


def check_file(path: str, qxf_defs=None, *, allow_fx: Iterable[str] = ()) -> Report:
    """D001 file-level checks, then :func:`check` if the file parses."""
    src = os.path.basename(path)
    try:
        with open(path, "rb") as fh:
            head = fh.read(512)
    except OSError as e:
        return make_report(src, [Finding("D001", ERROR, src, f"cannot read file: {e}")], {})
    pre: List[Finding] = []
    if not head.lstrip().startswith(b"<?xml"):
        pre.append(Finding("D001", ERROR, src, "missing XML declaration"))
    if b"<!DOCTYPE Workspace>" not in head:  # qxw-io: not output
        pre.append(Finding("D001", ERROR, src,
                           "missing <!DOCTYPE Workspace> — QLC+ will refuse the file"))  # qxw-io: not output
    try:
        tree = qxw_io.load_qxw(path)
    except ET.ParseError as e:
        return make_report(src, pre + [Finding(
            "D001", ERROR, src, f"not well-formed XML ({e})")], {})
    except ValueError as e:
        return make_report(src, pre + [Finding("D001", ERROR, src, str(e))], {})
    root = tree.getroot()
    if root.tag not in (qxw_io._NS_PREFIX + "Workspace", "Workspace"):
        return make_report(src, pre + [Finding(
            "D001", ERROR, src, f"root element is <{root.tag}>, not <Workspace>")], {})
    rep = check(root, qxf_defs, allow_fx=allow_fx, source=src)
    rep.findings[:0] = pre
    return rep
