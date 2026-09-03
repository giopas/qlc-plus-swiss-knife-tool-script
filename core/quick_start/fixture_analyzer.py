"""
core/quick_start/fixture_analyzer.py
=====================================
Scan QXF fixture definitions for capability flags (RGB, pan/tilt,
strobe, dimmer, color wheel) and group fixtures by type.

Works with the in-memory ``_qxf_defs`` dict populated by
``core.fixture.load_qxf`` — no additional file I/O.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional


# ─── channel-name patterns ────────────────────────────────────────────────────

_RE_PAN      = re.compile(r'\bPan\b',              re.IGNORECASE)
_RE_TILT     = re.compile(r'\bTilt\b',             re.IGNORECASE)
_RE_RED      = re.compile(r'\bRed\b',              re.IGNORECASE)
_RE_GREEN    = re.compile(r'\bGreen\b',            re.IGNORECASE)
_RE_BLUE     = re.compile(r'\bBlue\b',             re.IGNORECASE)
_RE_WHITE    = re.compile(r'\bWhite\b',            re.IGNORECASE)
_RE_AMBER    = re.compile(r'\bAmber\b',            re.IGNORECASE)
_RE_UV       = re.compile(r'\bUV\b',               re.IGNORECASE)
_RE_COLOR    = re.compile(r'\bColou?r\b',          re.IGNORECASE)
_RE_STROBE   = re.compile(r'\b(?:Strobe|Flash)\b', re.IGNORECASE)
_RE_DIMMER   = re.compile(r'\b(?:Dimmer|Intensity|Master)\b', re.IGNORECASE)
_RE_GOBO     = re.compile(r'\bGobo\b',             re.IGNORECASE)
_RE_PRISM    = re.compile(r'\bPrism\b',            re.IGNORECASE)
_RE_FOCUS    = re.compile(r'\bFocus\b',            re.IGNORECASE)
_RE_ZOOM     = re.compile(r'\bZoom\b',             re.IGNORECASE)
_RE_SHUTTER  = re.compile(r'\bShutter\b',          re.IGNORECASE)


def _find(channels: List[str], pattern: re.Pattern) -> List[str]:
    """Return channel names matching *pattern*."""
    return [ch for ch in channels if pattern.search(ch)]


# ═════════════════════════════════════════════════════════════════════════════
# Single-fixture capability analysis
# ═════════════════════════════════════════════════════════════════════════════

class FixtureCapabilities:
    """Analyse a single fixture type's channel list."""

    def __init__(self, channels: List[str]):
        self.channels = list(channels)

    # ── boolean probes ────────────────────────────────────────────────────

    def has_pan_tilt(self) -> bool:
        return bool(_find(self.channels, _RE_PAN) and
                     _find(self.channels, _RE_TILT))

    def has_rgb(self) -> bool:
        return bool(_find(self.channels, _RE_RED) and
                     _find(self.channels, _RE_GREEN) and
                     _find(self.channels, _RE_BLUE))

    def has_color_wheel(self) -> bool:
        return bool(_find(self.channels, _RE_COLOR))

    def has_strobe(self) -> bool:
        return bool(_find(self.channels, _RE_STROBE))

    def has_dimmer(self) -> bool:
        return bool(_find(self.channels, _RE_DIMMER))

    def has_gobo(self) -> bool:
        return bool(_find(self.channels, _RE_GOBO))

    def has_white(self) -> bool:
        return bool(_find(self.channels, _RE_WHITE))

    def has_amber(self) -> bool:
        return bool(_find(self.channels, _RE_AMBER))

    def has_uv(self) -> bool:
        return bool(_find(self.channels, _RE_UV))

    # ── structured breakdown ──────────────────────────────────────────────

    def channels_by_category(self) -> Dict[str, List[str]]:
        """
        Return channel names grouped by function category.

        Categories: dimmer, pan_tilt, rgb, color_wheel, strobe, gobo, other
        """
        cats: Dict[str, List[str]] = {
            "dimmer":      [],
            "pan_tilt":    [],
            "rgb":         [],
            "color_wheel": [],
            "strobe":      [],
            "gobo":        [],
            "other":       [],
        }
        for ch in self.channels:
            if _RE_DIMMER.search(ch):
                cats["dimmer"].append(ch)
            elif _RE_PAN.search(ch) or _RE_TILT.search(ch):
                cats["pan_tilt"].append(ch)
            elif (_RE_RED.search(ch) or _RE_GREEN.search(ch) or
                  _RE_BLUE.search(ch)):
                cats["rgb"].append(ch)
            elif _RE_COLOR.search(ch):
                cats["color_wheel"].append(ch)
            elif _RE_STROBE.search(ch) or _RE_SHUTTER.search(ch):
                cats["strobe"].append(ch)
            elif _RE_GOBO.search(ch):
                cats["gobo"].append(ch)
            else:
                cats["other"].append(ch)
        return cats

    def dimmer_channel_name(self) -> Optional[str]:
        """Return the first dimmer/intensity channel name, or None."""
        hits = _find(self.channels, _RE_DIMMER)
        return hits[0] if hits else None

    def rgb_channel_names(self) -> Optional[Dict[str, str]]:
        """Return {'red': name, 'green': name, 'blue': name} or None."""
        r = _find(self.channels, _RE_RED)
        g = _find(self.channels, _RE_GREEN)
        b = _find(self.channels, _RE_BLUE)
        if r and g and b:
            return {"red": r[0], "green": g[0], "blue": b[0]}
        return None

    def strobe_channel_name(self) -> Optional[str]:
        hits = _find(self.channels, _RE_STROBE)
        return hits[0] if hits else None

    def summary(self) -> Dict[str, bool]:
        """Flat dict of every boolean probe — handy for serialisation."""
        return {
            "has_pan_tilt":    self.has_pan_tilt(),
            "has_rgb":         self.has_rgb(),
            "has_color_wheel": self.has_color_wheel(),
            "has_strobe":      self.has_strobe(),
            "has_dimmer":      self.has_dimmer(),
            "has_gobo":        self.has_gobo(),
            "has_white":       self.has_white(),
            "has_amber":       self.has_amber(),
            "has_uv":          self.has_uv(),
            "channel_count":   len(self.channels),
        }


# ═════════════════════════════════════════════════════════════════════════════
# Whole-rig analysis
# ═════════════════════════════════════════════════════════════════════════════

class RigCapabilityAnalysis:
    """
    Analyse an entire rig (list of fixture entries from ``core.fixture``).

    Each entry is expected to carry at minimum:
        key (str)          — "Manufacturer::Model"
        ch_count (int)
    plus the ``_qxf_defs`` dict supplies the channel names.

    Parameters
    ----------
    rig : list[dict]
        The rig entries (from ``core.fixture.get_rig()``).
    qxf_defs : dict
        The QXF definitions (from ``core.fixture.get_qxf_defs()``).
    """

    def __init__(self, rig: list, qxf_defs: dict):
        self.rig = rig
        self.qxf_defs = qxf_defs
        self.fixture_caps: Dict[int, FixtureCapabilities] = {}

        for idx, entry in enumerate(rig):
            key = entry.get("key", "")
            defn = qxf_defs.get(key, {})
            channels = defn.get("channels", [])
            self.fixture_caps[idx] = FixtureCapabilities(channels)

    def group_by_type(self) -> Dict[str, List[int]]:
        """
        Categorise every rig fixture into one of:
          moving_heads, color_fixtures, dimmers_only, other

        Returns {group_name: [rig_indices]}.
        """
        groups: Dict[str, List[int]] = {
            "moving_heads":   [],
            "color_fixtures": [],
            "dimmers_only":   [],
            "other":          [],
        }

        for idx, caps in self.fixture_caps.items():
            if caps.has_pan_tilt():
                groups["moving_heads"].append(idx)
            elif caps.has_rgb() or caps.has_color_wheel():
                groups["color_fixtures"].append(idx)
            elif caps.has_dimmer():
                groups["dimmers_only"].append(idx)
            else:
                groups["other"].append(idx)

        return groups

    def has_any_rgb(self) -> bool:
        return any(c.has_rgb() for c in self.fixture_caps.values())

    def has_any_strobe(self) -> bool:
        return any(c.has_strobe() for c in self.fixture_caps.values())

    def has_any_dimmer(self) -> bool:
        return any(c.has_dimmer() for c in self.fixture_caps.values())

    def summary(self) -> dict:
        """Return JSON-friendly summary of the whole rig."""
        groups = self.group_by_type()
        return {
            "total_fixtures":  len(self.rig),
            "moving_heads":    len(groups["moving_heads"]),
            "color_fixtures":  len(groups["color_fixtures"]),
            "dimmers_only":    len(groups["dimmers_only"]),
            "other":           len(groups["other"]),
            "has_rgb":         self.has_any_rgb(),
            "has_strobe":      self.has_any_strobe(),
            "has_dimmer":      self.has_any_dimmer(),
            "total_channels":  sum(e.get("ch_count", 0) for e in self.rig),
        }
