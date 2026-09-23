"""
core/vc_ops.py
==============
Structural Virtual Console edits for the VC Visual Editor: copy or move
widgets between frames and pages, duplicate a page, create an empty page.

All operations work on the in-memory workspace tree (``_state['qxw_root']``)
and never touch the file on disk; the user saves with "Apply & Save QXW…",
which writes a new file through ``core.qxw_io``.

Rules
-----
* A *page* is a top-level ``<Frame>``/``<SoloFrame>`` under ``<VirtualConsole>``.
* Copies get fresh widget IDs: ``max(existing) + 1`` upwards, in document
  order (deterministic).  Moves keep their IDs.
* Copies drop keyboard and MIDI bindings (``<Key>``, ``<Input>``) by default,
  so the copy does not fire together with the original.  Pass
  ``keep_bindings=True`` to keep them (Trigger Manager flags duplicates).
* If both a frame and something inside it are selected, only the frame is
  copied/moved (its contents come with it).
* A widget ID that is used twice in the workspace cannot be addressed safely;
  such operations are refused with a message pointing at Doctor D002.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, Iterable, List, Optional, Tuple

from core.qxw_io import QLC_NS_URI

_NS = "{" + QLC_NS_URI + "}"
WIDGET_TYPES = {
    "Button", "Slider", "Knob", "SpeedDial", "XYPad", "Label", "Clock",
    "VUMeter", "AudioTrigger", "AudioTriggers", "Animation", "Frame",
    "SoloFrame", "CueList", "Matrix",
}
CONTAINERS = {"Frame", "SoloFrame"}
BINDING_TAGS = {"Key", "Input", "KeySequence"}


class VcOpError(ValueError):
    """A structural VC edit that cannot be done (shown to the user)."""


# ── helpers ──────────────────────────────────────────────────────────────────

def _local(tag: str) -> str:
    return tag[len(_NS):] if tag.startswith(_NS) else tag


def _q(tag: str, like: ET.Element) -> str:
    """Tag name in the same namespace style as *like*."""
    return (_NS + tag) if like.tag.startswith(_NS) else tag


def _is_widget(el: ET.Element) -> bool:
    return _local(el.tag) in WIDGET_TYPES


def _vc(root: ET.Element) -> ET.Element:
    vc = root.find(_NS + "VirtualConsole")
    if vc is None:
        vc = root.find("VirtualConsole")
    if vc is None:
        raise VcOpError("This workspace has no Virtual Console.")
    return vc


def _widgets(vc: ET.Element) -> List[ET.Element]:
    return [el for el in vc.iter() if el is not vc and _is_widget(el)]


def _int(s, default=-1) -> int:
    try:
        return int(str(s))
    except (TypeError, ValueError):
        return default


def _index(vc: ET.Element) -> Tuple[Dict[str, List[ET.Element]], Dict[ET.Element, ET.Element]]:
    by_id: Dict[str, List[ET.Element]] = {}
    parent: Dict[ET.Element, ET.Element] = {}
    for p in vc.iter():
        for c in p:
            parent[c] = p
            if _is_widget(c) and c.get("ID") is not None:
                by_id.setdefault(c.get("ID"), []).append(c)
    return by_id, parent


def _get(by_id, wid: str, what: str = "widget") -> ET.Element:
    els = by_id.get(str(wid), [])
    if not els:
        raise VcOpError(f"{what.capitalize()} ID {wid} not found.")
    if len(els) > 1:
        raise VcOpError(
            f"{what.capitalize()} ID {wid} is used by {len(els)} widgets, so it cannot be "
            f"moved or copied safely. Fix the duplicate first (Doctor check D002).")
    return els[0]


def _next_id(vc: ET.Element) -> int:
    return max([_int(w.get("ID")) for w in _widgets(vc)] + [-1]) + 1


def _renumber(el: ET.Element, start: int) -> Tuple[int, Dict[str, str]]:
    """Give *el* and every widget inside it new IDs from *start*. Returns (next, old→new)."""
    mapping: Dict[str, str] = {}
    n = start
    for w in el.iter():
        if _is_widget(w):
            mapping[w.get("ID", "")] = str(n)
            w.set("ID", str(n))
            n += 1
    return n, mapping


def _strip_bindings(el: ET.Element) -> int:
    """Remove <Key>/<Input> bindings inside *el*; drop containers left empty."""
    removed = 0
    for p in list(el.iter()):
        for c in list(p):
            if _local(c.tag) in BINDING_TAGS:
                p.remove(c)
                removed += 1
    # e.g. CueList <Next><Key>Space</Key></Next> → empty <Next/>: drop it
    for p in list(el.iter()):
        for c in list(p):
            if (_local(c.tag) in {"Next", "Previous", "Stop", "Playback", "CrossFade"}
                    and len(c) == 0 and not (c.text or "").strip() and not c.attrib):
                p.remove(c)
    return removed


def _window_state(el: ET.Element) -> ET.Element:
    ws = el.find(_q("WindowState", el))
    if ws is None:
        ws = ET.Element(_q("WindowState", el), {"Visible": "True", "X": "0", "Y": "0",
                                                  "Width": "100", "Height": "50"})
        el.insert(0, ws)
    return ws


def _xy(el: ET.Element) -> Tuple[int, int]:
    ws = _window_state(el)
    return _int(ws.get("X"), 0), _int(ws.get("Y"), 0)


def _set_xy(el: ET.Element, x: int, y: int) -> None:
    ws = _window_state(el)
    ws.set("X", str(int(x)))
    ws.set("Y", str(int(y)))


def _top_level(ids: Iterable[str], by_id, parent) -> List[ET.Element]:
    """Resolve IDs; drop any element that sits inside another selected one."""
    els = []
    for wid in dict.fromkeys(str(i) for i in ids):
        els.append(_get(by_id, wid))
    chosen = set(els)
    out = []
    for el in els:
        p, inside = parent.get(el), False
        while p is not None:
            if p in chosen:
                inside = True
                break
            p = parent.get(p)
        if not inside:
            out.append(el)
    return out


def _target(by_id, target_id: str) -> ET.Element:
    t = _get(by_id, target_id, "target frame")
    if _local(t.tag) not in CONTAINERS:
        raise VcOpError(f"Target {target_id} is a {_local(t.tag)}; choose a frame or a page.")
    return t


def _insert_child(target: ET.Element, el: ET.Element) -> None:
    """Append a widget after the frame's own settings (drawn on top)."""
    target.append(el)


def _placement(els: List[ET.Element], x: Optional[int], y: Optional[int],
               same_parent: bool) -> Tuple[int, int]:
    """Offset to apply to every element's X/Y so the group lands at (x, y)."""
    xs, ys = zip(*[_xy(e) for e in els])
    if x is not None and y is not None:
        return int(x) - min(xs), int(y) - min(ys)
    return (20, 20) if same_parent else (0, 0)


# ── public API ───────────────────────────────────────────────────────────────

def list_pages(root: ET.Element) -> List[dict]:
    """Pages with their frames: [{id, caption, frames:[{id, caption, depth}]}]."""
    vc = _vc(root)
    out = []
    for page in vc:
        if _local(page.tag) not in CONTAINERS:
            continue
        frames = []

        def walk(el, depth):
            for c in el:
                if _local(c.tag) in CONTAINERS:
                    frames.append({"id": c.get("ID", ""), "caption": c.get("Caption", ""),
                                   "depth": depth})
                    walk(c, depth + 1)
        walk(page, 1)
        out.append({"id": page.get("ID", ""), "caption": page.get("Caption", ""),
                    "frames": frames})
    return out


def copy_widgets(root: ET.Element, ids: Iterable[str], target_id: str, *,
                 x: Optional[int] = None, y: Optional[int] = None,
                 keep_bindings: bool = False) -> dict:
    """Copy widgets (with everything inside frames) into frame/page *target_id*."""
    vc = _vc(root)
    by_id, parent = _index(vc)
    els = _top_level(ids, by_id, parent)
    if not els:
        raise VcOpError("Nothing selected.")
    target = _target(by_id, target_id)
    same = all(parent.get(e) is target for e in els)
    dx, dy = _placement(els, x, y, same)
    nid, new_ids, stripped = _next_id(vc), [], 0
    for el in els:
        dup = copy.deepcopy(el)
        nid, mapping = _renumber(dup, nid)
        if not keep_bindings:
            stripped += _strip_bindings(dup)
        ex, ey = _xy(dup)
        _set_xy(dup, ex + dx, ey + dy)
        _insert_child(target, dup)
        new_ids.append(dup.get("ID"))
    return {"new_ids": new_ids, "count": sum(1 for e in els for w in e.iter() if _is_widget(w)),
            "bindings_removed": stripped}


def move_widgets(root: ET.Element, ids: Iterable[str], target_id: str, *,
                 x: Optional[int] = None, y: Optional[int] = None) -> dict:
    """Move widgets into frame/page *target_id* (IDs and bindings unchanged)."""
    vc = _vc(root)
    by_id, parent = _index(vc)
    els = _top_level(ids, by_id, parent)
    if not els:
        raise VcOpError("Nothing selected.")
    target = _target(by_id, target_id)
    for el in els:
        p = target
        while p is not None:
            if p is el:
                raise VcOpError(f"Cannot move '{el.get('Caption', '')}' into itself.")
            p = parent.get(p)
        if parent.get(el) is vc:
            raise VcOpError("A whole page cannot be moved into a frame; copy it instead.")
    dx, dy = _placement(els, x, y, same_parent=False)
    moved = []
    for el in els:
        if parent.get(el) is target and x is None:
            continue                     # already there
        parent[el].remove(el)
        ex, ey = _xy(el)
        _set_xy(el, ex + dx, ey + dy)
        _insert_child(target, el)
        moved.append(el.get("ID"))
    return {"moved_ids": moved}


def _page_template(vc: ET.Element) -> ET.Element:
    for p in vc:
        if _local(p.tag) in CONTAINERS:
            return p
    return None


def new_page(root: ET.Element, caption: str) -> dict:
    """Append an empty page, sized and styled like the first existing page."""
    vc = _vc(root)
    caption = (caption or "").strip() or "New page"
    tmpl = _page_template(vc)
    q = (lambda t: _NS + t) if vc.tag.startswith(_NS) else (lambda t: t)
    page = ET.Element(q("Frame"), {"Caption": caption, "ID": str(_next_id(vc))})
    if tmpl is not None:
        for c in tmpl:                  # copy the page's own settings, not its widgets
            if not _is_widget(c):
                page.append(copy.deepcopy(c))
    else:
        ET.SubElement(page, q("WindowState"), {"Visible": "True", "X": "0", "Y": "0",
                                               "Width": "1920", "Height": "1080"})
    _set_xy(page, 0, 0)
    _append_page(vc, page)
    return {"page_id": page.get("ID")}


def copy_page(root: ET.Element, page_id: str, caption: str = "", *,
              keep_bindings: bool = False) -> dict:
    """Duplicate a whole page (or any frame) as a new page."""
    vc = _vc(root)
    by_id, parent = _index(vc)
    src = _get(by_id, page_id, "page")
    if _local(src.tag) not in CONTAINERS:
        raise VcOpError("Only a page or a frame can be copied as a page.")
    dup = copy.deepcopy(src)
    _renumber(dup, _next_id(vc))
    stripped = 0 if keep_bindings else _strip_bindings(dup)
    dup.set("Caption", (caption or "").strip() or f"{src.get('Caption', 'Page')} (copy)")
    if parent.get(src) is not vc:            # a frame promoted to a page
        tmpl = _page_template(vc)
        if tmpl is not None:
            tw = _window_state(tmpl)
            ws = _window_state(dup)
            ws.set("Width", tw.get("Width", ws.get("Width")))
            ws.set("Height", tw.get("Height", ws.get("Height")))
    _set_xy(dup, 0, 0)
    _append_page(vc, dup)
    return {"page_id": dup.get("ID"), "bindings_removed": stripped}


def _append_page(vc: ET.Element, page: ET.Element) -> None:
    """Insert after the last existing page (before <Properties> etc.)."""
    last = -1
    for i, c in enumerate(list(vc)):
        if _local(c.tag) in CONTAINERS:
            last = i
    vc.insert(last + 1, page)
