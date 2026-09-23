"""
core/quick_start/vc_generator.py
=================================
Generate a complete QLC+ Virtual Console layout with backing functions
(Scenes, Chasers, RGBMatrix) from a rig + capability analysis.

Key design decisions (modelled on professional show files):
  - Every Scene sets ALL channels on ALL fixtures explicitly so that
    switching scenes never leaves stale DMX values.  Channels a look does
    not use get their capability-aware *neutral* value (shutter open,
    "no function", Pan/Tilt centred) — see channel_model.py.
  - Channel indices follow the fixture's selected mode, not the QXF
    definition order.
  - FixtureVal uses the correct QLC+ format:
        <FixtureVal ID="X">ch0,val0,ch1,val1,...,chN,valN</FixtureVal>
    i.e. ONE element per fixture with all channel/value pairs.
  - Scene buttons live inside SoloFrames for mutual exclusivity —
    only one scene per SoloFrame can be active at a time.
  - A PANIC / BLACKOUT button uses StopAll (function ID 4294967295)
    to kill all running functions instantly, and a PANIC RESET scene
    button puts every fixture back to its neutral state.
  - RGBMatrix functions provide colour-chase templates.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from core.quick_start.channel_model import (
    closed_value, mode_channels, neutral_map,
)
from core.quick_start.fixture_analyzer import RigCapabilityAnalysis
from core.quick_start.nomenclature import Nomenclature, load_profile
from core.quick_start.vc_style import VCStyle, load_style

QLC_NS_URI = "http://www.qlcplus.org/Workspace"


def _ns(tag: str) -> str:
    """Return a namespace-qualified tag."""
    return f"{{{QLC_NS_URI}}}{tag}"


def _sub(parent: ET.Element, tag: str, text: str = None, **attribs) -> ET.Element:
    """Create a namespaced sub-element with optional text and attributes."""
    el = ET.SubElement(parent, _ns(tag))
    if text is not None:
        el.text = str(text)
    for k, v in attribs.items():
        el.set(k, str(v))
    return el


# ═════════════════════════════════════════════════════════════════════════════
# ARGB color constants  (Qt QColor 32-bit unsigned format)
# ═════════════════════════════════════════════════════════════════════════════

_CLR_RED        = 4294901760   # 0xFFFF0000
_CLR_DARK_RED   = 4287299584   # 0xFF8B0000
_CLR_GREEN      = 4278236672   # 0xFF00C000
_CLR_DARK_GREEN = 4278218752   # 0xFF007000
_CLR_BLUE       = 4278222079   # 0xFF2080FF
_CLR_YELLOW     = 4294959360   # 0xFFFFD700  (gold)
_CLR_ORANGE     = 4294937600   # 0xFFFF8C00
_CLR_CYAN       = 4278255615   # 0xFF00FFFF
_CLR_MAGENTA    = 4294902015   # 0xFFFF00FF
_CLR_PURPLE     = 4287889619   # 0xFF9400D3
_CLR_WHITE      = 4294967295   # 0xFFFFFFFF
_CLR_BLACK      = 4278190080   # 0xFF000000
_CLR_WARM       = 4294950656   # 0xFFBF8F00  (warm amber)
_CLR_DARK_GRAY  = 4281611316   # 0xFF303034
_CLR_MID_GRAY   = 4284572001   # 0xFF5A5A61
_CLR_LIGHT_GRAY = 4290032820   # 0xFFB0B0B4

# StopAll special function ID (QLC+ constant for "no function — stop all")
_STOP_ALL_FID   = 4294967295   # 0xFFFFFFFF


# ═════════════════════════════════════════════════════════════════════════════
# ID counter — keeps function / widget IDs unique within one generation
# ═════════════════════════════════════════════════════════════════════════════

class _IDCounter:
    def __init__(self, start: int = 0):
        self._next = start

    def next(self) -> int:
        val = self._next
        self._next += 1
        return val


# ═════════════════════════════════════════════════════════════════════════════
# Function builders  (Scene / Chaser / RGBMatrix XML elements)
# ═════════════════════════════════════════════════════════════════════════════

def _build_scene(func_id: int, name: str,
                 fixture_channels: Dict[int, List[Tuple[int, int]]],
                 fade_in: int = 0, fade_out: int = 0) -> ET.Element:
    """
    Build a <Function Type="Scene"> element.

    fixture_channels: {fixture_id: [(ch_index, value), ...]}
        One entry per fixture. ALL channels for each fixture should be
        included (forced zeros for unused channels).
    """
    func = ET.Element(_ns("Function"))
    func.set("ID", str(func_id))
    func.set("Type", "Scene")
    func.set("Name", name)
    _sub(func, "Speed", FadeIn=str(fade_in), FadeOut=str(fade_out),
         Duration="0")
    for fid in sorted(fixture_channels.keys()):
        ch_vals = fixture_channels[fid]
        # Sort by channel index and format as "ch0,val0,ch1,val1,..."
        ch_vals_sorted = sorted(ch_vals, key=lambda x: x[0])
        pairs = ",".join(f"{ch},{val}" for ch, val in ch_vals_sorted)
        fv = _sub(func, "FixtureVal", ID=str(fid))
        fv.text = pairs
    return func


def _build_chaser(func_id: int, name: str,
                  step_func_ids: List[int],
                  fade_in: int = 500, fade_out: int = 500,
                  duration: int = 1000) -> ET.Element:
    """Build a <Function Type="Chaser"> element."""
    func = ET.Element(_ns("Function"))
    func.set("ID", str(func_id))
    func.set("Type", "Chaser")
    func.set("Name", name)
    _sub(func, "Speed",
         FadeIn=str(fade_in), FadeOut=str(fade_out),
         Duration=str(duration))
    _sub(func, "Direction", "Forward")
    _sub(func, "RunOrder", "Loop")
    _sub(func, "SpeedModes",
         FadeIn="Default", FadeOut="Default", Duration="Common")
    for i, sfid in enumerate(step_func_ids):
        step = _sub(func, "Step", Number=str(i), FadeIn="0",
                    Hold="0", FadeOut="0")
        step.text = str(sfid)
    return func


def _build_rgbmatrix(func_id: int, name: str,
                     fixture_group_id: int,
                     algorithm: str = "Stripes",
                     color0: int = _CLR_RED,
                     color1: int = None,
                     duration: int = 1000,
                     fade_in: int = 0, fade_out: int = 0,
                     direction: str = "Forward",
                     run_order: str = "Loop",
                     properties: Dict[str, str] = None) -> ET.Element:
    """Build a <Function Type="RGBMatrix"> element."""
    func = ET.Element(_ns("Function"))
    func.set("ID", str(func_id))
    func.set("Type", "RGBMatrix")
    func.set("Name", name)
    _sub(func, "Speed", FadeIn=str(fade_in), FadeOut=str(fade_out),
         Duration=str(duration))
    _sub(func, "Direction", direction)
    _sub(func, "RunOrder", run_order)
    algo = _sub(func, "Algorithm", Type="Script")
    algo.text = algorithm
    _sub(func, "DimmerControl", "1")
    _sub(func, "Color", str(color0), Index="0")
    if color1 is not None:
        _sub(func, "Color", str(color1), Index="1")
    _sub(func, "ControlMode", "RGB")
    _sub(func, "FixtureGroup", str(fixture_group_id))
    if properties:
        for pname, pval in properties.items():
            _sub(func, "Property", Name=pname, Value=pval)
    return func


# ═════════════════════════════════════════════════════════════════════════════
# VC widget builders
# ═════════════════════════════════════════════════════════════════════════════

def _vc_frame(wid: int, name: str, x: int, y: int, w: int, h: int,
              caption: str = None, header: bool = True,
              bg_color: int = None, font: str = "") -> ET.Element:
    frame = ET.Element(_ns("Frame"))
    frame.set("Caption", caption or name)
    frame.set("ID", str(wid))
    ws = _sub(frame, "WindowState")
    ws.set("Visible", "True")
    ws.set("X", str(x)); ws.set("Y", str(y))
    ws.set("Width", str(w)); ws.set("Height", str(h))
    app = _sub(frame, "Appearance")
    _sub(app, "FrameStyle", "Sunken")
    if bg_color is not None:
        _sub(app, "BackgroundColor", str(bg_color))
    if font:
        _sub(app, "Font", font)
    _sub(frame, "ShowHeader", "True" if header else "False")
    return frame


def _vc_solo_frame(wid: int, name: str, x: int, y: int, w: int, h: int,
                   caption: str = None, header: bool = True,
                   bg_color: int = None, font: str = "") -> ET.Element:
    """Build a SoloFrame — same as Frame but ensures mutual exclusivity."""
    frame = ET.Element(_ns("SoloFrame"))
    frame.set("Caption", caption or name)
    frame.set("ID", str(wid))
    ws = _sub(frame, "WindowState")
    ws.set("Visible", "True")
    ws.set("X", str(x)); ws.set("Y", str(y))
    ws.set("Width", str(w)); ws.set("Height", str(h))
    app = _sub(frame, "Appearance")
    _sub(app, "FrameStyle", "Sunken")
    if bg_color is not None:
        _sub(app, "BackgroundColor", str(bg_color))
    if font:
        _sub(app, "Font", font)
    _sub(frame, "ShowHeader", "True" if header else "False")
    return frame


def _vc_button(wid: int, caption: str, func_id: int, func_type: str,
               x: int, y: int, w: int = 120, h: int = 60,
               bg_color: int = None, fg_color: int = None,
               action: str = "Toggle", font: str = "") -> ET.Element:
    btn = ET.Element(_ns("Button"))
    btn.set("Caption", caption)
    btn.set("ID", str(wid))
    btn.set("Icon", "")
    ws = _sub(btn, "WindowState")
    ws.set("Visible", "True")
    ws.set("X", str(x)); ws.set("Y", str(y))
    ws.set("Width", str(w)); ws.set("Height", str(h))
    app = _sub(btn, "Appearance")
    _sub(app, "FrameStyle", "None")
    if bg_color is not None:
        _sub(app, "BackgroundColor", str(bg_color))
    if fg_color is not None:
        _sub(app, "ForegroundColor", str(fg_color))
    if font:
        _sub(app, "Font", font)
    _sub(btn, "Function", ID=str(func_id))
    _sub(btn, "Action", action)
    _sub(btn, "Intensity", Adjust="False")
    return btn


def _vc_slider(wid: int, caption: str, x: int, y: int,
               w: int = 60, h: int = 200,
               slider_mode: str = "Level",
               level_low: int = 0, level_high: int = 255,
               value: int = None,
               channels: List[Tuple[int, int]] = None) -> ET.Element:
    """Build a VC Slider widget (e.g. master dimmer)."""
    sl = ET.Element(_ns("Slider"))
    sl.set("Caption", caption)
    sl.set("ID", str(wid))
    ws = _sub(sl, "WindowState")
    ws.set("Visible", "True")
    ws.set("X", str(x)); ws.set("Y", str(y))
    ws.set("Width", str(w)); ws.set("Height", str(h))
    app = _sub(sl, "Appearance")
    _sub(app, "FrameStyle", "Sunken")
    if slider_mode == "Submaster":
        # Submaster scales every function started from widgets in the same
        # frame (as in the 20Minutes shows); it never *sets* a channel.
        _sub(sl, "SliderMode", slider_mode, ValueDisplayStyle="Percentage")
    else:
        _sub(sl, "SliderMode", slider_mode,
             ValueDisplayStyle="Exact", ClickAndGoType="None",
             Monitor="false")
    init_val = value if value is not None else level_high
    level = _sub(sl, "Level",
                 LowLimit=str(level_low), HighLimit=str(level_high),
                 Value=str(init_val))
    if channels:
        for fix_id, ch_idx in channels:
            _sub(level, "Channel", str(ch_idx), Fixture=str(fix_id))
    return sl


def _update_ws(elem: ET.Element, x: int, y: int):
    """Update the WindowState X/Y on an existing widget element."""
    ws = elem.find(_ns("WindowState"))
    if ws is not None:
        ws.set("X", str(x))
        ws.set("Y", str(y))


# ═════════════════════════════════════════════════════════════════════════════
# Main generator
# ═════════════════════════════════════════════════════════════════════════════

class VCLayoutGenerator:
    """
    Generate a complete VC layout with backing functions from a rig
    and its capability analysis.

    Usage::

        gen = VCLayoutGenerator(rig, qxf_defs, analysis)
        functions, vc_root, fixture_groups = gen.generate()
    """

    def __init__(self, rig: list, qxf_defs: dict,
                 analysis: RigCapabilityAnalysis,
                 nomenclature=None, style=None):
        self.rig = rig
        self.qxf_defs = qxf_defs
        self.analysis = analysis
        self.nom: Nomenclature = (nomenclature if isinstance(nomenclature, Nomenclature)
                                  else load_profile(nomenclature))
        self.style: VCStyle = load_style(style)
        self.functions: List[ET.Element] = []
        self.fixture_groups: List[ET.Element] = []
        self._fid = _IDCounter(start=len(rig))  # functions start after fixture IDs
        self._wid = _IDCounter(start=0)
        # Fixture group IDs start at 1 (0 is "All Fixtures" in qxw_builder)
        self._fg_id = _IDCounter(start=1)

    def _n(self, base: str, category: str = "all", kind: str = "static") -> str:
        """Function name according to the nomenclature profile."""
        return self.nom.name(base, category, kind)

    def _next_fid(self) -> int:
        return self._fid.next()

    def _next_wid(self) -> int:
        return self._wid.next()

    # ── Channel index helpers ─────────────────────────────────────────────

    def _mode_channels(self, rig_idx: int) -> List[str]:
        entry = self.rig[rig_idx]
        return mode_channels(entry, self.qxf_defs.get(entry.get("key", ""), {}))

    def _channel_index(self, rig_idx: int, pattern_name: str) -> Optional[int]:
        """0-based index of a channel within the fixture's *mode*.

        Exact name first, then a case-insensitive substring match.
        """
        channels = self._mode_channels(rig_idx)
        if pattern_name in channels:
            return channels.index(pattern_name)
        for i, ch in enumerate(channels):
            if pattern_name.lower() in ch.lower():
                return i
        return None

    def _neutral(self, rig_idx: int) -> Dict[int, int]:
        entry = self.rig[rig_idx]
        return neutral_map(entry, self.qxf_defs.get(entry.get("key", ""), {}))

    def _shutter_closed(self, rig_idx: int) -> Dict[int, int]:
        """{index: closed value} for shutter channels that can close."""
        entry = self.rig[rig_idx]
        defn = self.qxf_defs.get(entry.get("key", ""), {})
        defs = defn.get("channel_defs") or {}
        out = {}
        for i, n in enumerate(self._mode_channels(rig_idx)):
            d = defs.get(n) or {}
            if (d.get("group") or "").lower() == "shutter":
                cv = closed_value(d)
                if cv is not None:
                    out[i] = cv
        return out

    def _dimmer_index(self, rig_idx: int) -> Optional[int]:
        caps = self.analysis.fixture_caps[rig_idx]
        name = caps.dimmer_channel_name()
        if not name:
            return None
        return self._channel_index(rig_idx, name)

    def _rgb_indices(self, rig_idx: int) -> Optional[Dict[str, int]]:
        caps = self.analysis.fixture_caps[rig_idx]
        names = caps.rgb_channel_names()
        if not names:
            return None
        result = {}
        for color_key, ch_name in names.items():
            idx = self._channel_index(rig_idx, ch_name)
            if idx is not None:
                result[color_key] = idx
        return result if len(result) == 3 else None

    def _strobe_index(self, rig_idx: int) -> Optional[int]:
        caps = self.analysis.fixture_caps[rig_idx]
        name = caps.strobe_channel_name()
        if not name:
            return None
        return self._channel_index(rig_idx, name)

    def _ch_count(self, rig_idx: int) -> int:
        return self.rig[rig_idx].get("ch_count", 1)

    # ── Full-fixture channel value builder ────────────────────────────────

    def _set_channels(self, rig_idx: int,
                      overrides: Dict[int, int]) -> List[Tuple[int, int]]:
        """
        Build a full channel list for a fixture: every channel at its
        neutral value except those specified in `overrides`.
        """
        neutral = self._neutral(rig_idx)
        vals = {ch: neutral.get(ch, 0) for ch in range(self._ch_count(rig_idx))}
        vals.update(overrides)
        return [(ch, v) for ch, v in sorted(vals.items())]

    # ── Scene builders (forced zeros on ALL fixtures) ─────────────────────

    def _create_full_scene(self, name: str,
                           per_fixture_overrides: Dict[int, Dict[int, int]],
                           fade_in: int = 0, fade_out: int = 0) -> int:
        """
        Create a scene that sets ALL channels on ALL fixtures.

        per_fixture_overrides: {fixture_idx: {ch_index: value, ...}}
            Only the channels the look uses need to be specified;
            everything else gets its neutral value.
        """
        fid = self._next_fid()
        fixture_channels = {}
        for idx in range(len(self.rig)):
            overrides = per_fixture_overrides.get(idx, {})
            fixture_channels[idx] = self._set_channels(idx, overrides)
        self.functions.append(
            _build_scene(fid, name, fixture_channels, fade_in, fade_out))
        return fid

    def _create_all_on_scene(self, name: str = None) -> int:
        overrides = {}
        for idx in range(len(self.rig)):
            o = {}
            di = self._dimmer_index(idx)
            if di is not None:
                o[di] = 255
            # Also turn on RGB to white if available
            rgb = self._rgb_indices(idx)
            if rgb:
                o[rgb["red"]] = 255
                o[rgb["green"]] = 255
                o[rgb["blue"]] = 255
            overrides[idx] = o
        return self._create_full_scene(name or self._n("ALL ON"), overrides)

    def _create_blackout_scene(self, name: str = None) -> int:
        """Blackout: dimmers/colours at 0; fixtures without a dimmer
        channel also get their shutter closed."""
        return self._create_full_scene(name or self._n("BLACKOUT", kind="utility"),
                                       self._dark_overrides())

    def _dark_overrides(self) -> Dict[int, Dict[int, int]]:
        out = {}
        for idx in range(len(self.rig)):
            if self._dimmer_index(idx) is None:
                out[idx] = self._shutter_closed(idx)
        return out

    def _create_panic_reset_scene(self) -> int:
        """The PANIC RESET *state*: every fixture neutral (shutter open, no
        effects, Pan/Tilt centred) with intensity at 0."""
        return self._create_full_scene(self._n("Reset: neutral state", kind="utility"),
                                       self._dark_overrides())

    def _create_panic_reset_script(self, reset_scene: int) -> int:
        """PANIC RESET: a Script that stops every generated function and then
        starts the neutral scene.

        A scene alone cannot do it: intensity/colour channels are HTP in
        QLC+, so a scene at 0 does not pull down a look that is still
        running.  Stopping everything first releases them; the neutral
        scene then clears the LTP channels (shutter, programs, position).
        Commands are percent-encoded, as QLC+ writes them.
        """
        fid = self._next_fid()
        func = ET.Element(_ns("Function"))
        func.set("ID", str(fid))
        func.set("Type", "Script")
        func.set("Name", self._n("PANIC RESET", kind="utility"))
        _sub(func, "Speed", FadeIn="0", FadeOut="0", Duration="0")
        _sub(func, "Direction", "Forward")
        _sub(func, "RunOrder", "SingleShot")
        ids = [int(f.get("ID")) for f in self.functions]
        for i in sorted(ids):
            _sub(func, "Command", f"stopfunction%3A{i}")
        _sub(func, "Command", f"startfunction%3A{reset_scene}")
        self.functions.append(func)
        return fid

    def _create_warm_white_scene(self) -> int:
        overrides = {}
        for idx in range(len(self.rig)):
            o = {}
            di = self._dimmer_index(idx)
            if di is not None:
                o[di] = 255
            rgb = self._rgb_indices(idx)
            if rgb:
                o[rgb["red"]] = 255
                o[rgb["green"]] = 200
                o[rgb["blue"]] = 0
            overrides[idx] = o
        return self._create_full_scene(self._n("Warm White"), overrides)

    def _create_cold_white_scene(self) -> int:
        overrides = {}
        for idx in range(len(self.rig)):
            o = {}
            di = self._dimmer_index(idx)
            if di is not None:
                o[di] = 255
            rgb = self._rgb_indices(idx)
            if rgb:
                o[rgb["red"]] = 255
                o[rgb["green"]] = 255
                o[rgb["blue"]] = 255
            overrides[idx] = o
        return self._create_full_scene(self._n("Cold White"), overrides)

    def _create_color_scene(self, name: str, r: int, g: int, b: int) -> int:
        overrides = {}
        for idx in range(len(self.rig)):
            o = {}
            di = self._dimmer_index(idx)
            if di is not None:
                o[di] = 255
            rgb = self._rgb_indices(idx)
            if rgb:
                o[rgb["red"]] = r
                o[rgb["green"]] = g
                o[rgb["blue"]] = b
            overrides[idx] = o
        return self._create_full_scene(name, overrides)

    def _create_strobe_scene(self, name: str = "Strobe",
                             strobe_val: int = 200) -> int:
        overrides = {}
        for idx in range(len(self.rig)):
            o = {}
            si = self._strobe_index(idx)
            if si is not None:
                o[si] = strobe_val
            di = self._dimmer_index(idx)
            if di is not None:
                o[di] = 255
            # Set RGB to white so strobe is visible
            rgb = self._rgb_indices(idx)
            if rgb:
                o[rgb["red"]] = 255
                o[rgb["green"]] = 255
                o[rgb["blue"]] = 255
            overrides[idx] = o
        return self._create_full_scene(name, overrides)

    def _create_group_scene(self, group_name: str,
                            fixture_indices: List[int]) -> int:
        display = {
            "moving_heads":   "Moving Heads",
            "color_fixtures": "Color Fixtures",
            "dimmers_only":   "Dimmers",
            "other":          "Other",
        }.get(group_name, group_name)
        overrides = {}
        for idx in range(len(self.rig)):
            o = {}
            if idx in fixture_indices:
                di = self._dimmer_index(idx)
                if di is not None:
                    o[di] = 255
                rgb = self._rgb_indices(idx)
                if rgb:
                    o[rgb["red"]] = 255
                    o[rgb["green"]] = 255
                    o[rgb["blue"]] = 255
            # else: all zeros (fixture not in this group)
            overrides[idx] = o
        return self._create_full_scene(self._n(display, group_name), overrides)

    # ── Chaser builders ───────────────────────────────────────────────────

    def _create_dimmer_sweep_chaser(self) -> int:
        s_on  = self._create_all_on_scene(self._n("Dimmer Sweep: On", kind="pulse"))
        s_off = self._create_blackout_scene(self._n("Dimmer Sweep: Off", kind="pulse"))
        fid = self._next_fid()
        self.functions.append(
            _build_chaser(fid, self._n("Dimmer Sweep", kind="pulse"), [s_off, s_on],
                          fade_in=1000, fade_out=1000, duration=500))
        return fid

    def _create_color_fade_chaser(self) -> int:
        s_r = self._create_color_scene(self._n("Color Fade: Red", kind="dynamic"),     255,   0,   0)
        s_g = self._create_color_scene(self._n("Color Fade: Green", kind="dynamic"),     0, 255,   0)
        s_b = self._create_color_scene(self._n("Color Fade: Blue", kind="dynamic"),      0,   0, 255)
        s_y = self._create_color_scene(self._n("Color Fade: Yellow", kind="dynamic"),  255, 255,   0)
        s_m = self._create_color_scene(self._n("Color Fade: Magenta", kind="dynamic"), 255,   0, 255)
        s_c = self._create_color_scene(self._n("Color Fade: Cyan", kind="dynamic"),      0, 255, 255)
        fid = self._next_fid()
        self.functions.append(
            _build_chaser(fid, self._n("Color Fade", kind="dynamic"),
                          [s_r, s_y, s_g, s_c, s_b, s_m],
                          fade_in=2000, fade_out=0, duration=1000))
        return fid

    def _create_strobe_chaser(self, name: str, on_ms: int, off_ms: int) -> int:
        s_on  = self._create_strobe_scene(self._n(f"{name}: On", kind="fx"))
        s_off = self._create_blackout_scene(self._n(f"{name}: Off", kind="fx"))
        fid = self._next_fid()
        self.functions.append(
            _build_chaser(fid, self._n(name, kind="fx"), [s_on, s_off],
                          fade_in=0, fade_out=0, duration=on_ms))
        return fid

    # ── RGBMatrix builders ───────────────────────────────────────────────

    def _create_fixture_group_for_rgb(self) -> int:
        """Create a FixtureGroup with RGB-capable fixtures for RGBMatrix."""
        gid = self._fg_id.next()
        rgb_indices = []
        for idx in range(len(self.rig)):
            caps = self.analysis.fixture_caps[idx]
            if caps.has_rgb():
                rgb_indices.append(idx)
        if not rgb_indices:
            rgb_indices = list(range(len(self.rig)))

        fg = ET.Element(_ns("FixtureGroup"))
        fg.set("ID", str(gid))
        _sub(fg, "Name", "RGB Fixtures")
        _sub(fg, "Size", X=str(len(rgb_indices)), Y="1")
        for i, fix_idx in enumerate(rgb_indices):
            head = _sub(fg, "Head", X=str(i), Y="0", Fixture=str(fix_idx))
            head.text = "0"
        self.fixture_groups.append(fg)
        return gid

    def _create_fixture_group_vertical(self) -> int:
        """Create a vertical (1xN) FixtureGroup for vertical RGBMatrix effects."""
        gid = self._fg_id.next()
        rgb_indices = []
        for idx in range(len(self.rig)):
            caps = self.analysis.fixture_caps[idx]
            if caps.has_rgb():
                rgb_indices.append(idx)
        if not rgb_indices:
            rgb_indices = list(range(len(self.rig)))
        fg = ET.Element(_ns("FixtureGroup"))
        fg.set("ID", str(gid))
        _sub(fg, "Name", "RGB Fixtures (Vertical)")
        _sub(fg, "Size", X="1", Y=str(len(rgb_indices)))
        for i, fix_idx in enumerate(rgb_indices):
            head = _sub(fg, "Head", X="0", Y=str(i), Fixture=str(fix_idx))
            head.text = "0"
        self.fixture_groups.append(fg)
        return gid

    def _create_rgbmatrix_effects(self, fg_id: int, fg_id_v: int = None) -> List[Tuple[str, int]]:
        """Create RGBMatrix template effects. Returns [(name, fid), ...]."""
        effects = []

        # Stripes H (red/blue)
        fid = self._next_fid()
        self.functions.append(_build_rgbmatrix(
            fid, self._n("Stripes H (Red/Blue)", kind="matrix"), fg_id,
            algorithm="Stripes", color0=_CLR_RED, color1=4278190335,
            duration=800, properties={"orientation": "Horizontal"}))
        effects.append(("Stripes H", fid))

        # Stripes V (green/magenta) — vertical group for correct direction
        fid = self._next_fid()
        self.functions.append(_build_rgbmatrix(
            fid, self._n("Stripes V (Green/Mag)", kind="matrix"), fg_id_v or fg_id,
            algorithm="Stripes", color0=_CLR_GREEN, color1=_CLR_MAGENTA,
            duration=800, properties={"orientation": "Vertical"}))
        effects.append(("Stripes V", fid))

        # Plasma (red)
        fid = self._next_fid()
        self.functions.append(_build_rgbmatrix(
            fid, self._n("Plasma", kind="matrix"), fg_id,
            algorithm="Plasma", color0=_CLR_RED, duration=500))
        effects.append(("Plasma", fid))

        # Gradient (cyan/purple)
        fid = self._next_fid()
        self.functions.append(_build_rgbmatrix(
            fid, self._n("Gradient", kind="matrix"), fg_id,
            algorithm="Gradient", color0=_CLR_CYAN, color1=_CLR_PURPLE,
            duration=1200))
        effects.append(("Gradient", fid))

        # Waves (blue)
        fid = self._next_fid()
        self.functions.append(_build_rgbmatrix(
            fid, self._n("Waves", kind="matrix"), fg_id,
            algorithm="Waves", color0=_CLR_BLUE, duration=600))
        effects.append(("Waves", fid))

        # Full Row (orange) — vertical group so row sweeps across fixtures
        fid = self._next_fid()
        self.functions.append(_build_rgbmatrix(
            fid, self._n("Full Row", kind="matrix"), fg_id_v or fg_id,
            algorithm="Full Row", color0=_CLR_ORANGE, duration=1000))
        effects.append(("Full Row", fid))

        return effects

    # ── Main generation ───────────────────────────────────────────────────

    def generate(self) -> Tuple[List[ET.Element], ET.Element, List[ET.Element]]:
        """
        Generate the complete VC layout and backing functions.

        Returns
        -------
        (functions, vc_frame, fixture_groups)
            functions       : list of <Function> XML elements
            vc_frame        : root <Frame> XML element for the Virtual Console
            fixture_groups  : list of <FixtureGroup> XML elements (for RGBMatrix)
        """
        self.functions = []
        self.fixture_groups = []
        groups = self.analysis.group_by_type()

        st = self.style
        pad = st.gap
        hdr = st.header_h           # room for a frame's header before content
        btn_h = st.btn_h
        btn_w = st.btn_w

        # ── STATIC LOOKS (SoloFrame — mutual exclusivity) ────────────────
        static_entries = []   # (caption, fid, bg, fg)

        fid_on = self._create_all_on_scene()
        static_entries.append(("ALL ON", fid_on, _CLR_GREEN, _CLR_WHITE))

        fid_ww = self._create_warm_white_scene()
        static_entries.append(("Warm White", fid_ww, _CLR_WARM, _CLR_BLACK))

        fid_cw = self._create_cold_white_scene()
        static_entries.append(("Cold White", fid_cw, _CLR_LIGHT_GRAY, _CLR_BLACK))

        if self.analysis.has_any_rgb():
            fid_r = self._create_color_scene(self._n("Red"),     255,   0,   0)
            static_entries.append(("Red", fid_r, _CLR_RED, _CLR_WHITE))
            fid_g = self._create_color_scene(self._n("Green"),     0, 255,   0)
            static_entries.append(("Green", fid_g, _CLR_GREEN, _CLR_BLACK))
            fid_b = self._create_color_scene(self._n("Blue"),      0,   0, 255)
            static_entries.append(("Blue", fid_b, _CLR_BLUE, _CLR_WHITE))
            fid_y = self._create_color_scene(self._n("Yellow"),  255, 255,   0)
            static_entries.append(("Yellow", fid_y, _CLR_YELLOW, _CLR_BLACK))
            fid_m = self._create_color_scene(self._n("Magenta"), 255,   0, 255)
            static_entries.append(("Magenta", fid_m, _CLR_MAGENTA, _CLR_BLACK))
            fid_c = self._create_color_scene(self._n("Cyan"),      0, 255, 255)
            static_entries.append(("Cyan", fid_c, _CLR_CYAN, _CLR_BLACK))
            fid_p = self._create_color_scene(self._n("Purple"),  148,   0, 211)
            static_entries.append(("Purple", fid_p, _CLR_PURPLE, _CLR_WHITE))

        # Blackout scene (inside SoloFrame so it cancels any active look)
        fid_bo = self._create_blackout_scene()
        static_entries.append(("BLACKOUT", fid_bo, _CLR_DARK_RED, _CLR_WHITE))

        cols = 3
        static_rows = (len(static_entries) + cols - 1) // cols
        static_w = cols * (btn_w + pad) + pad
        static_h = hdr + static_rows * (btn_h + pad) + pad

        static_solo = _vc_solo_frame(
            self._next_wid(), "STATIC LOOKS",
            0, 0, static_w, static_h)
        for si, (caption, fid, bg, fg) in enumerate(static_entries):
            sc = si % cols
            sr = si // cols
            x = pad + sc * (btn_w + pad)
            y = hdr + sr * (btn_h + pad)
            static_solo.append(
                _vc_button(self._next_wid(), caption, fid, "Scene",
                           x, y, btn_w, btn_h,
                           bg_color=bg, fg_color=fg))

        # ── DYNAMIC EFFECTS (SoloFrame) ──────────────────────────────────
        effect_entries = []  # (caption, fid, ftype, bg, fg)

        fid_sweep = self._create_dimmer_sweep_chaser()
        effect_entries.append(("Dimmer Sweep", fid_sweep, "Chaser",
                               _CLR_ORANGE, _CLR_BLACK))

        if self.analysis.has_any_rgb():
            fid_cfade = self._create_color_fade_chaser()
            effect_entries.append(("Color Fade", fid_cfade, "Chaser",
                                   _CLR_PURPLE, _CLR_WHITE))

        if self.analysis.has_any_strobe():
            fid_slow = self._create_strobe_chaser("Strobe Slow", 200, 200)
            effect_entries.append(("Strobe Slow", fid_slow, "Chaser",
                                   _CLR_YELLOW, _CLR_BLACK))
            fid_fast = self._create_strobe_chaser("Strobe Fast", 50, 50)
            effect_entries.append(("Strobe Fast", fid_fast, "Chaser",
                                   _CLR_RED, _CLR_WHITE))

        # RGBMatrix effects (if we have RGB-capable fixtures)
        if self.analysis.has_any_rgb():
            fg_id = self._create_fixture_group_for_rgb()
            fg_id_v = self._create_fixture_group_vertical()
            rgbm_effects = self._create_rgbmatrix_effects(fg_id, fg_id_v)
            _RGBM_COLORS = [
                (_CLR_RED,    _CLR_WHITE),
                (_CLR_GREEN,  _CLR_BLACK),
                (_CLR_PURPLE, _CLR_WHITE),
                (_CLR_CYAN,   _CLR_BLACK),
                (_CLR_BLUE,   _CLR_WHITE),
                (_CLR_ORANGE, _CLR_BLACK),
            ]
            for i, (ename, efid) in enumerate(rgbm_effects):
                bg, fg = _RGBM_COLORS[i % len(_RGBM_COLORS)]
                effect_entries.append((ename, efid, "RGBMatrix", bg, fg))

        eff_cols = 3
        eff_rows = max((len(effect_entries) + eff_cols - 1) // eff_cols, 1)
        eff_w = eff_cols * (btn_w + pad) + pad
        eff_h = hdr + eff_rows * (btn_h + pad) + pad

        effects_solo = _vc_solo_frame(
            self._next_wid(), "DYNAMIC / EFFECTS",
            0, static_h + pad, eff_w, eff_h)
        for ei, (caption, fid, ftype, bg, fg) in enumerate(effect_entries):
            ec = ei % eff_cols
            er = ei // eff_cols
            x = pad + ec * (btn_w + pad)
            y = hdr + er * (btn_h + pad)
            effects_solo.append(
                _vc_button(self._next_wid(), caption, fid, ftype,
                           x, y, btn_w, btn_h,
                           bg_color=bg, fg_color=fg))

        # ── FIXTURE GROUPS (regular Frame) ────────────────────────────────
        active_groups = [(gn, gi) for gn, gi in groups.items() if gi]

        _GROUP_COLORS = {
            "moving_heads":   (_CLR_BLUE,       _CLR_WHITE),
            "color_fixtures": (_CLR_CYAN,        _CLR_BLACK),
            "dimmers_only":   (_CLR_YELLOW,      _CLR_BLACK),
            "other":          (_CLR_MID_GRAY,    _CLR_WHITE),
        }

        grp_rows = max(len(active_groups), 1)
        grp_w = 2 * btn_w + 3 * pad
        grp_h = hdr + grp_rows * (btn_h + pad) + pad

        groups_frame = _vc_frame(self._next_wid(), "FIXTURE GROUPS",
                                  0, static_h + pad + eff_h + pad,
                                  grp_w, grp_h)
        btn_y = hdr
        for gname, indices in active_groups:
            display = {
                "moving_heads":   "Moving Heads",
                "color_fixtures": "Color Fixtures",
                "dimmers_only":   "Dimmers",
                "other":          "Other",
            }.get(gname, gname)
            bg, fg = _GROUP_COLORS.get(gname, (_CLR_MID_GRAY, _CLR_WHITE))
            fid_g = self._create_group_scene(gname, indices)
            groups_frame.append(
                _vc_button(self._next_wid(), display, fid_g, "Scene",
                           pad, btn_y, 2 * btn_w + pad, btn_h,
                           bg_color=bg, fg_color=fg))
            btn_y += btn_h + pad

        # ── MASTER DIMMER SLIDER ─────────────────────────────────────────
        dimmer_channels = []
        for idx in range(len(self.rig)):
            di = self._dimmer_index(idx)
            if di is not None:
                dimmer_channels.append((idx, di))

        slider_w = st.slider_w
        slider_h = static_h + pad + eff_h + pad + grp_h
        # Submaster, not a Level slider on the dimmer channels: a Level slider
        # at 255 holds every dimmer at full (HTP), so BLACKOUT / PANIC RESET
        # could never bring intensity down.
        dimmer_slider = _vc_slider(
            self._next_wid(), "MASTER",
            0, 0, slider_w, slider_h,
            slider_mode="Submaster")

        # ── RGB + INTENSITY SLIDERS ───────────────────────────────────────
        rgb_sliders = []
        red_channels = []
        green_channels = []
        blue_channels = []
        for idx in range(len(self.rig)):
            rgb = self._rgb_indices(idx)
            if rgb:
                red_channels.append((idx, rgb["red"]))
                green_channels.append((idx, rgb["green"]))
                blue_channels.append((idx, rgb["blue"]))

        rgb_slider_w = max(slider_w - 10, 30)
        rgb_slider_h = slider_h  # same height as master
        if red_channels:
            sl_r = _vc_slider(self._next_wid(), "RED", 0, 0,
                              rgb_slider_w, rgb_slider_h,
                              slider_mode="Level", value=0, channels=red_channels)
            rgb_sliders.append(sl_r)
            sl_g = _vc_slider(self._next_wid(), "GREEN", 0, 0,
                              rgb_slider_w, rgb_slider_h,
                              slider_mode="Level", value=0, channels=green_channels)
            rgb_sliders.append(sl_g)
            sl_b = _vc_slider(self._next_wid(), "BLUE", 0, 0,
                              rgb_slider_w, rgb_slider_h,
                              slider_mode="Level", value=0, channels=blue_channels)
            rgb_sliders.append(sl_b)

        # ── PANIC button (StopAll) ───────────────────────────────────────
        panic_w = btn_w
        panic_h = max(80, btn_h)
        panic_btn = _vc_button(
            self._next_wid(),
            "PANIC\nBLACKOUT",
            _STOP_ALL_FID, "Scene",
            0, 0, panic_w, panic_h,
            bg_color=_CLR_DARK_RED, fg_color=_CLR_WHITE,
            action="StopAll")

        fid_reset = self._create_panic_reset_script(self._create_panic_reset_scene())
        reset_btn = _vc_button(
            self._next_wid(),
            "PANIC\nRESET",
            fid_reset, "Script",
            0, 0, panic_w, panic_h,
            bg_color=_CLR_ORANGE, fg_color=_CLR_BLACK)

        # ── Assemble main frame ──────────────────────────────────────────
        left_w = max(static_w, eff_w, grp_w)

        # RGB sliders go between master and the button panels
        rgb_block_w = len(rgb_sliders) * (rgb_slider_w + pad) if rgb_sliders else 0
        panels_x = slider_w + pad + rgb_block_w + pad
        right_col_x = panels_x + left_w + pad

        total_w = right_col_x + panic_w + pad
        left_h = static_h + pad + eff_h + pad + grp_h
        total_h = max(left_h, 2 * (panic_h + pad)) + hdr + pad
        # Reference page size (cloned style): the page is at least that big
        total_w = max(total_w, st.page_w)
        total_h = max(total_h, st.page_h)

        main_frame = _vc_frame(
            self._next_wid(), "Quick Start",
            0, 0, total_w, total_h,
            caption="Quick Start", font=st.font_page)

        # Position master slider on the far left
        _update_ws(dimmer_slider, pad, hdr)
        main_frame.append(dimmer_slider)

        # Position RGB sliders next to master
        for si, sl in enumerate(rgb_sliders):
            sx = slider_w + pad + si * (rgb_slider_w + pad)
            _update_ws(sl, sx, hdr)
            main_frame.append(sl)

        # Position static solo
        _update_ws(static_solo, panels_x, hdr)
        main_frame.append(static_solo)

        # Position effects solo
        _update_ws(effects_solo, panels_x,
                   hdr + static_h + pad)
        main_frame.append(effects_solo)

        # Position groups frame
        _update_ws(groups_frame, panels_x,
                   hdr + static_h + pad + eff_h + pad)
        main_frame.append(groups_frame)

        # Position panic button on the right side
        _update_ws(panic_btn, right_col_x, hdr)
        main_frame.append(panic_btn)
        _update_ws(reset_btn, right_col_x, hdr + panic_h + pad)
        main_frame.append(reset_btn)

        self._apply_fonts(main_frame)
        self._apply_caption_prefixes(main_frame)
        return self.functions, main_frame, self.fixture_groups

    def _apply_caption_prefixes(self, main_frame: ET.Element) -> None:
        """With ``prefix_captions``, a button shows its function's prefix
        too ("AS · Red") so the VC reads like the naming legend."""
        if not self.nom.prefix_captions:
            return
        names = {f.get("ID"): f.get("Name", "") for f in self.functions}
        for btn in main_frame.iter(_ns("Button")):
            fn = btn.find(_ns("Function"))
            pre = self.nom.prefix_of(names.get(fn.get("ID"), "")) if fn is not None else ""
            cap = btn.get("Caption", "")
            if pre and not cap.startswith(pre):
                btn.set("Caption", pre + cap)

    def _apply_fonts(self, main_frame: ET.Element) -> None:
        """Give buttons / inner frames the style's fonts (if any)."""
        st = self.style
        for el in main_frame.iter():
            tag = el.tag.split("}")[-1]
            font = (st.font_button if tag == "Button" else
                    st.font_frame if tag in ("Frame", "SoloFrame") and el is not main_frame
                    else "")
            if not font:
                continue
            app = el.find(_ns("Appearance"))
            if app is not None and app.find(_ns("Font")) is None:
                _sub(app, "Font", font)

    # ── Statistics ────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return counts of generated elements (call after generate())."""
        scenes  = sum(1 for f in self.functions
                      if f.get("Type") == "Scene")
        chasers = sum(1 for f in self.functions
                      if f.get("Type") == "Chaser")
        rgbm    = sum(1 for f in self.functions
                      if f.get("Type") == "RGBMatrix")
        return {
            "scenes":       scenes,
            "chasers":      chasers,
            "rgb_matrices": rgbm,
            "functions":    len(self.functions),
        }
