"""
core/rig_reducer.py — Rig Reducer (WORKPLAN Phase 2.2)
=====================================================
Keep some fixtures of a workspace, remove the others **with cascade**, and
optionally re-patch the kept ones.  Works on a copy; the result is written
to a new file (``<name>_v<N+1>.qxw``) and checked by the Workspace Doctor.

Cascade (in this order, until nothing changes):

1. ``<Fixture>`` elements of removed fixtures.
2. Fixture groups: heads of removed fixtures; a group left empty is removed.
3. Functions: scene values (``FixtureVal``) and Sequence step values of
   removed fixtures; EFX entries; RGB matrices whose group is gone.  A
   scene / sequence / EFX that *had* fixtures and has none left, a matrix
   without group, a chaser or collection left without steps are removed —
   and with them every step, script command and show item that used them.
4. Virtual Console: buttons (and sliders' playback) running a removed
   function are removed; a CueList whose chaser is gone is removed; Level
   sliders lose the channels of removed fixtures, and are removed when none
   is left.  Frames are kept (possibly empty — nothing is re-arranged).
5. 3D monitor: ``FxItem`` of removed fixtures.  Meshes are kept.

Re-patch: ``{fixture id: {"name", "universe", "address"}}`` (universe and
address 1-based as QLC+ shows them; stored 0-based in the file).

Deterministic: removals in document order; no new IDs are created.
"""

from __future__ import annotations

import copy
import os
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, Iterable, List, Optional

from core import qxw_io, vc_ops

NONE_ID = "4294967295"


def _engine(root):
    return root.find("Engine")


def fixtures(root: ET.Element) -> List[dict]:
    """Fixtures of a (namespaced or stripped) workspace for the UI:
    ``[{id, name, manufacturer, model, mode, universe (1-based), address
    (1-based), channels}]`` in document order."""
    r = qxw_io.strip_ns(copy.deepcopy(root)) if root.tag.startswith("{") else root
    out = []
    for f in _engine(r).findall("Fixture"):
        def t(tag, d=""):
            return (f.findtext(tag) or d).strip()
        out.append({"id": t("ID"), "name": t("Name"), "manufacturer": t("Manufacturer"),
                    "model": t("Model"), "mode": t("Mode"),
                    "universe": int(t("Universe", "0") or 0) + 1,
                    "address": int(t("Address", "0") or 0) + 1,
                    "channels": int(t("Channels", "0") or 0)})
    return out


def _seq_items(text: str):
    parts = (text or "").strip().split(":")
    return [(parts[i].strip(), parts[i + 1].strip()) for i in range(0, len(parts) - 1, 2)
            if parts[i].strip().isdigit()]


def _pairs_count(v: str) -> int:
    return len([x for x in (v or "").split(",") if x.strip()]) // 2


def reduce(root: ET.Element, keep: Iterable[str],
           repatch: Optional[Dict[str, dict]] = None) -> dict:
    """Keep only the fixtures in *keep* (IDs); returns
    ``{"root": new stripped root, "log": [lines], "removed": {...counts}}``."""
    work = qxw_io.strip_ns(copy.deepcopy(root))
    eng = _engine(work)
    keep = {str(k) for k in keep}
    all_ids = [(f.findtext("ID") or "").strip() for f in eng.findall("Fixture")]
    gone = [i for i in all_ids if i not in keep]
    gone_set = set(gone)
    log: List[str] = []
    counts = {"fixtures": 0, "groups": 0, "functions": 0, "widgets": 0, "values": 0}

    # 1. fixtures
    for f in list(eng.findall("Fixture")):
        if (f.findtext("ID") or "").strip() in gone_set:
            eng.remove(f)
            counts["fixtures"] += 1
            log.append(f"fixture {f.findtext('ID')} '{f.findtext('Name') or ''}' removed")

    # 2. groups
    dead_groups = set()
    for g in list(eng.findall("FixtureGroup")):
        heads = g.findall("Head")
        for h in heads:
            if h.get("Fixture") in gone_set:
                g.remove(h)
        if heads and not g.findall("Head"):
            eng.remove(g)
            dead_groups.add(g.get("ID"))
            counts["groups"] += 1
            log.append(f"fixture group {g.get('ID')} '{g.findtext('Name') or ''}' removed (empty)")

    # 3. functions (values, then removal cascade until stable)
    dead_fns: List[str] = []
    for fn in eng.findall("Function"):
        ftype = fn.get("Type")
        had = False
        if ftype in ("Scene", "Sequence"):
            vals = fn.findall("FixtureVal")
            had = bool(vals)
            for v in vals:
                if v.get("ID") in gone_set:
                    fn.remove(v)
                    counts["values"] += 1
            if ftype == "Sequence":
                for st in fn.findall("Step"):
                    items = _seq_items(st.text or "")
                    if items:
                        had = True
                        kept = [(a, b) for a, b in items if a not in gone_set]
                        if len(kept) != len(items):
                            st.text = ":".join(f"{a}:{b}" for a, b in kept)
                            st.set("Values", str(sum(_pairs_count(b) for _, b in kept)))
            if had and not fn.findall("FixtureVal") and not any(
                    _seq_items(s.text or "") for s in fn.findall("Step")):
                dead_fns.append(fn.get("ID"))
        elif ftype == "EFX":
            ents = fn.findall("Fixture")
            for e in ents:
                if (e.findtext("ID") or "").strip() in gone_set:
                    fn.remove(e)
            if ents and not fn.findall("Fixture"):
                dead_fns.append(fn.get("ID"))
        elif ftype == "RGBMatrix":
            if (fn.findtext("FixtureGroup") or "").strip() in dead_groups:
                dead_fns.append(fn.get("ID"))

    from core.doctor.fixes import _unlink_function
    steps_before = {f.get("ID"): len(f.findall("Step")) for f in eng.findall("Function")
                    if f.get("Type") in ("Chaser", "Collection")}
    removed_fns: List[str] = []
    queue = list(dict.fromkeys(dead_fns))
    while queue:
        fid = queue.pop(0)
        fn = next((f for f in eng.findall("Function") if f.get("ID") == fid), None)
        if fn is None:
            continue
        eng.remove(fn)
        removed_fns.append(fid)
        why = ("no step left" if fn.get("Type") in ("Chaser", "Collection")
               else "its bound scene was removed" if fn.get("BoundScene") in removed_fns
               else "no fixture left")
        log.append(f"function {fid} '{fn.get('Name', '')}' ({fn.get('Type')}) removed — {why}")
        _unlink_function(work, fid)
        # a Sequence without its bound scene can't run: it goes too
        for other in eng.findall("Function"):
            if other.get("BoundScene") == fid and other.get("ID") not in queue \
                    and other.get("ID") not in removed_fns:
                queue.append(other.get("ID"))
        # chasers / collections that *lost* all their steps go too
        for other in eng.findall("Function"):
            oid = other.get("ID")
            if (other.get("Type") in ("Chaser", "Collection") and oid not in queue
                    and oid not in removed_fns and steps_before.get(oid)
                    and not other.findall("Step")):
                queue.append(oid)
    counts["functions"] = len(removed_fns)

    # 4. Virtual Console
    vc = work.find("VirtualConsole")
    if vc is not None:
        parent = {c: p for p in vc.iter() for c in p}
        for w in [x for x in vc.iter() if vc_ops._is_widget(x)]:
            tag = w.tag
            drop = False
            if tag == "Button":
                fe = w.find("Function")
                action = (w.findtext("Action") or "").strip()
                drop = (fe is not None and fe.get("ID") == NONE_ID
                        and action not in ("StopAll", "Blackout")
                        and _was_linked(root, w))
            elif tag == "CueList":
                drop = (w.findtext("Chaser") or "").strip() == NONE_ID and _was_linked(root, w)
            elif tag == "Slider":
                lvl = w.find("Level")
                if lvl is not None:
                    chans = lvl.findall("Channel")
                    for ch in chans:
                        if ch.get("Fixture") in gone_set:
                            lvl.remove(ch)
                    drop = bool(chans) and not lvl.findall("Channel")
            if drop and w in parent:
                parent[w].remove(w)
                counts["widgets"] += 1
                log.append(f"VC {tag} '{(w.get('Caption') or '').strip()}' removed")

    # 5. 3D monitor
    mon = eng.find("Monitor")
    if mon is not None:
        for it in list(mon.findall("FxItem")):
            if it.get("ID") in gone_set:
                mon.remove(it)

    # 6. re-patch
    for f in eng.findall("Fixture"):
        fid = (f.findtext("ID") or "").strip()
        p = (repatch or {}).get(fid)
        if not p:
            continue
        for key, tag, conv in (("name", "Name", str), ("universe", "Universe", lambda v: str(int(v) - 1)),
                               ("address", "Address", lambda v: str(int(v) - 1))):
            if p.get(key) not in (None, ""):
                el = f.find(tag)
                if el is None:
                    el = ET.SubElement(f, tag)
                new = conv(p[key])
                if (el.text or "").strip() != new:
                    log.append(f"fixture {fid}: {tag} {el.text!r} → {new!r}"
                               + (" (file value, QLC+ shows +1)" if tag != "Name" else ""))
                    el.text = new
    return {"root": work, "log": log, "removed": counts, "removed_ids": gone}


def _was_linked(orig_root: ET.Element, w: ET.Element) -> bool:
    """True if the widget with the same ID pointed at a function in the
    original (so it was unlinked by the reduction, not a label before)."""
    wid = w.get("ID")
    r = orig_root
    for el in r.iter():
        tag = el.tag.split("}")[-1]
        if tag == w.tag and el.get("ID") == wid:
            if tag == "CueList":
                ch = next((c for c in el if c.tag.split("}")[-1] == "Chaser"), None)
                return ch is not None and (ch.text or "").strip() not in ("", NONE_ID)
            fe = next((c for c in el if c.tag.split("}")[-1] == "Function"), None)
            return fe is not None and fe.get("ID") not in (None, NONE_ID)
    return False


def format_report(res: dict, source: str, output: str, doctor=None) -> str:
    c = res["removed"]
    lines = ["═══ Rig Reducer — Report ═══", "", f"Source:  {source}", f"Output:  {output}", "",
             f"Removed: {c['fixtures']} fixture(s), {c['groups']} group(s), "
             f"{c['functions']} function(s), {c['widgets']} VC widget(s), "
             f"{c['values']} scene value set(s)", "", "── CHANGES ──"]
    lines += [f"  {x}" for x in res["log"]] or ["  (none)"]
    if doctor is not None:
        lines += ["", "── DOCTOR ──",
                  f"  {len(doctor.errors)} error(s), {len(doctor.warnings)} warning(s)"]
        for f in doctor.errors + doctor.warnings[:50]:
            lines.append(f"  [{f.severity}] {f.code} {f.location}: {f.message}")
    lines += ["", "═══════════════════════════════════════"]
    return "\n".join(lines) + "\n"


def report_path(qxw_path: str) -> str:
    return os.path.splitext(qxw_path)[0] + "_reduce_report.txt"


def run(root: ET.Element, keep, repatch=None, qxf_defs=None, source: str = "",
        output: str = "") -> dict:
    """Reduce + Doctor gate: ``{"root", "log", "removed", "doctor": {...},
    "blocked": bool, "report": text}``.  *blocked* when the result has
    Doctor errors the original didn't have (then it must not be written)."""
    from core.doctor import check
    res = reduce(root, keep, repatch)
    # compare with the original *renamed the same way* (fixture names are in
    # Doctor messages: a renamed fixture isn't a new finding)
    names = {k: {"name": v["name"]} for k, v in (repatch or {}).items() if v.get("name")}
    base = reduce(root, [f["id"] for f in fixtures(root)], names)["root"] if names else root
    before = check(base, qxf_defs)
    after = check(res["root"], qxf_defs)

    def key(f):
        return (f.code, f.location, f.message)
    old = {key(f) for f in before.findings}
    new = [f for f in after.findings if key(f) not in old and f.severity != "info"]
    res["doctor"] = {
        "new_errors": [f"{f.code} {f.location}: {f.message}" for f in new if f.severity == "error"],
        "new_warnings": [f"{f.code} {f.location}: {f.message}" for f in new if f.severity == "warning"],
        "total_errors": len(after.errors), "total_warnings": len(after.warnings),
    }
    res["blocked"] = bool(res["doctor"]["new_errors"])
    res["report"] = format_report(res, source, output, after)
    return res


def reduce_file(path: str, keep, repatch=None, qxf_defs=None,
                out_path: Optional[str] = None) -> dict:
    """Reduce *path* into a new file (default ``<name>_v<N+1>.qxw``) with
    ``<new name>_reduce_report.txt`` next to it.  Never overwrites *path*;
    nothing is written when the Doctor finds new errors."""
    tree = qxw_io.load_qxw(path)
    out = out_path or qxw_io.next_version_path(path)
    res = run(tree.getroot(), keep, repatch, qxf_defs,
              os.path.basename(path), os.path.basename(out))
    if res["blocked"]:
        return {**res, "output": None, "report_path": None}
    ET.indent(res["root"], space=" ")
    qxw_io.write_qxw(res["root"], out, protect=[path])
    rp = report_path(out)
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write(res["report"])
    return {**res, "output": out, "report_path": rp}
