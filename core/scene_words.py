"""
core/scene_words.py
===================
Say in plain words what a Scene looks like, for the Dictionary (v3.0.1).

A scene is a list of channel values per fixture.  With the fixture's
definition (.qxf) the values are decoded by capability
(``capability_map.decode``) into level, colour and shutter, and each fixture
gets a colour word: "red", "warm white", "dim blue", "red strobe", "off".
Fixtures with the same word are grouped:

    red on Drums Floor and Logo / Banner, blue on Front Left (Band) and
    Front Right (Band), warm white on the singers

Deterministic: the same scene always gives the same sentence.  A fixture with
no known definition is left out; a scene with none at all gives "".
"""

from __future__ import annotations

import colorsys
import re
from typing import Dict, List, Optional, Tuple

from core import capability_map as cm

RGB = Tuple[float, float, float]

# hue (degrees) upper bound → word, for saturated colours
_HUES: List[Tuple[float, str]] = [
    (12, "red"), (38, "orange"), (52, "amber"), (68, "yellow"), (95, "lime"),
    (150, "green"), (175, "teal"), (200, "cyan"), (245, "blue"), (275, "violet"),
    (300, "purple"), (330, "magenta"), (348, "pink"), (361, "red"),
]


def colour_word(rgb: Optional[RGB], level: float = 1.0) -> str:
    """One or two words for an emitted colour (components 0..1, *level* 0..1)."""
    if rgb is None:
        rgb = (1.0, 1.0, 1.0)
    lit = max(rgb) * level
    if lit < 0.04:
        return "off"
    h, s, _v = colorsys.rgb_to_hsv(*rgb)
    hue = h * 360.0
    if s < 0.22:
        word = "white"
    elif s < 0.62 and 15 <= hue <= 60:
        word = "warm white"
    elif s < 0.5 and 180 <= hue <= 250:
        word = "cool white"
    else:
        word = next(w for top, w in _HUES if hue < top)
    return ("dim " + word) if lit < 0.4 else word


def _short(name: str) -> str:
    """'FLB: Front Left (Band)' → 'Front Left (Band)'."""
    return re.sub(r"^[A-Z0-9]{1,5}:\s*", "", (name or "").strip()) or name


def _join(items: List[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def fixture_words(scene, info: Dict[str, dict]) -> List[Tuple[str, str]]:
    """[(fixture name, colour word)] for the fixtures of *scene* with a known
    definition, in the order the scene lists them."""
    out = []
    for fv in scene.iter("FixtureVal"):
        fx = info.get(fv.get("ID", ""))
        if not fx or fx.get("def") is None:
            continue
        try:
            st = cm.decode(fx["def"], fx["mode"], cm._pairs(fv.text or ""))
        except Exception:  # noqa: BLE001 — a description is never worth an error
            continue
        lvl = 1.0 if st.level is None else st.level
        if st.shutter == "closed":
            lvl = 0.0
        word = colour_word(st.colour, lvl)
        if st.shutter == "strobe" and word != "off":
            word += " strobe"
        out.append((_short(fx.get("name", "")), word))
    return out


def dominant(scene, info: Dict[str, dict]) -> str:
    """The colour most of the lit fixtures show ("" when unknown, "off" when dark)."""
    words = [w for _n, w in fixture_words(scene, info)]
    if not words:
        return ""
    lit = [w for w in words if w != "off"]
    if not lit:
        return "off"
    return max(dict.fromkeys(lit), key=lit.count)


def describe(scene, info: Dict[str, dict], max_groups: int = 4) -> str:
    """'red on Drums Floor and Logo / Banner, blue on …' ("" when unknown)."""
    pairs = fixture_words(scene, info)
    if not pairs:
        return ""
    groups: Dict[str, List[str]] = {}
    for name, word in pairs:
        groups.setdefault(word, []).append(name)
    if list(groups) == ["off"]:
        return "blackout (all off)"
    if len(groups) == 1:
        word = next(iter(groups))
        return f"all {len(pairs)} fixtures {word}" if len(pairs) > 1 else f"{word} on {pairs[0][0]}"
    lit = [(w, ns) for w, ns in groups.items() if w != "off"]
    lit.sort(key=lambda x: -len(x[1]))
    if len(lit) > max_groups:
        lit = lit[:max_groups]
    # the biggest group is said last as "the rest" (shorter, and the eye
    # reads the exceptions first) when it is a real majority and nothing is off
    rest = lit[0] if (len(lit) >= 2 and len(lit[0][1]) >= 3 and "off" not in groups) else None
    parts = [f"{w} on {_join(ns)}" for w, ns in lit if (w, ns) != rest]
    if rest:
        parts.append(f"{rest[0]} on the rest")
    text = ", ".join(parts)
    if "off" in groups:
        text += ", rest off"
    return text


def chase_words(scenes, info: Dict[str, dict]) -> Tuple[List[str], str]:
    """(colours, how) for the steps of a chase: *how* is "colours" (the
    colours change), "moves" (one colour travelling across the fixtures) or
    "level" (the same colours throughout, only the brightness changes)."""
    per_step = [fixture_words(sc, info) for sc in scenes]
    cols = palette(scenes, info)
    if len(per_step) < 2:
        return cols, "colours"
    if all(st == per_step[0] for st in per_step[1:]):
        return cols, "level"
    bags = [sorted(w for _n, w in st) for st in per_step]
    if all(b == bags[0] for b in bags[1:]):
        return cols, "moves"                       # the same colours, on other fixtures
    base = [[(n, w[4:] if w.startswith("dim ") else w) for n, w in st] for st in per_step]
    if all(b == base[0] for b in base[1:]):
        return cols, "level"                       # the same colours, brighter and dimmer
    return cols, "colours"


def palette(scenes, info: Dict[str, dict]) -> List[str]:
    """Every colour word the *scenes* use, in order of first appearance
    (a "dim" shade is left out when the full colour is there too)."""
    per_step = [fixture_words(sc, info) for sc in scenes]
    # a fixture that shows the same colour in every step is background (the
    # singers' warm white under a chase): it does not say what the chase does
    steady = set()
    if len(per_step) > 1:
        first = dict(per_step[0])
        steady = {n for n, w in first.items() if all(dict(st).get(n) == w for st in per_step[1:])}
        if all(n in steady for st in per_step for n, _w in st):
            steady = set()                         # nothing moves: keep every colour
    seen: List[str] = []
    for st in per_step:
        for n, w in st:
            if w != "off" and n not in steady and w not in seen:
                seen.append(w)
    return [w for w in seen if not (w.startswith("dim ") and w[4:] in seen)]
