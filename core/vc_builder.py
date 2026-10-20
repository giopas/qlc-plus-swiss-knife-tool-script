"""
core/vc_builder.py — VC Builder (WORKPLAN Phase 2.4)
===================================================
Build the Virtual Console, not only tidy it: create, delete and duplicate
widgets; wire them to functions; manage pages; layout helpers (label
panels, auto-arrange by nomenclature); screen profiles; page templates;
one-click setlist CueList.

Every operation works on the in-memory workspace (namespaced as loaded, or
stripped — both work), is deterministic, and is run by
``core.workspace.vc_structural_edit`` so it can be undone and is saved with
the VC Visual Editor's *Apply & Save* (a new file).

Only the ``<VirtualConsole>`` is changed; functions are referenced, never
created or edited.
"""

from __future__ import annotations

import copy
import json
import os
import re
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, List, Optional, Tuple

from core import vc_ops, vc_screens
from core.vc_ops import (CONTAINERS, VcOpError, _get, _index, _int, _is_widget, _local,
                         _next_id, _q, _renumber, _strip_bindings, _vc)

NONE_ID = "4294967295"
MARGIN, GAP = 10, 6
KINDS = ("Button", "Frame", "SoloFrame", "Slider", "Label", "CueList")
DEFAULT_SIZE = {"Button": (110, 55), "Frame": (400, 250), "SoloFrame": (400, 250),
                "Slider": (60, 200), "Label": (150, 30), "CueList": (720, 420)}   # wide enough for every column, Note included
SCREENS = {x["id"]: {"label": x["label"], "w": x["w"], "h": x["h"]} for x in vc_screens.BUILTIN}   # kept for old callers
_FONT = "Roboto,12,-1,5,50,0,0,0,0,0,0,0,0,0,0,1"


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def _engine(root: ET.Element) -> ET.Element:
    e = root.find(vc_ops._NS + "Engine")
    return e if e is not None else root.find("Engine")


def functions(root: ET.Element) -> Dict[str, dict]:
    """``{id: {"name", "type"}}`` of the workspace's functions."""
    eng = _engine(root)
    out: Dict[str, dict] = {}
    if eng is None:
        return out
    for f in eng:
        if _local(f.tag) == "Function":
            out[f.get("ID", "")] = {"name": f.get("Name", ""), "type": f.get("Type", "")}
    return out


def _sub(parent: ET.Element, tag: str, text: Optional[str] = None, **attrs) -> ET.Element:
    el = ET.SubElement(parent, _q(tag, parent), {k: str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el


def _child(el: ET.Element, tag: str) -> Optional[ET.Element]:
    return el.find(_q(tag, el))


def _rect(el: ET.Element) -> Tuple[int, int, int, int]:
    ws = _child(el, "WindowState")
    if ws is None:
        return 0, 0, 100, 50
    return (_int(ws.get("X"), 0), _int(ws.get("Y"), 0),
            _int(ws.get("Width"), 100), _int(ws.get("Height"), 50))


def _set_rect(el: ET.Element, x: int, y: int, w: Optional[int] = None, h: Optional[int] = None) -> None:
    ws = vc_ops._window_state(el)
    ws.set("X", str(int(x)))
    ws.set("Y", str(int(y)))
    if w is not None:
        ws.set("Width", str(int(w)))
    if h is not None:
        ws.set("Height", str(int(h)))


def _overlaps(a, b, gap=GAP) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw + gap <= bx or bx + bw + gap <= ax or ay + ah + gap <= by or by + bh + gap <= ay)


def _header(el: ET.Element) -> int:
    """Height taken by a frame's header (widgets start below it)."""
    if _local(el.tag) not in CONTAINERS:
        return 0
    sh = _child(el, "ShowHeader")
    return 0 if sh is not None and (sh.text or "").strip().lower() == "false" else 30


def free_spot(container: ET.Element, w: int, h: int, is_page: bool = False,
              strict: bool = False):
    """First free (x, y) for a w×h widget inside *container* (row by row);
    with *strict*, None when it doesn't fit anywhere."""
    _, _, cw, ch = _rect(container)
    rects = [_rect(c) for c in container if _is_widget(c)]
    top = MARGIN + (0 if is_page else _header(container))
    xs = sorted({MARGIN} | {r[0] + r[2] + GAP for r in rects})
    ys = sorted({top} | {r[1] + r[3] + GAP for r in rects})
    for y in ys:
        for x in xs:
            if x + w > cw - MARGIN + 1 or y + h > ch - MARGIN + 1:
                continue
            if y < top:
                continue
            if not any(_overlaps((x, y, w, h), r) for r in rects):
                return x, y
    if strict:
        return None
    # no free room: top-left, over the other widgets (still visible; move it)
    return MARGIN, top


def _is_page(vc: ET.Element, el: ET.Element) -> bool:
    return any(p is el for p in vc)


def _container(vc, by_id, cid: str) -> ET.Element:
    c = _get(by_id, cid, "frame")
    if _local(c.tag) not in CONTAINERS:
        raise VcOpError(f"Widget {cid} is a {_local(c.tag)}; pick a frame or a page.")
    return c


def _qlc_colour(hx: str) -> str:
    hx = (hx or "").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", hx):
        raise VcOpError(f"Not a colour: #{hx}")
    return str(0xFF000000 | int(hx, 16))


# ─────────────────────────────────────────────────────────────────────────────
# create / delete / duplicate
# ─────────────────────────────────────────────────────────────────────────────

def _new_element(like: ET.Element, kind: str, wid: int, caption: str, w: int, h: int,
                 bg: Optional[str] = None) -> ET.Element:
    el = ET.Element(_q(kind, like), {"Caption": caption, "ID": str(wid)})
    if kind in ("Button",):
        el.set("Icon", "")
    if kind == "Slider":
        el.set("WidgetStyle", "Slider")
        el.set("InvertedAppearance", "false")
    _sub(el, "WindowState", Visible="True", X=0, Y=0, Width=w, Height=h)
    app = _sub(el, "Appearance")
    _sub(app, "FrameStyle", "Sunken" if kind in CONTAINERS or kind == "Slider" else "None")
    if bg:
        _sub(app, "BackgroundColor", _qlc_colour(bg))
    if kind == "Label":
        _sub(app, "Font", _FONT)
    if kind in CONTAINERS:
        _sub(el, "AllowChildren", "True")
        _sub(el, "AllowResize", "True")
        _sub(el, "ShowHeader", "True")
        _sub(el, "ShowEnableButton", "True")
        _sub(el, "Collapsed", "False")
        _sub(el, "Disabled", "False")
    elif kind == "Button":
        _sub(el, "Function", ID=NONE_ID)
        _sub(el, "Action", "Toggle")
        _sub(el, "Intensity", Adjust="False")
    elif kind == "Slider":
        _sub(el, "SliderMode", "Submaster", ValueDisplayStyle="Percentage")
        _sub(el, "Level", LowLimit=0, HighLimit=255, Value=255)
    elif kind == "CueList":
        _sub(el, "Chaser", NONE_ID)
    return el


def create_widget(root: ET.Element, parent_id: str, kind: str, caption: str = "", *,
                  x: Optional[int] = None, y: Optional[int] = None,
                  w: Optional[int] = None, h: Optional[int] = None,
                  func_id: Optional[str] = None, bg_color: Optional[str] = None) -> dict:
    """New widget in frame/page *parent_id* (at x, y or the first free spot)."""
    if kind not in KINDS:
        raise VcOpError(f"Cannot create a {kind}; choose one of {', '.join(KINDS)}.")
    vc = _vc(root)
    by_id, _ = _index(vc)
    parent = _container(vc, by_id, str(parent_id))
    dw, dh = DEFAULT_SIZE[kind]
    w, h = int(w or dw), int(h or dh)
    el = _new_element(parent, kind, _next_id(vc), (caption or "").strip() or kind, w, h, bg_color)
    if x is None or y is None:
        x, y = free_spot(parent, w, h, _is_page(vc, parent))
    _set_rect(el, x, y)
    parent.append(el)
    out = {"new_ids": [el.get("ID")], "x": int(x), "y": int(y)}
    if func_id not in (None, "", NONE_ID):
        out["wired"] = wire(root, el.get("ID"), str(func_id))["wired"]
    return out


def delete_widgets(root: ET.Element, ids) -> dict:
    """Remove widgets (with everything inside frames). Pages are removed with
    :func:`delete_page`."""
    vc = _vc(root)
    by_id, parent = _index(vc)
    els = vc_ops._top_level(ids, by_id, parent)
    if not els:
        raise VcOpError("Nothing selected.")
    if any(parent.get(e) is vc for e in els):
        raise VcOpError("A page is removed with 'Delete page'.")
    n = 0
    for el in els:
        n += sum(1 for w in el.iter() if _is_widget(w))
        parent[el].remove(el)
    return {"deleted": n, "deleted_ids": [e.get("ID") for e in els]}


def duplicate_widgets(root: ET.Element, ids, keep_bindings: bool = False) -> dict:
    """Copy widgets next to themselves (same frame, +20/+20; bindings dropped)."""
    vc = _vc(root)
    by_id, parent = _index(vc)
    els = vc_ops._top_level(ids, by_id, parent)
    if not els:
        raise VcOpError("Nothing selected.")
    parents = {id(parent.get(e)) for e in els}
    if len(parents) != 1 or parent.get(els[0]) is vc:
        raise VcOpError("Select widgets of one frame (not a page) to duplicate.")
    return vc_ops.copy_widgets(root, [e.get("ID") for e in els], parent[els[0]].get("ID"),
                               keep_bindings=keep_bindings)


# ─────────────────────────────────────────────────────────────────────────────
# wiring
# ─────────────────────────────────────────────────────────────────────────────

def wire(root: ET.Element, widget_id: str, func_id: str) -> dict:
    """Connect a Button, CueList (chaser only) or Slider (playback) to a
    function.  ``func_id`` "" / None unwires."""
    vc = _vc(root)
    by_id, _ = _index(vc)
    w = _get(by_id, str(widget_id))
    kind = _local(w.tag)
    fns = functions(root)
    fid = str(func_id) if func_id not in (None, "") else NONE_ID
    fn = fns.get(fid)
    if fid != NONE_ID and fn is None:
        raise VcOpError(f"Function {fid} not found.")
    if kind == "Button":
        fe = _child(w, "Function")
        if fe is None:
            fe = ET.Element(_q("Function", w))
            ws = _child(w, "WindowState")
            idx = list(w).index(ws) + 1 if ws is not None else 0
            app = _child(w, "Appearance")
            if app is not None:
                idx = max(idx, list(w).index(app) + 1)
            w.insert(idx, fe)
        fe.set("ID", fid)
        fe.text = None
        if _child(w, "Action") is None:
            _sub(w, "Action", "Toggle")
    elif kind == "CueList":
        if fn is not None and fn["type"] != "Chaser":
            raise VcOpError(f"A CueList runs a chaser; '{fn['name']}' is a {fn['type']}.")
        ch = _child(w, "Chaser")
        if ch is None:
            ch = ET.Element(_q("Chaser", w))
            w.insert(1, ch)
        ch.text = fid
    elif kind == "Slider":
        mode = _child(w, "SliderMode")
        if mode is None:
            mode = _sub(w, "SliderMode")
        pb = _child(w, "Playback")
        if fid == NONE_ID:
            if pb is not None:
                w.remove(pb)
            mode.text = "Submaster"
            mode.attrib = {"ValueDisplayStyle": "Percentage"}
        else:
            mode.text = "Playback"
            mode.attrib = {"ValueDisplayStyle": "Exact", "ClickAndGoType": "None", "Monitor": "false"}
            if pb is None:
                pb = _sub(w, "Playback")
            for c in list(pb):
                pb.remove(c)
            _sub(pb, "Function", fid)
    else:
        raise VcOpError(f"A {kind} cannot run a function; pick a button, CueList or slider.")
    what = f"{fn['type']} {fid} '{fn['name']}'" if fn else "nothing"
    return {"wired": f"{kind} '{w.get('Caption', '')}' → {what}"}


# ─────────────────────────────────────────────────────────────────────────────
# pages
# ─────────────────────────────────────────────────────────────────────────────

def _pages(vc) -> List[ET.Element]:
    return [p for p in vc if _local(p.tag) in CONTAINERS]


def _page(vc, page_id: str) -> ET.Element:
    p = next((p for p in _pages(vc) if p.get("ID") == str(page_id)), None)
    if p is None:
        raise VcOpError(f"Page {page_id} not found.")
    return p


def rename_page(root, page_id: str, caption: str) -> dict:
    caption = (caption or "").strip()
    if not caption:
        raise VcOpError("A page needs a name.")
    _page(_vc(root), page_id).set("Caption", caption)
    return {"page_id": str(page_id)}


def move_page(root, page_id: str, index: int) -> dict:
    """Move a page to position *index* (0 = first page, the one QLC+ opens on)."""
    vc = _vc(root)
    pages = _pages(vc)
    p = _page(vc, page_id)
    index = max(0, min(int(index), len(pages) - 1))
    others = [x for x in pages if x is not p]
    anchor = others[index] if index < len(others) else None
    vc.remove(p)
    if anchor is None:
        last = others[-1] if others else None
        pos = list(vc).index(last) + 1 if last is not None else 0
    else:
        pos = list(vc).index(anchor)
    vc.insert(pos, p)
    return {"page_id": str(page_id), "index": index}


def delete_page(root, page_id: str) -> dict:
    vc = _vc(root)
    pages = _pages(vc)
    if len(pages) <= 1:
        raise VcOpError("The Virtual Console needs at least one page.")
    p = _page(vc, page_id)
    n = sum(1 for w in p.iter() if _is_widget(w))
    vc.remove(p)
    return {"deleted": n}


# ─────────────────────────────────────────────────────────────────────────────
# layout helpers
# ─────────────────────────────────────────────────────────────────────────────

def label_panel(root, parent_id: str, lines: List[str], *, columns: int = 2,
                title: str = "Legend", label_w: int = 220, label_h: int = 26,
                x: Optional[int] = None, y: Optional[int] = None) -> dict:
    """A frame of labels, *lines* filled column by column (e.g. the
    nomenclature legend)."""
    lines = [str(s).strip() for s in lines if str(s).strip()]
    if not lines:
        raise VcOpError("No text for the label panel.")
    columns = max(1, min(int(columns or 1), len(lines)))
    rows = (len(lines) + columns - 1) // columns
    fw = MARGIN * 2 + columns * label_w + (columns - 1) * GAP
    fh = 30 + MARGIN * 2 + rows * label_h + (rows - 1) * GAP
    res = create_widget(root, parent_id, "Frame", title, x=x, y=y, w=fw, h=fh)
    vc = _vc(root)
    by_id, _ = _index(vc)
    frame = _get(by_id, res["new_ids"][0])
    nid = _next_id(vc)
    for k, text in enumerate(lines):
        c, r = divmod(k, rows)
        lab = _new_element(frame, "Label", nid, text, label_w, label_h)
        nid += 1
        _set_rect(lab, MARGIN + c * (label_w + GAP), 30 + MARGIN + r * (label_h + GAP))
        frame.append(lab)
    return {"new_ids": res["new_ids"], "labels": len(lines)}


def legend_lines(profile) -> List[str]:
    """``"A — all fixtures"`` lines of a nomenclature profile (groups, then effects)."""
    out = [f"{k} — {v}" for k, v in profile.groups.items()]
    out += [f"·{k} — {v}" for k, v in profile.effects.items()]
    return out


def _sort_key_nom(profile, name: str, ftype: str):
    """(group rank, effect rank, name) from the name's prefix; names without a
    prefix sort after, by function type."""
    if profile is not None and not profile.is_plain:
        pre = profile.prefix_of(name)
        if pre:
            letters = [ch for ch in pre if ch.isalnum() or ch == "*"]
            g = letters[0] if letters else ""
            e = letters[1] if len(letters) > 1 else ""
            gorder = list(profile.groups) or []
            eorder = list(profile.effects) or []
            return (0, gorder.index(g) if g in gorder else len(gorder), g,
                    eorder.index(e) if e in eorder else len(eorder), name.lower())
    return (1, 0, ftype, 0, name.lower())


def auto_arrange(root, frame_id: str, profile=None, *, columns: Optional[int] = None) -> dict:
    """Re-arrange the buttons of a frame: one row (or more) per nomenclature
    group (the name prefix, e.g. ``AS ·``), in the profile's group / effect
    order; without a profile, by function type then name.  Button sizes are
    kept (the largest one sets the grid); other widgets stay put."""
    vc = _vc(root)
    by_id, _ = _index(vc)
    frame = _container(vc, by_id, str(frame_id))
    fns = functions(root)
    btns = [c for c in frame if _local(c.tag) == "Button"]
    if not btns:
        raise VcOpError("No buttons in this frame.")

    def fname(b):
        fe = _child(b, "Function")
        f = fns.get(fe.get("ID") if fe is not None else "", {})
        return f.get("name") or b.get("Caption", ""), f.get("type", "")
    keyed = sorted(btns, key=lambda b: (_sort_key_nom(profile, *fname(b)), _int(b.get("ID"), 0)))
    bw = max(_rect(b)[2] for b in btns)
    bh = max(_rect(b)[3] for b in btns)
    _, _, fw, _ = _rect(frame)
    top = MARGIN + (0 if _is_page(vc, frame) else _header(frame))
    per_row = columns or max(1, (fw - 2 * MARGIN + GAP) // (bw + GAP))
    x = y = None
    row_key, col, rows = None, 0, 0
    y = top
    for b in keyed:
        k = _sort_key_nom(profile, *fname(b))[:3]
        if row_key is not None and (k != row_key or col >= per_row):
            y += bh + GAP
            col = 0
        if k != row_key:
            rows += 1
        row_key = k
        x = MARGIN + col * (bw + GAP)
        _set_rect(b, x, y)
        col += 1
    return {"arranged": len(btns), "groups": rows}


_TAP_WIDGETS = ("Button", "Slider")
MODES = ("fit", "stretch", "page")


def _scale_font(spec: str, factor: float) -> str:
    """A Qt font string with its size scaled by *factor*, kept readable: never below 8
    (or the size it had, if smaller) and never above 28 (or the size it had, if larger)."""
    parts = spec.split(",")
    if len(parts) < 3:
        return spec
    for i in (1, 2):                                   # point size, else pixel size
        try:
            old = float(parts[i])
        except ValueError:
            continue
        if old > 0:
            new = int(round(old * factor))
            new = max(min(old, 8), min(max(old, 28), new))
            parts[i] = str(int(new))
            return ",".join(parts)
    return spec


def _fonts(el: ET.Element):
    for a in el:
        if _local(a.tag) == "Appearance":
            for f in a:
                if _local(f.tag) == "Font" and (f.text or "").strip():
                    yield f


def _content_extent(page: ET.Element) -> Tuple[int, int]:
    """Right and bottom edge of what is on the page (top-level widgets)."""
    right = bottom = 0
    for c in page:
        if _is_widget(c):
            x, y, w, h = _rect(c)
            right, bottom = max(right, x + w), max(bottom, y + h)
    return right, bottom


def _is_tappable(w: ET.Element) -> bool:
    """A button that runs something, or a slider.  Caption-only buttons are labels."""
    tag = _local(w.tag)
    if tag == "Slider":
        return True
    if tag != "Button":
        return False
    if (_child(w, "Action") is not None and (_child(w, "Action").text or "").strip() in ("StopAll", "Blackout")):
        return True
    fn = _child(w, "Function")
    return fn is not None and (fn.get("ID") or "") not in ("", NONE_ID)


def too_small_to_tap(page: ET.Element, tap: int = vc_screens.TAP_MIN) -> List[dict]:
    """Buttons and sliders of a page whose smaller side is under *tap* pixels."""
    out = []
    for w in page.iter():
        if w is page or not _is_widget(w) or not _is_tappable(w):
            continue
        _x, _y, ww, hh = _rect(w)
        if min(ww, hh) < tap:
            out.append({"id": w.get("ID", ""), "caption": (w.get("Caption") or "").replace("\n", " "),
                        "type": _local(w.tag), "w": ww, "h": hh})
    return out


def apply_screen(root, profile_id: Optional[str] = None, page_ids=None, scale: bool = False, *,
                 width=None, height=None, orientation: str = "landscape", mode: Optional[str] = None,
                 touch: bool = False) -> dict:
    """Fit pages to a screen: a known one (*profile_id*) or your own *width* × *height*,
    *orientation* ``landscape`` or ``portrait``.

    *mode*:

    * ``fit`` (the default of the editor): one factor for width and height, so shapes keep
      their proportions; every widget, and the text in it, is scaled by it.
    * ``stretch``: width and height scaled separately; text follows the smaller factor.
    * ``page``: only the size of the page is set; widgets stay where they are.

    Without *mode*, as before 3.7.0: *scale* true stretches the widgets (text unchanged),
    false sets the page size only, so a recorded session replays to the same file.

    Returns ``{pages, size, outside, mode, factor, touch, small_count, small}``; *small*
    names the buttons and sliders under :data:`vc_screens.TAP_MIN` pixels on a touch screen.
    """
    try:
        sw, sh, is_touch, label = vc_screens.resolve(profile_id, width, height, orientation, touch)
    except vc_screens.ScreenError as e:
        raise VcOpError(str(e))
    legacy = mode is None
    if legacy:
        mode = "stretch" if scale else "page"
    if mode not in MODES:
        raise VcOpError(f"Unknown way to fit: {mode} (use fit, stretch or page).")
    vc = _vc(root)
    pages = _pages(vc) if not page_ids else [_page(vc, p) for p in page_ids]
    outside, small, factor = 0, [], 1.0
    for p in pages:
        _, _, pw, ph = _rect(p)
        if mode == "fit":
            cw, ch = _content_extent(p)
            bw, bh = max(pw, cw, 1), max(ph, ch, 1)
            kx = ky = factor = min(sw / bw, sh / bh)
        else:
            kx, ky = (sw / pw if pw else 1.0), (sh / ph if ph else 1.0)
            factor = min(kx, ky)
        if mode != "page":
            for w in p.iter():
                if w is not p and _is_widget(w):
                    x, y, ww, hh = _rect(w)
                    _set_rect(w, round(x * kx), round(y * ky), max(10, round(ww * kx)), max(10, round(hh * ky)))
            if not legacy:                                  # text follows the widgets (not in old recipes)
                for el in p.iter():
                    if el is p or _is_widget(el):
                        for f in _fonts(el):
                            f.text = _scale_font(f.text.strip(), factor)
        _set_rect(p, 0, 0, sw, sh)
        for c in p:
            if _is_widget(c):
                x, y, ww, hh = _rect(c)
                if x + ww > sw + 8 or y + hh > sh + 8:
                    outside += 1
        if is_touch:
            small.extend({**s, "page": p.get("Caption", "")} for s in too_small_to_tap(p))
    return {"pages": len(pages), "size": f"{sw}×{sh}", "outside": outside, "mode": mode,
            "factor": round(factor, 3), "touch": is_touch, "screen": label,
            "small_count": len(small), "small": small[:30]}


def preview_screen(root, **kw) -> dict:
    """What :func:`apply_screen` would do, on a copy: the show is not touched."""
    return apply_screen(copy.deepcopy(root), **kw)


# ─────────────────────────────────────────────────────────────────────────────
# templates
# ─────────────────────────────────────────────────────────────────────────────

def templates_dir() -> str:
    return os.environ.get("QSK_VC_TEMPLATES") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "vc_templates")


def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")
    if not s:
        raise VcOpError("A template needs a name.")
    return s[:60]


def list_templates() -> List[dict]:
    d = templates_dir()
    out = []
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(d, fn), encoding="utf-8") as fh:
                        t = json.load(fh)
                    out.append({"name": t.get("name", fn[:-5]), "caption": t.get("caption", ""),
                                "widgets": t.get("widgets", 0), "functions": len(t.get("functions", {})),
                                "file": fn})
                except (OSError, ValueError):
                    continue
    return out


def save_template(root, page_id: str, name: str) -> dict:
    """Save a page (layout, colours, function *names*; no key/MIDI bindings)
    as a reusable template."""
    vc = _vc(root)
    page = copy.deepcopy(_page(vc, page_id))
    from core.qxw_io import strip_ns
    page = strip_ns(page)
    _strip_bindings(page)
    fns = functions(root)
    used = {}
    for el in page.iter():
        for fid in _refs(el):
            if fid in fns:
                used[fid] = fns[fid]
    data = {"name": name.strip(), "caption": page.get("Caption", ""),
            "widgets": sum(1 for w in page.iter() if _is_widget(w)),
            "functions": used,
            "xml": ET.tostring(page, encoding="unicode")}  # qxw-io: not output (template JSON)
    os.makedirs(templates_dir(), exist_ok=True)
    path = os.path.join(templates_dir(), _slug(name) + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    return {"template": data["name"], "widgets": data["widgets"], "functions": len(used)}


def delete_template(name: str) -> bool:
    path = os.path.join(templates_dir(), _slug(name) + ".json")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def _refs(el: ET.Element) -> List[str]:
    """Function IDs referenced directly by one VC element."""
    tag = _local(el.tag)
    if tag == "Function" and el.get("ID"):
        return [el.get("ID")]
    if tag == "Function" and (el.text or "").strip():
        return [(el.text or "").strip()]
    if tag == "Chaser" and (el.text or "").strip():
        return [(el.text or "").strip()]
    return []


def apply_template(root, name: str, caption: str = "") -> dict:
    """Add a saved template as a new page; functions are matched **by name and
    type** in this workspace (unmatched → unwired, listed)."""
    path = os.path.join(templates_dir(), _slug(name) + ".json")
    if not os.path.isfile(path):
        raise VcOpError(f"Template '{name}' not found.")
    with open(path, encoding="utf-8") as fh:
        t = json.load(fh)
    vc = _vc(root)
    page = ET.fromstring(t["xml"])  # nosec B314 — our own file
    if vc.tag.startswith(vc_ops._NS):
        for el in page.iter():
            el.tag = vc_ops._NS + el.tag
    by_name = {}
    for fid, f in sorted(functions(root).items(), key=lambda kv: _int(kv[0], 0)):
        by_name.setdefault((f["name"], f["type"]), fid)
    mapping, missing = {}, []
    for fid, f in t.get("functions", {}).items():
        new = by_name.get((f["name"], f["type"]))
        mapping[fid] = new or NONE_ID
        if not new:
            missing.append(f"{f['type']} '{f['name']}'")
    for el in page.iter():
        tag = _local(el.tag)
        if tag == "Function" and el.get("ID") in mapping:
            el.set("ID", mapping[el.get("ID")])
        elif tag in ("Function", "Chaser") and (el.text or "").strip() in mapping:
            el.text = mapping[(el.text or "").strip()]
    _renumber(page, _next_id(vc))
    page.set("Caption", (caption or "").strip() or t.get("caption") or t["name"])
    vc_ops._set_xy(page, 0, 0)
    vc_ops._append_page(vc, page)
    return {"page_id": page.get("ID"), "matched": len(mapping) - len(missing),
            "missing": sorted(missing)}


# ─────────────────────────────────────────────────────────────────────────────
# setlist
# ─────────────────────────────────────────────────────────────────────────────

def setlist_cuelist(root, chaser_id: str, *, cuelist_id: Optional[str] = None,
                    page_id: Optional[str] = None) -> dict:
    """Wire a setlist chaser to a CueList: the given one, or a new CueList on
    *page_id* (default: the first page)."""
    vc = _vc(root)
    pages = _pages(vc)
    if not pages:
        raise VcOpError("This workspace has no pages.")
    if str(chaser_id) == NEW_SETLIST:
        chaser_id = _new_setlist_chaser(root)
    if cuelist_id:
        return {**wire(root, cuelist_id, chaser_id), "new_ids": [], "chaser_id": str(chaser_id)}
    pid = page_id or pages[0].get("ID")
    f = functions(root).get(str(chaser_id))
    if f is None or f["type"] != "Chaser":
        raise VcOpError("Pick a chaser for the CueList.")
    # the widest size that fits on the page without covering other widgets
    by_id, _ = _index(vc)
    page = _container(vc, by_id, str(pid))
    for w, h in CUELIST_SIZES:
        if free_spot(page, w, h, True, strict=True):
            break
    else:
        w, h = DEFAULT_SIZE["CueList"]
    return {**create_widget(root, pid, "CueList", f["name"], func_id=str(chaser_id), w=w, h=h),
            "chaser_id": str(chaser_id)}


# a setlist CueList: wide enough for the notes; smaller if the page is full
CUELIST_SIZES = [(720, 420), (720, 340), (600, 300), (480, 260), (400, 220)]


def cuelists(root) -> list:
    """The CueList widgets of the show: id, caption and the chaser they play."""
    try:
        vc = _vc(root)
    except VcOpError:
        return []
    out = []
    for el in vc.iter():
        if _local(el.tag) != "CueList":
            continue
        ch = next((c for c in el if _local(c.tag) == "Chaser"), None)
        out.append({"id": el.get("ID"), "caption": el.get("Caption") or "",
                    "chaser_id": (ch.text or "").strip() if ch is not None else ""})
    return out


NEW_SETLIST = "__new__"


def _new_setlist_chaser(root) -> str:
    """An empty chaser for a new setlist (the Setlist tool fills it): steps
    with their own fades, held until Next."""
    eng = _engine(root)
    if eng is None:
        raise VcOpError("This workspace has no Engine.")
    ids = [_int(fid, -1) for fid in functions(root)]
    fid = str(max(ids + [-1]) + 1)
    names = {f["name"] for f in functions(root).values()}
    name, n = "Setlist", 2
    while name in names:
        name, n = f"Setlist {n}", n + 1
    kids = list(eng)
    last = max((i for i, c in enumerate(kids) if _local(c.tag) == "Function"), default=len(kids) - 1)
    fn = ET.Element(_q("Function", eng), {"ID": fid, "Type": "Chaser", "Name": name})
    eng.insert(last + 1, fn)
    _sub(fn, "Speed", FadeIn="0", FadeOut="0", Duration="4294967294")
    _sub(fn, "Direction", "Forward")
    _sub(fn, "RunOrder", "SingleShot")
    _sub(fn, "SpeedModes", FadeIn="PerStep", FadeOut="PerStep", Duration="PerStep")
    return fid


OPS = {
    "create": create_widget, "delete": delete_widgets, "duplicate": duplicate_widgets,
    "wire": wire, "rename_page": rename_page, "move_page": move_page,
    "delete_page": delete_page, "label_panel": label_panel, "auto_arrange": auto_arrange,
    "screen": apply_screen, "apply_template": apply_template, "setlist_cuelist": setlist_cuelist,
}
