"""
core/porter_vc.py — Virtual Console porting for the Function Porter
===================================================================
Brings the VC widgets of ported functions into the target workspace:
buttons, sliders, CueLists and the frames around them.

Rules
-----
* **Units.** What is placed on the target page is a *unit*: a widget or
  frame that sits directly on a source page.  With an explicit *scope* the
  user picks units (a page = all its widgets); otherwise (auto) every unit
  that contains a widget of a ported function comes along.
* **Pruning.** Inside a unit a widget stays when every function it uses is
  ported (IDs remapped); widgets whose function is not ported are dropped
  and reported.  Level sliders keep the channels of ported fixtures (fixture
  IDs remapped through the fan-in blocks) and are dropped when none is left;
  they start at their low limit (a Level slider left at 255 would hold its
  channels up through every blackout and PANIC RESET).
  Widgets without a function (StopAll buttons, caption-only labels) stay
  inside frames that are kept.  In auto mode a frame is kept only if it still
  holds a working widget.
* **IDs.** Every ported widget gets a new ID, ``max(target) + 1`` upwards, in
  document order (deterministic).
* **Bindings.** ``bindings="keep_free"`` (default) keeps a key or MIDI binding
  unless the target already uses it; ``"keep"`` keeps all, ``"drop"`` none.
* **Placement.** Units keep their size and inner layout.  They are placed on
  the chosen page (default: a new page) at the first free spot, top to
  bottom then left to right, never overlapping existing widgets; when the
  page is full, a continuation page is created.

Works on namespace-stripped trees (``qxw_io.load_qxw(..., strip_namespace=True)``).
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, Iterable, List, Optional, Tuple

from core import vc_ops

NONE_ID = "4294967295"
MARGIN = 10
GAP = 10

_local = vc_ops._local
_is_widget = vc_ops._is_widget
CONTAINERS = vc_ops.CONTAINERS


# ── references ───────────────────────────────────────────────────────────────

def widget_function_refs(w: ET.Element) -> List[str]:
    """Function IDs a widget itself uses (not its children)."""
    tag = _local(w.tag)
    refs: List[str] = []
    if tag == "CueList":
        c = (w.findtext("Chaser") or "").strip()
        return [c] if c and c != NONE_ID else []
    for el in list(w) + list(w.findall("Playback")):
        if _local(el.tag) == "Function":
            fid = el.get("ID") or (el.text or "").strip()
            if fid and fid != NONE_ID:
                refs.append(fid)
    return refs


def _set_function_refs(w: ET.Element, fmap: Dict[str, str]) -> None:
    if _local(w.tag) == "CueList":
        c = w.find("Chaser")
        if c is not None and (c.text or "").strip() in fmap:
            c.text = fmap[c.text.strip()]
        return
    for el in list(w) + list(w.findall("Playback")):
        if _local(el.tag) == "Function":
            if el.get("ID") in fmap:
                el.set("ID", fmap[el.get("ID")])
            elif (el.text or "").strip() in fmap:
                el.text = fmap[el.text.strip()]


def _fixture_holders(w: ET.Element) -> List[Tuple[ET.Element, ET.Element, str]]:
    """(parent, element, attribute) for fixture references of a widget:
    Level slider channels (``<Channel Fixture=..>``), XY pad fixtures."""
    out = []
    tag = _local(w.tag)
    if tag == "Slider":
        for p in w.iter():
            for c in list(p):
                if _local(c.tag) == "Channel" and c.get("Fixture") is not None:
                    out.append((p, c, "Fixture"))
    elif tag == "XYPad":
        for c in list(w):
            if _local(c.tag) == "Fixture" and c.get("ID") is not None:
                out.append((w, c, "ID"))
    return out


# ── source VC listing (for the UI) ───────────────────────────────────────────

def _vc(root: ET.Element) -> Optional[ET.Element]:
    return root.find("VirtualConsole")


def _all_widgets(vc: ET.Element) -> List[ET.Element]:
    return [el for el in vc.iter() if el is not vc and _is_widget(el)]


def widget_keys(root: ET.Element) -> Dict[str, ET.Element]:
    """Stable keys ``"w<N>"`` (document order) — widget IDs may be duplicated
    in real files (Doctor D002), so the Porter addresses source widgets by key."""
    vc = _vc(root)
    if vc is None:
        return {}
    return {f"w{i}": el for i, el in enumerate(_all_widgets(vc))}


def list_source_vc(root: ET.Element) -> List[dict]:
    """Pages and their frames/widgets as a tree for the Porter UI:
    ``[{key, id, tag, caption, depth, functions, fids}]`` in document order, where
    ``functions`` counts the function IDs used in the element's subtree and
    ``fids`` lists the ones the widget itself uses."""
    vc = _vc(root)
    if vc is None:
        return []
    keys = {id(el): k for k, el in widget_keys(root).items()}
    out = []

    def walk(el, depth):
        for c in el:
            if not _is_widget(c):
                continue
            fns = sorted({f for w in c.iter() if _is_widget(w) for f in widget_function_refs(w)})
            if _local(c.tag) in CONTAINERS or fns:
                out.append({"key": keys[id(c)], "id": c.get("ID", ""), "tag": _local(c.tag),
                            "caption": (c.get("Caption") or "").replace("\n", " "),
                            "depth": depth, "functions": len(fns),
                            "fids": widget_function_refs(c)})
            if _local(c.tag) in CONTAINERS:
                walk(c, depth + 1)
    walk(vc, 0)
    return out


def seeds_from_widgets(root: ET.Element, keys: Iterable[str]) -> List[str]:
    """Function IDs used by the chosen source widgets (and everything inside
    them), in document order — the seeds for a "port this frame" workflow."""
    by_key = widget_keys(root)
    out: List[str] = []
    for k in keys:
        el = by_key.get(str(k))
        if el is None:
            continue
        for w in el.iter():
            if _is_widget(w):
                for f in widget_function_refs(w):
                    if f not in out:
                        out.append(f)
    return out


def list_target_pages(root: ET.Element) -> List[dict]:
    vc = _vc(root)
    if vc is None:
        return []
    return [{"id": p.get("ID", ""), "caption": p.get("Caption", "")}
            for p in vc if _local(p.tag) in CONTAINERS]


# ── pruning ──────────────────────────────────────────────────────────────────

class _Pruner:
    def __init__(self, fmap: Dict[str, str], fx_map: Dict[str, List[str]]):
        self.fmap = fmap
        self.fx_map = fx_map
        self.dropped: List[str] = []
        self.levels_reset = 0

    @staticmethod
    def _label(w: ET.Element) -> str:
        return f"{_local(w.tag)} '{(w.get('Caption') or '').replace(chr(10), ' ')}'"

    def prune(self, w: ET.Element, explicit: bool) -> Tuple[bool, bool]:
        """Prune *w* in place. Returns (keep, functional)."""
        tag = _local(w.tag)
        if tag in CONTAINERS:
            functional = any_kept = False
            for c in list(w):
                if not _is_widget(c):
                    continue
                keep, func = self.prune(c, explicit)
                if keep:
                    any_kept = True
                    functional = functional or func
                else:
                    w.remove(c)
            return (functional or (explicit and any_kept)), functional

        refs = widget_function_refs(w)
        if refs:
            missing = [r for r in refs if r not in self.fmap]
            if missing:
                self.dropped.append(f"{self._label(w)}: function {', '.join(missing)} not ported")
                return False, False
            _set_function_refs(w, self.fmap)
            return True, True

        holders = _fixture_holders(w)
        if holders:
            seen = set()
            kept = 0
            for parent, el, attr in holders:
                parent.remove(el)
            for parent, el, attr in holders:
                for t in self.fx_map.get(el.get(attr), []):
                    key = (id(parent), t, (el.text or "").strip())
                    if key in seen:
                        continue
                    seen.add(key)
                    dup = copy.deepcopy(el)
                    dup.set(attr, t)
                    parent.append(dup)
                    kept += 1
            if not kept:
                self.dropped.append(f"{self._label(w)}: none of its fixtures is ported")
                return False, False
            mode = w.find("SliderMode")
            lvl = w.find("Level")
            if (mode is not None and (mode.text or "").strip() == "Level" and lvl is not None
                    and lvl.get("Value") not in (None, lvl.get("LowLimit", "0"))):
                lvl.set("Value", lvl.get("LowLimit", "0"))
                self.levels_reset += 1
            return True, True
        return True, False


# ── bindings ─────────────────────────────────────────────────────────────────

def _binding_key(el: ET.Element):
    tag = _local(el.tag)
    if tag == "Key":
        return ("key", (el.text or "").strip())
    if tag == "Input":
        return ("input", el.get("Universe", ""), el.get("Channel", ""))
    return None


def _used_bindings(vc: Optional[ET.Element]) -> set:
    used = set()
    if vc is not None:
        for el in vc.iter():
            k = _binding_key(el)
            if k is not None:
                used.add(k)
    return used


def _filter_bindings(unit: ET.Element, mode: str, used: set) -> Tuple[int, int]:
    """Apply the binding policy to *unit*. Returns (kept, dropped)."""
    kept = dropped = 0
    for p in list(unit.iter()):
        for c in list(p):
            k = _binding_key(c)
            if k is None and _local(c.tag) != "KeySequence":
                continue
            drop = mode == "drop" or (mode == "keep_free" and k in used)
            if drop:
                p.remove(c)
                dropped += 1
            else:
                kept += 1
                if k is not None:
                    used.add(k)
    for p in list(unit.iter()):
        for c in list(p):
            if (_local(c.tag) in {"Next", "Previous", "Stop", "Playback", "CrossFade"}
                    and len(c) == 0 and not (c.text or "").strip() and not c.attrib):
                p.remove(c)
    return kept, dropped


# ── placement ────────────────────────────────────────────────────────────────

def _rect(el: ET.Element) -> Tuple[int, int, int, int]:
    ws = el.find("WindowState")
    if ws is None:
        return 0, 0, 100, 50
    g = lambda k, d: vc_ops._int(ws.get(k), d)  # noqa: E731
    return g("X", 0), g("Y", 0), g("Width", 100), g("Height", 50)


def _overlaps(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw + GAP <= bx or bx + bw + GAP <= ax or
                ay + ah + GAP <= by or by + bh + GAP <= ay)


class _Page:
    def __init__(self, el: ET.Element, top: Optional[int] = None):
        self.el = el
        _, _, self.w, self.h = _rect(el)
        self.rects = [_rect(c) for c in el if _is_widget(c)]
        self.top = top if top is not None else (
            min((r[1] for r in self.rects), default=MARGIN) if self.rects else MARGIN)

    def find_spot(self, w: int, h: int) -> Optional[Tuple[int, int]]:
        xs = {MARGIN} | {r[0] + r[2] + GAP for r in self.rects}
        ys = {self.top} | {r[1] + r[3] + GAP for r in self.rects}
        for y in sorted(ys):
            for x in sorted(xs):
                if x + w > self.w - MARGIN + 1 or y + h > self.h:
                    continue
                if not any(_overlaps((x, y, w, h), r) for r in self.rects):
                    return x, y
        return None

    def add(self, unit: ET.Element, x: int, y: int) -> None:
        vc_ops._set_xy(unit, x, y)
        self.el.append(unit)
        self.rects.append(_rect(unit))


def _new_page(tgt_vc: ET.Element, caption: str, like: Optional[ET.Element],
              page_id: int) -> ET.Element:
    """Empty page styled like the target's first page (or *like*)."""
    tmpl = next((p for p in tgt_vc if _local(p.tag) in CONTAINERS), None)
    if tmpl is None:
        tmpl = like
    page = ET.Element("Frame", {"Caption": caption, "ID": str(page_id)})
    if tmpl is not None:
        for c in tmpl:
            if not _is_widget(c):
                page.append(copy.deepcopy(c))
    else:
        ET.SubElement(page, "WindowState", {"Visible": "True", "X": "0", "Y": "0",
                                            "Width": "1920", "Height": "1080"})
    vc_ops._set_xy(page, 0, 0)
    vc_ops._append_page(tgt_vc, page)
    return page


# ── main entry ───────────────────────────────────────────────────────────────

def port_vc(src_root: ET.Element, tgt_root: ET.Element, fmap: Dict[str, str],
            blocks: Dict[str, List[str]], opts: dict, src_name: str = "source") -> dict:
    """Port VC widgets of ported functions into *tgt_root* (in place).

    *fmap*    source function ID → new target function ID (ported functions only)
    *blocks*  target fixture ID → [source fixture IDs] (from the Porter)
    *opts*    ``scope`` (list of widget keys, or empty for auto),
              ``target_page`` (target page ID, or empty for a new page),
              ``page_caption``, ``bindings`` (keep_free | keep | drop)

    Returns a summary dict (``summary`` lines, ``dropped`` list, counts, pages).
    """
    src_vc = _vc(src_root)
    summary: List[str] = []
    if src_vc is None:
        return {"summary": ["The source has no Virtual Console."], "dropped": [],
                "widgets": 0, "units": 0, "pages": []}

    fx_map: Dict[str, List[str]] = {}
    for t in sorted(blocks, key=lambda i: (len(i), i)):
        for s in blocks[t]:
            fx_map.setdefault(s, []).append(t)

    # 1. units
    keys = widget_keys(src_root)
    parent = {c: p for p in src_vc.iter() for c in p}
    pages = [p for p in src_vc if _local(p.tag) in CONTAINERS]
    scope = [str(k) for k in (opts.get("scope") or []) if str(k) in keys]
    units: List[Tuple[ET.Element, ET.Element]] = []       # (element, its source page)

    def page_of(el):
        while parent.get(el) is not None and parent[el] is not src_vc:
            el = parent[el]
        return el

    if scope:
        chosen = [keys[k] for k in scope]
        chosen_set = set(chosen)
        for el in chosen:
            p, inside = parent.get(el), False
            while p is not None:
                if p in chosen_set:
                    inside = True
                    break
                p = parent.get(p)
            if inside:
                continue
            if el in pages:
                units += [(c, el) for c in el if _is_widget(c)]
            else:
                units.append((el, page_of(el)))
    else:
        for pg in pages:
            for c in pg:
                if _is_widget(c) and any(
                        r in fmap for w in c.iter() if _is_widget(w)
                        for r in widget_function_refs(w)):
                    units.append((c, pg))

    # 2. prune copies
    pruner = _Pruner(fmap, fx_map)
    ready: List[Tuple[ET.Element, ET.Element]] = []
    for el, pg in units:
        dup = copy.deepcopy(el)
        keep, _func = pruner.prune(dup, explicit=bool(scope))
        if keep:
            ready.append((dup, pg))
    if not ready:
        return {"summary": ["No VC widget uses a ported function; nothing placed."],
                "dropped": pruner.dropped, "widgets": 0, "units": 0, "pages": []}

    # 3. target VC and page
    tgt_vc = _vc(tgt_root)
    if tgt_vc is None:
        tgt_vc = ET.SubElement(tgt_root, "VirtualConsole")
    used = _used_bindings(tgt_vc)
    mode = opts.get("bindings") or "keep_free"
    caption = (opts.get("page_caption") or "").strip() or f"Ported from {src_name}"
    page_el = None
    if opts.get("target_page") not in (None, ""):
        page_el = next((p for p in tgt_vc if _local(p.tag) in CONTAINERS
                        and p.get("ID") == str(opts["target_page"])), None)
        if page_el is None:
            summary.append(f"Target page {opts['target_page']} not found; using a new page.")
    created = []
    nid = vc_ops._next_id(tgt_vc)
    if page_el is None:
        page_el = _new_page(tgt_vc, caption, ready[0][1], nid)
        nid += 1
        created.append(page_el)
        page = _Page(page_el, top=MARGIN)
    else:
        page = _Page(page_el)

    # 4. renumber, bindings, place
    n_widgets = kept_b = dropped_b = 0
    for unit, _pg in ready:
        nid, _mapping = vc_ops._renumber(unit, nid)
        k, d = _filter_bindings(unit, mode, used)
        kept_b += k
        dropped_b += d
        _, _, w, h = _rect(unit)
        spot = page.find_spot(w, h)
        if spot is None and page.rects:           # page full: continuation page
            cont = _new_page(tgt_vc, f"{caption} ({len(created) + 1})" if created else caption,
                             ready[0][1], nid)
            nid += 1
            created.append(cont)
            page = _Page(cont, top=MARGIN)
            spot = page.find_spot(w, h)
        if spot is None:
            summary.append(f"'{unit.get('Caption', '')}' ({w}×{h}) is larger than the "
                           f"page ({page.w}×{page.h}); placed at the top left.")
            spot = (MARGIN, page.top)
        page.add(unit, *spot)
        n_widgets += sum(1 for x in unit.iter() if _is_widget(x))

    target_caps = [p.get("Caption", "") for p in created] or [page_el.get("Caption", "")]
    summary.insert(0, f"{n_widgets} widget(s) in {len(ready)} unit(s) placed on page(s): "
                   + ", ".join(f"'{c}'" for c in target_caps)
                   + (" (new)" if created else ""))
    if kept_b or dropped_b:
        summary.append(f"Key/MIDI bindings: {kept_b} kept, {dropped_b} dropped ({mode}).")
    if pruner.levels_reset:
        summary.append(f"{pruner.levels_reset} Level slider(s) set to their low limit.")
    if pruner.dropped:
        summary.append(f"{len(pruner.dropped)} widget(s) left out (function or fixtures not ported).")
    return {"summary": summary, "dropped": pruner.dropped, "widgets": n_widgets,
            "units": len(ready), "pages": [p.get("ID") for p in created],
            "bindings_kept": kept_b, "bindings_dropped": dropped_b}
