"""
core/qxw_io.py
==============
The single place where QLC+ workspaces (.qxw) are read and written.

Rules (WORKPLAN §2):

* Every serialised workspace starts with the XML declaration **and**
  ``<!DOCTYPE Workspace>`` — QLC+ refuses files without the DOCTYPE.
* ``ElementTree.write()`` is never used for workspaces.
* Writes never touch the source file: callers pass the paths to protect,
  and new files get a versioned name via :func:`next_version_path`.
* Output is deterministic: the same tree always gives the same bytes.
"""

from __future__ import annotations

import copy
import os
import re
import tempfile
import xml.etree.ElementTree as ET  # nosec B405
from typing import Iterable

QLC_NS_URI = "http://www.qlcplus.org/Workspace"
ET.register_namespace("", QLC_NS_URI)

XML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n'
MAX_QXW_BYTES = 50 * 1024 * 1024   # 50 MB cap (billion-laughs mitigation)

_VERSION_RE = re.compile(r"^(?P<stem>.*)_v(?P<num>\d+)$", re.IGNORECASE)


class OverwriteError(ValueError):
    """Raised when a write would replace a protected (source) file."""


# ── Reading ──────────────────────────────────────────────────────────────────

def load_qxw(path: str, strip_namespace: bool = False) -> ET.ElementTree:
    """Parse a .qxw file (size-capped) and return its ElementTree.

    With ``strip_namespace=True`` tags are plain (``"Engine"``) instead of
    ``"{http://www.qlcplus.org/Workspace}Engine"``.
    """
    size = os.path.getsize(path)
    if size > MAX_QXW_BYTES:
        raise ValueError(
            f"File too large ({size // (1024 * 1024)} MB). "
            f"Max allowed: {MAX_QXW_BYTES // (1024 * 1024)} MB."
        )
    tree = ET.parse(path)  # nosec B314
    if strip_namespace:
        strip_ns(tree.getroot())
    return tree


def loads_qxw(data: bytes) -> ET.Element:
    """Parse workspace bytes and return the root element."""
    if len(data) > MAX_QXW_BYTES:
        raise ValueError("Workspace data too large.")
    return ET.fromstring(data)  # nosec B314


# ── Namespace helpers ────────────────────────────────────────────────────────
# Real QLC+ files declare xmlns="http://www.qlcplus.org/Workspace", so ET
# tags look like "{http://www.qlcplus.org/Workspace}Engine".  Modules that
# prefer plain tag names (Merger, Porter) strip the namespace on load;
# qxw_bytes() puts it back on output.

_NS_PREFIX = "{" + QLC_NS_URI + "}"


def strip_ns(root: ET.Element) -> ET.Element:
    """Remove the QLC+ namespace from every tag in place; returns *root*."""
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.startswith(_NS_PREFIX):
            el.tag = el.tag[len(_NS_PREFIX):]
    return root


def qualify_ns(root: ET.Element) -> ET.Element:
    """Put every un-namespaced tag in the QLC+ namespace in place; returns *root*."""
    for el in root.iter():
        if isinstance(el.tag, str) and not el.tag.startswith("{"):
            el.tag = _NS_PREFIX + el.tag
    return root


# ── Serialising ──────────────────────────────────────────────────────────────

def qxw_bytes(root: ET.Element) -> bytes:
    """Serialise a workspace root to canonical UTF-8 bytes (with DOCTYPE).

    A tree whose tags were stripped of the QLC+ namespace (see
    :func:`strip_ns`) is re-qualified on a copy, so the output always
    carries ``xmlns="http://www.qlcplus.org/Workspace"`` like QLC+'s own files.
    """
    if isinstance(root, ET.ElementTree):
        root = root.getroot()
    if root.tag == "Workspace":
        root = qualify_ns(copy.deepcopy(root))
    body = ET.tostring(root, encoding="unicode")
    return (XML_HEADER + body).encode("utf-8")


def _check_protected(path: str, protect: Iterable[str]) -> None:
    target = os.path.realpath(os.path.abspath(path))
    for p in protect or ():
        if p and os.path.realpath(os.path.abspath(p)) == target:
            raise OverwriteError(
                "Refusing to overwrite the source workspace — "
                "choose a different file name.")


def write_bytes(data: bytes, path: str, protect: Iterable[str] = ()) -> str:
    """Atomically write *data* to *path*, refusing any path in *protect*.

    The file is written to a temporary sibling and then renamed, so a crash
    never leaves a half-written workspace.  Returns *path*.
    """
    _check_protected(path, protect)
    folder = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".swk-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def write_qxw(root: ET.Element, path: str, protect: Iterable[str] = ()) -> str:
    """Serialise *root* with :func:`qxw_bytes` and write it to *path*.

    *protect* lists paths that must never be overwritten (normally the
    source workspace).  Returns *path*.
    """
    return write_bytes(qxw_bytes(root), path, protect)


# ── Versioned file names ─────────────────────────────────────────────────────

def next_version_name(filename: str) -> str:
    """``Show_v41.qxw`` → ``Show_v42.qxw``; anything else → ``<stem>_v2.qxw``.

    Zero padding is kept (``_v09`` → ``_v10``).  Works on bare names and
    paths; the extension defaults to ``.qxw``.
    """
    folder, base = os.path.split(filename)
    stem, ext = os.path.splitext(base)
    ext = ext or ".qxw"
    m = _VERSION_RE.match(stem)
    if m:
        num = m.group("num")
        stem = f"{m.group('stem')}_v{str(int(num) + 1).zfill(len(num))}"
    else:
        stem = f"{stem}_v2"
    return os.path.join(folder, stem + ext)


def next_version_path(path: str) -> str:
    """Next free versioned path next to *path* (skips names already on disk)."""
    candidate = next_version_name(path)
    while os.path.exists(candidate):
        candidate = next_version_name(candidate)
    return candidate


def suffixed_name(filename: str, suffix: str) -> str:
    """``Show_v41.qxw`` + ``doctor`` → ``Show_v41_doctor.qxw``."""
    folder, base = os.path.split(filename)
    stem, ext = os.path.splitext(base)
    return os.path.join(folder, f"{stem}_{suffix}{ext or '.qxw'}")
