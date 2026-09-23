"""
core/quick_start/vc_style.py
============================
VC *style* — button size, gaps, fonts, page size — as data, optionally
cloned from a reference workspace (WORKPLAN 1.1 "Clone VC style").

``extract_style(root)`` reads a (namespace-stripped) QXW tree and measures
what its author actually used:

* page size      — most common size of the top-level VC frames (pages);
* button size    — most common Width×Height among "real" buttons
                   (≥ 30 px tall, so label-strip buttons don't win);
* gap            — median horizontal gap between neighbouring buttons;
* header offset  — smallest child Y inside frames that show a header;
* fonts          — most common button / frame / page font strings;
* slider width   — most common slider width.

The generator only uses the geometry and fonts; colours stay semantic
(red button = red look) so the output reads the same in any style.
"""

from __future__ import annotations

import json
import os
import statistics
from collections import Counter
from typing import Optional

from core.qxw_io import load_qxw

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "profiles", "vc_style")

DEFAULTS = {
    "id": "default",
    "label": "Default",
    "source": "",
    "page_w": 0,          # 0 = fit to content
    "page_h": 0,
    "btn_w": 130,
    "btn_h": 55,
    "gap": 5,
    "header_h": 40,
    "slider_w": 70,
    "font_button": "",
    "font_frame": "",
    "font_page": "",
}

_INT_KEYS = ("page_w", "page_h", "btn_w", "btn_h", "gap", "header_h", "slider_w")


class VCStyle:
    def __init__(self, data: Optional[dict] = None):
        d = {**DEFAULTS, **(data or {})}
        for k in _INT_KEYS:
            d[k] = int(d.get(k) or 0)
        d["btn_w"] = max(d["btn_w"], 40)
        d["btn_h"] = max(d["btn_h"], 20)
        d["header_h"] = max(d["header_h"], 20)
        d["slider_w"] = max(d["slider_w"], 30)
        self.__dict__.update(d)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in DEFAULTS}


def _ws(el):
    w = el.find("WindowState")
    if w is None:
        return None
    try:
        return tuple(int(w.get(k, 0)) for k in ("X", "Y", "Width", "Height"))
    except ValueError:
        return None


def _mode(counter: Counter, default):
    return counter.most_common(1)[0][0] if counter else default


def extract_style(root, source: str = "") -> VCStyle:
    """Measure the VC style of a namespace-stripped workspace tree."""
    vc = root.find("VirtualConsole")
    if vc is None:
        return VCStyle({"source": source})
    pages = [c for c in vc if c.tag in ("Frame", "SoloFrame")]
    page_sizes = Counter((g[2], g[3]) for g in map(_ws, pages) if g)
    page_fonts = Counter(p.findtext("Appearance/Font") for p in pages
                         if p.findtext("Appearance/Font"))

    btn_sizes, btn_fonts, frame_fonts, slider_w = Counter(), Counter(), Counter(), Counter()
    gaps, header = [], []
    for el in vc.iter():
        if el.tag == "Button":
            g = _ws(el)
            if g and g[3] >= 30:
                btn_sizes[(g[2], g[3])] += 1
            f = el.findtext("Appearance/Font")
            if f:
                btn_fonts[f] += 1
        elif el.tag == "Slider":
            g = _ws(el)
            if g:
                slider_w[g[2]] += 1
        elif el.tag in ("Frame", "SoloFrame") and el not in pages:
            f = el.findtext("Appearance/Font")
            if f:
                frame_fonts[f] += 1
        if el.tag in ("Frame", "SoloFrame"):
            kids = [(_ws(c), c.tag) for c in el
                    if c.tag in ("Button", "Slider", "Frame", "SoloFrame", "Label")]
            if (el.findtext("ShowHeader") or "").lower() == "true" and el not in pages:
                ys = [g[1] for g, _ in kids if g]
                if ys:
                    header.append(min(ys))
            btns = [g for g, t in kids if g and t == "Button"]
            for a in btns:
                for b in btns:
                    if a is not b and abs(a[1] - b[1]) < 3 and b[0] > a[0]:
                        gap = b[0] - a[0] - a[2]
                        if 0 <= gap <= 40:
                            gaps.append(gap)

    bw, bh = _mode(btn_sizes, (DEFAULTS["btn_w"], DEFAULTS["btn_h"]))
    pw, ph = _mode(page_sizes, (0, 0))
    name = os.path.splitext(os.path.basename(source))[0] if source else "reference"
    return VCStyle({
        "id": "custom",
        "label": f"From {name}",
        "source": os.path.basename(source),
        "page_w": pw, "page_h": ph,
        "btn_w": bw, "btn_h": bh,
        "gap": int(statistics.median(gaps)) if gaps else DEFAULTS["gap"],
        "header_h": min(max(min(header), 20), 60) if header else DEFAULTS["header_h"],
        "slider_w": _mode(slider_w, DEFAULTS["slider_w"]),
        "font_button": _mode(btn_fonts, ""),
        "font_frame": _mode(frame_fonts, ""),
        "font_page": _mode(page_fonts, ""),
    })


def extract_style_file(path: str) -> VCStyle:
    return extract_style(load_qxw(path, strip_namespace=True), source=path)


def list_styles() -> list:
    out = [{"id": "default", "label": "Default"}]
    for fn in sorted(os.listdir(PROFILE_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(PROFILE_DIR, fn), encoding="utf-8") as fh:
                d = json.load(fh)
            out.append({"id": d.get("id", fn[:-5]), "label": d.get("label", fn[:-5])})
    return out


def load_style(ref=None) -> VCStyle:
    """``None``/"default" → defaults; a dict → that style; a built-in id →
    ``profiles/vc_style/<id>.json``; a ``.qxw`` path → extracted."""
    if isinstance(ref, VCStyle):
        return ref
    if isinstance(ref, dict):
        return VCStyle(ref)
    if not ref or ref == "default":
        return VCStyle()
    if ref.lower().endswith(".qxw") and os.path.isfile(ref):
        return extract_style_file(ref)
    path = os.path.join(PROFILE_DIR, f"{os.path.basename(ref)}.json")
    if not os.path.isfile(path):
        raise ValueError(f"Unknown VC style: {ref}")
    with open(path, encoding="utf-8") as fh:
        return VCStyle(json.load(fh))
