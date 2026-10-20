"""
core/vc_screens.py
==================
Screen sizes for the Virtual Console, as data (3.7.0).

QLC+ places Virtual Console widgets at fixed pixel positions.  A console made
on a laptop overflows a small touchscreen and is tiny on a big one.  This
module lists the screens the VC Visual Editor can fit a console to: the ones
that ship with Swiss Knife and your own (a JSON file each, shared through the
Library as the kind *Screen size*).

Sizes are given in landscape, in the pixels the screen (or the browser on it)
reports.  *Portrait* swaps them.  A *touch* screen also gets the warning for
buttons and sliders too small to tap (:data:`TAP_MIN`).
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Tuple

#: smallest side, in screen pixels, of a button or slider that can be tapped with a finger
#: (Apple asks for 44 pt, Material for 48 dp)
TAP_MIN = 44
MIN_SIDE, MAX_SIDE = 200, 10000

# The first four are the sizes of 2.x and keep their ids (old recipes name them).
BUILTIN: List[dict] = [
    {"id": "macbook", "label": "MacBook 1650 × 884", "w": 1650, "h": 884, "touch": False},
    {"id": "hd", "label": "HD laptop 1366 × 768", "w": 1366, "h": 768, "touch": False},
    {"id": "fullhd", "label": "Full HD 1920 × 1080", "w": 1920, "h": 1080, "touch": False},
    {"id": "qhd", "label": "QHD 2560 × 1440", "w": 2560, "h": 1440, "touch": False},
    {"id": "uhd", "label": "4K UHD 3840 × 2160", "w": 3840, "h": 2160, "touch": False},
    {"id": "touch7_800", "label": "7″ touchscreen 800 × 480", "w": 800, "h": 480, "touch": True},
    {"id": "touch7_1024", "label": "7″ touchscreen 1024 × 600", "w": 1024, "h": 600, "touch": True},
    {"id": "pi_touch2", "label": "Raspberry Pi Touch Display 2 (7″) 1280 × 720", "w": 1280, "h": 720, "touch": True},
    {"id": "tablet", "label": "Tablet 1280 × 800", "w": 1280, "h": 800, "touch": True},
    {"id": "ipad", "label": "iPad 1024 × 768", "w": 1024, "h": 768, "touch": True},
    {"id": "ipad_mini", "label": "iPad mini 1133 × 744", "w": 1133, "h": 744, "touch": True},
    {"id": "ipad_10_2", "label": "iPad 10.2″ 1080 × 810", "w": 1080, "h": 810, "touch": True},
    {"id": "ipad_10_9", "label": "iPad 10.9″ / Air 11″ 1180 × 820", "w": 1180, "h": 820, "touch": True},
    {"id": "ipad_12_9", "label": "iPad Pro 12.9″ / Air 13″ 1366 × 1024", "w": 1366, "h": 1024, "touch": True},
]


class ScreenError(ValueError):
    pass


def user_dir() -> str:
    """Your own screen sizes (files made by hand or imported from the Library)."""
    return os.environ.get("QSK_VC_SCREENS") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "vc_screens")


def slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "").strip()).strip("_")[:60]
    return s


def clean(d: dict, *, label: str = "") -> dict:
    """A valid screen from *d* (``w``, ``h``, ``touch``, ``label``); raises :class:`ScreenError`."""
    try:
        w, h = int(d.get("w")), int(d.get("h"))
    except (TypeError, ValueError):
        raise ScreenError("the width and the height must be numbers")
    for v in (w, h):
        if not MIN_SIDE <= v <= MAX_SIDE:
            raise ScreenError(f"a side must be between {MIN_SIDE} and {MAX_SIDE} pixels")
    w, h = max(w, h), min(w, h)                     # stored in landscape
    name = str(label or d.get("label") or "").strip()[:60]
    return {"label": name or f"{w} × {h}", "w": w, "h": h, "touch": bool(d.get("touch"))}


def list_screens() -> List[dict]:
    """The built-in sizes, then yours (sorted by name)."""
    out = [{**b, "builtin": True} for b in BUILTIN]
    taken = {b["id"] for b in BUILTIN}
    folder = user_dir()
    mine = []
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(folder, fn), encoding="utf-8") as fh:
                    raw = json.load(fh)
                sid = slug(raw.get("id") or fn[:-5])
                if not sid or sid in taken:
                    continue
                c = clean(raw)
                mine.append({"id": sid, **c, "builtin": False})
            except (OSError, ValueError, ScreenError, AttributeError):
                continue
    mine.sort(key=lambda s: s["label"].lower())
    return out + mine


def get(screen_id: str) -> Optional[dict]:
    return next((s for s in list_screens() if s["id"] == screen_id), None)


def resolve(profile_id: Optional[str] = None, width=None, height=None, orientation: str = "landscape",
            touch: bool = False) -> Tuple[int, int, bool, str]:
    """``(width, height, touch, label)`` of the screen asked for: a known id, or a width and
    a height of your own.  *orientation* ``portrait`` swaps the sides."""
    if profile_id:
        s = get(str(profile_id))
        if s is None:
            raise ScreenError(f"Unknown screen profile: {profile_id}")
        w, h, tch, label = s["w"], s["h"], s["touch"], s["label"]
    else:
        c = clean({"w": width, "h": height, "touch": touch})
        w, h, tch, label = c["w"], c["h"], c["touch"], c["label"]
    if orientation not in ("landscape", "portrait"):
        raise ScreenError("The orientation is landscape or portrait.")
    if orientation == "portrait":
        w, h = h, w
    return w, h, tch, label
