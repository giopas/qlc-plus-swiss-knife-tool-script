"""
core/definitions.py
===================
Fixture definitions that travel with a show (3.7.0).

A ``.qxw`` names each fixture's manufacturer, model, mode and channel count
but does not carry the definition.  QLC+ finds it in its stock library, in the
user's fixtures folder, or next to the workspace as
``<Manufacturer>-<Model>.qxf`` (``Fixture::loader``).  On another computer a
custom definition is missing and QLC+ makes a generic dimmer with the
channel count of the file.

This module says where each definition of a show was found
(:func:`describe`) and builds the *Take the show elsewhere* zip
(:func:`build_zip`): the show, every definition that is not in QLC+'s stock
library saved under the name QLC+ looks for, the side files, and a short text.
The zip is deterministic: sorted entries, fixed timestamps, no dates in the text.
"""

from __future__ import annotations

import copy
import io
import os
import re
import zipfile
from typing import Dict, Iterable, List, Optional, Tuple

from core import palettes, qxw_io
from core.quick_start import qlc_library

#: where a definition was found, in the words of the interface
LIBRARY, USER, SHOW, CHOSEN = "QLC+ library", "user folder", "show folder", "chosen folder"

_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _under(path: str, folder: str) -> bool:
    try:
        p, f = os.path.realpath(path), os.path.realpath(folder)
        return os.path.commonpath([p, f]) == f
    except ValueError:          # another drive on Windows
        return False


def source_of(path: str, show_dir: str = "", chosen_dirs: Iterable[str] = ()) -> str:
    """Where a definition file lives: *QLC+ library*, *user folder*, *show folder*,
    *chosen folder*, or ``""`` when it is none of these."""
    if not path:
        return ""
    if any(_under(path, d) for d in qlc_library.stock_dirs()):
        return LIBRARY
    if any(_under(path, d) for d in qlc_library.user_dirs()):
        return USER
    if show_dir and _under(path, show_dir):
        return SHOW
    if any(_under(path, d) for d in chosen_dirs if d):
        return CHOSEN
    return ""


def qxf_name(manufacturer: str, model: str) -> str:
    """The file name QLC+ looks for next to a workspace."""
    return re.sub(r"[\\/]", "_", f"{manufacturer}-{model}.qxf")


def describe(root, defs: Dict, show_path: str = "", chosen_dirs: Iterable[str] = ()) -> List[dict]:
    """One row per fixture model in the show, sorted by manufacturer and model.

    ``{manufacturer, model, modes, fixtures, path, source, found, travels, file}``
    *travels* is true for a definition QLC+'s stock library does not have, so it
    has to go with the show.  *defs* is a ``load_qxf_defs`` result.
    """
    if hasattr(root, "getroot"):
        root = root.getroot()
    root = qxw_io.strip_ns(copy.deepcopy(root))
    eng = root.find("Engine")
    show_dir = os.path.dirname(os.path.abspath(show_path)) if show_path else ""
    rows: Dict[Tuple[str, str], dict] = {}
    for el in (eng.findall("Fixture") if eng is not None else []):
        info = {"manufacturer": el.findtext("Manufacturer") or "", "model": el.findtext("Model") or "",
                "mode": el.findtext("Mode") or "", "channels": el.findtext("Channels") or ""}
        d = defs.get((info["manufacturer"].strip().lower(), info["model"].strip().lower()))
        if d is None and palettes.is_builtin_generic(info):
            continue                                    # QLC+'s own generic dimmer
        if not info["manufacturer"] and not info["model"]:
            continue
        key = (info["manufacturer"].strip().lower(), info["model"].strip().lower())
        row = rows.setdefault(key, {
            "manufacturer": info["manufacturer"], "model": info["model"], "modes": [], "fixtures": 0,
            "path": (d or {}).get("path", ""), "found": d is not None})
        row["fixtures"] += 1
        if info["mode"] and info["mode"] not in row["modes"]:
            row["modes"].append(info["mode"])
    out = []
    for key in sorted(rows):
        r = rows[key]
        r["modes"].sort()
        r["source"] = source_of(r["path"], show_dir, chosen_dirs) if r["found"] else ""
        r["travels"] = r["found"] and r["source"] != LIBRARY
        r["file"] = qxf_name(r["manufacturer"], r["model"])
        out.append(r)
    return out


def sidecars(show_path: str) -> List[str]:
    """The side files that belong to the show and exist on disk."""
    if not show_path:
        return []
    from core import stage_monitor
    from core.cabling import plan
    found = []
    for p in (stage_monitor.sidecar_path(show_path), plan.sidecar_path(show_path)):
        if os.path.isfile(p):
            found.append(p)
    return found


_README = """\
{show}: the show and what it needs to open on another computer
{rule}

Open {show} in QLC+. The fixture definitions listed below are saved in this
folder as <Manufacturer>-<Model>.qxf. QLC+ looks for them there when it opens a
show, so you do not have to copy anything: keep the .qxf files next to the show.

If you prefer to install them once, put the .qxf files in QLC+'s user fixtures
folder and restart QLC+:

  macOS    ~/Library/Application Support/QLC+/Fixtures
  Linux    ~/.qlcplus/fixtures
           (Raspberry Pi and other Linux computers too)
  Windows  %USERPROFILE%\\QLC+\\Fixtures

Without a definition QLC+ makes a generic dimmer with the channel count stored
in the show. Sliders, channel names and colours are then wrong.

Definitions in this zip
-----------------------
{defs}
{missing}{side}{media}"""


def _media_text(show_bytes: bytes, show_dir: str = "") -> str:
    """The sound and video files the show plays.  They are not packed (they can be
    large and are not ours to copy); the text says where each one was and whether
    it was found, so they can be copied by hand next to the show."""
    from core import media
    try:
        root = qxw_io.loads_qxw(show_bytes)
    except Exception:  # noqa: BLE001 — the zip is built even from a file we cannot read
        return ""
    files = media.media_files(root, show_dir)
    if not files:
        return ""
    label = {"found": "found", "missing": "NOT FOUND here", "url": "stream", "empty": "no file set",
             "unknown": "not checked"}
    return ("\nSound and video files (NOT in this zip)\n"
            "---------------------------------------\n"
            "The show plays these files. Copy them to the other computer and, if their\n"
            "folder is different there, point each Audio / Video function to the new place.\n"
            + "\n".join(f"  {r['source'] or '(none)'}   [{label.get(r['status'], r['status'])}; {r['name']}]"
                       for r in files) + "\n")


def _readme(show_name: str, rows: List[dict], side: List[str], media_text: str = "") -> str:
    travel = [r for r in rows if r["travels"]]
    defs = "\n".join(f"  {r['file']}   ({r['source']}; {r['fixtures']} fixture(s); mode "
                     f"{', '.join(r['modes']) or '?'})" for r in travel) or "  (none: every definition is in QLC+'s stock library)"
    miss = [r for r in rows if not r["found"]]
    missing = ""
    if miss:
        missing = ("\nNot found on the computer that made this zip, so not included\n"
                   "---------------------------------------------------------------\n"
                   + "\n".join(f"  {r['manufacturer']} {r['model']}" for r in miss)
                   + "\nGet these definitions from QLC+'s Fixture Editor or the Open Fixture Library.\n")
    sides = ""
    if side:
        sides = ("\nSide files (settings of Swiss Knife, not read by QLC+)\n"
                 "-------------------------------------------------------\n"
                 + "\n".join(f"  {os.path.basename(p)}" for p in side) + "\n")
    return _README.format(show=show_name, rule="=" * (len(show_name) + 53), defs=defs,
                          missing=missing, side=sides, media=media_text)


def build_zip(show_name: str, show_bytes: bytes, rows: List[dict], show_path: str = "") -> bytes:
    """The *Take the show elsewhere* zip, byte for byte the same for the same input."""
    side = sidecars(show_path)
    files: Dict[str, bytes] = {show_name: show_bytes}
    for r in rows:
        if r["travels"] and r["path"] and os.path.isfile(r["path"]):
            with open(r["path"], "rb") as fh:
                files.setdefault(r["file"], fh.read())
    for p in side:
        with open(p, "rb") as fh:
            files.setdefault(os.path.basename(p), fh.read())
    files["READ ME.txt"] = _readme(show_name, rows, side, _media_text(
        show_bytes, os.path.dirname(os.path.abspath(show_path)) if show_path else "")).encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, files[name])
    return buf.getvalue()


def zip_name(show_name: str) -> str:
    """``Festival_v4.qxw`` → ``Festival_v4_to_go.zip``."""
    return os.path.splitext(os.path.basename(show_name))[0] + "_to_go.zip"
