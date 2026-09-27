"""
core/capability_map.py
======================
Translate scene values between **different fixture types** by capability,
not by channel index (WORKPLAN Phase 1.5).

Porting a look from a 7-channel RGB PAR to a moving head with a colour
wheel cannot copy "channel 2 = 255": channel 2 means *Red* on one and
*Pan fine* on the other.  Instead the source values are decoded into an
abstract :class:`LookState` (dimmer, colour, pan/tilt, shutter) and that
state is encoded on the target's channels.

Rules (deterministic — same input, same output):

* **Intensity** — the source "level" is its master dimmer (1.0 when it has
  none).  Colour comes from its colour-mixing emitters (R, G, B, W, A, UV,
  C, M, Y, Lime, Indigo) or its colour wheel; a fixture with neither is
  white.  Target with dimmer + RGB: dimmer = level, RGB = colour.  Target
  RGB without dimmer: RGB = colour × level.  Target with dimmer + wheel:
  dimmer = level × brightest component, wheel = nearest colour.  Target with
  a dimmer only: dimmer = level × brightest component.
* **White emitter** on the target gets the source's white emitter (0 when
  the source has none), so RGB→RGBW stays the same colour.
* **Colour wheel** — nearest slot by colour (``Res1`` hex, else a colour
  word in the label; *Open*/*White* = white), compared on the normalised
  colour.  Wheels with no known colours are left neutral.
* **Pan / tilt** — centre-relative degrees from the QXF ``<Focus PanMax/
  TiltMax>``: 90° left of centre stays 90° left of centre on a head with a
  different range (clamped).  Fraction of range when either side has no
  range.  16-bit when the mode has fine channels.
* **Shutter** — *open* → the target's open value, *closed* → its closed
  value (or intensity 0 when it has none), *strobe* → the same relative
  speed inside the target's first strobe range, or dropped with
  ``strobe="drop"`` (then open).
* **Gobo** — the same slot number on the target's gobo wheel (*Open*
  stays open; wraps round on a smaller wheel, noted); dropped if it has none.
* **Everything else** (prism, macros, programs, speeds, zoom …) →
  the target's capability-aware neutral value (``channel_model``).

Every channel of the target mode is declared (no LTP bleed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.quick_start.channel_model import (closed_value, mode_channels,
                                            neutral_value)

RGB = Tuple[float, float, float]

# emitter role → contribution to (r, g, b)
_EMITTER_RGB: Dict[str, RGB] = {
    "Red": (1.0, 0.0, 0.0), "Green": (0.0, 1.0, 0.0), "Blue": (0.0, 0.0, 1.0),
    "White": (1.0, 1.0, 1.0), "Amber": (1.0, 0.75, 0.0), "Uv": (0.3, 0.0, 1.0),
    "UV": (0.3, 0.0, 1.0), "Cyan": (0.0, 1.0, 1.0), "Magenta": (1.0, 0.0, 1.0),
    "Yellow": (1.0, 1.0, 0.0), "Lime": (0.75, 1.0, 0.0), "Indigo": (0.3, 0.0, 0.5),
}
_MIX_ROLES = ("Red", "Green", "Blue")

# colour words found in wheel labels (first match wins; order matters:
# "light blue" before "blue", "orange" before "red" …)
_COLOUR_WORDS: List[Tuple[str, RGB]] = [
    ("open", (1, 1, 1)), ("white", (1, 1, 1)), ("light blue", (0.5, 0.8, 1)),
    ("cyan", (0, 1, 1)), ("turquoise", (0, 1, 0.8)), ("lime", (0.75, 1, 0)),
    ("orange", (1, 0.55, 0)), ("amber", (1, 0.75, 0)), ("yellow", (1, 1, 0)),
    ("magenta", (1, 0, 1)), ("pink", (1, 0.4, 0.7)), ("purple", (0.6, 0, 1)),
    ("violet", (0.6, 0, 1)), ("uv", (0.3, 0, 1)), ("red", (1, 0, 0)),
    ("green", (0, 1, 0)), ("blue", (0, 0, 1)),
]
_STROBE_PRESET = re.compile(r"^(Strobe|Pulse|Ramp)", re.IGNORECASE)
_STROBE_LABEL = re.compile(r"strob|flash|pulse", re.IGNORECASE)


@dataclass
class LookState:
    """What a fixture is doing, independent of its channel layout."""
    level: Optional[float] = None          # master dimmer 0..1 (None = no dimmer channel)
    colour: Optional[RGB] = None           # emitted colour 0..1 per component
    white: Optional[float] = None          # the source's own white emitter
    colour_source: str = "none"            # "mix" | "wheel" | "none"
    pan: Optional[float] = None            # degrees from centre (or fraction if no range)
    tilt: Optional[float] = None
    pan_is_deg: bool = False
    tilt_is_deg: bool = False
    shutter: Optional[str] = None          # "open" | "closed" | "strobe"
    strobe_speed: float = 0.0              # 0..1 inside the strobe range
    gobo: Optional[int] = None             # 0 = open, n = n-th gobo slot (None = no wheel)
    notes: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def _layout(defn: dict, mode: str) -> List[Tuple[int, str, dict]]:
    """[(index, channel name, channel def)] for *mode*."""
    names = mode_channels({"mode": mode}, defn)
    defs = defn.get("channel_defs") or {}
    return [(i, n, defs.get(n) or {"name": n, "group": "Nothing", "byte": 0,
                                    "capabilities": []})
            for i, n in enumerate(names)]


def _role(chdef: dict) -> Optional[str]:
    if (chdef.get("group") or "") != "Intensity":
        return None
    r = chdef.get("colour_role")
    return "UV" if r == "Uv" else r


def _cap_at(chdef: dict, value: int) -> Optional[dict]:
    for c in chdef.get("capabilities") or []:
        if int(c.get("min", 0)) <= value <= int(c.get("max", 255)):
            return c
    return None


def _hex(s: Optional[str]) -> Optional[RGB]:
    if not s or not s.startswith("#") or len(s) < 7:
        return None
    try:
        return tuple(int(s[i:i + 2], 16) / 255.0 for i in (1, 3, 5))  # type: ignore
    except ValueError:
        return None


def cap_colour(cap: dict) -> Optional[RGB]:
    """Colour of a colour-wheel capability (``Res1`` hex, else a colour word)."""
    c = _hex(cap.get("res1"))
    if c is not None:
        return c
    lbl = (cap.get("label") or "").lower()
    if "no function" in lbl or "macro" in lbl or "rainbow" in lbl or "rotat" in lbl:
        return None
    for word, rgb in _COLOUR_WORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", lbl):
            return tuple(float(x) for x in rgb)  # type: ignore
    return None


def _is_wheel(chdef: dict) -> bool:
    return (chdef.get("group") == "Colour"
            and any(cap_colour(c) is not None for c in chdef.get("capabilities") or []))


def _gobo_slots(chdef: dict) -> List[dict]:
    """Slots of a gobo wheel, in wheel order ([] if *chdef* isn't one):
    capabilities with preset GoboMacro, or labelled *Open* / *Gobo N*."""
    if (chdef.get("group") or "") != "Gobo":
        return []
    return [c for c in chdef.get("capabilities") or []
            if c.get("preset") == "GoboMacro"
            or re.match(r"^\s*(open|gobo\s*\d+)\b", c.get("label") or "", re.I)]


def _is_open_slot(cap: dict) -> bool:
    return bool(re.search(r"\bopen\b", cap.get("label") or "", re.I))


def _shutter_kind(cap: Optional[dict]) -> Optional[str]:
    if cap is None:
        return None
    p = cap.get("preset") or ""
    lbl = cap.get("label") or ""
    if p == "ShutterClose" or re.search(r"\bclosed?\b|blackout", lbl, re.I):
        return "closed"
    if p == "ShutterOpen" or re.search(r"\bopen\b|no function|no flash|\bon\b", lbl, re.I):
        return "open"
    if _STROBE_PRESET.match(p) or _STROBE_LABEL.search(lbl):
        return "strobe"
    return None


def _norm(c: RGB) -> RGB:
    m = max(c)
    return (0.0, 0.0, 0.0) if m <= 0 else tuple(x / m for x in c)  # type: ignore


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _dmx(x: float) -> int:
    return int(round(_clamp01(x) * 255))


def _range(defn: dict, axis: str) -> float:
    return float((defn.get("physical") or {}).get(f"{axis}_max") or 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# decode
# ─────────────────────────────────────────────────────────────────────────────

def decode(defn: dict, mode: str, values: Dict[int, int]) -> LookState:
    """Read a fixture's channel values into a :class:`LookState`."""
    st = LookState()
    lay = _layout(defn, mode)
    mix = [0.0, 0.0, 0.0]
    has_mix = False
    wheel: Optional[RGB] = None
    pos = {"pan": [None, None], "tilt": [None, None]}   # coarse, fine

    for i, name, cd in lay:
        v = int(values.get(i, 0))
        grp = cd.get("group") or ""
        role = _role(cd)
        if role == "Dimmer" and not cd.get("byte"):
            st.level = v / 255.0
        elif role in _EMITTER_RGB and not cd.get("byte"):
            has_mix = True
            for k in range(3):
                mix[k] += _EMITTER_RGB[role][k] * v / 255.0
            if role == "White":
                st.white = v / 255.0
        elif grp in ("Pan", "Tilt"):
            pos[grp.lower()][1 if cd.get("byte") else 0] = v
        elif grp == "Colour" and _is_wheel(cd):
            cap = _cap_at(cd, v)
            wheel = cap_colour(cap) if cap else None
            if wheel is None:
                st.notes.append(f"colour wheel value {v} has no known colour")
        elif _gobo_slots(cd) and st.gobo is None:
            slots = _gobo_slots(cd)
            cap = _cap_at(cd, v)
            if cap in slots:
                gobos = [c for c in slots if not _is_open_slot(c)]
                st.gobo = 0 if _is_open_slot(cap) else gobos.index(cap) + 1
        elif grp == "Shutter":
            kind = _shutter_kind(_cap_at(cd, v))
            if kind:
                st.shutter = kind
                if kind == "strobe":
                    cap = _cap_at(cd, v)
                    lo, hi = int(cap["min"]), int(cap["max"])
                    st.strobe_speed = 0.0 if hi <= lo else (v - lo) / (hi - lo)

    if has_mix:
        st.colour = tuple(_clamp01(x) for x in mix)  # type: ignore
        st.colour_source = "mix"
    elif wheel is not None:
        st.colour = wheel
        st.colour_source = "wheel"

    for axis in ("pan", "tilt"):
        coarse, fine = pos[axis]
        if coarse is None:
            continue
        frac = (coarse * 256 + fine) / 65535.0 if fine is not None else coarse / 255.0
        rng = _range(defn, axis)
        if rng > 0:
            setattr(st, axis, (frac - 0.5) * rng)
            setattr(st, f"{axis}_is_deg", True)
        else:
            setattr(st, axis, frac - 0.5)
    return st


# ─────────────────────────────────────────────────────────────────────────────
# encode
# ─────────────────────────────────────────────────────────────────────────────

def nearest_wheel_value(chdef: dict, colour: RGB) -> Optional[int]:
    """DMX value (capability minimum) of the wheel slot nearest *colour*."""
    target = _norm(colour)
    best = None
    for c in chdef.get("capabilities") or []:
        cc = cap_colour(c)
        if cc is None:
            continue
        d = sum((a - b) ** 2 for a, b in zip(_norm(cc), target))
        key = (round(d, 9), int(c.get("min", 0)))
        if best is None or key < best[0]:
            best = (key, int(c.get("min", 0)))
    return None if best is None else best[1]


def _strobe_value(chdef: dict, speed: float) -> Optional[int]:
    for c in chdef.get("capabilities") or []:
        if _shutter_kind(c) == "strobe":
            lo, hi = int(c["min"]), int(c["max"])
            return lo + int(round(_clamp01(speed) * (hi - lo)))
    return None


def encode(defn: dict, mode: str, st: LookState,
           strobe: str = "keep") -> Tuple[Dict[int, int], List[str]]:
    """Write *st* onto every channel of the target mode.

    Returns ``({channel index: value}, notes)``.
    """
    notes: List[str] = []
    lay = _layout(defn, mode)
    out = {i: neutral_value(n, cd) for i, n, cd in lay}

    has_dimmer = any(_role(cd) == "Dimmer" and not cd.get("byte") for _, _, cd in lay)
    mix_idx = {r: i for i, _, cd in lay if not cd.get("byte")
               for r in [_role(cd)] if r in _EMITTER_RGB}
    has_rgb = all(r in mix_idx for r in _MIX_ROLES)
    wheel_ch = next(((i, cd) for i, _, cd in lay if _is_wheel(cd)), None)

    level = 1.0 if st.level is None else st.level
    colour = st.colour if st.colour is not None else (1.0, 1.0, 1.0)
    shutter = st.shutter
    if shutter == "strobe" and strobe == "drop":
        shutter = "open"
        notes.append("strobe dropped")
    if shutter == "closed":
        shutter_ch = [(i, cd) for i, _, cd in lay if cd.get("group") == "Shutter"]
        if not any(closed_value(cd) is not None for _, cd in shutter_ch):
            level = 0.0                       # no closed position: go dark

    peak = max(colour)
    if has_rgb:
        # colour on the emitters; level on the dimmer (or baked in without one)
        k = 1.0 if has_dimmer else level
        white = st.white or 0.0
        base = [c - white for c in colour] if "White" in mix_idx else list(colour)
        for r, idx in zip(_MIX_ROLES, (0, 1, 2)):
            out[mix_idx[r]] = _dmx(base[idx] * k)
        if "White" in mix_idx:
            out[mix_idx["White"]] = _dmx(white * k)
        for r in mix_idx:
            if r not in _MIX_ROLES and r != "White":
                out[mix_idx[r]] = 0
        if has_dimmer:
            for i, _, cd in lay:
                if _role(cd) == "Dimmer" and not cd.get("byte"):
                    out[i] = _dmx(level)
    else:
        for i, _, cd in lay:
            if _role(cd) == "Dimmer" and not cd.get("byte"):
                out[i] = _dmx(level * peak)
        if wheel_ch is not None and peak > 0:
            v = nearest_wheel_value(wheel_ch[1], colour)
            if v is not None:
                out[wheel_ch[0]] = v
        elif (wheel_ch is None and peak > 0 and st.colour_source != "none"
              and _norm(colour) != (1.0, 1.0, 1.0)):
            notes.append("target cannot make colour; intensity only")
        if not has_dimmer and mix_idx:
            notes.append("target colour channels incomplete; left neutral")

    # position
    for axis in ("pan", "tilt"):
        val = getattr(st, axis)
        chans = [(i, cd) for i, _, cd in lay if (cd.get("group") or "").lower() == axis]
        if val is None or not chans:
            # within about one DMX step of centre (127 vs 127.5)
            centred = val is None or abs(val) < (3.0 if getattr(st, f"{axis}_is_deg") else 0.005)
            if not centred and not chans:
                notes.append(f"target has no {axis}; position dropped")
            continue
        rng = _range(defn, axis)
        if getattr(st, f"{axis}_is_deg") and rng > 0:
            frac = 0.5 + val / rng
        elif getattr(st, f"{axis}_is_deg"):
            frac = 0.5 + val / 540.0 if axis == "pan" else 0.5 + val / 270.0
        else:
            frac = 0.5 + val
        if not 0.0 <= frac <= 1.0:
            notes.append(f"{axis} clamped to the target range")
        frac = _clamp01(frac)
        fine = [i for i, cd in chans if cd.get("byte")]
        coarse = [i for i, cd in chans if not cd.get("byte")]
        if fine:
            v16 = int(round(frac * 65535))
            for i in coarse:
                out[i] = v16 >> 8
            for i in fine:
                out[i] = v16 & 0xFF
        else:
            for i in coarse:
                out[i] = _dmx(frac)

    # gobo: same slot number (open stays open; wraps on a smaller wheel)
    if st.gobo:
        wheel = next(((i, _gobo_slots(cd)) for i, _, cd in lay if _gobo_slots(cd)), None)
        gobos = [c for c in wheel[1] if not _is_open_slot(c)] if wheel else []
        if gobos:
            k = (st.gobo - 1) % len(gobos)
            out[wheel[0]] = int(gobos[k].get("min", 0))
            if k != st.gobo - 1:
                notes.append(f"gobo {st.gobo} → gobo {k + 1} (smaller wheel)")
        else:
            notes.append("target has no gobo wheel; gobo dropped")

    # shutter
    for i, _, cd in lay:
        if cd.get("group") != "Shutter":
            continue
        if shutter == "closed":
            cv = closed_value(cd)
            if cv is not None:
                out[i] = cv
        elif shutter == "strobe":
            sv = _strobe_value(cd, st.strobe_speed)
            if sv is not None:
                out[i] = sv
            else:
                notes.append("target shutter has no strobe range")
    if shutter == "strobe" and not any(cd.get("group") == "Shutter" for _, _, cd in lay):
        notes.append("target has no shutter; strobe dropped")
    return out, notes


# ─────────────────────────────────────────────────────────────────────────────
# public entry points
# ─────────────────────────────────────────────────────────────────────────────

def translate(src_def: dict, src_mode: str, tgt_def: dict, tgt_mode: str,
              values: Dict[int, int], strobe: str = "keep"
              ) -> Tuple[Dict[int, int], List[str]]:
    """Source channel values → target channel values (every target channel)."""
    st = decode(src_def, src_mode, values)
    out, notes = encode(tgt_def, tgt_mode, st, strobe=strobe)
    return out, st.notes + notes


def _pairs(text: str) -> Dict[int, int]:
    parts = (text or "").strip().split(",")
    out: Dict[int, int] = {}
    for i in range(0, len(parts) - 1, 2):
        try:
            out[int(parts[i])] = int(parts[i + 1])
        except ValueError:
            continue
    return out


def translate_text(src_def: dict, src_mode: str, tgt_def: dict, tgt_mode: str,
                   text: str, strobe: str = "keep") -> Tuple[str, List[str]]:
    """Same as :func:`translate` on a QLC+ ``FixtureVal`` text ("ch,val,…")."""
    out, notes = translate(src_def, src_mode, tgt_def, tgt_mode, _pairs(text), strobe)
    return ",".join(f"{c},{out[c]}" for c in sorted(out)), notes


def can_translate(defn: Optional[dict], mode: str) -> bool:
    """True when *defn* describes *mode* (so its channels can be decoded)."""
    return bool(defn) and mode in (defn.get("mode_channels") or {})


def kind(defn: Optional[dict], mode: str) -> str:
    """Rough fixture family used to pair different types in fan-in:
    ``"moving"`` (pan/tilt), ``"colour"`` (RGB mixing or a colour wheel),
    ``"dimmer"`` (intensity only), ``"unknown"`` (no definition)."""
    if not can_translate(defn, mode):
        return "unknown"
    lay = _layout(defn, mode)  # type: ignore[arg-type]
    if any((cd.get("group") or "") in ("Pan", "Tilt") for _, _, cd in lay):
        return "moving"
    roles = {_role(cd) for _, _, cd in lay}
    if all(r in roles for r in _MIX_ROLES) or any(_is_wheel(cd) for _, _, cd in lay):
        return "colour"
    return "dimmer"


def efx_modes(defn: Optional[dict], mode: str) -> Optional[set]:
    """EFX modes a fixture can run (QLC+ EFX fixture ``<Mode>``: 0 position,
    1 dimmer, 2 RGB) as ``{"position", "dimmer", "rgb"}``; None when the
    definition is unknown (then nothing is dropped)."""
    if not can_translate(defn, mode):
        return None
    lay = _layout(defn, mode)  # type: ignore[arg-type]
    out = set()
    groups = {(cd.get("group") or "") for _, _, cd in lay}
    if "Pan" in groups or "Tilt" in groups:
        out.add("position")
    roles = {_role(cd) for _, _, cd in lay}
    if all(r in roles for r in _MIX_ROLES):
        out.add("rgb")
    if roles - {None}:
        out.add("dimmer")
    return out
