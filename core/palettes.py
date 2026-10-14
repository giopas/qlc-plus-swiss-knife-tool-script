"""
QLC+ 5 palettes and the scenes that use them (3.1.0).

QLC+ 5.3's Show Wizard builds most of its looks as *palette scenes*: a
``<Function Type="Scene">`` that holds a ``<FixtureGroup ID>`` and one or more
``<Palette ID>`` and no ``<FixtureVal>``.  QLC+ works out the channel values
when the scene runs (``Scene::write`` → ``QLCPalette::valuesFromFixtures``).
Swiss Knife reads looks from ``<FixtureVal>``, so without this module such a
scene looks empty, and the Doctor, the Rig Reducer and the Porter get it
wrong.

This module is read-only.  It mirrors QLC+'s own rules (``qlcpalette.cpp``,
``qlcfixturemode.cpp``, ``qlcfixturehead.cpp`` at QLC+ 5.3.0):

==========  ================================================================
Palette     What it sets on each fixture of the scene
==========  ================================================================
Dimmer      the master intensity channel and the intensity channel of
            every head (value 0-255)
Color       R/G/B and C/M/Y of every head, plus White/Amber/UV when the
            palette has the 13-character ``#rrggbbwwaauv`` form; a colour
            wheel is **not** set (QLC+ doesn't either)
Shutter     on every shutter channel, the capability with the palette's
            preset (open/close: middle of the range; others: min + percent)
Pan, Tilt,  pan / tilt in degrees through the fixture's physical range
PanTilt
Position3D  pan / tilt that aim the head at a point on the stage (metres);
            computed from the fixture's 3D position and rotation, without
            the small offset of the moving-head model's light emitter, so a
            value can differ from QLC+'s by a step or two
Gobo, Zoom  Gobo: the gobo channel at the stored value; Zoom: not resolved
==========  ================================================================

Fanning (``Fan``, ``Layout``, ``Amount``, ``FanValue``) is applied for
Dimmer, Color, Pan, Tilt and PanTilt as QLC+ does it.

Two more helpers live here because every tool needs them:

* :func:`scene_layer` — a *layer scene* sets one family of channels
  (colour, gobo, shutter, position or intensity) on purpose, to be combined
  with others.  The wizard's colour-wheel and gobo buttons are layer scenes.
* :func:`infrastructure_fixtures` — the 1-channel dimmers the wizard patches
  on a Loopback universe to switch frame pages.  They are not lights.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET  # nosec B405
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

PALETTE_TYPES = ("Dimmer", "Color", "Pan", "Tilt", "PanTilt", "Position3D",
                 "Shutter", "Gobo", "Zoom")

# QLCCapability::Preset, in enum order (qlccapability.h).  The Shutter
# palette stores the preset as this number.
CAP_PRESETS = (
    "Custom", "SlowToFast", "FastToSlow", "NearToFar", "FarToNear", "BigToSmall",
    "SmallToBig", "ShutterOpen", "ShutterClose", "StrobeSlowToFast",
    "StrobeFastToSlow", "StrobeRandom", "StrobeRandomSlowToFast",
    "StrobeRandomFastToSlow", "StrobeFrequency", "StrobeFreqRange",
    "PulseSlowToFast", "PulseFastToSlow", "PulseFrequency", "PulseFreqRange",
    "RampUpSlowToFast", "RampUpFastToSlow", "RampDownSlowToFast",
    "RampDownFastToSlow", "RampUpFrequency", "RampUpFreqRange",
    "RampDownFrequency", "RampDownFreqRange", "RotationStop", "RotationIndexed",
    "RotationClockwise", "RotationClockwiseSlowToFast",
    "RotationClockwiseFastToSlow", "RotationCounterClockwise",
    "RotationCounterClockwiseSlowToFast", "RotationCounterClockwiseFastToSlow",
    "ColorMacro", "ColorDoubleMacro", "ColorWheelIndex", "GoboMacro",
    "GoboShakeMacro", "GenericPicture", "PrismEffectOn", "PrismEffectOff",
    "LampOn", "LampOff", "ResetAll", "ResetPanTilt", "ResetPan", "ResetTilt",
    "ResetMotors", "ResetGobo", "ResetColor", "ResetCMY", "ResetCTO",
    "ResetEffects", "ResetPrism", "ResetBlades", "ResetIris", "ResetFrost",
    "ResetZoom", "SilentModeOn", "SilentModeOff", "SilentModeAutomatic", "Alias",
)

# Families a layer scene can set.  "other" (beam, prism, effect, speed …) is
# never a layer on its own.
LAYER_FAMILIES = ("colour", "gobo", "shutter", "position", "intensity", "maintenance")

WIZARD_PATH = "Show Wizard"
PAGE_SWITCH_RE = re.compile(r"^page\s*switch\s*\d+$", re.I)


# ═════════════════════════════════════════════════════════════════════════════
# Reading palettes and references
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Palette:
    """One ``<Palette>`` of the Engine."""
    id: str
    type: str
    name: str
    value: str                       # the raw Value attribute
    fan: str = "Flat"                # Fan: Flat | Linear | Sine | Square | Saw
    layout: str = "XAscending"
    amount: int = 100
    fan_value: str = ""

    def numbers(self) -> List[float]:
        """The Value attribute as numbers (``"9,85"`` → ``[9.0, 85.0]``)."""
        out = []
        for p in (self.value or "").split(","):
            try:
                out.append(float(p))
            except ValueError:
                pass
        return out

    def colours(self) -> Tuple[Optional[Tuple[int, int, int]], Optional[Tuple[int, int, int]]]:
        """``(rgb, wauv)`` of a Color palette; wauv is None for ``#rrggbb``."""
        return parse_colour(self.value)

    def label(self) -> str:
        return f"palette {self.id} '{self.name}' ({self.type})"


def parse_colour(s: str):
    """``#rrggbb`` or ``#rrggbbwwaauv`` → ``((r, g, b), (w, a, uv) | None)``."""
    s = (s or "").strip()
    if not s.startswith("#") or len(s) not in (7, 13):
        return None, None
    try:
        rgb = tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
        wauv = tuple(int(s[i:i + 2], 16) for i in (7, 9, 11)) if len(s) == 13 else None
    except ValueError:
        return None, None
    return rgb, wauv


def _strip(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _engine(root: ET.Element) -> Optional[ET.Element]:
    if _strip(root.tag) == "Engine":
        return root
    for c in root:
        if _strip(c.tag) == "Engine":
            return c
    return None


def _children(el: ET.Element, tag: str) -> List[ET.Element]:
    return [c for c in el if _strip(c.tag) == tag]


def read_palettes(root: ET.Element) -> Dict[str, Palette]:
    """``{palette id: Palette}`` in document order (namespaced or not)."""
    eng = _engine(root)
    out: Dict[str, Palette] = {}
    if eng is None:
        return out
    for p in _children(eng, "Palette"):
        pid = p.get("ID")
        if pid is None:
            continue
        try:
            amount = int(p.get("Amount", "100"))
        except ValueError:
            amount = 100
        out.setdefault(pid, Palette(pid, p.get("Type", ""), p.get("Name", ""),
                                    p.get("Value", ""), p.get("Fan", "Flat") or "Flat",
                                    p.get("Layout", "XAscending") or "XAscending",
                                    amount, p.get("FanValue", "")))
    return out


def scene_groups(fn: ET.Element) -> List[str]:
    """IDs of the fixture groups a scene uses (``<FixtureGroup ID>``)."""
    return [g.get("ID") for g in _children(fn, "FixtureGroup") if g.get("ID") is not None]


def scene_palettes(fn: ET.Element) -> List[str]:
    """IDs of the palettes a scene uses (``<Palette ID>``)."""
    return [p.get("ID") for p in _children(fn, "Palette") if p.get("ID") is not None]


def is_palette_scene(fn: ET.Element) -> bool:
    """A scene that uses at least one palette."""
    return fn.get("Type") == "Scene" and bool(scene_palettes(fn))


def has_values(fn: ET.Element) -> bool:
    """A scene with at least one ``<FixtureVal>`` that carries values."""
    return any((v.text or "").strip() for v in _children(fn, "FixtureVal"))


def group_fixture_ids(group: ET.Element) -> List[str]:
    """Fixture IDs of a group, in grid order (row by row), each once."""
    heads = []
    for h in _children(group, "Head"):
        try:
            heads.append((int(h.get("Y", 0)), int(h.get("X", 0)), h.get("Fixture", "")))
        except ValueError:
            continue
    out: List[str] = []
    for _y, _x, f in sorted(heads):
        if f and f not in out:
            out.append(f)
    return out


def groups_by_id(root: ET.Element) -> Dict[str, ET.Element]:
    eng = _engine(root)
    return {g.get("ID"): g for g in (_children(eng, "FixtureGroup") if eng is not None else [])}


def palette_users(root: ET.Element) -> Dict[str, List[str]]:
    """``{palette id: [function ids that use it]}``."""
    eng = _engine(root)
    out: Dict[str, List[str]] = {}
    if eng is None:
        return out
    for fn in _children(eng, "Function"):
        for pid in scene_palettes(fn):
            out.setdefault(pid, []).append(fn.get("ID"))
    return out


# ═════════════════════════════════════════════════════════════════════════════
# The channels of a fixture, the way QLC+ sees them
# ═════════════════════════════════════════════════════════════════════════════

_ROLE_TO_COLOUR = {"Red": "Red", "Green": "Green", "Blue": "Blue", "Cyan": "Cyan",
                   "Magenta": "Magenta", "Yellow": "Yellow", "White": "White",
                   "Amber": "Amber", "Uv": "UV", "UV": "UV", "Lime": "Lime",
                   "Indigo": "Indigo"}


@dataclass
class Channel:
    index: int
    name: str
    group: str                    # QLC+ channel group (Intensity, Pan, Colour …)
    colour: Optional[str]         # Intensity only: Red, Green … ; None = dimmer
    msb: bool                     # coarse byte
    chdef: dict = field(default_factory=dict)


@dataclass
class FixtureModel:
    """What QLC+ needs from a fixture to resolve a palette."""
    id: str
    name: str
    type: str                     # QLC+ fixture type ("Moving Head", "Dimmer" …)
    channels: List[Channel]
    heads: List[List[int]]        # channel indexes per head (one implicit head if none)
    pan_max: float = 0.0
    tilt_max: float = 0.0
    builtin: bool = False         # QLC+'s built-in generic dimmer (no .qxf)

    def channel(self, i: int) -> Optional[Channel]:
        return self.channels[i] if 0 <= i < len(self.channels) else None

    def master_intensity(self) -> Optional[int]:
        """First coarse no-colour intensity channel that is in no head
        (``QLCFixtureMode::cacheHeads``); a Dimmer-type fixture uses 0."""
        if self.type == "Dimmer":
            return 0 if self.channels else None
        in_head = {i for h in self._declared_heads for i in h}
        for c in self.channels:
            if c.group == "Intensity" and c.msb and c.colour is None and c.index not in in_head:
                return c.index
        return None

    _declared_heads: List[List[int]] = field(default_factory=list)

    def head_map(self, h: int) -> Dict[Tuple[str, bool], int]:
        """``{(group-or-colour, msb): channel}`` of head *h*: first channel
        wins; pan/tilt fall back to the mode's (``QLCFixtureHead::cacheChannels``)."""
        out: Dict[Tuple[str, bool], int] = {}
        for i in self.heads[h] if 0 <= h < len(self.heads) else []:
            c = self.channel(i)
            if c is None:
                continue
            if c.group in ("Pan", "Tilt"):
                out.setdefault((c.group, c.msb), i)
            elif c.group == "Intensity":
                out.setdefault((c.colour or "Intensity", c.msb), i)
        for axis in ("Pan", "Tilt"):
            for msb in (True, False):
                if (axis, msb) not in out:
                    m = next((c.index for c in self.channels if c.group == axis and c.msb == msb), None)
                    if m is not None:
                        out[(axis, msb)] = m
        return out

    def shutter_channels(self, h: int) -> List[int]:
        return sorted(i for i in (self.heads[h] if 0 <= h < len(self.heads) else [])
                      if self.channel(i) and self.channel(i).group == "Shutter" and self.channel(i).msb)

    def channel_number(self, group: str, msb: bool = True) -> Optional[int]:
        return next((c.index for c in self.channels if c.group == group and c.msb == msb), None)


def _def_key(manufacturer: str, model: str) -> Tuple[str, str]:
    return ((manufacturer or "").strip().lower(), (model or "").strip().lower())


def _builtin_channels(info: dict) -> Optional[int]:
    """Channels of QLC+'s built-in generic dimmer (``Generic`` / ``Generic``,
    mode ``N Channel``), which has no .qxf file."""
    if _def_key(info.get("manufacturer"), info.get("model")) != ("generic", "generic"):
        return None
    m = re.match(r"^\s*(\d+)\s*channels?\s*$", info.get("mode") or "", re.I)
    if m:
        return int(m.group(1))
    try:
        n = int(info.get("channels") or 0)
    except (TypeError, ValueError):
        n = 0
    return n or None


def is_builtin_generic(info: dict) -> bool:
    """True for QLC+'s built-in generic dimmer, known without a .qxf."""
    return _builtin_channels(info) is not None


def fixture_model(info: dict, defn: Optional[dict]) -> Optional[FixtureModel]:
    """A :class:`FixtureModel` from a fixture (``{id, name, manufacturer, model,
    mode, channels}``) and its ``parse_qxf`` definition.  QLC+'s built-in
    generic dimmer needs no definition.  None when the mode is unknown."""
    n = _builtin_channels(info)
    if n is not None and (defn is None or info.get("mode") not in (defn.get("mode_channels") or {})):
        chans = [Channel(i, f"Dimmer {i + 1}", "Intensity", None, True,
                         {"name": f"Dimmer {i + 1}", "group": "Intensity", "byte": 0,
                          "colour_role": "Dimmer", "capabilities": []}) for i in range(n)]
        m = FixtureModel(info.get("id", ""), info.get("name", ""), "Dimmer", chans,
                         [[i] for i in range(n)], builtin=True)
        m._declared_heads = [[i] for i in range(n)]
        return m
    if not defn:
        return None
    names = (defn.get("mode_channels") or {}).get(info.get("mode") or "")
    if not names:
        return None
    defs = defn.get("channel_defs") or {}
    chans = []
    for i, nm in enumerate(names):
        cd = defs.get(nm) or {"name": nm, "group": "Nothing", "byte": 0, "capabilities": []}
        grp = cd.get("group") or "Nothing"
        colour = None
        if grp == "Intensity":
            colour = _ROLE_TO_COLOUR.get(cd.get("colour_role") or "")
        chans.append(Channel(i, nm, grp, colour, not cd.get("byte"), cd))
    declared = [list(h) for h in (defn.get("mode_heads") or {}).get(info.get("mode"), []) if h]
    heads = declared or [list(range(len(names)))]
    phys = defn.get("physical") or {}
    m = FixtureModel(info.get("id", ""), info.get("name", ""), defn.get("type") or "",
                     chans, heads, float(phys.get("pan_max") or 0.0),
                     float(phys.get("tilt_max") or 0.0))
    m._declared_heads = declared
    return m


# ═════════════════════════════════════════════════════════════════════════════
# Stage positions (for fanning layouts and Position3D)
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Stage:
    grid: Tuple[float, float, float] = (5.0, 3.0, 5.0)    # metres
    items: Dict[str, Tuple[float, float, float, float, float, float]] = field(default_factory=dict)
    # fid → (x, y, z mm, xrot, yrot, zrot)

    def position(self, fid: str) -> Tuple[float, float, float]:
        it = self.items.get(fid)
        return (it[0], it[1], it[2]) if it else (0.0, 0.0, 0.0)


def read_stage(root: ET.Element) -> Stage:
    """Grid size (metres) and fixture items (head 0) of the 3D monitor."""
    eng = _engine(root)
    st = Stage()
    mon = next((c for c in _children(eng, "Monitor")), None) if eng is not None else None
    if mon is None:
        return st

    def f(el, k, d=0.0):
        try:
            return float(el.get(k, d))
        except (TypeError, ValueError):
            return d
    g = next((c for c in _children(mon, "Grid")), None)
    if g is not None:
        scale = 1.0 if g.get("Units", "0") == "0" else 0.3048
        st.grid = (f(g, "Width", 5) * scale, f(g, "Height", 3) * scale, f(g, "Depth", 5) * scale)
    for it in _children(mon, "FxItem"):
        if it.get("Head", "0") not in ("0", None) or it.get("Linked", "0") not in ("0", None):
            continue
        st.items.setdefault(it.get("ID"), (f(it, "XPos"), f(it, "YPos"), f(it, "ZPos"),
                                           f(it, "XRot"), f(it, "YRot"), f(it, "ZRot")))
    return st


def _quat(axis, deg):
    h = math.radians(deg) / 2.0
    s = math.sin(h)
    return (math.cos(h), axis[0] * s, axis[1] * s, axis[2] * s)


def _qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


def _qrot(q, v):
    w, x, y, z = q
    vx, vy, vz = v
    # v' = q v q*
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


def _rotation(rx, ry, rz):
    """``MonitorProperties::fixtureRotationMatrix``: qZ·qY·qX with negated angles."""
    q = _qmul(_qmul(_quat((0, 0, 1), -rz), _quat((0, 1, 0), -ry)), _quat((1, 0, 0), -rx))
    return lambda v: _qrot(q, v)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm3(v):
    n = math.sqrt(_dot(v, v))
    return (0.0, 0.0, 0.0) if n == 0 else (v[0] / n, v[1] / n, v[2] / n)


def aim_degrees(stage: Stage, fid: str, target: Tuple[float, float, float],
                pan_max: float, tilt_max: float) -> Tuple[Optional[float], Optional[float]]:
    """Pan and tilt (degrees, in the fixture's own range) that aim fixture
    *fid* at *target* (metres, stage frame), as ``QLCPalette`` Position3D."""
    it = stage.items.get(fid)
    if it is None:
        return None, None
    gx, _gy, gz = stage.grid
    # rootPos in world metres, then the grid-offset adjustment of QLC+
    lp = (it[0] / 1000.0, it[1] / 1000.0, it[2] / 1000.0)
    rot = _rotation(it[3], it[4], it[5])
    xa, ya, za = (_norm3(rot((1, 0, 0))), _norm3(rot((0, 1, 0))), _norm3(rot((0, 0, 1))))
    d = _norm3((target[0] - lp[0], target[1] - lp[1], target[2] - lp[2]))
    # lightMatrix is the transposed axis matrix: lightMatrix * e_k = k-th row
    lxa = (xa[0], ya[0], za[0])
    lza = (xa[2], ya[2], za[2])
    lya_neg = (-xa[1], -ya[1], -za[1])
    px = _dot(d, lxa)
    pz = _dot(d, lza)
    b, c = abs(px), abs(pz)
    # QLC+: 90° - atan(c / b); atan(c / 0) is 90°, so b == 0 gives 0°
    pan = 0.0 if b == 0 else math.degrees(math.pi / 2 - math.atan(c / b))
    x_left, z_back = px < 0, pz < 0
    if x_left and not z_back:
        pan = 90.0 + (90.0 - pan)
    elif not x_left and not z_back:
        pan = 180.0 + pan
    elif not x_left and z_back:
        pan = 270.0 + (90.0 - pan)
    tmax = tilt_max or 270.0
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, _dot(d, lya_neg)))))
    tilt = max(0.0, min(tilt, tmax / 2))
    tilt = tmax / 2 - tilt
    return pan, tilt


# ═════════════════════════════════════════════════════════════════════════════
# Palette → channel values
# ═════════════════════════════════════════════════════════════════════════════

def _factor(pal: Palette, progress: float) -> float:
    """``QLCPalette::valueFactor``."""
    amt = pal.amount / 100.0
    if pal.fan == "Linear":
        if amt < 1.0:
            return 1.0 if progress > amt else progress * amt
        if amt > 1.0:
            return progress / amt
        return progress
    if pal.fan == "Sine":
        deg = progress * 360.0 + 270.0
        return (math.sin(amt * math.radians(deg)) + 1.0) / 2.0
    if pal.fan == "Square":
        return 1.0 if math.sin(amt * math.radians(progress * 360.0)) < 0 else 0.0
    return 1.0


def _position_values(m: FixtureModel, axis: str, degrees: float) -> Dict[int, int]:
    """``Fixture::positionToValues`` for every head (MSB and LSB)."""
    maxd = (m.pan_max or 360.0) if axis == "Pan" else (m.tilt_max or 270.0)
    v16 = int(max(0.0, min(degrees, maxd)) * 65535.0 / maxd) & 0xFFFF
    out: Dict[int, int] = {}
    for h in range(len(m.heads)):
        hm = m.head_map(h)
        msb = hm.get((axis, True))
        if msb is None or msb in out:
            continue
        out[msb] = v16 >> 8
        lsb = hm.get((axis, False))
        if lsb is not None:
            out[lsb] = v16 & 0xFF
    return out


def _shutter_value(cd: dict, preset: str, pct: int) -> Optional[int]:
    for cap in cd.get("capabilities") or []:
        if cap.get("preset") != preset:
            continue
        lo, hi = int(cap.get("min", 0)), int(cap.get("max", 255))
        if preset in ("ShutterOpen", "ShutterClose"):
            return (lo + hi) // 2
        return int(lo + (hi - lo) * pct / 100)
    return None


def palette_values(pal: Palette, models: List[FixtureModel], stage: Optional[Stage] = None
                   ) -> Dict[str, Dict[int, int]]:
    """``{fixture id: {channel: value}}`` that *pal* sets on *models*
    (``QLCPalette::valuesFromFixtures``).  Fixtures it cannot act on are left
    out, so an empty result means the palette does nothing there."""
    stage = stage or Stage()
    out: Dict[str, Dict[int, int]] = {}
    lay = pal.layout or "XAscending"
    axis = {"X": 0, "Y": 1, "Z": 2}.get(lay[:1], 0)
    centred = lay.endswith("Centered")
    models = list(models)
    coords = [stage.position(m.id)[axis] for m in models]
    centre = (min(coords) + max(coords)) / 2.0 if (centred and coords) else 0.0
    maxdist = max((abs(c - centre) for c in coords), default=0.0) if centred else 0.0

    def key(m):
        c = stage.position(m.id)[axis]
        if centred:
            return (abs(c - centre), c)
        return -c if lay.endswith("Descending") else c
    if pal.fan != "Flat" or centred:
        models.sort(key=key)

    nums = pal.numbers()
    n = len(models)
    for k, m in enumerate(models):
        progress = k / (n - 1) if n > 1 else 0.0
        factor = _factor(pal, progress)
        sign = 1
        if centred:
            c = stage.position(m.id)[axis]
            sign = 1 if c > centre else -1 if c < centre else 0
            factor = _factor(pal, abs(c - centre) / maxdist if maxdist > 0 else 0.0)
        vals: Dict[int, int] = {}
        t = pal.type
        if t == "Dimmer" and nums:
            d = int(nums[0])
            if pal.fan != "Flat":
                try:
                    d = int((int(float(pal.fan_value)) - d) * factor + d)
                except ValueError:
                    pass
            d = max(0, min(255, d))
            mi = m.master_intensity()
            if mi is not None:
                vals[mi] = d
            for h in range(len(m.heads)):
                hd = m.head_map(h).get(("Intensity", True))
                if hd is not None:
                    vals[hd] = d
        elif t == "Color":
            rgb, wauv = pal.colours()
            if rgb is None:
                continue
            if pal.fan != "Flat":
                end, _ = parse_colour(pal.fan_value)
                if end:
                    rgb = tuple(int(s + round((e - s) * factor)) for s, e in zip(rgb, end))
            cmy = _cmy(rgb)
            for h in range(len(m.heads)):
                hm = m.head_map(h)
                trio = [hm.get((c, True)) for c in ("Red", "Green", "Blue")]
                if None not in trio:
                    for ch, v in zip(trio, rgb):
                        vals[ch] = v
                trio = [hm.get((c, True)) for c in ("Cyan", "Magenta", "Yellow")]
                if None not in trio:
                    for ch, v in zip(trio, cmy):
                        vals[ch] = v
                if wauv is not None:
                    for c, v in zip(("White", "Amber", "UV"), wauv):
                        ch = hm.get((c, True))
                        if ch is not None:
                            vals[ch] = v
        elif t in ("Pan", "Tilt", "PanTilt") and nums:
            off = 0
            if pal.fan != "Flat":
                try:
                    off = int(float(pal.fan_value) * factor) * (sign if centred else 1)
                except ValueError:
                    off = 0
            if t == "Pan":
                vals.update(_position_values(m, "Pan", int(nums[0] + off)))
            elif t == "Tilt":
                vals.update(_position_values(m, "Tilt", int((nums[1] if len(nums) == 2 else nums[0]) + off)))
            elif len(nums) == 2:
                vals.update(_position_values(m, "Pan", int(nums[0] + off)))
                vals.update(_position_values(m, "Tilt", int(nums[1] + off)))
        elif t == "Shutter" and len(nums) >= 2:
            pi = int(nums[0])
            preset = CAP_PRESETS[pi] if 0 <= pi < len(CAP_PRESETS) else ""
            for h in range(len(m.heads)):
                for ch in m.shutter_channels(h):
                    v = _shutter_value(m.channel(ch).chdef, preset, int(nums[1]))
                    if v is not None:
                        vals[ch] = max(0, min(255, v))
        elif t == "Gobo" and nums:
            ch = m.channel_number("Gobo")
            if ch is not None:
                vals[ch] = max(0, min(255, int(nums[0])))
        elif t == "Position3D" and len(nums) >= 3:
            if m.channel_number("Pan") is None and m.channel_number("Tilt") is None:
                continue
            pan, tilt = aim_degrees(stage, m.id, (nums[0], nums[1], nums[2]), m.pan_max, m.tilt_max)
            if pan is None:
                continue
            if m.channel_number("Pan") is not None:
                vals.update(_position_values(m, "Pan", pan))
            if m.channel_number("Tilt") is not None:
                vals.update(_position_values(m, "Tilt", tilt))
        if vals:
            out[m.id] = vals
    return out


def _cmy(rgb):
    """``QColor::cyan()/magenta()/yellow()`` of an RGB colour (0-255)."""
    r, g, b = (x / 255.0 for x in rgb)
    k = 1.0 - max(r, g, b)
    if k >= 1.0:
        return (0, 0, 0)
    return tuple(int(round((1.0 - x - k) / (1.0 - k) * 255)) for x in (r, g, b))


# ═════════════════════════════════════════════════════════════════════════════
# A whole workspace
# ═════════════════════════════════════════════════════════════════════════════

def _fixture_infos(root: ET.Element) -> Dict[str, dict]:
    eng = _engine(root)
    out: Dict[str, dict] = {}
    for f in (_children(eng, "Fixture") if eng is not None else []):
        def t(tag, d=""):
            el = next((c for c in f if _strip(c.tag) == tag), None)
            return (el.text or d).strip() if el is not None and el.text else d
        fid = t("ID")
        out.setdefault(fid, {"id": fid, "name": t("Name"), "manufacturer": t("Manufacturer"),
                             "model": t("Model"), "mode": t("Mode"),
                             "universe": t("Universe", "0"), "address": t("Address", "0"),
                             "channels": t("Channels", "0")})
    return out


def _lookup(defs, info) -> Optional[dict]:
    if not defs:
        return None
    if isinstance(defs, dict):
        return defs.get(_def_key(info["manufacturer"], info["model"]))
    for d in defs:
        if _def_key(d.get("manufacturer"), d.get("model")) == _def_key(info["manufacturer"], info["model"]):
            return d
    return None


class Resolver:
    """Palette-aware view of one workspace.  Build once, ask many times."""

    def __init__(self, root: ET.Element, defs=None):
        self.root = root
        self.palettes = read_palettes(root)
        self.groups = groups_by_id(root)
        self.infos = _fixture_infos(root)
        self.stage = read_stage(root)
        self.models: Dict[str, Optional[FixtureModel]] = {
            fid: fixture_model(inf, _lookup(defs, inf)) for fid, inf in self.infos.items()}

    def scene_fixtures(self, fn: ET.Element) -> List[str]:
        """Fixtures a scene acts on: its groups' fixtures, then its own."""
        out: List[str] = []
        for gid in scene_groups(fn):
            g = self.groups.get(gid)
            for f in (group_fixture_ids(g) if g is not None else []):
                if f not in out:
                    out.append(f)
        for v in _children(fn, "FixtureVal"):
            f = v.get("ID")
            if f and f not in out:
                out.append(f)
        return out

    def palette_on(self, pal: Palette, fixture_ids: Iterable[str]) -> Dict[str, Dict[int, int]]:
        models = [self.models[f] for f in fixture_ids if self.models.get(f) is not None]
        return palette_values(pal, models, self.stage)

    def resolve(self, fn: ET.Element) -> Dict[str, Dict[int, int]]:
        """``{fixture id: {channel: value}}`` a scene sets when it runs:
        palettes on its groups' fixtures, then on its own fixtures, then its
        own ``<FixtureVal>`` values (which win)."""
        out: Dict[str, Dict[int, int]] = {}
        own = [v.get("ID") for v in _children(fn, "FixtureVal") if v.get("ID")]
        group_fx: List[str] = []
        for gid in scene_groups(fn):
            g = self.groups.get(gid)
            if g is not None:
                group_fx += [f for f in group_fixture_ids(g) if f not in group_fx]
        for pid in scene_palettes(fn):
            pal = self.palettes.get(pid)
            if pal is None:
                continue
            for fx_set in (group_fx, own):
                for fid, vals in self.palette_on(pal, fx_set).items():
                    out.setdefault(fid, {}).update(vals)
        for v in _children(fn, "FixtureVal"):
            fid = v.get("ID")
            nums = [x.strip() for x in (v.text or "").split(",") if x.strip()]
            d = out.setdefault(fid, {})
            for c, val in zip(nums[0::2], nums[1::2]):
                try:
                    d[int(c)] = int(val)
                except ValueError:
                    pass
        return out

    def unresolved(self, fn: ET.Element) -> List[str]:
        """Palettes of a scene that set nothing on its fixtures (the fixtures
        can't take them).  Fixtures without a definition, and fixtures the
        scene already sets by hand in the palette's family, are not counted."""
        known = [f for f in self.scene_fixtures(fn) if self.models.get(f) is not None]
        own = {v.get("ID"): v for v in _children(fn, "FixtureVal")}
        out = []
        for pid in scene_palettes(fn):
            pal = self.palettes.get(pid)
            if pal is None or pal.type not in PALETTE_TYPES or pal.type == "Zoom":
                continue
            fam = palette_family(pal.type)
            todo = [f for f in known if not (f in own and fam in _families_of(own[f], self.models[f]))]
            if todo and not self.palette_on(pal, todo):
                out.append(pid)
        return out


def _families_of(val_el: ET.Element, m: "FixtureModel") -> set:
    nums = [x.strip() for x in (val_el.text or "").split(",") if x.strip()]
    out = set()
    for c in nums[0::2]:
        ch = m.channel(int(c)) if c.isdigit() else None
        if ch is not None:
            out.add(channel_family(ch))
    return out


def resolve_scene(root: ET.Element, fn: ET.Element, defs=None) -> Dict[str, Dict[int, int]]:
    """One-off :meth:`Resolver.resolve`."""
    return Resolver(root, defs).resolve(fn)


def fixture_val_text(vals: Dict[int, int]) -> str:
    """``{ch: v}`` → QLC+ ``FixtureVal`` text (``"0,255,1,0"``)."""
    return ",".join(f"{c},{vals[c]}" for c in sorted(vals))


# ═════════════════════════════════════════════════════════════════════════════
# Layer scenes
# ═════════════════════════════════════════════════════════════════════════════

_NAME_FAMILY = (
    (re.compile(r"\b(pan|tilt)\b", re.I), "position"),
    (re.compile(r"\bgobo\b", re.I), "gobo"),
    (re.compile(r"\b(shutter|strobe)\b", re.I), "shutter"),
    (re.compile(r"\b(red|green|blue|cyan|magenta|yellow|white|amber|uv|lime|indigo|colou?r|cto|ctb)\b", re.I), "colour"),
    (re.compile(r"\b(dimmer|intensity|master)\b", re.I), "intensity"),
)


def channel_family(c: Channel) -> str:
    """Family of one channel: colour, gobo, shutter, position, intensity,
    maintenance or other."""
    g = c.group
    if g == "Intensity":
        return "colour" if c.colour else "intensity"
    if g == "Colour":
        return "colour"
    if g in ("Pan", "Tilt"):
        return "position"
    if g == "Gobo":
        return "gobo"
    if g == "Shutter":
        return "shutter"
    if g == "Maintenance":
        return "maintenance"
    return "other"


def scene_families(fn: ET.Element, models: Dict[str, Optional[FixtureModel]]
                   ) -> Optional[Dict[str, set]]:
    """``{fixture id: {families its FixtureVal touches}}``, or None when a
    fixture of the scene has no known model."""
    out: Dict[str, set] = {}
    for v in _children(fn, "FixtureVal"):
        m = models.get(v.get("ID"))
        if m is None:
            return None
        nums = [x.strip() for x in (v.text or "").split(",") if x.strip()]
        fam = set()
        for c, val in zip(nums[0::2], nums[1::2]):
            try:
                ch = m.channel(int(c))
            except ValueError:
                ch = None
            f = channel_family(ch) if ch else "other"
            # a dimmer at 0 adds nothing: intensity is HTP, the highest wins
            if f == "intensity" and val == "0":
                continue
            fam.add(f)
        if fam:
            out[v.get("ID")] = fam
    return out


def palette_family(pal_type: str) -> Optional[str]:
    return {"Dimmer": "intensity", "Color": "colour", "Pan": "position", "Tilt": "position",
            "PanTilt": "position", "Position3D": "position", "Shutter": "shutter",
            "Gobo": "gobo"}.get(pal_type)


def scene_layer(fn: ET.Element, resolver: "Resolver") -> Optional[str]:
    """The one family a *layer scene* sets, or None when *fn* is not one.

    A layer scene is a QLC+ 5 group-based scene (it carries a
    ``<FixtureGroup>``, or it was made by the Show Wizard) whose values and
    palettes all belong to one family: colour, gobo, shutter, position,
    intensity or maintenance (lamp on); or a palette scene with a few values
    of its own (family ``"palette"``).  It is meant to be combined with other
    scenes, so the rule "declare every channel" does not apply to it.
    None also when a fixture of the scene has no known definition."""
    if fn.get("Type") != "Scene":
        return None
    designed = bool(scene_groups(fn)) or (fn.get("Path") or "").startswith(WIZARD_PATH)
    if not designed:
        return None
    fams = scene_families(fn, resolver.models)
    if fams is None:
        return None
    union = set().union(*fams.values()) if fams else set()
    for pid in scene_palettes(fn):
        pal = resolver.palettes.get(pid)
        f = palette_family(pal.type) if pal else None
        if f:
            union.add(f)
    if len(union) == 1:
        fam = next(iter(union))
        if fam in LAYER_FAMILIES:
            return fam
    # a palette scene composes by design: its palettes plus a few values
    if scene_palettes(fn) and union and "other" not in union:
        return "palette"
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Infrastructure fixtures (wizard page switching)
# ═════════════════════════════════════════════════════════════════════════════

def loopback_output_universes(root: ET.Element) -> List[str]:
    """IDs (0-based, as in the file) of universes whose output is the
    Loopback plugin."""
    eng = _engine(root)
    iom = next((c for c in _children(eng, "InputOutputMap")), None) if eng is not None else None
    out = []
    for u in (_children(iom, "Universe") if iom is not None else []):
        if any(o.get("Plugin") == "Loopback" for o in _children(u, "Output")):
            out.append(u.get("ID"))
    return out


def infrastructure_fixtures(root: ET.Element) -> List[str]:
    """Fixtures that are not lights: QLC+ built-in generic dimmers patched on a
    Loopback output universe (the Show Wizard's *Page Switch N*), or named
    *Page Switch N* and used only by ``Show Wizard/Page Switch`` scenes.
    Sorted by ID."""
    loop = set(loopback_output_universes(root))
    infos = _fixture_infos(root)
    eng = _engine(root)
    switch_fx = set()
    for fn in (_children(eng, "Function") if eng is not None else []):
        if (fn.get("Path") or "").startswith(f"{WIZARD_PATH}/Page Switch"):
            switch_fx |= {v.get("ID") for v in _children(fn, "FixtureVal")}
    out = []
    for fid, inf in infos.items():
        on_loop = inf["universe"] in loop and is_builtin_generic(inf)
        named = bool(PAGE_SWITCH_RE.match(inf["name"] or "")) and (fid in switch_fx or inf["universe"] in loop)
        if on_loop or named:
            out.append(fid)
    return sorted(out, key=lambda i: (0, int(i)) if i.isdigit() else (1, i))


def is_wizard_show(root: ET.Element) -> bool:
    """True when the workspace has functions made by the QLC+ Show Wizard."""
    eng = _engine(root)
    return eng is not None and any((fn.get("Path") or "").startswith(WIZARD_PATH + "/")
                                   or fn.get("Path") == WIZARD_PATH
                                   for fn in _children(eng, "Function"))
