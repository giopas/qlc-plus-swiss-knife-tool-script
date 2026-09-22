"""
core/qxf_parser.py — Deep QXF fixture-definition parser
=========================================================
Pure functions, no module state, no Tkinter, no Flask.

Extends the shallow parse done by ``core.fixture.load_qxf()`` with:

- Per-channel group, byte order, preset, and capability ranges
- Per-mode ordered channel lists (not just counts)
- Physical data (pan/tilt max, dimensions, weight, power)
- 16-bit fine-channel pairing detection
- A value decoder: raw DMX → human label

Backward compatible: returns a dict that is a superset of the existing
``_qxf_defs`` entry shape.  Existing consumers that only read
``channels``, ``modes``, ``manufacturer``, ``model``, ``type``, ``path``
are unaffected.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

QXF_NS_URI = "http://www.qlcplus.org/FixtureDefinition"
_NS = {"f": QXF_NS_URI}


# ═══════════════════════════════════════════════════════════════════════════════
# Preset → group mapping
# ═══════════════════════════════════════════════════════════════════════════════
# QLC+ presets encode channel semantics without explicit <Group>/<Capability>
# children.  This table maps known presets to (group_name, byte_order).
# byte_order: 0 = coarse / MSB, 1 = fine / LSB.
#
# Source: qlcplus/resources/fixtures/scripts/fixtures-tool.py and qlcfixturedef.cpp

PRESET_GROUPS: dict[str, tuple[str, int]] = {
    # ── Position ──────────────────────────────────────────────────────────
    "PositionPan":                ("Pan", 0),
    "PositionPanFine":            ("Pan", 1),
    "PositionTilt":               ("Tilt", 0),
    "PositionTiltFine":           ("Tilt", 1),

    # ── Intensity ─────────────────────────────────────────────────────────
    "IntensityMasterDimmer":      ("Intensity", 0),
    "IntensityMasterDimmerFine":  ("Intensity", 1),
    "IntensityDimmer":            ("Intensity", 0),
    "IntensityDimmerFine":        ("Intensity", 1),
    "IntensityRed":               ("Intensity", 0),
    "IntensityRedFine":           ("Intensity", 1),
    "IntensityGreen":             ("Intensity", 0),
    "IntensityGreenFine":         ("Intensity", 1),
    "IntensityBlue":              ("Intensity", 0),
    "IntensityBlueFine":          ("Intensity", 1),
    "IntensityWhite":             ("Intensity", 0),
    "IntensityWhiteFine":         ("Intensity", 1),
    "IntensityAmber":             ("Intensity", 0),
    "IntensityAmberFine":         ("Intensity", 1),
    "IntensityUV":                ("Intensity", 0),
    "IntensityUVFine":            ("Intensity", 1),
    "IntensityIndigo":            ("Intensity", 0),
    "IntensityIndigoFine":        ("Intensity", 1),
    "IntensityLime":              ("Intensity", 0),
    "IntensityLimeFine":          ("Intensity", 1),
    "IntensityCyan":              ("Intensity", 0),
    "IntensityCyanFine":          ("Intensity", 1),
    "IntensityMagenta":           ("Intensity", 0),
    "IntensityMagentaFine":       ("Intensity", 1),
    "IntensityHue":               ("Intensity", 0),
    "IntensityHueFine":           ("Intensity", 1),
    "IntensitySaturation":        ("Intensity", 0),
    "IntensitySaturationFine":    ("Intensity", 1),
    "IntensityLightness":         ("Intensity", 0),
    "IntensityLightnessFine":     ("Intensity", 1),
    "IntensityValue":             ("Intensity", 0),
    "IntensityValueFine":         ("Intensity", 1),

    # ── Colour ────────────────────────────────────────────────────────────
    "ColorMacro":                 ("Colour", 0),
    "ColorWheel":                 ("Colour", 0),
    "ColorWheelFine":             ("Colour", 1),
    "ColorRGBMixer":              ("Colour", 0),
    "ColorCTOMixer":              ("Colour", 0),
    "ColorCTBMixer":              ("Colour", 0),
    "ColorCTCMixer":              ("Colour", 0),

    # ── Gobo ──────────────────────────────────────────────────────────────
    "GoboWheel":                  ("Gobo", 0),
    "GoboWheelFine":              ("Gobo", 1),
    "GoboIndex":                  ("Gobo", 0),
    "GoboIndexFine":              ("Gobo", 1),

    # ── Shutter ───────────────────────────────────────────────────────────
    "ShutterStrobeSlowFast":      ("Shutter", 0),
    "ShutterStrobeFastSlow":      ("Shutter", 0),
    "ShutterIrisMinToMax":        ("Shutter", 0),
    "ShutterIrisMaxToMin":        ("Shutter", 0),
    "ShutterIrisFine":            ("Shutter", 1),

    # ── Beam / Prism / Focus / Zoom ───────────────────────────────────────
    "BeamFocusNearFar":           ("Beam", 0),
    "BeamFocusFarNear":           ("Beam", 0),
    "BeamFocusFine":              ("Beam", 1),
    "BeamZoomSmallBig":           ("Beam", 0),
    "BeamZoomBigSmall":           ("Beam", 0),
    "BeamZoomFine":               ("Beam", 1),
    "PrismRotationSlowFast":      ("Prism", 0),
    "PrismRotationFastSlow":      ("Prism", 0),
    "PrismEffectOn":              ("Prism", 0),
    "PrismEffectOff":             ("Prism", 0),

    # ── Speed ─────────────────────────────────────────────────────────────
    "SpeedPanSlowFast":           ("Speed", 0),
    "SpeedPanFastSlow":           ("Speed", 0),
    "SpeedTiltSlowFast":          ("Speed", 0),
    "SpeedTiltFastSlow":          ("Speed", 0),
    "SpeedPanTiltSlowFast":       ("Speed", 0),
    "SpeedPanTiltFastSlow":       ("Speed", 0),

    # ── Maintenance ───────────────────────────────────────────────────────
    "NoFunction":                 ("Nothing", 0),
    "GenericPicture":             ("Effect", 0),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Colour-role classification for Intensity-group presets
# ═══════════════════════════════════════════════════════════════════════════════
# The Show Book decoder needs to know "this is the Red channel" vs "this is
# the master dimmer".  Both sit under group "Intensity".  This table extracts
# a colour role from the preset name.

PRESET_COLOUR_ROLE: dict[str, str] = {
    "IntensityRed":        "Red",
    "IntensityRedFine":    "Red",
    "IntensityGreen":      "Green",
    "IntensityGreenFine":  "Green",
    "IntensityBlue":       "Blue",
    "IntensityBlueFine":   "Blue",
    "IntensityWhite":      "White",
    "IntensityWhiteFine":  "White",
    "IntensityAmber":      "Amber",
    "IntensityAmberFine":  "Amber",
    "IntensityUV":         "UV",
    "IntensityUVFine":     "UV",
    "IntensityIndigo":     "Indigo",
    "IntensityIndigoFine": "Indigo",
    "IntensityLime":       "Lime",
    "IntensityLimeFine":   "Lime",
    "IntensityCyan":       "Cyan",
    "IntensityCyanFine":   "Cyan",
    "IntensityMagenta":    "Magenta",
    "IntensityMagentaFine":"Magenta",
    "IntensityHue":        "Hue",
    "IntensityHueFine":    "Hue",
    "IntensitySaturation": "Saturation",
    "IntensitySaturationFine": "Saturation",
    "IntensityLightness":  "Lightness",
    "IntensityLightnessFine": "Lightness",
    "IntensityValue":      "Value",
    "IntensityValueFine":  "Value",
    "IntensityMasterDimmer":     "Dimmer",
    "IntensityMasterDimmerFine": "Dimmer",
    "IntensityDimmer":           "Dimmer",
    "IntensityDimmerFine":       "Dimmer",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Channel parser
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_channel(ch_el: ET.Element) -> dict:
    """Parse one top-level <Channel> element into a rich dict.

    Returns
    -------
    dict with keys:
        name        str   — channel name (unique within a QXF)
        group       str   — channel group (Pan, Tilt, Intensity, Colour, Gobo, …)
        byte        int   — 0 = coarse/MSB, 1 = fine/LSB
        preset      str|None — QXF preset name if present
        colour_role str|None — for Intensity-group channels: Red, Green, Blue,
                               Dimmer, etc.; None otherwise
        capabilities list[dict] — [{min, max, label, preset, res1}, …]
    """
    name   = ch_el.get("Name", "?")
    preset = ch_el.get("Preset")

    group  = "Nothing"
    byte   = 0
    colour_role = None
    capabilities: list[dict] = []

    if preset and preset in PRESET_GROUPS:
        group, byte = PRESET_GROUPS[preset]
        colour_role = PRESET_COLOUR_ROLE.get(preset)
        # Preset channels have implicit 0-255 range with the preset name as label
        capabilities = [{"min": 0, "max": 255, "label": name, "preset": preset, "res1": None}]
    else:
        # Explicit <Group> and <Capability> children
        group_el = ch_el.find("f:Group", _NS)
        if group_el is None:
            # Try without namespace (some older files)
            group_el = ch_el.find("Group")
        if group_el is not None:
            group = (group_el.text or "Nothing").strip()
            byte_str = group_el.get("Byte", "0")
            byte = int(byte_str) if byte_str.isdigit() else 0

        for cap_el in ch_el.findall("f:Capability", _NS):
            cap = {
                "min":    int(cap_el.get("Min", "0")),
                "max":    int(cap_el.get("Max", "255")),
                "label":  (cap_el.text or "").strip(),
                "preset": cap_el.get("Preset"),
                "res1":   cap_el.get("Res1"),
            }
            capabilities.append(cap)

        # If no explicit capabilities were found, add a catch-all
        if not capabilities:
            capabilities = [{"min": 0, "max": 255, "label": name, "preset": preset, "res1": None}]

        # Infer colour role from channel name for Intensity-group channels
        if group == "Intensity":
            ln = name.lower()
            for role in ("red", "green", "blue", "white", "amber", "uv",
                         "cyan", "magenta", "indigo", "lime"):
                if role in ln:
                    colour_role = role.capitalize()
                    break
            else:
                if any(w in ln for w in ("dimmer", "intensity", "master", "brightness")):
                    colour_role = "Dimmer"

    return {
        "name":         name,
        "group":        group,
        "byte":         byte,
        "preset":       preset,
        "colour_role":  colour_role,
        "capabilities": capabilities,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Physical parser
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_physical(root: ET.Element) -> dict:
    """Parse the <Physical> block.

    Returns a dict with all available physical properties, or an empty
    dict if the block is absent.
    """
    phys = root.find("f:Physical", _NS)
    if phys is None:
        return {}

    result: dict = {}

    focus = phys.find("f:Focus", _NS)
    if focus is not None:
        for attr, key in [("PanMax", "pan_max"), ("TiltMax", "tilt_max")]:
            val = focus.get(attr)
            if val is not None:
                try:
                    result[key] = float(val)
                except ValueError:
                    pass
        result["focus_type"] = focus.get("Type", "")

    dims = phys.find("f:Dimensions", _NS)
    if dims is not None:
        for attr, key in [("Weight", "weight"), ("Width", "width"),
                          ("Height", "height"), ("Depth", "depth")]:
            val = dims.get(attr)
            if val is not None:
                try:
                    result[key] = float(val)
                except ValueError:
                    pass

    bulb = phys.find("f:Bulb", _NS)
    if bulb is not None:
        result["bulb_type"] = bulb.get("Type", "")
        for attr, key in [("Lumens", "lumens"), ("ColourTemperature", "colour_temp")]:
            val = bulb.get(attr)
            if val is not None:
                try:
                    result[key] = float(val)
                except ValueError:
                    pass

    tech = phys.find("f:Technical", _NS)
    if tech is not None:
        val = tech.get("PowerConsumption")
        if val is not None:
            try:
                result["power"] = float(val)
            except ValueError:
                pass
        result["dmx_connector"] = tech.get("DmxConnector", "")

    lens = phys.find("f:Lens", _NS)
    if lens is not None:
        result["lens_name"] = lens.get("Name", "")
        for attr, key in [("DegreesMin", "lens_min"), ("DegreesMax", "lens_max")]:
            val = lens.get(attr)
            if val is not None:
                try:
                    result[key] = float(val)
                except ValueError:
                    pass

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Fine-channel pairing
# ═══════════════════════════════════════════════════════════════════════════════

def detect_fine_pairs(channel_defs: dict[str, dict],
                      mode_channel_names: list[str]) -> dict[str, str]:
    """Detect coarse→fine channel pairs within a single mode.

    Strategy (in order):
    1. Preset-based: e.g. PositionPan (byte=0) pairs with PositionPanFine (byte=1)
    2. Group + byte: within the same group, byte=0 pairs with byte=1
       (only when exactly one of each exists in the mode for that group)
    3. Name heuristic: "X" pairs with "X Fine" or "X fine"

    Returns
    -------
    dict  coarse_channel_name → fine_channel_name
    """
    # Build lookup of channels actually in this mode
    mode_defs = {name: channel_defs[name] for name in mode_channel_names
                 if name in channel_defs}

    pairs: dict[str, str] = {}
    paired_fine: set[str] = set()

    # ── Strategy 1: Preset-based pairing ──────────────────────────────────
    # Build: preset_base → {0: name, 1: name}
    preset_map: dict[str, dict[int, str]] = {}
    for name, defn in mode_defs.items():
        p = defn.get("preset")
        if not p:
            continue
        # Normalize: strip trailing "Fine" to get the base preset
        base = p.removesuffix("Fine") if p.endswith("Fine") else p
        if base not in preset_map:
            preset_map[base] = {}
        preset_map[base][defn["byte"]] = name

    for base, by_byte in preset_map.items():
        if 0 in by_byte and 1 in by_byte:
            pairs[by_byte[0]] = by_byte[1]
            paired_fine.add(by_byte[1])

    # ── Strategy 2: Group + byte order ────────────────────────────────────
    # Group channels not yet paired
    from collections import defaultdict
    group_byte: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for name, defn in mode_defs.items():
        if name in pairs or name in paired_fine:
            continue
        group_byte[defn["group"]][defn["byte"]].append(name)

    for grp, by_byte in group_byte.items():
        coarse = by_byte.get(0, [])
        fine   = by_byte.get(1, [])
        if len(coarse) == 1 and len(fine) == 1:
            pairs[coarse[0]] = fine[0]
            paired_fine.add(fine[0])

    # ── Strategy 3: Name heuristic ────────────────────────────────────────
    remaining_coarse = [n for n in mode_channel_names
                        if n not in pairs and n not in paired_fine]
    remaining_fine   = [n for n in mode_channel_names
                        if n not in pairs and n not in paired_fine
                        and mode_defs.get(n, {}).get("byte") == 1]

    for fine_name in remaining_fine:
        # Try matching "X fine" / "X Fine" → "X"
        for suffix in (" fine", " Fine", "Fine"):
            if fine_name.endswith(suffix):
                candidate = fine_name[:-len(suffix)].rstrip()
                if candidate in remaining_coarse and candidate not in pairs:
                    pairs[candidate] = fine_name
                    paired_fine.add(fine_name)
                    break

    return pairs


# ═══════════════════════════════════════════════════════════════════════════════
# Main parser
# ═══════════════════════════════════════════════════════════════════════════════

def parse_qxf(path: str) -> dict:
    """Parse a QXF fixture definition file into a rich dictionary.

    The returned dict is a superset of the existing ``_qxf_defs`` entry
    shape.  All existing keys are preserved with compatible values.

    Parameters
    ----------
    path : str
        Filesystem path to the ``.qxf`` file.

    Returns
    -------
    dict with keys:
        manufacturer  str
        model         str
        type          str
        path          str
        channels      list[str]          — flat name list (backward compat)
        modes         dict[str, int]     — mode_name → channel count (backward compat)
        channel_defs  dict[str, dict]    — name → rich channel definition
        mode_channels dict[str, list[str]] — mode_name → ordered channel names
        physical      dict               — physical properties
        fine_pairs    dict[str, dict[str, str]] — mode_name → {coarse → fine}

    Raises
    ------
    ValueError  if the file is not a valid QXF.
    """
    tree = ET.parse(path)
    root = tree.getroot()

    if QXF_NS_URI not in (root.tag or ""):
        raise ValueError(
            f"Not a valid QXF file. Expected namespace '{QXF_NS_URI}', "
            f"got: '{root.tag}'"
        )

    mfg   = root.findtext("f:Manufacturer", default="Unknown", namespaces=_NS)
    model = root.findtext("f:Model",        default="Unknown", namespaces=_NS)
    ftype = root.findtext("f:Type",         default="Color Changer", namespaces=_NS)

    # ── Parse all top-level channel definitions ───────────────────────────
    channel_defs: dict[str, dict] = {}
    channel_names: list[str] = []
    for ch_el in root.findall("f:Channel", _NS):
        defn = _parse_channel(ch_el)
        channel_defs[defn["name"]] = defn
        channel_names.append(defn["name"])

    # ── Parse modes ───────────────────────────────────────────────────────
    modes: dict[str, int] = {}
    mode_channels: dict[str, list[str]] = {}
    for mode_el in root.findall("f:Mode", _NS):
        mname = mode_el.get("Name", "Default")
        ch_els = mode_el.findall("f:Channel", _NS)
        # Sort by Number attribute to get the correct order
        ordered = sorted(ch_els, key=lambda e: int(e.get("Number", "0")))
        names = [(e.text or "").strip() for e in ordered]
        modes[mname] = len(names)
        mode_channels[mname] = names

    # ── Parse physical ────────────────────────────────────────────────────
    physical = _parse_physical(root)

    # ── Detect fine pairs per mode ────────────────────────────────────────
    fine_pairs: dict[str, dict[str, str]] = {}
    for mname, ch_list in mode_channels.items():
        fine_pairs[mname] = detect_fine_pairs(channel_defs, ch_list)

    return {
        # Backward-compatible fields
        "manufacturer":  mfg,
        "model":         model,
        "type":          ftype,
        "modes":         modes,
        "channels":      channel_names,
        "path":          path,
        # New rich fields
        "channel_defs":  channel_defs,
        "mode_channels": mode_channels,
        "physical":      physical,
        "fine_pairs":    fine_pairs,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Value decoder
# ═══════════════════════════════════════════════════════════════════════════════

def decode_value(channel_def: dict, raw: int,
                 fine_raw: Optional[int] = None,
                 physical: Optional[dict] = None) -> dict:
    """Decode a raw DMX value using the channel definition.

    Parameters
    ----------
    channel_def : dict
        A single channel definition from ``channel_defs``.
    raw : int
        The coarse (8-bit) DMX value, 0–255.
    fine_raw : int or None
        The fine (8-bit) DMX value from the paired fine channel, if
        16-bit decoding is desired.
    physical : dict or None
        Physical data from the fixture definition (for pan/tilt degrees).

    Returns
    -------
    dict with keys:
        label       str   — human-readable decoded value
        raw         int   — the coarse raw value
        fine_raw    int|None — the fine raw value if supplied
        raw_16bit   int|None — combined 16-bit value if fine was supplied
        group       str   — channel group
        colour_role str|None
        confidence  str   — "exact" | "interpolated" | "preset_inferred" | "raw_only"
    """
    group       = channel_def.get("group", "Nothing")
    colour_role = channel_def.get("colour_role")
    name        = channel_def.get("name", "?")
    caps        = channel_def.get("capabilities", [])
    preset      = channel_def.get("preset")

    # Combined 16-bit value
    raw_16bit = None
    if fine_raw is not None:
        raw_16bit = (raw << 8) | fine_raw

    physical = physical or {}

    # ── Pan / Tilt: decode to degrees ─────────────────────────────────────
    if group in ("Pan", "Tilt"):
        max_deg = physical.get("pan_max" if group == "Pan" else "tilt_max")
        if max_deg and max_deg > 0:
            if raw_16bit is not None:
                degrees = (raw_16bit / 65535) * max_deg
                label = f"{degrees:.1f}° ({raw} / {fine_raw})"
            else:
                degrees = (raw / 255) * max_deg
                label = f"{degrees:.1f}° ({raw})"
            return {
                "label": label, "raw": raw, "fine_raw": fine_raw,
                "raw_16bit": raw_16bit, "group": group,
                "colour_role": colour_role, "confidence": "exact",
            }
        # No physical data — fall through to percentage
        if raw_16bit is not None:
            pct = (raw_16bit / 65535) * 100
            label = f"{pct:.1f}% ({raw} / {fine_raw})"
        else:
            pct = (raw / 255) * 100
            label = f"{pct:.1f}% ({raw})"
        return {
            "label": label, "raw": raw, "fine_raw": fine_raw,
            "raw_16bit": raw_16bit, "group": group,
            "colour_role": colour_role, "confidence": "interpolated",
        }

    # ── Intensity / Dimmer: decode to percentage ──────────────────────────
    if group == "Intensity" and colour_role in ("Dimmer", None):
        if raw_16bit is not None:
            pct = (raw_16bit / 65535) * 100
            label = f"{pct:.1f}% ({raw} / {fine_raw})"
        else:
            pct = (raw / 255) * 100
            label = f"{pct:.0f}% ({raw})"
        return {
            "label": label, "raw": raw, "fine_raw": fine_raw,
            "raw_16bit": raw_16bit, "group": group,
            "colour_role": colour_role, "confidence": "exact",
        }

    # ── Colour channels (RGB etc): raw value ──────────────────────────────
    if group == "Intensity" and colour_role:
        # These are 0-255 level channels; show as raw
        label = f"{raw}"
        if fine_raw is not None:
            label = f"{raw} / {fine_raw}"
        return {
            "label": label, "raw": raw, "fine_raw": fine_raw,
            "raw_16bit": raw_16bit, "group": group,
            "colour_role": colour_role, "confidence": "exact",
        }

    # ── Capability lookup for everything else ─────────────────────────────
    if caps and not (len(caps) == 1 and caps[0]["min"] == 0 and caps[0]["max"] == 255
                     and caps[0].get("preset")):
        # Real capability ranges — find the one that contains our value
        for cap in caps:
            if cap["min"] <= raw <= cap["max"]:
                cap_label = cap.get("label", "")
                if cap_label:
                    label = f"{cap_label} ({raw})"
                else:
                    label = f"{raw}"
                return {
                    "label": label, "raw": raw, "fine_raw": fine_raw,
                    "raw_16bit": raw_16bit, "group": group,
                    "colour_role": colour_role, "confidence": "exact",
                }

    # ── Preset-only channel: just name + raw ──────────────────────────────
    if preset:
        label = f"{raw}"
        return {
            "label": label, "raw": raw, "fine_raw": fine_raw,
            "raw_16bit": raw_16bit, "group": group,
            "colour_role": colour_role, "confidence": "preset_inferred",
        }

    # ── Fallback: raw only ────────────────────────────────────────────────
    label = f"{raw}"
    return {
        "label": label, "raw": raw, "fine_raw": fine_raw,
        "raw_16bit": raw_16bit, "group": group,
        "colour_role": colour_role, "confidence": "raw_only",
    }
