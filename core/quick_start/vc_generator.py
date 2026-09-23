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

import re
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
    # QLC+ 5 treats a missing InvertedAppearance as "true" (0 at the top)
    sl.set("WidgetStyle", "Slider")
    sl.set("InvertedAppearance", "false")
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
                 nomenclature=None, style=None, groups=None):
        self.rig = rig
        self.qxf_defs = qxf_defs
        self.analysis = analysis
        self.nom: Nomenclature = (nomenclature if isinstance(nomenclature, Nomenclature)
                                  else load_profile(nomenclature))
        self.style: VCStyle = load_style(style)
        # User-defined fixture groups [{name, fixtures:[rig idx]}]; None = auto
        self.groups = self._clean_groups(groups) if groups is not None else None
        self.page_size = (0, 0)
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

    # ── Scene builders (scope-aware) ──────────────────────────────────────
    #
    # A *scope* is a list of rig indices.  Whole-rig functions use every
    # fixture; group functions only the fixtures of that group.  A scene
    # declares every channel of every fixture in its scope (unused channels
    # at their neutral value) and leaves other fixtures alone.

    def _all(self) -> List[int]:
        return list(range(len(self.rig)))

    def _scene(self, name: str, overrides: Dict[int, Dict[int, int]],
               scope: Optional[List[int]] = None,
               fade_in: int = 0, fade_out: int = 0) -> int:
        fid = self._next_fid()
        idxs = self._all() if scope is None else list(scope)
        fixture_channels = {i: self._set_channels(i, overrides.get(i, {})) for i in idxs}
        self.functions.append(_build_scene(fid, name, fixture_channels, fade_in, fade_out))
        return fid

    # kept for callers / tests that use the old name
    def _create_full_scene(self, name: str,
                           per_fixture_overrides: Dict[int, Dict[int, int]],
                           fade_in: int = 0, fade_out: int = 0) -> int:
        return self._scene(name, per_fixture_overrides, None, fade_in, fade_out)

    def _light(self, idx: int, rgb: Optional[Tuple[int, int, int]] = (255, 255, 255),
               level: int = 255) -> Dict[int, int]:
        """Overrides that light fixture *idx* at *level* in colour *rgb*."""
        o: Dict[int, int] = {}
        di = self._dimmer_index(idx)
        if di is not None:
            o[di] = level
        ri = self._rgb_indices(idx)
        if ri and rgb:
            o[ri["red"]], o[ri["green"]], o[ri["blue"]] = rgb
        return o

    def _dark(self, idx: int) -> Dict[int, int]:
        """Overrides that keep fixture *idx* dark (shutter closed if it has
        no dimmer channel)."""
        return {} if self._dimmer_index(idx) is not None else self._shutter_closed(idx)

    def _color_scene(self, name: str, rgb, scope: Optional[List[int]] = None) -> int:
        idxs = self._all() if scope is None else scope
        return self._scene(name, {i: self._light(i, rgb) for i in idxs}, scope)

    def _dark_scene(self, name: str, scope: Optional[List[int]] = None) -> int:
        idxs = self._all() if scope is None else scope
        return self._scene(name, {i: self._dark(i) for i in idxs}, scope)

    def _create_all_on_scene(self, name: str = None) -> int:
        return self._color_scene(name or self._n("ALL ON"), (255, 255, 255))

    def _create_blackout_scene(self, name: str = None) -> int:
        """Blackout: dimmers/colours at 0; fixtures without a dimmer
        channel also get their shutter closed."""
        return self._dark_scene(name or self._n("BLACKOUT", kind="utility"))

    def _dark_overrides(self) -> Dict[int, Dict[int, int]]:
        return {i: self._dark(i) for i in self._all()}

    def _create_panic_reset_scene(self) -> int:
        """The PANIC RESET *state*: every fixture neutral (shutter open, no
        effects, Pan/Tilt centred) with intensity at 0."""
        return self._scene(self._n("Reset: neutral state", kind="utility"),
                           self._dark_overrides())

    def _create_panic_reset_script(self, reset_scene: int) -> int:
        """PANIC RESET: a Script that stops every generated function and then
        starts the neutral scene.

        A scene alone cannot do it: intensity/colour channels are HTP in
        QLC+, so a scene at 0 does not pull down a look that is still
        running.  Stopping everything first releases them; the neutral
        scene then clears the LTP channels (shutter, programs, position).
        Commands are percent-encoded, as QLC+ writes them
        (``QUrl::toPercentEncoding`` in Script::saveXML).
        """
        fid = self._next_fid()
        func = ET.Element(_ns("Function"))
        func.set("ID", str(fid))
        func.set("Type", "Script")
        func.set("Name", self._n("PANIC RESET", kind="utility"))
        _sub(func, "Speed", FadeIn="0", FadeOut="0", Duration="0")
        _sub(func, "Direction", "Forward")
        _sub(func, "RunOrder", "SingleShot")
        # A QLC+ Script stops every function it started when it ends
        # (stoponexit defaults to true, engine/src/script.cpp preRun) —
        # without this line the neutral scene is switched off at once.
        _sub(func, "Command", "stoponexit%3Afalse")
        ids = [int(f.get("ID")) for f in self.functions]
        for i in sorted(ids):
            if i != reset_scene:        # keep it if it's already running
                _sub(func, "Command", f"stopfunction%3A{i}")
        _sub(func, "Command", f"startfunction%3A{reset_scene}")
        # Give the engine time to carry out the queued start/stop commands.
        # QLC+ 5.2.2 drops them when the script code ends before the next
        # engine tick (fixed upstream in Aug 2026, qlcplus ca8ffd41).
        _sub(func, "Command", "wait%3A100ms")
        # Finally stop the script itself.  QLC+ 5 (at least up to spring
        # 2026) never ends a script on its own, so its Toggle button stayed
        # "on" and every second press just switched it off — nothing
        # happened.  Tested headless on QLC+ 4.12.7, 4.14.5 and 5.2.1.
        _sub(func, "Command", f"stopfunction%3A{fid}")
        self.functions.append(func)
        return fid

    # ── Chasers ───────────────────────────────────────────────────────────

    def _chaser(self, name: str, steps: List[int], fade_in: int, fade_out: int,
                duration: int) -> int:
        fid = self._next_fid()
        self.functions.append(_build_chaser(fid, name, steps, fade_in=fade_in,
                                            fade_out=fade_out, duration=duration))
        return fid

    def _dimmer_sweep(self, base: str, cat: str, scope=None) -> int:
        on = self._color_scene(self._n(f"{base}: On", cat, "pulse"), (255, 255, 255), scope)
        off = self._dark_scene(self._n(f"{base}: Off", cat, "pulse"), scope)
        return self._chaser(self._n(base, cat, "pulse"), [off, on], 1000, 1000, 500)

    _FADE_COLOURS = [("Red", (255, 0, 0)), ("Yellow", (255, 255, 0)),
                     ("Green", (0, 255, 0)), ("Cyan", (0, 255, 255)),
                     ("Blue", (0, 0, 255)), ("Magenta", (255, 0, 255))]

    def _color_fade(self, base: str, cat: str, scope=None) -> int:
        steps = [self._color_scene(self._n(f"{base}: {c}", cat, "dynamic"), rgb, scope)
                 for c, rgb in self._FADE_COLOURS]
        return self._chaser(self._n(base, cat, "dynamic"), steps, 2000, 0, 1000)

    def _create_strobe_scene(self, name: str = "Strobe", strobe_val: int = 200,
                             scope=None) -> int:
        idxs = self._all() if scope is None else scope
        ov = {}
        for i in idxs:
            o = self._light(i, (255, 255, 255))
            si = self._strobe_index(i)
            if si is not None:
                o[si] = strobe_val
            ov[i] = o
        return self._scene(name, ov, scope)

    def _strobe(self, base: str, cat: str, on_ms: int, scope=None) -> int:
        on = self._create_strobe_scene(self._n(f"{base}: On", cat, "fx"), scope=scope)
        off = self._dark_scene(self._n(f"{base}: Off", cat, "fx"), scope)
        return self._chaser(self._n(base, cat, "fx"), [on, off], 0, 0, on_ms)

    # ── Sound-active (the fixtures' own music mode) ──────────────────────

    _SOUND_RE = re.compile(r"sound|audio|music", re.IGNORECASE)

    def _sound_overrides(self, idx: int) -> Optional[Dict[int, int]]:
        """{channel: value} that puts fixture *idx* in its built-in
        sound-active mode (middle of the first "Sound/Audio/Music"
        capability in its mode), or None if it has none."""
        entry = self.rig[idx]
        defs = (self.qxf_defs.get(entry.get("key", ""), {}) or {}).get("channel_defs") or {}
        for ch, name in enumerate(self._mode_channels(idx)):
            for cap in (defs.get(name) or {}).get("capabilities") or []:
                if self._SOUND_RE.search(cap.get("label") or ""):
                    return {ch: (int(cap["min"]) + int(cap["max"])) // 2}
        return None

    def _sound_scope(self, scope=None) -> List[int]:
        idxs = self._all() if scope is None else scope
        return [i for i in idxs if self._sound_overrides(i)]

    def _sound_scene(self, name: str, scope=None) -> int:
        """Fixtures with a sound mode: full + sound mode on; the others in
        the scope stay dark.  The name must say "Audio" so Workspace Doctor
        treats the program channel as intentional (D006)."""
        idxs = self._all() if scope is None else scope
        ov = {}
        for i in idxs:
            snd = self._sound_overrides(i)
            ov[i] = {**self._light(i, (255, 255, 255)), **snd} if snd else self._dark(i)
        return self._scene(name, ov, scope)

    # ── RGB matrix effects ────────────────────────────────────────────────

    def _rgb_scope(self, scope=None) -> List[int]:
        idxs = self._all() if scope is None else scope
        return [i for i in idxs if self._rgb_indices(i)]

    def _fixture_group(self, name: str, idxs: List[int]) -> int:
        """QLC+ FixtureGroup (1 × N, ordered left → right on stage)."""
        key = tuple(idxs)
        if key in self._fg_cache:
            return self._fg_cache[key]
        order = sorted(idxs, key=lambda i: (self.rig[i].get("x_mm", 0), i))
        gid = self._fg_id.next()
        fg = ET.Element(_ns("FixtureGroup"))
        fg.set("ID", str(gid))
        _sub(fg, "Name", name)
        _sub(fg, "Size", X=str(len(order)), Y="1")
        for x, fix in enumerate(order):
            _sub(fg, "Head", "0", X=str(x), Y="0", Fixture=str(fix))
        self.fixture_groups.append(fg)
        self._fg_cache[key] = gid
        return gid

    def _matrix(self, base: str, cat: str, algorithm: str, colors: List[int],
                duration: int, scope=None, props: Dict[str, str] = None) -> int:
        """RGB matrix effect that is visible on fixtures with a master dimmer.

        QLC+ matrices in RGB mode only drive the colour channels (the
        DimmerControl flag is ignored in RGB mode, rgbmatrix.cpp), so a
        fixture with a dimmer stays dark.  The button therefore runs a
        Collection: a scene that opens the dimmers of the matrix fixtures +
        the matrix itself.
        """
        rgb = self._rgb_scope(scope)
        gid = self._fixture_group(f"QS · {cat.split(':', 1)[-1] if cat != 'all' else 'All RGB'}", rgb)
        mid = self._next_fid()
        self.functions.append(_build_rgbmatrix(
            mid, self._n(f"{base} (matrix)", cat, "matrix"), gid,
            algorithm=algorithm, color0=colors[0],
            color1=colors[1] if len(colors) > 1 else None,
            duration=duration, properties=props or {}))
        dim = self._scene(self._n(f"{base}: dimmers", cat, "matrix"),
                          {i: self._light(i, None) for i in rgb}, rgb)
        cid = self._next_fid()
        coll = ET.Element(_ns("Function"))
        coll.set("ID", str(cid))
        coll.set("Type", "Collection")
        coll.set("Name", self._n(base, cat, "matrix"))
        _sub(coll, "Speed", FadeIn="0", FadeOut="0", Duration="0")
        for n, f in enumerate((dim, mid)):
            _sub(coll, "Step", str(f), Number=str(n))
        self.functions.append(coll)
        return cid

    # Whole-rig matrix effects: (caption, script, colours, duration ms, props)
    _MATRIX_ALL = [
        ("Chase",     "One By One", [_CLR_RED],               300,  {}),
        ("Even/Odd",  "Even/Odd",   [_CLR_BLUE, _CLR_ORANGE], 600,  {}),
        ("Gradient",  "Gradient",   [_CLR_CYAN, _CLR_PURPLE], 1200, {}),
        # QLC+ 5 Plasma defaults to "User Defined" colours: with one colour
        # it is mostly black. "Rainbow" exists in QLC+ 4 and 5.
        ("Plasma",    "Plasma",     [_CLR_RED],               500,  {"presetIndex": "Rainbow"}),
        ("Waves",     "Waves",      [_CLR_BLUE],              600,  {}),
        ("Stripes",   "Stripes",    [_CLR_RED, _CLR_BLUE],    800,  {"orientation": "Horizontal"}),
    ]

    # ── Groups ────────────────────────────────────────────────────────────

    def _default_groups(self) -> List[dict]:
        """One group per fixture name ("Spot 1", "Spot 2" → "Spot")."""
        import re as _re
        groups: Dict[str, List[int]] = {}
        for i, e in enumerate(self.rig):
            base = _re.sub(r"\s*\d+$", "", e.get("name") or e.get("model") or "Group").strip()
            groups.setdefault(base or "Group", []).append(i)
        return [{"name": n, "fixtures": f} for n, f in groups.items()]

    def _clean_groups(self, groups) -> List[dict]:
        out, n = [], len(self.rig)
        for g in groups or []:
            idxs = sorted({int(i) for i in g.get("fixtures", []) if 0 <= int(i) < n})
            name = (g.get("name") or "").strip()
            if idxs and name:
                out.append({"name": name, "fixtures": idxs})
        return out

    # ── Main generation ───────────────────────────────────────────────────

    def generate(self) -> Tuple[List[ET.Element], ET.Element, List[ET.Element]]:
        """
        Generate the complete VC page and backing functions.

        Layout (one QLC+ page, sized to the VC style's page):

        * **MASTER** — submaster slider on the left: scales everything.
        * **SHOW** — one SoloFrame holding every look and effect, so pressing
          any button switches the previous one off (nothing mixes):

          - LOOKS (whole rig) and EFFECTS (whole rig);
          - one frame per fixture group: its own submaster slider, looks
            (on / colours) and effects (pulse, colour fade, chase).
        * **PANIC / BLACKOUT** (StopAll) and **PANIC RESET** on the right.

        Returns (functions, page_frame, fixture_groups).
        """
        self.functions = []
        self.fixture_groups = []
        self._fg_cache: Dict[tuple, int] = {}
        st = self.style
        pad, hdr, bw, bh = st.gap, st.header_h, st.btn_w, st.btn_h
        page_w = st.page_w or 1650
        page_h = st.page_h or 884
        groups = self.groups if self.groups is not None else self._default_groups()
        any_rgb = self.analysis.has_any_rgb()
        any_strobe = self.analysis.has_any_strobe()
        n_rgb_all = len(self._rgb_scope())

        # ── whole-rig looks ─────────────────────────────────────────────
        looks = [(self._n("ALL ON"), self._color_scene(self._n("ALL ON"), (255, 255, 255)),
                  "ALL ON", _CLR_GREEN, _CLR_WHITE)]
        looks.append(("", self._color_scene(self._n("Warm White"), (255, 160, 60)),
                      "Warm White", _CLR_WARM, _CLR_BLACK))
        looks.append(("", self._color_scene(self._n("Cold White"), (200, 220, 255)),
                      "Cold White", _CLR_LIGHT_GRAY, _CLR_BLACK))
        if any_rgb:
            for cap, rgb, bg, fg in (("Red", (255, 0, 0), _CLR_RED, _CLR_WHITE),
                                     ("Green", (0, 255, 0), _CLR_GREEN, _CLR_BLACK),
                                     ("Blue", (0, 0, 255), _CLR_BLUE, _CLR_WHITE),
                                     ("Yellow", (255, 255, 0), _CLR_YELLOW, _CLR_BLACK),
                                     ("Magenta", (255, 0, 255), _CLR_MAGENTA, _CLR_BLACK),
                                     ("Cyan", (0, 255, 255), _CLR_CYAN, _CLR_BLACK),
                                     ("Purple", (148, 0, 211), _CLR_PURPLE, _CLR_WHITE)):
                looks.append(("", self._color_scene(self._n(cap), rgb), cap, bg, fg))
        looks.append(("", self._create_blackout_scene(), "BLACKOUT", _CLR_DARK_RED, _CLR_WHITE))

        # ── whole-rig effects ───────────────────────────────────────────
        effects = [("", self._dimmer_sweep("Dimmer Sweep", "all"), "Dimmer Sweep",
                    _CLR_ORANGE, _CLR_BLACK)]
        if any_rgb:
            effects.append(("", self._color_fade("Color Fade", "all"), "Color Fade",
                            _CLR_PURPLE, _CLR_WHITE))
        if any_strobe:
            effects.append(("", self._strobe("Strobe Slow", "all", 200), "Strobe Slow",
                            _CLR_YELLOW, _CLR_BLACK))
            effects.append(("", self._strobe("Strobe Fast", "all", 50), "Strobe Fast",
                            _CLR_RED, _CLR_WHITE))
        if self._sound_scope():
            effects.append(("", self._sound_scene(self._n("Audio React", "all", "fx")),
                            "Audio React", _CLR_MAGENTA, _CLR_BLACK))
        if n_rgb_all >= 2:
            pal = [(_CLR_RED, _CLR_WHITE), (_CLR_BLUE, _CLR_WHITE), (_CLR_CYAN, _CLR_BLACK),
                   (_CLR_PURPLE, _CLR_WHITE), (_CLR_GREEN, _CLR_BLACK), (_CLR_ORANGE, _CLR_BLACK)]
            for k, (cap, algo, cols, dur, props) in enumerate(self._MATRIX_ALL):
                bg, fg = pal[k % len(pal)]
                effects.append(("", self._matrix(cap, "all", algo, cols, dur, None, props),
                                cap, bg, fg))

        # ── per-group looks + effects ───────────────────────────────────
        group_blocks = []   # (name, [(fid, caption, bg, fg)])
        for g in groups:
            scope, cat = g["fixtures"], f"group:{g['name']}"
            has_rgb = bool(self._rgb_scope(scope))
            btns = [(self._color_scene(self._n(f"{g['name']} On", cat), (255, 255, 255), scope),
                     "On", _CLR_GREEN, _CLR_WHITE)]
            if has_rgb:
                for cap, rgb, bg, fg in (("Red", (255, 0, 0), _CLR_RED, _CLR_WHITE),
                                         ("Blue", (0, 0, 255), _CLR_BLUE, _CLR_WHITE),
                                         ("Green", (0, 255, 0), _CLR_GREEN, _CLR_BLACK),
                                         ("Warm", (255, 160, 60), _CLR_WARM, _CLR_BLACK)):
                    btns.append((self._color_scene(self._n(f"{g['name']} {cap}", cat), rgb, scope),
                                 cap, bg, fg))
            btns.append((self._dimmer_sweep(f"{g['name']} Pulse", cat, scope), "Pulse",
                         _CLR_ORANGE, _CLR_BLACK))
            if has_rgb:
                btns.append((self._color_fade(f"{g['name']} Color Fade", cat, scope), "Color Fade",
                             _CLR_PURPLE, _CLR_WHITE))
            if len(self._rgb_scope(scope)) >= 2:
                btns.append((self._matrix(f"{g['name']} Chase", cat, "One By One", [_CLR_RED],
                                          300, scope), "Chase", _CLR_CYAN, _CLR_BLACK))
            if self._sound_scope(scope):
                btns.append((self._sound_scene(self._n(f"{g['name']} Audio React", cat, "fx"), scope),
                             "Audio React", _CLR_MAGENTA, _CLR_BLACK))
            group_blocks.append((g["name"], btns))

        # ── PANIC (last, so the reset script can stop everything) ───────
        fid_reset = self._create_panic_reset_script(self._create_panic_reset_scene())

        # ── layout ──────────────────────────────────────────────────────
        def grid(frame, entries, x0, y0, cols, w=bw):
            for k, (fid, cap, bg, fg) in enumerate(entries):
                c, r = k % cols, k // cols
                frame.append(_vc_button(self._next_wid(), cap, fid, "",
                                        x0 + c * (w + pad), y0 + r * (bh + pad), w, bh,
                                        bg_color=bg, fg_color=fg))

        def rows_h(n, cols):
            return hdr + max((n + cols - 1) // cols, 1) * (bh + pad) + pad

        master_w = st.slider_w
        right_w = bw
        show_x = pad + master_w + pad
        show_w = page_w - show_x - right_w - 2 * pad
        inner_w = show_w - 2 * pad

        # Row 1: LOOKS | EFFECTS, each half of the SHOW width
        half = (inner_w - pad) // 2
        cols1 = max(1, (half - pad) // (bw + pad))
        e_looks = [(f, c, b, g) for _, f, c, b, g in looks]
        e_fx = [(f, c, b, g) for _, f, c, b, g in effects]
        row1_h = max(rows_h(len(e_looks), cols1), rows_h(len(e_fx), cols1))

        # Row 2+: one frame per group, flowing left to right
        blocks = []
        for name, btns in group_blocks:
            gcols = max(1, min(3, (len(btns) + 2) // 3))
            gw = pad + st.slider_w + pad + gcols * (bw + pad)
            gh = max(rows_h(len(btns), gcols), hdr + 3 * (bh + pad) + pad)
            blocks.append((name, btns, gcols, gw, gh))
        # SHOW (whole rig) holds only LOOKS + EFFECTS; each group is its own
        # SoloFrame under it, so groups combine with each other (Front Red +
        # Floor Blue) while buttons inside one group stay one-at-a-time.
        show_h = hdr + pad + row1_h + pad
        gx0, gy0 = show_x, pad + show_h + pad
        placements, x, y, line_h = [], gx0, gy0, 0
        for b in blocks:
            if x > gx0 and x + b[3] > show_x + show_w:
                x, y, line_h = gx0, y + line_h + pad, 0
            placements.append((b, x, y))
            x += b[3] + pad
            line_h = max(line_h, b[4])
        bottom = (y + line_h) if blocks else pad + show_h
        page_h = max(page_h, bottom + pad)

        page = _vc_frame(self._next_wid(), "Quick Start", 0, 0, page_w, page_h,
                         caption="Quick Start", header=False, font=st.font_page)
        page.append(_vc_slider(self._next_wid(), "MASTER", pad, pad, master_w,
                               page_h - 2 * pad, slider_mode="Submaster"))
        show = _vc_solo_frame(self._next_wid(), "SHOW", show_x, pad, show_w, show_h,
                              caption="WHOLE RIG — one at a time")
        page.append(show)

        f_looks = _vc_frame(self._next_wid(), "LOOKS", pad, hdr + pad, half, row1_h)
        grid(f_looks, e_looks, pad, hdr, cols1)
        show.append(f_looks)
        f_fx = _vc_frame(self._next_wid(), "EFFECTS", pad + half + pad, hdr + pad, half, row1_h)
        grid(f_fx, e_fx, pad, hdr, cols1)
        show.append(f_fx)

        for (name, btns, gcols, gw, gh), gx, gy in placements:
            gf = _vc_solo_frame(self._next_wid(), f"GROUP · {name}", gx, gy, gw, gh)
            gf.append(_vc_slider(self._next_wid(), name.upper()[:10], pad, hdr,
                                 st.slider_w, gh - hdr - pad, slider_mode="Submaster"))
            grid(gf, btns, pad + st.slider_w + pad, hdr, gcols)
            page.append(gf)

        rx = page_w - pad - right_w
        ph = max(80, bh)
        page.append(_vc_button(self._next_wid(), "PANIC\nBLACKOUT", _STOP_ALL_FID, "",
                               rx, pad, right_w, ph, bg_color=_CLR_DARK_RED,
                               fg_color=_CLR_WHITE, action="StopAll"))
        page.append(_vc_button(self._next_wid(), "PANIC\nRESET", fid_reset, "",
                               rx, pad + ph + pad, right_w, ph,
                               bg_color=_CLR_ORANGE, fg_color=_CLR_BLACK))

        self.page_size = (page_w, page_h)
        self._apply_fonts(page)
        self._apply_caption_prefixes(page)
        return self.functions, page, self.fixture_groups

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
