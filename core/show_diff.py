"""core/show_diff.py — what an in-place step changed in the show (WORKPLAN
2.8): the show report's detail lines for the tools that edit the show in
place (Stage groups, VC Editor, setlist, triggers…).  Same show before and
after, so things are matched by their IDs."""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405

from core import qxw_io

MAX_NAMES = 8


def _names(items) -> str:
    items = list(items)
    out = ", ".join(f"'{x}'" for x in items[:MAX_NAMES])
    return out + (f" and {len(items) - MAX_NAMES} more" if len(items) > MAX_NAMES else "")


def _key(el) -> bytes:
    return ET.tostring(el)  # qxw-io: not output (comparison key)


def _index(root):
    eng = root.find("Engine")
    eng = eng if eng is not None else ET.Element("Engine")
    fx = {(e.findtext("ID") or "").strip(): e for e in eng.findall("Fixture")}
    grp = {g.get("ID"): g for g in eng.findall("FixtureGroup")}
    fn = {f.get("ID"): f for f in eng.findall("Function")}
    mon = eng.find("Monitor")
    pos = {e.get("ID"): e for e in (mon.findall("FxItem") if mon is not None else [])}
    vc = root.find("VirtualConsole")
    pages, widgets = {}, {}
    if vc is not None:
        top = [c for c in vc if c.tag in ("Frame", "SoloFrame")]
        if len(top) == 1 and not top[0].get("Caption"):
            top = [c for c in top[0] if c.tag in ("Frame", "SoloFrame")] or top
        for p in top:
            pages[p.get("ID")] = p
            for w in p.iter():
                if w is not p and w.get("ID") is not None and w.tag in (
                        "Button", "Slider", "CueList", "Knob", "XYPad", "SpeedDial", "Label",
                        "Frame", "SoloFrame", "AudioTriggers", "Clock", "Animation"):
                    widgets[(p.get("ID"), w.get("ID"))] = (p, w)
    return fx, grp, fn, pos, pages, widgets


def _wname(w) -> str:
    return (w.get("Caption") or "").strip() or w.tag


def summarise(before: ET.Element, after: ET.Element) -> list[str]:
    """Lines saying what changed from *before* to *after* (un-namespaced
    or not)."""
    if before.tag != "Workspace":
        before = qxw_io.strip_ns(before)
    if after.tag != "Workspace":
        after = qxw_io.strip_ns(after)
    fa, ga, na, pa, va, wa = _index(before)
    fb, gb, nb, pb, vb, wb = _index(after)
    out: list[str] = []

    def three(label, a, b, name):
        add = [name(b[k]) for k in b if k not in a]
        rem = [name(a[k]) for k in a if k not in b]
        ren = [f"{name(a[k])}' → '{name(b[k])}" for k in a if k in b and name(a[k]) != name(b[k])]
        chg = [name(b[k]) for k in a if k in b and name(a[k]) == name(b[k]) and _key(a[k]) != _key(b[k])]
        for what, items in (("added", add), ("removed", rem), ("renamed", ren), ("changed", chg)):
            if items:
                out.append(f"{label} {what} ({len(items)}): {_names(items)}")

    three("Fixtures", fa, fb, lambda e: e.findtext("Name") or "")
    moved = [fb[k].findtext("Name") or k for k in pb if k in pa and k in fb and _key(pa[k]) != _key(pb[k])]
    if moved:
        out.append(f"Moved on the stage ({len(moved)}): {_names(moved)}")
    three("Fixture groups", ga, gb, lambda e: e.findtext("Name") or "")
    three("Functions", na, nb, lambda e: e.get("Name") or "")
    three("Virtual Console pages", va, vb, lambda e: (e.get("Caption") or "").strip() or "(no caption)")
    if [k for k in va if k in vb] != [k for k in vb if k in va]:
        out.append("Virtual Console page order now: " + _names(
            (vb[k].get("Caption") or "").strip() or "(no caption)" for k in vb))
    wadd = [f"{_wname(w)} on '{(p.get('Caption') or '').strip()}'" for k, (p, w) in wb.items() if k not in wa]
    wrem = [f"{_wname(w)} on '{(p.get('Caption') or '').strip()}'" for k, (p, w) in wa.items()
            if k not in wb and k[0] in vb]
    wchg = [f"{_wname(wb[k][1])} on '{(wb[k][0].get('Caption') or '').strip()}'" for k in wa
            if k in wb and _key(_shallow(wa[k][1])) != _key(_shallow(wb[k][1]))]
    for what, items in (("added", wadd), ("removed", wrem), ("changed", wchg)):
        if items:
            out.append(f"Widgets {what} ({len(items)}): {_names(items)}")
    return out


def _shallow(w: ET.Element) -> ET.Element:
    """The widget without its child widgets (a frame changes when only a
    button inside it did otherwise)."""
    c = ET.Element(w.tag, w.attrib)
    c.text = w.text
    for ch in w:
        if ch.get("ID") is None or ch.tag not in ("Button", "Slider", "CueList", "Knob", "XYPad", "SpeedDial",
                                                   "Label", "Frame", "SoloFrame", "AudioTriggers", "Clock",
                                                   "Animation"):
            c.append(ch)
    return c
