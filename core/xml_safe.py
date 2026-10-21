"""core/xml_safe.py — one way to read XML files that come from outside (3.9.7).

Shows (``.qxw``), fixture definitions (``.qxf``) and input profiles (``.qxi``) are plain XML
without entities: QLC+ writes a bare document type line and nothing else.  A file that declares
an entity is either broken or an attack (a "billion laughs" file expands a few hundred bytes into
gigabytes of memory), so it is refused before it is parsed, whatever the XML library's own
protection is on the computer.  The size is capped as well.
"""
import os
import xml.etree.ElementTree as ET

MAX_BYTES = 64 * 1024 * 1024        # a show; definitions and profiles are far smaller (see max_bytes)
MAX_DEFINITION_BYTES = 8 * 1024 * 1024


class UnsafeXML(ET.ParseError, ValueError):
    """The file declares entities or is too large."""


def _check(data: bytes, max_bytes: int) -> None:
    if len(data) > max_bytes:
        raise UnsafeXML(f"File too large ({len(data) // (1024 * 1024)} MB). Max allowed: {max_bytes // (1024 * 1024)} MB.")
    head = data[:65536].lower()                     # entities are declared in the prolog
    if b"<!entity" in head:
        raise UnsafeXML("This XML file declares entities, which QLC+ files never do. Not opened.")


def parse(path: str, max_bytes: int = MAX_BYTES) -> ET.ElementTree:
    """Like ``ET.parse(path)``, after the size and entity checks."""
    size = os.path.getsize(path)
    if size > max_bytes:
        raise UnsafeXML(f"File too large ({size // (1024 * 1024)} MB). Max allowed: {max_bytes // (1024 * 1024)} MB.")
    with open(path, "rb") as fh:
        data = fh.read()
    _check(data, max_bytes)
    return ET.ElementTree(ET.fromstring(data))


def fromstring(data, max_bytes: int = MAX_BYTES) -> ET.Element:
    """Like ``ET.fromstring(data)``, after the size and entity checks."""
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    _check(raw, max_bytes)
    return ET.fromstring(raw)
