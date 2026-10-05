"""
core/doctor/fixes.py — Workspace Doctor auto-fixes (WORKPLAN Phase 2.1)
=====================================================================
Opt-in fixes for Doctor findings.  Every fix works on a copy: the result is
written to a **new file** (``<name>_v<N+1>.qxw``, never the original) with a
fix report next to it (``<new name>_fix_report.txt``).

Fixable findings (:func:`fixable`):

======  ================================================================
D002    duplicate function IDs → later copies renumbered ``max + 1``
        (references keep pointing at the first); duplicate VC widget IDs
        → renumbered (``vc_ops.fix_duplicate_ids``).  Duplicate fixture /
        group IDs: not fixed (which one is meant can't be known).
D003    dangling references removed: chaser/collection steps, show items
        and script commands → missing function; scene values / EFX
        entries / slider channels for missing fixtures; buttons → missing
        function become caption-only.  Not fixed: CueList without chaser,
        RGB matrix → missing group, missing bound scene.
D004    empty scenes and empty collections removed, with every step,
        script command and button that used them.  Degenerate chasers (0 or
        1 step), option ``d004`` (default ``merge``): ``merge`` points every
        user of the chaser at its one scene and removes the chaser; ``remove``
        removes it with its users; an empty chaser is always removed.
D005    missing channels added at the fixture's neutral value
        (``channel_model.neutral_value``; 0 without a definition).
D006    the strobe / program channel set to its neutral value.
D007    the scene is duplicated for the chaser(s) (``<name> (chaser)``);
        the VC button keeps the original — no more latch conflict.
D008    no PANIC RESET: creates *Reset: neutral state* (every fixture
        neutral, intensity 0) and a *PANIC RESET* script (stop every
        function, start the reset scene), with a button on the first page.
        PANIC RESET not on a button: adds the button.
D010    the setlist page (the only page with a CueList) moved to page 1.
D011    a widget sticking out of its page / frame moved back inside (not
        when it is larger than its page / frame).
D013    chaser steps that last 0 ms get a duration: option ``d013`` =
        ``{"ms": 500}`` or ``{"bpm": 120}`` (default 500 ms).
D015    unnamed function removed when nothing uses it; option ``d015`` =
        ``rename`` names it from its context instead (the button that starts
        it, else its parent chaser / collection and step number).
D016    unreferenced function removed.
D017    PANIC RESET scene → wrapped in a *PANIC RESET* script (stop every
        function, then start the scene); its buttons now run the script.
======  ================================================================

Deterministic: fixes run in code order, items in document order, new IDs
``max + 1``.
"""

from __future__ import annotations

import copy
import os
import re
import xml.etree.ElementTree as ET  # nosec B405
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

from core import qxw_io, vc_ops
from core.doctor.checks import (NONE_ID, UNNAMED_RE, PANIC_RE, SCRIPT_FUNC_RE, _normalise_defs,
                                _scene_pairs, _Workspace, check)
from core.doctor.report import Finding, Report

# Fixes that delete functions: offered, but not selected by default
REMOVING = {"D004", "D015", "D016"}
OPTION_CODES = {"D003", "D004", "D013", "D015"}      # fixes that take options
DEFAULT_CODES = {"D002", "D003", "D005", "D006", "D007", "D008", "D011", "D017"}

FIX_ORDER = ["D002", "D003", "D004", "D005", "D006", "D007", "D010", "D011", "D013",
             "D015", "D016", "D017", "D008"]


@dataclass
class FixResult:
    root: ET.Element                     # fixed, namespace-stripped tree
    before: Report
    after: Report
    actions: List[dict] = field(default_factory=list)      # {code, location, action}
    skipped: List[dict] = field(default_factory=list)      # selected but not fixable

    @property
    def changed(self) -> bool:
        return bool(self.actions)


def clean_options(raw) -> dict:
    """The *options* of :func:`fix` from untrusted input (JSON body, CLI)."""
    o, raw = {}, (raw if isinstance(raw, dict) else {})
    for k, allowed in (("d003", ("unlink", "rewire")), ("d004", ("merge", "remove")),
                       ("d015", ("remove", "rename"))):
        if raw.get(k) in allowed:
            o[k] = raw[k]
    t = raw.get("d013")
    if isinstance(t, dict):
        try:
            if t.get("bpm"):
                o["d013"] = {"bpm": min(max(float(t["bpm"]), 1.0), 999.0)}
            elif t.get("ms"):
                o["d013"] = {"ms": min(max(int(t["ms"]), 1), 3600000)}
        except (TypeError, ValueError):
            pass
    return o


# ── selection ────────────────────────────────────────────────────────────────

def finding_key(f: Finding) -> str:
    """Stable key of a finding (for picking fixes one by one)."""
    return f"{f.code}|{f.location}|{f.message}"


def fixable(f: Finding) -> bool:
    """True when :func:`fix` knows how to fix this finding."""
    r = f.ref or {}
    if f.code == "D002":
        return "function" in r or "widget" in r
    if f.code == "D003":
        if "group" in r:
            return False
        if "widget" in r and "target" not in r and "fixture" not in r:
            return True                        # CueList without chaser: rewire only
        if "widget" in r and "target" in r and "CueList" in f.location:
            return True                        # rewire / detach
        if "bound" in f.message:
            return False
        return True
    if f.code in ("D004", "D013"):
        return True
    if f.code in ("D005", "D006", "D007", "D010", "D011", "D016", "D017"):
        return True
    if f.code == "D008":
        return True
    if f.code == "D015":
        return True                            # removed only if unused (checked at fix time)
    return False


def fix_hint(f: Finding) -> str:
    """One line: what the fix will do (for the UI)."""
    return {
        "D002": "renumber the later copies",
        "D003": "remove the broken reference (or rewire it to the function with the same name)",
        "D004": ("merge it into its one scene, or remove it" if "degenerate" in f.message
                 else "remove it (and the steps/buttons that use it)"),
        "D013": "give the steps a duration (ms or BPM)",
        "D005": "add the missing channels at their neutral value",
        "D006": "set the channel to its neutral value",
        "D007": "give the chaser its own copy of the scene",
        "D008": ("create PANIC RESET (script + neutral scene) and its button"
                 if "no PANIC" in f.message else "add a PANIC RESET button"),
        "D010": "move the setlist page to page 1",
        "D011": "move it inside (when it fits)",
        "D015": "remove it if nothing uses it, or give it a name from its context",
        "D016": "remove the unused function",
        "D017": "wrap the scene in a PANIC RESET script that stops everything first",
    }.get(f.code, "") if fixable(f) else ""


# ── helpers ──────────────────────────────────────────────────────────────────

def _engine(root):
    return root.find("Engine")


def _functions(root) -> List[ET.Element]:
    return _engine(root).findall("Function")


def _fn(root, fid) -> Optional[ET.Element]:
    return next((f for f in _functions(root) if f.get("ID") == fid), None)


def _max_fid(root) -> int:
    return max([int(f.get("ID")) for f in _functions(root) if (f.get("ID") or "").isdigit()] + [-1])


def _insert_function(root, fn: ET.Element) -> None:
    eng = _engine(root)
    last = None
    for i, c in enumerate(list(eng)):
        if c.tag == "Function":
            last = i
    if last is None:
        last = max([i for i, c in enumerate(list(eng)) if c.tag in ("Fixture", "FixtureGroup")] + [-1])
    eng.insert(last + 1, fn)


def _renumber_steps(fn: ET.Element) -> None:
    for n, st in enumerate(fn.findall("Step")):
        if st.get("Number") is not None:
            st.set("Number", str(n))


def _unlink_function(root, fid: str) -> List[str]:
    """Remove every reference to function *fid*; returns what changed."""
    out = []
    for f in _functions(root):
        if f.get("Type") != "Sequence":
            dead = [s for s in f.findall("Step") if (s.text or "").strip() == fid]
            for s in dead:
                f.remove(s)
            if dead:
                _renumber_steps(f)
                out.append(f"{len(dead)} step(s) of function {f.get('ID')} '{f.get('Name', '')}'")
        for tr in f.findall("Track"):
            for sf in [x for x in tr.findall("ShowFunction") if x.get("ID") == fid]:
                tr.remove(sf)
                out.append(f"show item of function {f.get('ID')}")
        if f.get("Type") == "Script":
            for c in list(f.findall("Command")):
                from urllib.parse import unquote
                ids = [m.group(1) for m in SCRIPT_FUNC_RE.finditer(unquote(c.text or ""))]
                if fid in ids:
                    f.remove(c)
                    out.append(f"script command in function {f.get('ID')}")
    vc = root.find("VirtualConsole")
    if vc is not None:
        for w in vc.iter():
            if w.tag == "CueList":
                ch = w.find("Chaser")
                if ch is not None and (ch.text or "").strip() == fid:
                    ch.text = NONE_ID
                    out.append(f"CueList '{w.get('Caption', '')}' detached")
                continue
            for fe in list(w.findall("Function")) + [e for p in w.findall("Playback")
                                                     for e in p.findall("Function")]:
                if fe.get("ID") == fid:
                    fe.set("ID", NONE_ID)
                    out.append(f"{w.tag} '{(w.get('Caption') or '').strip()}' unlinked")
                elif fe.get("ID") is None and (fe.text or "").strip() == fid:
                    fe.text = NONE_ID           # slider playback: <Function>id</Function>
                    out.append(f"{w.tag} '{(w.get('Caption') or '').strip()}' unlinked")
    return out


def _remove_function(root, fid: str) -> List[str]:
    fn = _fn(root, fid)
    if fn is None:
        return []
    _engine(root).remove(fn)
    return _unlink_function(root, fid)


def _neutral_values(ws: _Workspace, fx_id: str, intensity_zero: bool = False) -> Dict[int, int]:
    from core.quick_start.channel_model import neutral_value
    fx = ws.fixtures.get(fx_id)
    if fx is None:
        return {}
    out = {}
    d = fx.get("def")
    for c in range(fx["channels"]):
        name = fx["channel_names"][c] if c < len(fx["channel_names"]) else ""
        cd = (d or {}).get("channel_defs", {}).get(name) if d else None
        v = neutral_value(name, cd) if cd else 0
        if intensity_zero and cd and cd.get("group") == "Intensity":
            v = 0
        out[c] = v
    return out


def _fmt(pairs: Dict[int, int]) -> str:
    return ",".join(f"{c},{pairs[c]}" for c in sorted(pairs))


def _first_page(root) -> Optional[ET.Element]:
    vc = root.find("VirtualConsole")
    if vc is None:
        return None
    return next((p for p in vc if p.tag in ("Frame", "SoloFrame")), None)


def _add_button(root, caption: str, fid: str) -> str:
    """Toggle button for *fid* on the first page at a free spot."""
    from core import porter_vc
    page = _first_page(root)
    vc = root.find("VirtualConsole")
    if vc is None:
        vc = ET.SubElement(root, "VirtualConsole")
    if page is None:
        page = ET.SubElement(vc, "Frame", {"Caption": "Page 1", "ID": str(vc_ops._next_id(vc))})
        ET.SubElement(page, "WindowState", {"Visible": "True", "X": "0", "Y": "0",
                                            "Width": "1920", "Height": "1080"})
    pg = porter_vc._Page(page)
    w, h = 150, 60
    spot = pg.find_spot(w, h) or (porter_vc.MARGIN, porter_vc.MARGIN)
    btn = ET.Element("Button", {"Caption": caption, "ID": str(vc_ops._next_id(vc)), "Icon": ""})
    ET.SubElement(btn, "WindowState", {"Visible": "True", "X": str(spot[0]), "Y": str(spot[1]),
                                       "Width": str(w), "Height": str(h)})
    app = ET.SubElement(btn, "Appearance")
    ET.SubElement(app, "FrameStyle").text = "None"
    ET.SubElement(app, "BackgroundColor").text = "4294932639"      # pink, like Quick Start
    ET.SubElement(btn, "Function", {"ID": fid})
    ET.SubElement(btn, "Action").text = "Toggle"
    ET.SubElement(btn, "Intensity", {"Adjust": "False"})
    pg.add(btn, *spot)
    return f"button '{caption}' on page '{page.get('Caption', '')}' at {spot[0]},{spot[1]}"


def _panic_script(root, reset_scene: str, name: str = "PANIC RESET") -> str:
    """Script: stop every function (except the reset scene), start the reset
    scene, wait a tick, stop itself — the Quick Start PANIC RESET recipe."""
    fid = str(_max_fid(root) + 1)
    fn = ET.Element("Function", {"ID": fid, "Type": "Script", "Name": name})
    ET.SubElement(fn, "Speed", {"FadeIn": "0", "FadeOut": "0", "Duration": "0"})
    ET.SubElement(fn, "Direction").text = "Forward"
    ET.SubElement(fn, "RunOrder").text = "SingleShot"
    ET.SubElement(fn, "Command").text = "stoponexit%3Afalse"
    for f in sorted(_functions(root), key=lambda x: int(x.get("ID", "0") or 0)):
        if f.get("ID") != reset_scene:
            ET.SubElement(fn, "Command").text = f"stopfunction%3A{f.get('ID')}"
    ET.SubElement(fn, "Command").text = f"startfunction%3A{reset_scene}"
    ET.SubElement(fn, "Command").text = "wait%3A100ms"
    ET.SubElement(fn, "Command").text = f"stopfunction%3A{fid}"
    _insert_function(root, fn)
    return fid


# ── fixers (each returns [action strings] for one finding) ───────────────────

def _fix_d002(root, f: Finding, done: Set[str]) -> List[str]:
    r = f.ref
    if "widget" in r:
        if "vc" in done:
            return []
        done.add("vc")
        ch = vc_ops.fix_duplicate_ids(root)["renumbered"]
        return [f"VC widget '{c['caption']}' {c['old']} → {c['new']}" for c in ch]
    fid = r.get("function")
    dups = [x for x in _functions(root) if x.get("ID") == fid]
    out = []
    for x in dups[1:]:
        new = str(_max_fid(root) + 1)
        x.set("ID", new)
        out.append(f"function '{x.get('Name', '')}' {fid} → {new} (references keep the first)")
    return out


def _fix_d003(root, f: Finding) -> List[str]:
    r = f.ref
    tgt, fx = r.get("target"), r.get("fixture")
    if "function" in r:
        fn = _fn(root, r["function"])
        if fn is None:
            return []
        if fx:
            n = 0
            for tag, key in (("FixtureVal", None), ("Fixture", "ID")):
                for el in list(fn.findall(tag)):
                    x = el.get("ID") if key is None else (el.findtext("ID") or "").strip()
                    if x == fx:
                        fn.remove(el)
                        n += 1
            return [f"removed {n} entr{'y' if n == 1 else 'ies'} for missing fixture {fx}"] if n else []
        if tgt:
            out = []
            dead = [s for s in fn.findall("Step") if (s.text or "").strip() == tgt]
            for s in dead:
                fn.remove(s)
            if dead:
                _renumber_steps(fn)
                out.append(f"removed {len(dead)} step(s) → missing function {tgt}")
            for tr in fn.findall("Track"):
                for sf in [x for x in tr.findall("ShowFunction") if x.get("ID") == tgt]:
                    tr.remove(sf)
                    out.append(f"removed show item → missing function {tgt}")
            from urllib.parse import unquote
            for c in list(fn.findall("Command")):
                if tgt in [m.group(1) for m in SCRIPT_FUNC_RE.finditer(unquote(c.text or ""))]:
                    fn.remove(c)
                    out.append(f"removed script command → missing function {tgt}")
            return out
        dead = [s for s in fn.findall("Step") if not (s.text or "").strip()]
        for s in dead:
            fn.remove(s)
        _renumber_steps(fn)
        return [f"removed {len(dead)} empty step(s)"] if dead else []
    if "widget" in r:
        vc = root.find("VirtualConsole")
        ws = [w for w in vc.iter() if w.get("ID") == r["widget"] and vc_ops._is_widget(w)]
        out = []
        for w in ws:
            if fx:
                for lvl in w.iter("Level"):
                    for ch in [c for c in lvl.findall("Channel") if c.get("Fixture") == fx]:
                        lvl.remove(ch)
                        out.append(f"removed level channel of missing fixture {fx}")
            elif tgt:
                for fe in w.iter("Function"):
                    if fe.get("ID") == tgt:
                        fe.set("ID", NONE_ID)
                        out.append(f"unlinked from missing function {tgt} (caption only)")
        return out
    return []



def _opt(options, code: str, default):
    return ((options or {}).get(code.lower()) if options else None) or default


def _replace_refs(root, old: str, new: str) -> int:
    """Point every user of function *old* at *new*; returns how many places."""
    from urllib.parse import quote, unquote
    n = 0
    for f in _functions(root):
        if f.get("Type") in ("Chaser", "Collection"):
            for st in f.findall("Step"):
                if (st.text or "").strip() == old:
                    st.text = new
                    n += 1
        if f.get("Type") == "Script":
            for c in f.findall("Command"):
                t = unquote(c.text or "")
                m = re.match(r"((?:start|stop)function:)(\d+)$", t, re.I)
                if m and m.group(2) == old:
                    c.text = quote(m.group(1) + new, safe="")
                    n += 1
    vc = root.find("VirtualConsole")
    if vc is not None:
        for w in vc.iter():
            if w.tag == "CueList":
                continue
            for fe in w.findall("Function"):
                if fe.get("ID") == old:
                    fe.set("ID", new)
                    n += 1
    return n


def _fix_d004_chaser(root, f: Finding, options) -> List[str]:
    fid = f.ref["function"]
    ch = _fn(root, fid)
    if ch is None:
        return []
    steps = [s for s in ch.findall("Step") if (s.text or "").strip()]
    name = ch.get("Name", "")
    if len(steps) == 1 and _opt(options, "D004", "merge") == "merge":
        scene = (steps[0].text or "").strip()
        n = _replace_refs(root, fid, scene)
        _engine(root).remove(ch)
        return [f"chaser {name!r} merged into function {scene}: {n} user(s) now run it directly"]
    touched = _remove_function(root, fid)
    return [f"removed {name!r}" + (f"; also: {', '.join(touched)}" if touched else "")]


def _fix_d013(root, f: Finding, options) -> List[str]:
    fn = _fn(root, f.ref["function"])
    if fn is None:
        return []
    raw = (options or {}).get("d013") or {}
    if raw.get("bpm"):
        ms = max(1, int(round(60000 / float(raw["bpm"]))))
        how = f"{raw['bpm']} BPM"
    else:
        ms = max(1, int(raw.get("ms") or 500))
        how = f"{ms} ms"
    sm = fn.find("SpeedModes")
    dmode = (sm.get("Duration") if sm is not None else "Default") or "Default"
    out = []
    if dmode == "PerStep":
        for i in f.ref.get("steps", []):
            st = fn.findall("Step")[i - 1]
            st.set("Hold", str(ms))
        out.append(f"{len(f.ref.get('steps', []))} step(s) now hold {ms} ms ({how})")
    else:
        sp = fn.find("Speed")
        if sp is not None:
            sp.set("Duration", str(ms))
            out.append(f"chaser duration 0 → {ms} ms ({how})")
    return out


def _suggest_name(root, fid: str) -> Optional[str]:
    """A name for an unnamed function from where it is used."""
    fn = _fn(root, fid)
    if fn is None:
        return None
    vc = root.find("VirtualConsole")
    if vc is not None:
        for w in vc.iter():
            if w.tag == "Button" and any(fe.get("ID") == fid for fe in w.findall("Function")):
                cap = " ".join((w.get("Caption") or "").split())
                if cap:
                    return cap
    for p in _functions(root):
        if p.get("Type") in ("Chaser", "Collection") and not UNNAMED_RE.match(p.get("Name", "")):
            steps = [s for s in p.findall("Step") if (s.text or "").strip()]
            for i, s in enumerate(steps):
                if (s.text or "").strip() == fid:
                    return f"{p.get('Name', '')} - step {i + 1}"
    return None


def _fix_d015_rename(root, f: Finding) -> List[str]:
    fid = f.ref.get("function")
    fn = _fn(root, fid) if fid is not None else None
    if fn is None:
        return []
    new = _suggest_name(root, fid)
    if not new:
        return []
    names = {x.get("Name") for x in _functions(root)}
    base, k = new, 2
    while new in names:
        new, k = f"{base} ({k})", k + 1
    old = fn.get("Name", "")
    fn.set("Name", new)
    return [f"renamed {old!r} → {new!r}"]


def _fix_d003_rewire(root, f: Finding) -> List[str]:
    """Widget → missing / absent function: point it at the function with the
    caption's name (CueList: a chaser, caption match or the only chaser)."""
    r = f.ref
    vc = root.find("VirtualConsole")
    if vc is None or "widget" not in r:
        return []
    funcs = _functions(root)
    out = []
    for w in [x for x in vc.iter() if vc_ops._is_widget(x) and x.get("ID") == r["widget"]]:
        cap = " ".join((w.get("Caption") or "").split()).lower()
        if w.tag == "CueList":
            chasers = [x for x in funcs if x.get("Type") == "Chaser"]
            cand = [x for x in chasers if " ".join(x.get("Name", "").split()).lower() == cap] or \
                   (chasers if len(chasers) == 1 else [])
            if len(cand) == 1:
                ch = w.find("Chaser")
                if ch is None:
                    ch = ET.SubElement(w, "Chaser")
                ch.text = cand[0].get("ID")
                out.append(f"CueList '{w.get('Caption', '')}' → chaser {cand[0].get('ID')} '{cand[0].get('Name', '')}'")
            continue
        cand = [x for x in funcs if cap and " ".join(x.get("Name", "").split()).lower() == cap]
        if len(cand) == 1:
            for fe in w.iter("Function"):
                if fe.get("ID") == r.get("target"):
                    fe.set("ID", cand[0].get("ID"))
                    out.append(f"{w.tag} '{w.get('Caption', '')}' → function {cand[0].get('ID')} '{cand[0].get('Name', '')}'")
    return out


def _fix_remove(root, f: Finding, only_unused: bool = False) -> List[str]:
    fid = f.ref.get("function")
    if fid is None or _fn(root, fid) is None:
        return []
    if only_unused:
        ws = _Workspace(root, {})
        if ws.parents.get(fid) or ws.vc_refs.get(fid):
            return []
    name = _fn(root, fid).get("Name", "")
    touched = _remove_function(root, fid)
    return [f"removed {name!r}" + (f"; also: {', '.join(touched)}" if touched else "")]


def _fix_d005(root, f: Finding, defs) -> List[str]:
    ws = _Workspace(root, defs)
    fn = _fn(root, f.ref["function"])
    fxid = f.ref["fixture"]
    neutral = _neutral_values(ws, fxid)
    for v in (fn.findall("FixtureVal") if fn is not None else []):
        if v.get("ID") == fxid:
            pairs = _scene_pairs(v)
            added = [c for c in neutral if c not in pairs]
            for c in added:
                pairs[c] = neutral[c]
            v.text = _fmt(pairs)
            return [f"fixture {fxid}: added channels {', '.join(str(c + 1) for c in added)} "
                    f"at neutral"] if added else []
    return []


def _fix_d006(root, f: Finding, defs) -> List[str]:
    ws = _Workspace(root, defs)
    fn = _fn(root, f.ref["function"])
    fxid, ch = f.ref["fixture"], int(f.ref["channel"])
    val = _neutral_values(ws, fxid).get(ch, 0)
    for v in (fn.findall("FixtureVal") if fn is not None else []):
        if v.get("ID") == fxid:
            pairs = _scene_pairs(v)
            old = pairs.get(ch)
            pairs[ch] = val
            v.text = _fmt(pairs)
            return [f"fixture {fxid} channel {ch + 1}: {old} → {val}"]
    return []


def _fix_d007(root, f: Finding) -> List[str]:
    fid = f.ref["function"]
    src = _fn(root, fid)
    if src is None:
        return []
    new = copy.deepcopy(src)
    nid = str(_max_fid(root) + 1)
    new.set("ID", nid)
    new.set("Name", f"{src.get('Name', '')} (chaser)")
    _insert_function(root, new)
    n = 0
    for ch in _functions(root):
        if ch.get("Type") == "Chaser":
            for s in ch.findall("Step"):
                if (s.text or "").strip() == fid:
                    s.text = nid
                    n += 1
    return [f"chaser steps ({n}) now use copy {nid} '{new.get('Name')}'; the button keeps {fid}"]


def _fix_d008(root, f: Finding, defs) -> List[str]:
    if "no PANIC" not in f.message:
        fid = f.ref.get("function")
        return [_add_button(root, "PANIC RESET", fid)] if fid else []
    ws = _Workspace(root, defs)
    sid = str(_max_fid(root) + 1)
    scene = ET.Element("Function", {"ID": sid, "Type": "Scene", "Name": "Reset: neutral state"})
    ET.SubElement(scene, "Speed", {"FadeIn": "0", "FadeOut": "0", "Duration": "0"})
    for fxid in ws.fixtures:
        vals = _neutral_values(ws, fxid, intensity_zero=True)
        if vals:
            ET.SubElement(scene, "FixtureVal", {"ID": fxid}).text = _fmt(vals)
    _insert_function(root, scene)
    pid = _panic_script(root, sid)
    return [f"created scene {sid} 'Reset: neutral state' and script {pid} 'PANIC RESET'",
            _add_button(root, "PANIC RESET", pid)]


def _fix_d010(root, f: Finding) -> List[str]:
    vc = root.find("VirtualConsole")
    page = next((p for p in vc if p.tag in ("Frame", "SoloFrame") and p.get("ID") == f.ref.get("page")), None)
    if page is None:
        return []
    first = next(i for i, p in enumerate(list(vc)) if p.tag in ("Frame", "SoloFrame"))
    vc.remove(page)
    vc.insert(first, page)
    return [f"page '{page.get('Caption', '')}' is now page 1"]


def _fix_d011(root, f: Finding) -> List[str]:
    vc = root.find("VirtualConsole")
    parent = {c: p for p in vc.iter() for c in p}
    out = []
    for w in [x for x in vc.iter() if vc_ops._is_widget(x) and x.get("ID") == f.ref.get("widget")]:
        par = parent.get(w)
        ws_, pws = w.find("WindowState"), par.find("WindowState") if par is not None else None
        if ws_ is None or pws is None:
            continue
        x, y = int(ws_.get("X", 0)), int(ws_.get("Y", 0))
        ww, hh = int(ws_.get("Width", 0)), int(ws_.get("Height", 0))
        pw, ph = int(pws.get("Width", 0)), int(pws.get("Height", 0))
        if ww > pw or hh > ph:
            continue                           # can't fit: leave it
        nx, ny = min(max(0, x), pw - ww), min(max(0, y), ph - hh)
        if (nx, ny) != (x, y):
            vc_ops._set_xy(w, nx, ny)
            out.append(f"moved from {x},{y} to {nx},{ny}")
    return out


def _fix_d017(root, f: Finding) -> List[str]:
    sid = f.ref["function"]
    scene = _fn(root, sid)
    if scene is None:
        return []
    name = scene.get("Name", "PANIC RESET")
    pid = _panic_script(root, sid, name=name)
    scene.set("Name", f"{name} (state)")
    n = 0
    vc = root.find("VirtualConsole")
    if vc is not None:
        for w in vc.iter("Button"):
            for fe in w.findall("Function"):
                if fe.get("ID") == sid:
                    fe.set("ID", pid)
                    n += 1
    return [f"script {pid} {name!r} stops every function, then starts scene {sid} "
            f"(renamed '{name} (state)'); {n} button(s) now run the script"]


# ── public API ───────────────────────────────────────────────────────────────

def fix(root, qxf_defs=None, *, keys: Optional[Iterable[str]] = None,
        codes: Optional[Iterable[str]] = None, allow_fx: Iterable[str] = (),
        options: Optional[dict] = None) -> FixResult:
    """Apply the selected fixes to a copy of *root*.

    *options* per code, lower-case keys: ``d003`` ``"unlink"``|``"rewire"``,
    ``d004`` ``"merge"``|``"remove"``, ``d013`` ``{"ms"|"bpm": n}``,
    ``d015`` ``"remove"``|``"rename"``.

    *keys*   finding keys (:func:`finding_key`) to fix; ``None`` = all fixable
    *codes*  restrict to these codes (e.g. ``{"D003", "D005"}``)
    """
    if isinstance(root, ET.ElementTree):
        root = root.getroot()
    work = qxw_io.strip_ns(copy.deepcopy(root))
    defs = _normalise_defs(qxf_defs)
    before = check(work, defs, allow_fx=allow_fx)
    keyset = set(keys) if keys is not None else None
    codeset = set(codes) if codes is not None else None
    chosen = [f for f in before.findings
              if (keyset is None or finding_key(f) in keyset)
              and (codeset is None or f.code in codeset)]
    actions, skipped = [], []
    done: Set[str] = set()
    for code in FIX_ORDER:
        for f in [x for x in chosen if x.code == code]:
            if not fixable(f):
                continue
            if code == "D002":
                acts = _fix_d002(work, f, done)
            elif code == "D003":
                acts = []
                if (options or {}).get("d003") == "rewire" and "widget" in f.ref:
                    acts = _fix_d003_rewire(work, f)
                if not acts and not ("widget" in f.ref and "CueList" in f.location):
                    acts = _fix_d003(work, f)       # a CueList can only be rewired
            elif code == "D004":
                acts = _fix_d004_chaser(work, f, options) if "degenerate" in f.message \
                    else _fix_remove(work, f)
            elif code == "D013":
                acts = _fix_d013(work, f, options)
            elif code == "D005":
                acts = _fix_d005(work, f, defs)
            elif code == "D006":
                acts = _fix_d006(work, f, defs)
            elif code == "D007":
                acts = _fix_d007(work, f)
            elif code == "D015":
                acts = _fix_d015_rename(work, f) if (options or {}).get("d015") == "rename" \
                    else _fix_remove(work, f, only_unused=True)
            elif code == "D016":
                acts = _fix_remove(work, f)
            elif code == "D017":
                acts = _fix_d017(work, f)
            elif code == "D010":
                acts = _fix_d010(work, f)
            elif code == "D011":
                acts = _fix_d011(work, f)
            elif code == "D008":
                acts = _fix_d008(work, f, defs)
            else:
                acts = []
            if acts:
                actions += [{"code": f.code, "location": f.location, "action": a} for a in acts]
            elif code == "D015":
                skipped.append({"code": f.code, "location": f.location,
                                "reason": "still used — give it a name in QLC+"})
            elif code == "D011":
                skipped.append({"code": f.code, "location": f.location,
                                "reason": "larger than its page / frame — resize it in QLC+"})
            elif code == "D003" and "widget" in f.ref and "CueList" in f.location:
                skipped.append({"code": f.code, "location": f.location,
                                "reason": "no chaser to rewire it to (need option d003 = rewire and "
                                          "a chaser named like the CueList, or only one chaser) — "
                                          "attach one in QLC+"})
            elif code not in ("D002",):
                skipped.append({"code": f.code, "location": f.location,
                                "reason": "nothing left to change (fixed by an earlier fix)"})
    for f in chosen:
        if not fixable(f) and f.severity != "info":
            skipped.append({"code": f.code, "location": f.location,
                            "reason": "no automatic fix — " + f.message})
    after = check(work, defs, allow_fx=allow_fx)
    return FixResult(work, before, after, actions, skipped)


def format_report(res: FixResult, source: str = "", output: str = "") -> str:
    b, a = res.before.severity_counts(), res.after.severity_counts()
    lines = ["═══ Workspace Doctor — Fix Report ═══", ""]
    if source:
        lines.append(f"Source:  {source}")
    if output:
        lines.append(f"Output:  {output}")
    lines += [f"Before:  {b['error']} error(s), {b['warning']} warning(s)",
              f"After:   {a['error']} error(s), {a['warning']} warning(s)", ""]
    lines.append(f"── FIXES ({len(res.actions)}) ──")
    for x in res.actions:
        lines.append(f"  {x['code']} {x['location']}: {x['action']}")
    if not res.actions:
        lines.append("  (none)")
    if res.skipped:
        lines += ["", f"── NOT FIXED ({len(res.skipped)}) ──"]
        for x in res.skipped:
            lines.append(f"  {x['code']} {x['location']}: {x['reason']}")
    rem = [f for f in res.after.findings if f.severity != "info"]
    if rem:
        lines += ["", f"── STILL OPEN ({len(rem)}) ──"]
        for f in rem[:200]:
            lines.append(f"  [{f.severity}] {f.code} {f.location}: {f.message}")
        if len(rem) > 200:
            lines.append(f"  … {len(rem) - 200} more")
    lines += ["", "═══════════════════════════════════════"]
    return "\n".join(lines) + "\n"


def report_path(qxw_path: str) -> str:
    stem, _ = os.path.splitext(qxw_path)
    return stem + "_fix_report.txt"


def fix_file(path: str, qxf_defs=None, *, out_path: Optional[str] = None,
             keys=None, codes=None, allow_fx=(), options=None) -> dict:
    """Fix *path* into a new file (default ``<name>_v<N+1>.qxw`` next to it)
    and write the fix report next to that.  Never overwrites *path*.
    Returns ``{"output", "report_path", "result"}``."""
    tree = qxw_io.load_qxw(path)
    res = fix(tree.getroot(), qxf_defs, keys=keys, codes=codes, allow_fx=allow_fx, options=options)
    out = out_path or qxw_io.next_version_path(path)
    ET.indent(res.root, space=" ")
    qxw_io.write_qxw(res.root, out, protect=[path])
    rp = report_path(out)
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write(format_report(res, os.path.basename(path), os.path.basename(out)))
    return {"output": out, "report_path": rp, "result": res}
