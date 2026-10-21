"""
core/cabling/fixtures.py — fixture models for your kit
======================================================

*My kit* lists the fixtures you own as models (manufacturer and model, how
many, the DMX connector, how they terminate).  They come from:

* the QLC+ fixture library installed on this computer (searched here,
  offline: :func:`search`);
* the QLC+ library on GitHub (through Quick Start's ``/gh/…`` routes, when
  you choose to go on the internet), parsed by :func:`item_from_qxf_bytes`;
* the show in progress (the screen builds those from the rig);
* by hand, or from Claude (the ``cabling`` tool's *fixture* action).

A model's DMX connector and power come from its definition
(``Physical/Technical``); nothing found means 3-pin, marked as a guess.
"""

from __future__ import annotations

import os
import re
import tempfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from core.cabling import kit as kit_mod
from core import xml_safe

_names: Dict[Tuple[str, ...], List[Tuple[str, str, str]]] = {}


def _library() -> List[Tuple[str, str, str]]:
    """``[(manufacturer, model, path)]`` of the installed QLC+ library, as
    written (not lower-cased).  Cached per set of folders."""
    from core.quick_start import qlc_library
    dirs = qlc_library.library_dirs()
    key = tuple(dirs)
    if key in _names:
        return _names[key]
    out: List[Tuple[str, str, str]] = []
    seen = set()
    for d in dirs:
        fmap = os.path.join(d, "FixturesMap.xml")
        if os.path.isfile(fmap):
            try:
                for m in xml_safe.parse(fmap).getroot():
                    for f in m:
                        mf, md = m.get("n", ""), f.get("m", "")
                        if (mf.lower(), md.lower()) not in seen:
                            seen.add((mf.lower(), md.lower()))
                            out.append((mf, md, os.path.join(d, mf, f.get("n", "") + ".qxf")))
                continue
            except ET.ParseError:
                pass
        for dirpath, _dirs, files in os.walk(d):
            for fn in files:
                if fn.lower().endswith(".qxf"):
                    p = os.path.join(dirpath, fn)
                    mm = qlc_library._read_mfr_model(p)
                    if mm and (mm[0].lower(), mm[1].lower()) not in seen:
                        seen.add((mm[0].lower(), mm[1].lower()))
                        out.append((mm[0], mm[1], p))
    out.sort(key=lambda t: (t[0].lower(), t[1].lower()))
    _names[key] = out
    return out


def has_library() -> bool:
    from core.quick_start import qlc_library
    return bool(qlc_library.library_dirs())


def search(q: str, limit: int = 40) -> List[dict]:
    """Models of the installed QLC+ library whose manufacturer and model hold
    every word of *q*: ``[{manufacturer, model}]``."""
    words = [w for w in re.split(r"\s+", (q or "").lower()) if w]
    if not words:
        return []
    out = []
    for mf, md, _p in _library():
        hay = f"{mf} {md}".lower()
        if all(w in hay for w in words):
            out.append({"manufacturer": mf, "model": md})
            if len(out) >= limit:
                break
    return out


def _from_parsed(d: dict, manufacturer: str, model: str, source: str) -> dict:
    phys = d.get("physical") or {}
    conns, known = kit_mod.connectors_from_qxf(phys.get("dmx_connector", ""))
    it = kit_mod.fixture_item(d.get("manufacturer") or manufacturer, d.get("model") or model, conns=conns,
                              sources={"connector": source if known else "guess"})
    if phys.get("power"):
        it["power"] = f"{phys['power']:g} W"
    return kit_mod.clean_item(it)


def item_from_library(manufacturer: str, model: str) -> dict:
    """A kit item for a model of the installed library (or 3-pin, a guess,
    when it is not there)."""
    from core.qxf_parser import parse_qxf
    path = next((p for mf, md, p in _library()
                 if mf.lower() == manufacturer.lower() and md.lower() == model.lower()), None)
    if path and os.path.isfile(path):
        try:
            return _from_parsed(parse_qxf(path), manufacturer, model, "QLC+ definition")
        except Exception:                          # a broken file: fall back to a guess
            pass
    return kit_mod.clean_item(kit_mod.fixture_item(manufacturer, model, sources={"connector": "guess"}))


def item_from_qxf_bytes(raw: bytes, manufacturer: str = "", model: str = "") -> dict:
    """A kit item from a .qxf file's content (from GitHub, or a file you chose)."""
    from core.qxf_parser import parse_qxf
    fd, path = tempfile.mkstemp(suffix=".qxf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
        return _from_parsed(parse_qxf(path), manufacturer, model, "QLC+ definition")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
