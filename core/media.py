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


# ── length of a sound file (3.9.8, Song Builder) ─────────────────────────────

AUDIO_EXTS = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")
_MP3_BITRATES = {  # (version, layer 3) → kbps by index
    1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
}
_MP3_RATES = {1: [44100, 48000, 32000], 2: [22050, 24000, 16000], 25: [11025, 12000, 8000]}


def _mp3_ms(data: bytes, size: int) -> Optional[int]:
    """Length of an MP3 (layer III) from its first frame: the Xing/Info frame
    count when there is one, else the file size at the constant bitrate."""
    pos = 0
    if data[:3] == b"ID3" and len(data) >= 10:
        pos = 10 + ((data[6] & 0x7F) << 21 | (data[7] & 0x7F) << 14 | (data[8] & 0x7F) << 7 | (data[9] & 0x7F))
    for i in range(pos, min(len(data) - 4, pos + 8192)):
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            b1, b2, b3 = data[i + 1], data[i + 2], data[i + 3]
            ver_bits, layer = (b1 >> 3) & 3, (b1 >> 1) & 3
            if ver_bits == 1 or layer != 1:            # reserved version / not layer III
                continue
            ver = {3: 1, 2: 2, 0: 25}[ver_bits]
            kbps = _MP3_BITRATES[1 if ver == 1 else 2][(b2 >> 4) & 15]
            rate_i = (b2 >> 2) & 3
            if not kbps or rate_i == 3:
                continue
            rate = _MP3_RATES[ver][rate_i]
            spf = 1152 if ver == 1 else 576
            mono = ((b3 >> 6) & 3) == 3
            off = i + 4 + (17 if ver == 1 and mono else 32 if ver == 1 else 9 if mono else 17)
            tag = data[off:off + 4]
            if tag in (b"Xing", b"Info") and len(data) >= off + 12 and data[off + 7] & 1:
                frames = int.from_bytes(data[off + 8:off + 12], "big")
                return round(frames * spf * 1000 / rate)
            return round((size - i) * 8 / (kbps * 1000) * 1000)
    return None


def audio_length_ms(path: str) -> Optional[int]:
    """Length in ms of a .wav or .mp3 file, or None when it cannot be told
    (another format, a missing file).  Reads only the start of the file."""
    import wave
    try:
        if not os.path.isfile(path):
            return None
        ext = os.path.splitext(path)[1].lower()
        if ext == ".wav":
            with wave.open(path, "rb") as w:
                return round(w.getnframes() * 1000 / w.getframerate())
        if ext == ".mp3":
            size = os.path.getsize(path)
            with open(path, "rb") as fh:
                return _mp3_ms(fh.read(16384), size)
    except (OSError, EOFError, wave.Error, ValueError):
        return None
    return None
