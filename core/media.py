"""
Sound and video files used by a workspace (v3.9.8).

An Audio or Video function stores only the *path* of its file, never the
file.  The path is machine specific, so a show that plays on one computer
can be silent on another.  This module lists those files and tells whether
each one is there; it never opens or copies them.

Status of a file:
  found    the file exists
  missing  the path is set but nothing is there
  url      a stream / web address, not checked
  empty    the function has no file at all
  unknown  a relative path and no folder to look in
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

MEDIA_TYPES = ("Audio", "Video")
_URL_RE = re.compile(r"^[a-z][a-z0-9+.-]{1,12}://", re.I)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kids(el, name: str):
    return [c for c in el if _local(c.tag) == name]


def _functions(root):
    for eng in _kids(root, "Engine"):
        for f in _kids(eng, "Function"):
            yield f


def media_status(source: str, base_dir: str = "") -> str:
    src = (source or "").strip()
    if not src:
        return "empty"
    if _URL_RE.match(src):
        return "url"
    if os.path.isabs(src) or re.match(r"^[A-Za-z]:[\\/]", src):
        return "found" if os.path.isfile(src) else "missing"
    if not base_dir:
        return "unknown"
    return "found" if os.path.isfile(os.path.join(base_dir, src)) else "missing"


def media_files(root, base_dir: str = "") -> List[Dict[str, str]]:
    """Every Audio / Video function of *root* (namespaced or not), in file order."""
    out: List[Dict[str, str]] = []
    for f in _functions(root):
        typ = f.get("Type", "")
        if typ not in MEDIA_TYPES:
            continue
        srcs = _kids(f, "Source")
        source = (srcs[0].text or "").strip() if srcs else ""
        out.append({"id": f.get("ID", ""), "name": f.get("Name", ""), "type": typ,
                    "source": source, "status": media_status(source, base_dir)})
    return out


def show_items(func) -> List[Dict[str, object]]:
    """The items of a Show function: [{track, function, start, duration}] (ms)."""
    items: List[Dict[str, object]] = []
    for tr in _kids(func, "Track"):
        for it in _kids(tr, "ShowFunction"):
            try:
                start = int(it.get("StartTime", "0"))
                dur = int(it.get("Duration", "0"))
            except ValueError:
                continue
            items.append({"track": tr.get("Name", ""), "function": it.get("ID", ""),
                          "start": start, "duration": dur})
    return items


def show_length_ms(func) -> int:
    """When the last item of the Show ends (0 for an empty Show)."""
    return max((int(i["start"]) + int(i["duration"]) for i in show_items(func)), default=0)


def base_dir_of(path: Optional[str]) -> str:
    return os.path.dirname(os.path.abspath(path)) if path else ""
