"""
core/quick_start/vc_generator.py
=================================
Generate a complete QLC+ Virtual Console layout with backing functions
(Scenes, Chasers) from a rig + capability analysis.

Produces QLC+ XML elements directly — no intermediate widget classes
needed.  The output plugs straight into workspace_builder's QXW
serialisation.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from core.quick_start.fixture_analyzer import RigCapabilityAnalysis

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
# Function builders  (Scene / Chaser XML elements)
# ═════════════════════════════════════════════════════════════════════════════

def _build_scene(func_id: int, name: str,
                 fixture_values: List[Tuple[int, int, int]]) -> ET.Element:
    """
    Build a <Function Type="Scene"> element.

    fixture_values: [(fixture_id, channel_index, value), ...]
    """
    func = ET.Element(_ns("Function"))
    func.set("ID", str(func_id))
    func.set("Type", "Scene")
    func.set("Name", name)
    _sub(func, "Speed", FadeIn="0", FadeOut="0", Duration="0")
    for fid, ch, val in fixture_values:
        fv = _sub(func, "FixtureVal", ID=str(fid))
        fv.text = f"{ch},{val}"
    return func


def _build_chaser(func_id: int, name: str,
                  step_func_ids: List[int],
                  fade_in: int = 500, fade_out: int = 500,
                  duration: int = 1000) -> ET.Element:
    """
    Build a <Function Type="Chaser"> element.

    step_func_ids: list of function IDs to use as chaser steps.
    """
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


# ═════════════════════════════════════════════════════════════════════════════
# VC widget builders
# ═════════════════════════════════════════════════════════════════════════════

_WIDGET_ID = _IDCounter(0)   # reset per generation via generate()


def _vc_frame(wid: int, name: str, x: int, y: int, w: int, h: int,
              caption: str = None, header: bool = True,
              bg_color: int = None) -> ET.Element:
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
    if header:
        _sub(frame, "ShowHeader", "True")
    return frame


def _vc_button(wid: int, caption: str, func_id: int, func_type: str,
               x: int, y: int, w: int = 120, h: int = 60,
               bg_color: int = None, fg_color: int = None) -> ET.Element:
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
    _sub(btn, "Function", str(func_id), ID=str(func_id))
    if func_type == "Chaser":
        _sub(btn, "Action", "Toggle")
    else:
        _sub(btn, "Action", "Toggle")
    _sub(btn, "Intensity", Adjust="False")
    return btn


def _vc_label(wid: int, caption: str, x: int, y: int,
              w: int = 200, h: int = 30,
              bg_color: int = None, fg_color: int = None) -> ET.Element:
    """Build a VC Label widget (static text)."""
    lbl = ET.Element(_ns("Label"))
    lbl.set("Caption", caption)
    lbl.set("ID", str(wid))
    ws = _sub(lbl, "WindowState")
    ws.set("Visible", "True")
    ws.set("X", str(x)); ws.set("Y", str(y))
    ws.set("Width", str(w)); ws.set("Height", str(h))
    app = _sub(lbl, "Appearance")
    _sub(app, "FrameStyle", "None")
    if bg_color is not None:
        _sub(app, "BackgroundColor", str(bg_color))
    if fg_color is not None:
        _sub(app, "ForegroundColor", str(fg_color))
    return lbl


# ═════════════════════════════════════════════════════════════════════════════
# Main generator
# ═════════════════════════════════════════════════════════════════════════════

class VCLayoutGenerator:
    """
    Generate a complete VC layout with backing functions from a rig
    and its capability analysis.

    Usage::

        gen = VCLayoutGenerator(rig, qxf_defs, analysis)
        functions, vc_root = gen.generate()
    """

    def __init__(self, rig: list, qxf_defs: dict,
                 analysis: RigCapabilityAnalysis):
        self.rig = rig
        self.qxf_defs = qxf_defs
        self.analysis = analysis
        self.functions: List[ET.Element] = []
        self._fid = _IDCounter(start=len(rig))  # functions start after fixture IDs
        self._wid = _IDCounter(start=0)

    def _next_fid(self) -> int:
        return self._fid.next()

    def _next_wid(self) -> int:
        return self._wid.next()

    # ── Channel index helpers ─────────────────────────────────────────────

    def _channel_index(self, rig_idx: int, pattern_name: str) -> Optional[int]:
        """Find the 0-based channel index for a channel name within a fixture."""
        entry = self.rig[rig_idx]
        key = entry.get("key", "")
        defn = self.qxf_defs.get(key, {})
        channels = defn.get("channels", [])
        for i, ch in enumerate(channels):
            if pattern_name.lower() in ch.lower():
                return i
        return None

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

    # ── Scene builders ────────────────────────────────────────────────────

    def _create_all_on_scene(self) -> int:
        fid = self._next_fid()
        vals = []
        for idx in range(len(self.rig)):
            di = self._dimmer_index(idx)
            if di is not None:
                vals.append((idx, di, 255))
        self.functions.append(_build_scene(fid, "ALL ON", vals))
        return fid

    def _create_all_off_scene(self) -> int:
        fid = self._next_fid()
        vals = []
        for idx in range(len(self.rig)):
            di = self._dimmer_index(idx)
            if di is not None:
                vals.append((idx, di, 0))
        self.functions.append(_build_scene(fid, "ALL OFF", vals))
        return fid

    def _create_blackout_scene(self) -> int:
        """Blackout: all channels to 0."""
        fid = self._next_fid()
        vals = []
        for idx, entry in enumerate(self.rig):
            ch_count = entry.get("ch_count", 0)
            for ch in range(ch_count):
                vals.append((idx, ch, 0))
        self.functions.append(_build_scene(fid, "BLACKOUT", vals))
        return fid

    def _create_warm_white_scene(self) -> int:
        fid = self._next_fid()
        vals = []
        for idx in range(len(self.rig)):
            caps = self.analysis.fixture_caps[idx]
            if caps.has_rgb():
                rgb = self._rgb_indices(idx)
                if rgb:
                    vals.append((idx, rgb["red"],   255))
                    vals.append((idx, rgb["green"], 200))
                    vals.append((idx, rgb["blue"],    0))
            di = self._dimmer_index(idx)
            if di is not None:
                vals.append((idx, di, 255))
        self.functions.append(_build_scene(fid, "Warm White", vals))
        return fid

    def _create_cold_white_scene(self) -> int:
        fid = self._next_fid()
        vals = []
        for idx in range(len(self.rig)):
            caps = self.analysis.fixture_caps[idx]
            if caps.has_rgb():
                rgb = self._rgb_indices(idx)
                if rgb:
                    vals.append((idx, rgb["red"],   255))
                    vals.append((idx, rgb["green"], 255))
                    vals.append((idx, rgb["blue"],  255))
            di = self._dimmer_index(idx)
            if di is not None:
                vals.append((idx, di, 255))
        self.functions.append(_build_scene(fid, "Cold White", vals))
        return fid

    def _create_color_scene(self, name: str,
                            r: int, g: int, b: int) -> int:
        fid = self._next_fid()
        vals = []
        for idx in range(len(self.rig)):
            caps = self.analysis.fixture_caps[idx]
            if caps.has_rgb():
                rgb = self._rgb_indices(idx)
                if rgb:
                    vals.append((idx, rgb["red"],   r))
                    vals.append((idx, rgb["green"], g))
                    vals.append((idx, rgb["blue"],  b))
            di = self._dimmer_index(idx)
            if di is not None:
                vals.append((idx, di, 255))
        self.functions.append(_build_scene(fid, name, vals))
        return fid

    def _create_strobe_scene(self) -> int:
        fid = self._next_fid()
        vals = []
        for idx in range(len(self.rig)):
            si = self._strobe_index(idx)
            if si is not None:
                vals.append((idx, si, 200))
            di = self._dimmer_index(idx)
            if di is not None:
                vals.append((idx, di, 255))
        self.functions.append(_build_scene(fid, "Strobe", vals))
        return fid

    def _create_group_scene(self, group_name: str,
                            fixture_indices: List[int]) -> int:
        display = {
            "moving_heads":   "Moving Heads",
            "color_fixtures": "Color Fixtures",
            "dimmers_only":   "Dimmers",
            "other":          "Other",
        }.get(group_name, group_name)
        fid = self._next_fid()
        vals = []
        for idx in fixture_indices:
            di = self._dimmer_index(idx)
            if di is not None:
                vals.append((idx, di, 255))
        self.functions.append(_build_scene(fid, display, vals))
        return fid

    # ── Chaser builders ───────────────────────────────────────────────────

    def _create_dimmer_sweep_chaser(self) -> int:
        # Two-step chaser: all dimmers 0 → 255 → 0
        s_on  = self._create_all_on_scene()
        s_off = self._create_all_off_scene()
        fid = self._next_fid()
        self.functions.append(
            _build_chaser(fid, "Dimmer Sweep", [s_off, s_on],
                          fade_in=1000, fade_out=1000, duration=500))
        return fid

    def _create_color_fade_chaser(self) -> int:
        # Cycle through primary / secondary colours
        s_r = self._create_color_scene("Red",     255,   0,   0)
        s_g = self._create_color_scene("Green",     0, 255,   0)
        s_b = self._create_color_scene("Blue",      0,   0, 255)
        s_y = self._create_color_scene("Yellow",  255, 255,   0)
        s_m = self._create_color_scene("Magenta", 255,   0, 255)
        s_c = self._create_color_scene("Cyan",      0, 255, 255)
        fid = self._next_fid()
        self.functions.append(
            _build_chaser(fid, "Color Fade", [s_r, s_y, s_g, s_c, s_b, s_m],
                          fade_in=2000, fade_out=0, duration=1000))
        return fid

    def _create_strobe_chaser(self, name: str, on_ms: int, off_ms: int) -> int:
        # On/off strobe effect
        s_on  = self._create_strobe_scene()
        s_off_id = self._next_fid()
        # Off scene: strobe channels to 0
        vals = []
        for idx in range(len(self.rig)):
            si = self._strobe_index(idx)
            if si is not None:
                vals.append((idx, si, 0))
        self.functions.append(_build_scene(s_off_id, f"{name} Off", vals))
        fid = self._next_fid()
        self.functions.append(
            _build_chaser(fid, name, [s_on, s_off_id],
                          fade_in=0, fade_out=0, duration=on_ms))
        return fid

    # ── Main generation ───────────────────────────────────────────────────

    def generate(self) -> Tuple[List[ET.Element], ET.Element]:
        """
        Generate the complete VC layout and backing functions.

        Returns
        -------
        (functions, vc_frame)
            functions : list of <Function> XML elements
            vc_frame  : root <Frame> XML element for the Virtual Console
        """
        self.functions = []
        groups = self.analysis.group_by_type()

        pad = 5
        btn_h = 55
        btn_w = 130

        # ── Macros ────────────────────────────────────────────────────────
        macro_h = 40 + 2 * (btn_h + pad) + pad   # header + 2 rows
        macros_frame = _vc_frame(self._next_wid(), "Macros",
                                 0, 0, 280, macro_h)
        btn_y = 40   # below header
        fid_on  = self._create_all_on_scene()
        macros_frame.append(
            _vc_button(self._next_wid(), "ALL ON", fid_on, "Scene",
                       pad, btn_y, btn_w, btn_h,
                       bg_color=_CLR_GREEN, fg_color=_CLR_WHITE))
        fid_off = self._create_all_off_scene()
        macros_frame.append(
            _vc_button(self._next_wid(), "ALL OFF", fid_off, "Scene",
                       pad + btn_w + pad, btn_y, btn_w, btn_h,
                       bg_color=_CLR_DARK_GRAY, fg_color=_CLR_LIGHT_GRAY))
        btn_y += btn_h + pad
        fid_bo = self._create_blackout_scene()
        macros_frame.append(
            _vc_button(self._next_wid(), "BLACKOUT", fid_bo, "Scene",
                       pad, btn_y, 2 * btn_w + pad, btn_h,
                       bg_color=_CLR_DARK_RED, fg_color=_CLR_WHITE))

        # ── Fixture Groups ────────────────────────────────────────────────
        active_groups = [(gn, gi) for gn, gi in groups.items() if gi]
        grp_rows = max(len(active_groups), 1)
        grp_h = 40 + grp_rows * (btn_h + pad) + pad
        groups_frame = _vc_frame(self._next_wid(), "Fixture Groups",
                                 0, macro_h + pad, 280, grp_h)

        _GROUP_COLORS = {
            "moving_heads":   (_CLR_BLUE,       _CLR_WHITE),
            "color_fixtures": (_CLR_CYAN,        _CLR_BLACK),
            "dimmers_only":   (_CLR_YELLOW,      _CLR_BLACK),
            "other":          (_CLR_MID_GRAY,    _CLR_WHITE),
        }

        btn_y = 40
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

        # ── Scenes ────────────────────────────────────────────────────────
        # Collect scene entries first so we can size the frame
        scene_entries = []   # (caption, fid, ftype, bg, fg)

        fid_ww = self._create_warm_white_scene()
        scene_entries.append(("Warm White", fid_ww, "Scene",
                              _CLR_WARM, _CLR_BLACK))

        fid_cw = self._create_cold_white_scene()
        scene_entries.append(("Cold White", fid_cw, "Scene",
                              _CLR_LIGHT_GRAY, _CLR_BLACK))

        if self.analysis.has_any_rgb():
            fid_colors = self._create_color_scene("Colors", 0, 128, 255)
            scene_entries.append(("Colors", fid_colors, "Scene",
                                  _CLR_CYAN, _CLR_BLACK))

        if self.analysis.has_any_strobe():
            fid_strobe = self._create_strobe_scene()
            scene_entries.append(("Strobe", fid_strobe, "Scene",
                                  _CLR_YELLOW, _CLR_BLACK))

        # Custom empty slots
        for i in range(1, 5):
            custom_fid = self._next_fid()
            self.functions.append(_build_scene(custom_fid, f"Custom {i}", []))
            scene_entries.append((f"Custom {i}", custom_fid, "Scene",
                                  _CLR_MID_GRAY, _CLR_WHITE))

        cols = 4
        scene_rows = (len(scene_entries) + cols - 1) // cols
        scene_h = 40 + scene_rows * (btn_h + pad) + pad
        left_col_w = 280 + pad
        right_col_w = cols * (btn_w + pad) + pad

        scenes_frame = _vc_frame(self._next_wid(), "Scenes",
                                 left_col_w, 0, right_col_w, scene_h)
        for si, (caption, fid, ftype, bg, fg) in enumerate(scene_entries):
            sc = si % cols
            sr = si // cols
            x = pad + sc * (btn_w + pad)
            y = 40 + sr * (btn_h + pad)
            scenes_frame.append(
                _vc_button(self._next_wid(), caption, fid, ftype,
                           x, y, btn_w, btn_h,
                           bg_color=bg, fg_color=fg))

        # ── Effects ───────────────────────────────────────────────────────
        effect_entries = []  # (caption, fid, bg, fg)

        fid_sweep = self._create_dimmer_sweep_chaser()
        effect_entries.append(("Dimmer Sweep", fid_sweep,
                               _CLR_ORANGE, _CLR_BLACK))

        if self.analysis.has_any_rgb():
            fid_cfade = self._create_color_fade_chaser()
            effect_entries.append(("Color Fade", fid_cfade,
                                   _CLR_PURPLE, _CLR_WHITE))

        if self.analysis.has_any_strobe():
            fid_slow = self._create_strobe_chaser("Strobe Low", 200, 200)
            effect_entries.append(("Strobe Low", fid_slow,
                                   _CLR_YELLOW, _CLR_BLACK))
            fid_fast = self._create_strobe_chaser("Strobe High", 50, 50)
            effect_entries.append(("Strobe High", fid_fast,
                                   _CLR_RED, _CLR_WHITE))

        eff_rows = max((len(effect_entries) + cols - 1) // cols, 1)
        eff_h = 40 + eff_rows * (btn_h + pad) + pad

        effects_frame = _vc_frame(self._next_wid(), "Effects",
                                  left_col_w, scene_h + pad,
                                  right_col_w, eff_h)
        for ei, (caption, fid, bg, fg) in enumerate(effect_entries):
            ec = ei % cols
            er = ei // cols
            x = pad + ec * (btn_w + pad)
            y = 40 + er * (btn_h + pad)
            effects_frame.append(
                _vc_button(self._next_wid(), caption, fid, "Chaser",
                           x, y, btn_w, btn_h,
                           bg_color=bg, fg_color=fg))

        # ── Main frame ────────────────────────────────────────────────────
        total_w = left_col_w + right_col_w + pad
        left_h = macro_h + pad + grp_h
        right_h = scene_h + pad + eff_h
        total_h = max(left_h, right_h) + pad
        main_frame = _vc_frame(self._next_wid(), "Quick Start",
                               0, 0, total_w, total_h,
                               caption="Quick Start")
        main_frame.append(macros_frame)
        main_frame.append(groups_frame)
        main_frame.append(scenes_frame)
        main_frame.append(effects_frame)

        return self.functions, main_frame

    # ── Statistics ────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return counts of generated elements (call after generate())."""
        scenes  = sum(1 for f in self.functions
                      if f.get("Type") == "Scene")
        chasers = sum(1 for f in self.functions
                      if f.get("Type") == "Chaser")
        return {
            "scenes":    scenes,
            "chasers":   chasers,
            "functions": len(self.functions),
        }
