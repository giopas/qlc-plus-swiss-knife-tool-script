"""
A read-only picture of a Show (3.10.0).

The Song Builder draws its Show as coloured bars while it is typed.  This module does the
same for **any** Show of the open file: one row per track, one bar per item, sound and
video items marked with the state of their file.  It only reads; QLC+ has its own timeline
editor for fine work and nothing here can change a Show.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List

from core import media

MAX_TRACKS = 200
MAX_ITEMS = 5000
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
TYPE_COLORS = {"Audio": "#4a90d9", "Video": "#9b59b6", "Scene": "#f0ad4e", "Chaser": "#5cb85c",
               "Collection": "#1abc9c", "RGBMatrix": "#e91e63", "EFX": "#e67e22", "Script": "#5bc0de"}
DEFAULT_COLOR = "#8a8f98"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kids(el, name: str):
    return [c for c in el if _local(c.tag) == name]


def _color(raw: str, ftype: str) -> str:
    raw = (raw or "").strip()
    return raw if _HEX.match(raw) else TYPE_COLORS.get(ftype, DEFAULT_COLOR)


def shows(engine) -> List[Dict[str, str]]:
    """Every Show of the file: [{id, name}]."""
    return [{"id": f.get("ID", ""), "name": f.get("Name", "")} for f in _kids(engine, "Function")
            if f.get("Type") == "Show"]


def picture(engine, show_id: str, base_dir: str = "") -> Dict[str, object]:
    """The tracks and items of one Show, ready to draw.  Raises ValueError for an unknown id or a
    function that is not a Show."""
    funcs = {f.get("ID"): f for f in _kids(engine, "Function")}
    show = funcs.get(str(show_id))
    if show is None or show.get("Type") != "Show":
        raise ValueError("That function is not a Show of this file.")
    td = next(iter(_kids(show, "TimeDivision")), None)
    tracks, n_items, cut = [], 0, False
    for tr in _kids(show, "Track"):
        if len(tracks) >= MAX_TRACKS:
            cut = True
            break
        items = []
        for it in _kids(tr, "ShowFunction"):
            if n_items >= MAX_ITEMS:
                cut = True
                break
            try:
                start, dur = int(it.get("StartTime", "0")), int(it.get("Duration", "0"))
            except ValueError:
                continue
            if start < 0 or dur < 0:
                continue
            f = funcs.get(it.get("ID", ""))
            ftype = f.get("Type", "") if f is not None else ""
            row = {"function": it.get("ID", ""), "name": f.get("Name", "") if f is not None else "",
                   "type": ftype, "start": start, "duration": dur, "color": _color(it.get("Color", ""), ftype),
                   "status": "ok" if f is not None else "missing"}
            if ftype in media.MEDIA_TYPES:
                src = next(iter(_kids(f, "Source")), None)
                source = (src.text or "").strip() if src is not None else ""
                st = media.media_status(source, base_dir)
                row["file"] = os.path.basename(source.replace("\\", "/"))
                row["status"] = "missing" if st in ("missing", "empty") else "ok"
            items.append(row)
            n_items += 1
        tracks.append({"name": tr.get("Name", ""), "mute": tr.get("isMute", "0") == "1", "items": items})
    length = max((i["start"] + i["duration"] for t in tracks for i in t["items"]), default=0)
    return {"id": show.get("ID"), "name": show.get("Name", ""), "length_ms": length,
            "bpm": td.get("BPM", "") if td is not None else "", "tracks": tracks, "cut": cut,
            "song": "SwissKnifeSong" in show.attrib}
