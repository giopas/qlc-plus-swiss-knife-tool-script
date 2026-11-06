"""core/qlc531.py — what QLC+ 5.3.1 changed in the files Swiss Knife reads (3.13.0).

Read in the QLC+ source at tag ``QLC+_5.3.1`` (5 November 2026).

**Virtual Console pages have no ID in the file.**  QLC+ 5.3.1 gives a page an
ID while it runs, from the top of the ID range, and no longer saves it
(``VCWidget::saveXMLCommon``); an ID read from a file is ignored
(``VCPage::setID``).  Swiss Knife finds pages by ``ID`` everywhere, so
:func:`give_pages_ids` gives each page without one the next free ID when a show
is read (``core/xml_safe.py`` calls it for every workspace).  The same file
always gets the same IDs.  A page ID in a file is harmless in 5.3.1, and
QLC+ 5.2.2 and 5.3.0 expect one.

**Cross-universe fixtures have a mode** (``Fixture::CrossUniverseMode``).
``<CrossUniverse>`` was ``True``; 5.3.1 writes ``Pixel`` (whole heads only: a
head that would not fit starts the next universe) or ``Fill`` (the channels
run straight on).  5.3.1 reads an old ``True`` as ``Pixel``; 5.3.0 and 5.2.2
read any value as straight on.  :func:`addresses` places a fixture's channels
the way 5.3.1 does (``Fixture::channelAddress``,
``Fixture::crossUniversePixelSize``).  A fixture without the flag that does not
fit its universe is moved to address 1 by every QLC+ when the show loads
(``Fixture::loadXML``).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 — elements only, parsing is in xml_safe
from typing import List, Optional, Sequence, Tuple

LATEST = (5, 3, 1)
LATEST_TEXT = "5.3.1"

UNIVERSE = 512
INVALID_ID = 4294967295          # QLC+'s "no ID" (a button with no function)
PAGE_TAGS = ("Frame", "SoloFrame")

NONE, PIXEL, FILL, LEGACY = "none", "pixel", "fill", "legacy"


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


# ── Virtual Console pages ────────────────────────────────────────────────────

def _vc(root: ET.Element) -> Optional[ET.Element]:
    for c in root:
        if _local(c.tag) == "VirtualConsole":
            return c
    return None


def _is_widget(el: ET.Element) -> bool:
    """A Virtual Console widget has its own ``<WindowState>``; a reference
    such as ``<Function ID="…"/>`` inside a button does not."""
    return any(_local(c.tag) == "WindowState" for c in el)


def pages(root: ET.Element) -> List[ET.Element]:
    """The Virtual Console pages: the frames right under ``<VirtualConsole>``."""
    vc = _vc(root)
    return [] if vc is None else [c for c in vc if _local(c.tag) in PAGE_TAGS]


def give_pages_ids(root: ET.Element) -> int:
    """Give every page without an ``ID`` the next free one (above every
    widget ID, never QLC+'s "no ID" 4294967295), in page order.  Returns how many were given.
    Anything that is not a QLC+ workspace is left alone."""
    if root is None or _local(root.tag) != "Workspace":
        return 0
    missing = [p for p in pages(root) if not (p.get("ID") or "").strip()]
    if not missing:
        return 0
    used = [int(v) for el in _vc(root).iter() if _is_widget(el)
            for v in [(el.get("ID") or "").strip()]
            if v.isdigit() and int(v) < INVALID_ID]
    nid = max(used + [-1]) + 1
    for p in missing:
        p.set("ID", str(nid))
        nid += 1
    return len(missing)


# ── cross-universe fixtures ──────────────────────────────────────────────────

def cross_mode(fixture: ET.Element) -> str:
    """``none``, ``pixel``, ``fill`` or ``legacy`` (an old ``True``, or any
    other value 5.3.1 reads as Pixel)."""
    el = next((c for c in fixture if _local(c.tag) == "CrossUniverse"), None)
    if el is None:
        return NONE
    text = (el.text or "").strip()
    if text == "Fill":
        return FILL
    if text == "Pixel":
        return PIXEL
    return LEGACY


def set_cross_mode(fixture: ET.Element, mode: str) -> None:
    """Write ``Pixel`` or ``Fill`` (or remove the flag for ``none``), right
    after ``<Universe>`` where QLC+ writes it."""
    el = next((c for c in fixture if _local(c.tag) == "CrossUniverse"), None)
    if mode == NONE:
        if el is not None:
            fixture.remove(el)
        return
    if el is None:
        uni = next((c for c in fixture if _local(c.tag) == "Universe"), None)
        tag = fixture.tag[: -len(_local(fixture.tag))] + "CrossUniverse"
        el = ET.Element(tag)
        kids = list(fixture)
        fixture.insert(kids.index(uni) + 1 if uni is not None else len(kids), el)
    el.text = "Pixel" if mode == PIXEL else "Fill"


def pixel_size(channels: int, heads: Optional[Sequence[Sequence[int]]]) -> int:
    """``Fixture::crossUniversePixelSize``: the first head's channel count,
    when every head is that size and they cover all the channels; else 1."""
    if not heads:
        return 1
    size = len(heads[0])
    if size <= 0 or size > UNIVERSE:
        return 1
    if size * len(heads) != channels:
        return 1
    return size


def addresses(universe: int, address: int, channels: int, mode: str,
              heads: Optional[Sequence[Sequence[int]]] = None,
              version: Tuple[int, ...] = LATEST) -> List[Tuple[int, int]]:
    """``(universe, channel)`` of each channel of a fixture, both from 0, as
    the given QLC+ version patches it.  *address* is from 0 as in the file.
    A fixture without the flag that does not fit is moved to address 0, as
    QLC+ does when it loads the show."""
    channels = max(int(channels or 0), 0)
    if mode == LEGACY:
        mode = PIXEL if tuple(version) >= LATEST else FILL
    if mode == PIXEL and tuple(version) < LATEST:
        mode = FILL                                   # older QLC+: straight on
    if mode == NONE:
        if address > UNIVERSE - 1 or address + channels - 1 > UNIVERSE - 1:
            address = 0
        return [(universe, address + c) for c in range(channels)]
    base = universe * UNIVERSE + address
    if mode == FILL:
        return [divmod(base + c, UNIVERSE) for c in range(channels)]
    size = pixel_size(channels, heads)
    first = (UNIVERSE - address) // size
    per = UNIVERSE // size
    out = []
    for c in range(channels):
        pixel = c // size
        if pixel < first:
            out.append(divmod(base + c, UNIVERSE))
            continue
        pixel -= first
        uni = universe + 1 + pixel // per
        out.append((uni, (pixel % per) * size + c % size))
    return out


def does_not_fit(address: int, channels: int) -> bool:
    """A fixture without the cross-universe flag that runs past channel 512."""
    return address > UNIVERSE - 1 or address + max(channels, 1) - 1 > UNIVERSE - 1
