"""
core/quick_start/qlc_library.py
===============================
Does the installed QLC+ already know a fixture?

QLC+ resolves a workspace fixture from its fixture library (the stock
definitions shipped with the app + the user fixtures folder).  Only when a
definition is missing there does it look next to the workspace for
``<Manufacturer>-<Model>.qxf`` (``Fixture::loader``).  Quick Start therefore
writes a .qxf next to an exported workspace **only** for fixtures the
installed QLC+ doesn't have.

Library folders (from QLC+'s ``variables.cmake``):

=========  ==============================================  =========================================
OS         stock definitions                               user definitions
=========  ==============================================  =========================================
macOS      /Applications/QLC+.app/Contents/Resources/Fixtures  ~/Library/Application Support/QLC+/Fixtures
Linux      /usr/share/qlcplus/fixtures (also /usr/local)   ~/.qlcplus/fixtures
Windows    C:\\qlcplus\\Fixtures                             %USERPROFILE%\\QLC+\\Fixtures
=========  ==============================================  =========================================

``QLCPLUS_FIXTURES`` (os.pathsep-separated) overrides the list — handy for
tests and unusual installs.
"""

from __future__ import annotations

import os
import platform
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

_QXF_NS = "{http://www.qlcplus.org/FixtureDefinition}"
_cache: Dict[Tuple[str, ...], Dict[Tuple[str, str], str]] = {}


def library_dirs() -> List[str]:
    env = os.environ.get("QLCPLUS_FIXTURES")
    if env is not None:
        return [d for d in env.split(os.pathsep) if d and os.path.isdir(d)]
    home = os.path.expanduser("~")
    system = platform.system()
    if system == "Darwin":
        cands = ["/Applications/QLC+.app/Contents/Resources/Fixtures",
                 os.path.join(home, "Applications/QLC+.app/Contents/Resources/Fixtures"),
                 os.path.join(home, "Library/Application Support/QLC+/Fixtures")]
    elif system == "Windows":
        drive = os.environ.get("SystemDrive", "C:")
        cands = [os.path.join(drive + os.sep, "qlcplus", "Fixtures"),
                 os.path.join(drive + os.sep, "QLC+", "Fixtures"),
                 os.path.join(home, "QLC+", "Fixtures")]
    else:
        cands = ["/usr/share/qlcplus/fixtures", "/usr/local/share/qlcplus/fixtures",
                 os.path.join(home, ".qlcplus/fixtures"), os.path.join(home, ".qlcplus/Fixtures")]
    return [d for d in cands if os.path.isdir(d)]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _index(dirs: List[str]) -> Dict[Tuple[str, str], str]:
    """{(manufacturer, model) lower-cased: path to .qxf}."""
    key = tuple(dirs)
    if key in _cache:
        return _cache[key]
    idx: Dict[Tuple[str, str], str] = {}
    for d in dirs:
        fmap = os.path.join(d, "FixturesMap.xml")
        if os.path.isfile(fmap):            # stock library: fast path
            try:
                root = ET.parse(fmap).getroot()
                for m in root:
                    for f in m:
                        path = os.path.join(d, m.get("n", ""), f.get("n", "") + ".qxf")
                        idx.setdefault((_norm(m.get("n")), _norm(f.get("m"))), path)
                continue
            except ET.ParseError:
                pass
        for dirpath, _dirs, files in os.walk(d):
            for fn in files:
                if fn.lower().endswith(".qxf"):
                    path = os.path.join(dirpath, fn)
                    mm = _read_mfr_model(path)
                    if mm:
                        idx.setdefault((_norm(mm[0]), _norm(mm[1])), path)
    _cache[key] = idx
    return idx


def _read_mfr_model(path: str) -> Optional[Tuple[str, str]]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(4096)
    except OSError:
        return None
    m = re.search(r"<Manufacturer>([^<]*)</Manufacturer>", head)
    n = re.search(r"<Model>([^<]*)</Model>", head)
    return (m.group(1), n.group(1)) if m and n else None


def _modes(path: str) -> Optional[set]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    return {m.get("Name", "") for m in root.iter(f"{_QXF_NS}Mode")}


def find(manufacturer: str, model: str) -> Optional[str]:
    """Path of the installed definition for this fixture, or None."""
    return _index(library_dirs()).get((_norm(manufacturer), _norm(model)))


def check(manufacturer: str, model: str, modes: List[str]) -> Tuple[str, str]:
    """('installed' | 'missing' | 'mode-missing' | 'no-qlc', detail)."""
    dirs = library_dirs()
    if not dirs:
        return "no-qlc", "QLC+ fixture library not found on this computer"
    path = _index(dirs).get((_norm(manufacturer), _norm(model)))
    if not path:
        return "missing", "not in the installed QLC+ library"
    have = _modes(path)
    if have is not None:
        lost = [m for m in modes if m not in have]
        if lost:
            return "mode-missing", (f"the installed QLC+ definition ({path}) has no mode "
                                    + ", ".join(f"'{m}'" for m in lost))
    return "installed", path


def clear_cache() -> None:
    _cache.clear()
