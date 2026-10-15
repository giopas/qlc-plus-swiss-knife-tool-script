"""
core/vc_group_pages.py — a Virtual Console page with one multipage frame and a
page per fixture group, like the QLC+ 5.3 Show Wizard's (3.2.0, shared in 3.3.0).

Used by Upgrade to QLC+ 5.3 (its *Groups* page) and by the Look & Chaser
Builder (buttons on a page per group).  The page is picked in the frame's
header, so no Loopback universe is needed, and everything works in QLC+ 5.2.2
too (the XY pad's floor mode is 5.3 only; 5.2.2 uses it as a pan/tilt pad).

A page is a dict::

    {"name": "Back",
     "slider": [(fixture id, channel), …],        # intensity slider (Level mode)
     "looks":  [[fid, …], …],                     # one solo frame, a line per list
     "effects": [fid, …],                         # toggles (or flashes), line by line
     "flash":  {fid, …},                          # effects that flash instead of toggle
     "colours": {fid: "#rrggbb"},                 # button colours (else the default)
     "xypad":  [fixture id, …]}                   # moving heads

Layout is deterministic: the same pages give the same XML.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET  # nosec B405
from typing import Callable, Dict, List, Optional, Tuple

BUTTON = 85                       # the wizard's button size and spacing
GAP = 20
MARGIN = 20
TOP = 60                          # first row inside the frame (below its header)
SLIDER = (75, 335)
XYPAD = (295, 295)
RED = "4294901760"
LOOK_BG = "4282664004"


def _fmt(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def qlc_colour(hx: str) -> str:
    hx = hx.lstrip("#")
    r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    return str(0xFF000000 | (r << 16) | (g << 8) | b)


def _text_colour(hx: str) -> str:
    hx = hx.lstrip("#")
    r, g, b = (int(hx[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return str(0xFF000000 if 0.299 * r + 0.587 * g + 0.114 * b > 0.55 else 0xFFFFFFFF)


def ws(el: ET.Element, x: int, y: int, w: int, h: int, visible: bool) -> None:
    ET.SubElement(el, "WindowState", {"Visible": "True" if visible else "False", "X": str(x),
                                      "Y": str(y), "Width": str(w), "Height": str(h)})


def frame_flags(el: ET.Element, header: bool = True) -> None:
    for tag, val in (("AllowResize", "True"), ("ShowHeader", "True" if header else "False"),
                     ("ShowEnableButton", "True"), ("Collapsed", "False"), ("Disabled", "False")):
        ET.SubElement(el, tag).text = val


def button(nid: Callable[[], int], caption: str, fid: str, x: int, y: int, *, page: Optional[int] = None,
           visible: bool = True, bg: str = LOOK_BG, hexcol: Optional[str] = None,
           action: str = "Toggle") -> ET.Element:
    attrs = {"Caption": caption[:32], "ID": str(nid())}
    if page:
        attrs["Page"] = str(page)
    b = ET.Element("Button", attrs)
    ws(b, x, y, BUTTON, BUTTON, visible)
    app = ET.SubElement(b, "Appearance")
    if hexcol:
        ET.SubElement(app, "BackgroundColor").text = qlc_colour(hexcol)
        ET.SubElement(app, "ForegroundColor").text = _text_colour(hexcol)
    else:
        ET.SubElement(app, "BackgroundColor").text = bg
    ET.SubElement(b, "Function", {"ID": fid})
    ET.SubElement(b, "Action").text = action
    return b


def build(work: ET.Element, caption: str, pages: List[dict], names: Dict[str, str], *,
          floor: Tuple[float, float, float], panic: Optional[str] = None,
          looks_caption: str = "Looks") -> Tuple[str, List[str]]:
    """Add a VC page *caption* holding one frame with a page per entry of
    *pages*; ``(VC page id, report lines)``."""
    from core import vc_ops
    vc = work.find("VirtualConsole")
    if vc is None:
        vc = ET.SubElement(work, "VirtualConsole")
    page_id = vc_ops.new_page(work, caption)["page_id"]
    page_el = next(p for p in vc if p.get("ID") == page_id)
    pw, ph = 1920, 1080
    st = page_el.find("WindowState")
    if st is not None:
        try:
            pw, ph = int(st.get("Width", pw)), int(st.get("Height", ph))
        except ValueError:
            pass
    counter = [vc_ops._next_id(vc)]

    def nid():
        counter[0] += 1
        return counter[0] - 1

    fw, fh = pw - 2 * MARGIN, ph - 2 * MARGIN
    fr = ET.Element("Frame", {"Caption": caption, "ID": str(nid())})
    ws(fr, MARGIN, MARGIN, fw, fh, True)
    frame_flags(fr)
    ET.SubElement(fr, "Multipage", {"PagesNum": str(len(pages)), "CurrentPage": "0"})
    for i, p in enumerate(pages):
        ET.SubElement(fr, "Shortcut", {"Page": str(i), "Name": p["name"]})
    page_el.append(fr)
    per_page: List[str] = []

    for i, p in enumerate(pages):
        vis = i == 0
        colours = p.get("colours") or {}
        flash = p.get("flash") or set()
        looks_rows = [r for r in (p.get("looks") or []) if r]
        n_looks = sum(len(r) for r in looks_rows)
        placed_l, placed_e, lost = 0, 0, []
        if panic:
            fr.append(button(nid, "PANIC RESET", panic, fw - MARGIN - BUTTON, TOP, page=i, visible=vis, bg=RED))
        cx = MARGIN
        y_col = TOP + BUTTON + GAP
        if p.get("slider"):
            s = ET.Element("Slider", {"Caption": "Intensity", "ID": str(nid()), "WidgetStyle": "Slider",
                                      "InvertedAppearance": "false"})
            if i:
                s.set("Page", str(i))
            ws(s, MARGIN, y_col, SLIDER[0], SLIDER[1], vis)
            app = ET.SubElement(s, "Appearance")
            ET.SubElement(app, "BackgroundColor").text = LOOK_BG
            ET.SubElement(s, "SliderMode", {"ValueDisplayStyle": "Exact"}).text = "Level"
            lv = ET.SubElement(s, "Level", {"LowLimit": "0", "HighLimit": "255", "Value": "0"})
            for f, c in p["slider"]:
                ET.SubElement(lv, "Channel", {"Fixture": f}).text = str(c)
            fr.append(s)
            cx = MARGIN + SLIDER[0] + GAP
        # moving heads: the XY pad gets the right-hand column, under PANIC RESET
        pad_col = XYPAD[0] + GAP if p.get("xypad") else 0
        avail = fw - cx - MARGIN - pad_col
        y = y_col
        # looks: one at a time, in a solo frame; each list starts a new line
        if n_looks:
            longest = max(len(r) for r in looks_rows)
            cols = max(1, min(longest, (avail - 2 * MARGIN + GAP) // (BUTTON + GAP)))
            room_rows = max(0, (fh - MARGIN - y - MARGIN + GAP) // (BUTTON + GAP))
            cells: List[Tuple[int, int, str]] = []
            line = 0
            for r in looks_rows:
                for k, fid in enumerate(r):
                    cells.append((line + k // cols, k % cols, fid))
                line += math.ceil(len(r) / cols)
            keep = [c for c in cells if c[0] < room_rows]
            if keep:
                rows = max(c[0] for c in keep) + 1
                sw = 2 * MARGIN + cols * BUTTON + (cols - 1) * GAP
                sh = 2 * MARGIN + rows * BUTTON + (rows - 1) * GAP
                solo = ET.Element("SoloFrame", {"Caption": looks_caption, "ID": str(nid())})
                if i:
                    solo.set("Page", str(i))
                ws(solo, cx, y, sw, sh, vis)
                frame_flags(solo, header=False)
                for row, col, fid in keep:
                    solo.append(button(nid, names[fid], fid, MARGIN + col * (BUTTON + GAP),
                                       MARGIN + row * (BUTTON + GAP), hexcol=colours.get(fid)))
                fr.append(solo)
                placed_l = len(keep)
                y += sh + GAP
            lost += [c[2] for c in cells if c[0] >= room_rows]
        # effects: toggles (or flashes), line by line
        effects = p.get("effects") or []
        if effects:
            per_row = max(1, (avail + GAP) // (BUTTON + GAP))
            k = 0
            for fid in effects:
                bx = cx + (k % per_row) * (BUTTON + GAP)
                by = y + (k // per_row) * (BUTTON + GAP)
                if by + BUTTON > fh - MARGIN:
                    lost.append(fid)
                    continue
                fr.append(button(nid, names[fid], fid, bx, by, page=i, visible=vis, hexcol=colours.get(fid),
                                 action="Flash" if fid in flash else "Toggle"))
                k += 1
            placed_e = k
            if k:
                y += math.ceil(k / per_row) * (BUTTON + GAP)
        # moving heads: an XY pad that aims at the stage floor in QLC+ 5.3
        pad = False
        if p.get("xypad"):
            px = fw - MARGIN - XYPAD[0]
            py = y_col
            if py + XYPAD[1] <= fh - MARGIN:
                xy = ET.Element("XYPad", {"Caption": "Position", "ID": str(nid())})
                if i:
                    xy.set("Page", str(i))
                xy.set("InvertedAppearance", "0")
                xy.set("FloorControl", "1")
                ws(xy, px, py, XYPAD[0], XYPAD[1], vis)
                ET.SubElement(xy, "Appearance")
                for f in p["xypad"]:
                    ET.SubElement(xy, "Fixture", {"ID": f, "Head": "0"})
                ET.SubElement(xy, "Window", {"hMin": "0", "hMax": "255", "vMin": "0", "vMax": "255"})
                ET.SubElement(xy, "Pan", {"Position": "0"})
                ET.SubElement(xy, "Tilt", {"Position": "0"})
                ET.SubElement(xy, "FloorPosition", {"X": _fmt(floor[0]), "Y": "0", "Z": _fmt(floor[2])})
                fr.append(xy)
                pad = True
            else:
                lost.append("XY pad")
        bits = []
        if p.get("slider"):
            bits.append("intensity slider")
        if placed_l:
            bits.append(f"{placed_l} look(s)")
        if placed_e:
            bits.append(f"{placed_e} effect(s)")
        if pad:
            bits.append(f"XY pad for {len(p['xypad'])} moving head(s)")
        per_page.append(f"page '{p['name']}': " + (", ".join(bits) or "empty"))
        if lost:
            per_page.append(f"page '{p['name']}': no room for " + ", ".join(names.get(x, x) for x in lost))
    return page_id, per_page
