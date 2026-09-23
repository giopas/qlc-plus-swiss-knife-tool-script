"""
core/quick_start/channel_model.py
=================================
Mode-aware channel lists and capability-aware "neutral" DMX values.

Two things the Quick Start generator must get right on real fixtures:

1. **Channel order is per mode.**  A QXF lists its channels once, in
   definition order, but each <Mode> picks and re-orders them.  The
   Chauvet Intimidator Spot 110 in 6-channel mode is
   Pan, Tilt, Colour, Strobe, Dimmer, Gobo — not the definition order.
   Channel indices in scenes and sliders must follow the selected mode.

2. **"Zero" is not always "neutral".**  On many moving heads DMX 0 on the
   shutter channel means *closed*: a look that forces every channel to 0
   leaves the head dark.  A neutral value is the one that means "open /
   no function / white" for that channel, taken from its capabilities.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# Capability labels that mean "this does nothing / let light through".
_NEUTRAL_LABEL = re.compile(
    r"\bopen\b|no\s*function|\bnone\b|\bnothing\b|\boff\b|\bwhite\b|"
    r"no\s*effect|no\s*rotation|\bstop\b|\bidle\b|\bdefault\b|\bn/?a\b",
    re.IGNORECASE)
_CLOSED_LABEL = re.compile(r"\bclosed?\b|blackout", re.IGNORECASE)
_NEUTRAL_PRESETS = {"ShutterOpen"}
_CLOSED_PRESETS = {"ShutterClose"}

PAN_TILT_CENTRE = 127


def mode_channels(entry: dict, defn: dict) -> List[str]:
    """Ordered channel names for the rig entry's mode.

    Falls back to the definition order when the definition has no
    per-mode data (hand-built test dicts, older callers).
    """
    by_mode = defn.get("mode_channels") or {}
    names = by_mode.get(entry.get("mode", ""))
    if names is None and len(by_mode) == 1:
        names = next(iter(by_mode.values()))
    if names is None:
        names = defn.get("channels", [])
    return list(names)


def _caps(chdef: Optional[dict]) -> List[dict]:
    return list((chdef or {}).get("capabilities") or [])


def neutral_value(name: str, chdef: Optional[dict]) -> int:
    """The DMX value that leaves this channel 'doing nothing'.

    * Pan / Tilt coarse → centre (127); fine bytes → 0.
    * A capability with preset ShutterOpen → its minimum.
    * Otherwise the lowest capability whose label reads neutral
      ("Open", "No function", "White", "Off", …) and not closed → its
      minimum.
    * Anything else → 0.
    """
    d = chdef or {}
    group = (d.get("group") or "").lower()
    if group in ("pan", "tilt"):
        return PAN_TILT_CENTRE if not d.get("byte") else 0
    caps = _caps(d)
    if not caps:
        return 0
    for c in caps:
        if c.get("preset") in _NEUTRAL_PRESETS:
            return int(c.get("min", 0))
    for c in sorted(caps, key=lambda c: int(c.get("min", 0))):
        lbl = c.get("label", "")
        if c.get("preset") in _CLOSED_PRESETS or _CLOSED_LABEL.search(lbl):
            continue
        if _NEUTRAL_LABEL.search(lbl):
            return int(c.get("min", 0))
    return 0


def closed_value(chdef: Optional[dict]) -> Optional[int]:
    """The DMX value that closes a shutter channel, or None if it has none."""
    for c in _caps(chdef):
        if c.get("preset") in _CLOSED_PRESETS or _CLOSED_LABEL.search(c.get("label", "")):
            return int(c.get("min", 0))
    return None


def neutral_map(entry: dict, defn: dict) -> Dict[int, int]:
    """{channel_index: neutral value} for every channel of the entry's mode."""
    defs = defn.get("channel_defs") or {}
    names = mode_channels(entry, defn)
    out = {i: neutral_value(n, defs.get(n)) for i, n in enumerate(names)}
    for i in range(len(names), int(entry.get("ch_count", len(names)) or 0)):
        out[i] = 0
    return out
