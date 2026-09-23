"""
test_qxf_parser.py — Tests for the deep QXF parser
=====================================================
Run with:  python3 -m pytest tests/test_qxf_parser.py -v
"""

import os
import sys
import pytest

# Module under test
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.qxf_parser import (
    parse_qxf, decode_value, detect_fine_pairs,
    PRESET_GROUPS, PRESET_COLOUR_ROLE, _parse_channel, _parse_physical,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ═══════════════════════════════════════════════════════════════════════════════
# Test fixture paths
# ═══════════════════════════════════════════════════════════════════════════════

SPOT_110  = os.path.join(FIXTURES_DIR, "Chauvet-Intimidator-Spot-110.qxf")
SLIMPAR   = os.path.join(FIXTURES_DIR, "Chauvet-SlimPAR-56.qxf")
SPOT_375Z = os.path.join(FIXTURES_DIR, "Chauvet-Intimidator-Spot-375Z-IRC.qxf")


# ═══════════════════════════════════════════════════════════════════════════════
# Basic parse tests — Spot 110 (moving head with presets + explicit channels)
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseSpot110:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.data = parse_qxf(SPOT_110)

    def test_metadata(self):
        assert self.data["manufacturer"] == "Chauvet"
        assert self.data["model"] == "Intimidator Spot 110"
        assert self.data["type"] == "Moving Head"
        assert self.data["path"] == SPOT_110

    def test_backward_compat_channels(self):
        """The flat channel name list must match what the old parser produced."""
        ch = self.data["channels"]
        assert isinstance(ch, list)
        assert "Pan" in ch
        assert "Pan fine" in ch
        assert "Dimmer" in ch
        assert "Color Wheel" in ch
        assert len(ch) == 12

    def test_backward_compat_modes(self):
        """Mode dict: mode_name → channel count."""
        modes = self.data["modes"]
        assert modes["12 Channel"] == 12
        assert modes["6 Channel"] == 6

    def test_channel_defs_present(self):
        defs = self.data["channel_defs"]
        assert isinstance(defs, dict)
        assert len(defs) == 12
        assert "Pan" in defs
        assert "Color Wheel" in defs

    def test_preset_channel_parsing(self):
        """Preset channels: Pan, Pan fine, Dimmer, etc."""
        pan = self.data["channel_defs"]["Pan"]
        assert pan["group"] == "Pan"
        assert pan["byte"] == 0
        assert pan["preset"] == "PositionPan"
        assert pan["colour_role"] is None

        pan_fine = self.data["channel_defs"]["Pan fine"]
        assert pan_fine["group"] == "Pan"
        assert pan_fine["byte"] == 1
        assert pan_fine["preset"] == "PositionPanFine"

        dimmer = self.data["channel_defs"]["Dimmer"]
        assert dimmer["group"] == "Intensity"
        assert dimmer["byte"] == 0
        assert dimmer["colour_role"] == "Dimmer"

    def test_explicit_channel_parsing(self):
        """Channels with explicit <Group> and <Capability> children."""
        cw = self.data["channel_defs"]["Color Wheel"]
        assert cw["group"] == "Colour"
        assert cw["byte"] == 0
        assert cw["preset"] is None

        caps = cw["capabilities"]
        assert len(caps) == 8
        assert caps[0]["min"] == 0
        assert caps[0]["max"] == 31
        assert caps[0]["label"] == "Open"
        assert caps[1]["label"] == "Color 1 (Red)"
        assert caps[1]["min"] == 32
        assert caps[1]["max"] == 63

    def test_gobo_capabilities(self):
        gobo = self.data["channel_defs"]["Gobo Wheel"]
        assert gobo["group"] == "Gobo"
        caps = gobo["capabilities"]
        assert len(caps) == 8
        assert caps[0]["label"] == "Open"

    def test_function_channel_capabilities(self):
        func = self.data["channel_defs"]["Function"]
        assert func["group"] == "Effect"
        caps = func["capabilities"]
        # Check a specific range
        reset = [c for c in caps if c["label"] == "Reset all"]
        assert len(reset) == 1
        assert reset[0]["min"] == 200
        assert reset[0]["max"] == 209

    def test_mode_channels_order(self):
        """Mode channels must be in DMX-address order."""
        mc = self.data["mode_channels"]
        assert mc["12 Channel"] == [
            "Pan", "Pan fine", "Tilt", "Tilt fine", "Pan/Tilt speed",
            "Color Wheel", "Strobe", "Dimmer", "Gobo Wheel",
            "Function", "Movement Macro", "Movement Macro Speed"
        ]
        assert mc["6 Channel"] == [
            "Pan", "Tilt", "Color Wheel", "Strobe", "Dimmer", "Gobo Wheel"
        ]

    def test_physical(self):
        phys = self.data["physical"]
        assert phys["pan_max"] == 540.0
        assert phys["tilt_max"] == 270.0
        assert phys["weight"] == 2.3
        assert phys["width"] == 127.0
        assert phys["height"] == 279.0
        assert phys["depth"] == 190.0
        assert phys["power"] == 41.0
        assert phys["dmx_connector"] == "3-pin"
        assert phys["focus_type"] == "Head"
        assert phys["lens_min"] == 13.0
        assert phys["lens_max"] == 13.0

    def test_fine_pairs_12ch(self):
        """In 12-channel mode, Pan↔Pan fine and Tilt↔Tilt fine."""
        fp = self.data["fine_pairs"]["12 Channel"]
        assert fp["Pan"] == "Pan fine"
        assert fp["Tilt"] == "Tilt fine"
        assert len(fp) == 2

    def test_fine_pairs_6ch(self):
        """In 6-channel mode, no fine channels → no pairs."""
        fp = self.data["fine_pairs"]["6 Channel"]
        assert len(fp) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# SlimPAR 56 — RGB fixture, no pan/tilt, all presets for colour
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseSlimPAR:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.data = parse_qxf(SLIMPAR)

    def test_metadata(self):
        assert self.data["manufacturer"] == "Chauvet"
        assert self.data["model"] == "SlimPAR 56"
        assert self.data["type"] == "Color Changer"

    def test_rgb_channels(self):
        r = self.data["channel_defs"]["Red"]
        assert r["group"] == "Intensity"
        assert r["colour_role"] == "Red"
        assert r["preset"] == "IntensityRed"

        g = self.data["channel_defs"]["Green"]
        assert g["colour_role"] == "Green"

        b = self.data["channel_defs"]["Blue"]
        assert b["colour_role"] == "Blue"

    def test_dimmer_preset(self):
        d = self.data["channel_defs"]["Dimmer"]
        assert d["group"] == "Intensity"
        assert d["colour_role"] == "Dimmer"
        assert d["preset"] == "IntensityDimmer"

    def test_explicit_mode_channel(self):
        cm = self.data["channel_defs"]["Color Macros"]
        assert cm["group"] == "Colour"
        assert len(cm["capabilities"]) == 2

    def test_modes(self):
        assert self.data["modes"]["7-Ch"] == 7
        assert self.data["modes"]["3-Ch"] == 3

    def test_mode_channels_3ch(self):
        assert self.data["mode_channels"]["3-Ch"] == ["Red", "Green", "Blue"]

    def test_no_fine_pairs(self):
        """SlimPAR 56 has no fine channels."""
        for mode, fp in self.data["fine_pairs"].items():
            assert len(fp) == 0, f"Unexpected fine pair in mode {mode}"

    def test_physical_fixed(self):
        phys = self.data["physical"]
        assert phys["pan_max"] == 0.0
        assert phys["tilt_max"] == 0.0
        assert phys["focus_type"] == "Fixed"


# ═══════════════════════════════════════════════════════════════════════════════
# Spot 375Z IRC — moving head with focus/zoom presets, more modes
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseSpot375Z:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.data = parse_qxf(SPOT_375Z)

    def test_metadata(self):
        assert self.data["manufacturer"] == "Chauvet"
        assert self.data["model"] == "Intimidator Spot 375Z IRC"

    def test_fine_pairs_15ch(self):
        fp = self.data["fine_pairs"]["15 channel"]
        assert fp["Pan coarse"] == "Pan fine"
        assert fp["Tilt coarse"] == "Tilt fine"
        assert len(fp) == 2

    def test_fine_pairs_9ch(self):
        """9-channel mode has no fine channels for pan/tilt."""
        fp = self.data["fine_pairs"]["9 channel"]
        assert len(fp) == 0

    def test_focus_zoom_preset_channels(self):
        focus = self.data["channel_defs"]["Focus"]
        assert focus["group"] == "Beam"
        assert focus["byte"] == 0
        assert focus["preset"] == "BeamFocusNearFar"

        zoom = self.data["channel_defs"]["Zoom"]
        assert zoom["group"] == "Beam"
        assert zoom["preset"] == "BeamZoomBigSmall"

    def test_prism_channel(self):
        prism = self.data["channel_defs"]["Prism"]
        assert prism["group"] == "Prism"
        caps = prism["capabilities"]
        assert len(caps) > 5
        # First cap: No function
        assert caps[0]["label"] == "No function"
        assert caps[0]["min"] == 0
        assert caps[0]["max"] == 3

    def test_maintenance_channel(self):
        ctrl = self.data["channel_defs"]["Control Functions"]
        assert ctrl["group"] == "Maintenance"

    def test_physical(self):
        phys = self.data["physical"]
        assert phys["pan_max"] == 540.0
        assert phys["tilt_max"] == 270.0
        assert phys["weight"] == 12.4
        assert phys["power"] == 270.0

    def test_15ch_mode_order(self):
        mc = self.data["mode_channels"]["15 channel"]
        assert mc[0] == "Pan coarse"
        assert mc[1] == "Pan fine"
        assert mc[2] == "Tilt coarse"
        assert mc[3] == "Tilt fine"
        assert len(mc) == 15


# ═══════════════════════════════════════════════════════════════════════════════
# Value decoder tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecodeValue:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.spot = parse_qxf(SPOT_110)
        self.slim = parse_qxf(SLIMPAR)

    def test_pan_with_physical(self):
        """Pan at DMX 128 with 540° max → ~270°."""
        pan_def = self.spot["channel_defs"]["Pan"]
        result = decode_value(pan_def, 128, physical=self.spot["physical"])
        assert result["confidence"] == "exact"
        assert result["group"] == "Pan"
        assert "°" in result["label"]
        # 128/255 * 540 ≈ 271.1
        assert "271" in result["label"]

    def test_pan_16bit(self):
        """Pan with coarse=128, fine=0 → exactly halfway."""
        pan_def = self.spot["channel_defs"]["Pan"]
        result = decode_value(pan_def, 128, fine_raw=0, physical=self.spot["physical"])
        assert result["raw_16bit"] == 128 << 8
        assert result["confidence"] == "exact"
        assert "°" in result["label"]

    def test_pan_no_physical(self):
        """Pan without physical data falls back to percentage."""
        pan_def = self.spot["channel_defs"]["Pan"]
        result = decode_value(pan_def, 128, physical={})
        assert result["confidence"] == "interpolated"
        assert "%" in result["label"]

    def test_dimmer_percentage(self):
        """Dimmer at 255 → 100%."""
        dim_def = self.spot["channel_defs"]["Dimmer"]
        result = decode_value(dim_def, 255)
        assert result["confidence"] == "exact"
        assert "100%" in result["label"]
        assert result["colour_role"] == "Dimmer"

    def test_dimmer_zero(self):
        """Dimmer at 0 → 0%."""
        dim_def = self.spot["channel_defs"]["Dimmer"]
        result = decode_value(dim_def, 0)
        assert "0%" in result["label"]

    def test_colour_wheel_cap_lookup(self):
        """Color Wheel at DMX 40 → Color 1 (Red)."""
        cw_def = self.spot["channel_defs"]["Color Wheel"]
        result = decode_value(cw_def, 40)
        assert result["confidence"] == "exact"
        assert "Color 1 (Red)" in result["label"]
        assert result["group"] == "Colour"

    def test_colour_wheel_first_range(self):
        """Color Wheel at DMX 0 → Open."""
        cw_def = self.spot["channel_defs"]["Color Wheel"]
        result = decode_value(cw_def, 0)
        assert "Open" in result["label"]

    def test_gobo_cap_lookup(self):
        """Gobo Wheel at DMX 70 → Gobo 2."""
        gobo_def = self.spot["channel_defs"]["Gobo Wheel"]
        result = decode_value(gobo_def, 70)
        assert "Gobo 2" in result["label"]

    def test_rgb_channel_raw(self):
        """Red channel at 200 → shows raw value."""
        r_def = self.slim["channel_defs"]["Red"]
        result = decode_value(r_def, 200)
        assert result["confidence"] == "exact"
        assert result["colour_role"] == "Red"
        assert "200" in result["label"]

    def test_strobe_cap_lookup(self):
        """Strobe at DMX 80 → 'Strobe, Slow to Fast'."""
        strobe_def = self.spot["channel_defs"]["Strobe"]
        result = decode_value(strobe_def, 80)
        assert result["confidence"] == "exact"
        assert "Strobe" in result["label"]

    def test_function_cap_lookup(self):
        """Function at DMX 205 → 'Reset all'."""
        func_def = self.spot["channel_defs"]["Function"]
        result = decode_value(func_def, 205)
        assert "Reset all" in result["label"]

    def test_movement_macro_speed_preset_only(self):
        """Movement Macro Speed has only one 0-255 range → raw value."""
        ms_def = self.spot["channel_defs"]["Movement Macro Speed"]
        result = decode_value(ms_def, 100)
        # Single catch-all range should still do capability lookup
        assert "100" in result["label"]

    def test_speed_preset_channel(self):
        """Pan/Tilt speed is a preset channel → preset_inferred or raw."""
        speed_def = self.spot["channel_defs"]["Pan/Tilt speed"]
        result = decode_value(speed_def, 100)
        assert "100" in result["label"]


# ═══════════════════════════════════════════════════════════════════════════════
# Fine-pair detection edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinePairs:
    def test_preset_based_pairing(self):
        """Pan (PositionPan) pairs with Pan fine (PositionPanFine)."""
        channel_defs = {
            "Pan":      {"group": "Pan", "byte": 0, "preset": "PositionPan"},
            "Pan fine":  {"group": "Pan", "byte": 1, "preset": "PositionPanFine"},
            "Dimmer":   {"group": "Intensity", "byte": 0, "preset": "IntensityMasterDimmer"},
        }
        pairs = detect_fine_pairs(channel_defs, ["Pan", "Pan fine", "Dimmer"])
        assert pairs == {"Pan": "Pan fine"}

    def test_group_byte_pairing(self):
        """When there's exactly one coarse and one fine in a group."""
        channel_defs = {
            "MyCoarse": {"group": "Gobo", "byte": 0, "preset": None},
            "MyFine":   {"group": "Gobo", "byte": 1, "preset": None},
        }
        pairs = detect_fine_pairs(channel_defs, ["MyCoarse", "MyFine"])
        assert pairs == {"MyCoarse": "MyFine"}

    def test_name_heuristic_pairing(self):
        """'Focus' pairs with 'Focus Fine' via name heuristic."""
        channel_defs = {
            "Focus":      {"group": "Beam", "byte": 0, "preset": None},
            "Focus Fine": {"group": "Beam", "byte": 1, "preset": None},
        }
        pairs = detect_fine_pairs(channel_defs, ["Focus", "Focus Fine"])
        assert pairs == {"Focus": "Focus Fine"}

    def test_no_false_pairs(self):
        """Two coarse channels in the same group should NOT pair."""
        channel_defs = {
            "Gobo Wheel":    {"group": "Gobo", "byte": 0, "preset": None},
            "Gobo Rotation": {"group": "Gobo", "byte": 0, "preset": None},
        }
        pairs = detect_fine_pairs(channel_defs, ["Gobo Wheel", "Gobo Rotation"])
        assert pairs == {}

    def test_ambiguous_group_no_pair(self):
        """Two coarse + one fine in same group → skip (ambiguous)."""
        channel_defs = {
            "Gobo1": {"group": "Gobo", "byte": 0, "preset": None},
            "Gobo2": {"group": "Gobo", "byte": 0, "preset": None},
            "GoboF": {"group": "Gobo", "byte": 1, "preset": None},
        }
        pairs = detect_fine_pairs(channel_defs, ["Gobo1", "Gobo2", "GoboF"])
        # Strategy 2 won't pair because there are 2 coarse
        # Strategy 3 won't pair because "GoboF" doesn't end with " fine"/"Fine"
        assert pairs == {}


# ═══════════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrors:
    def test_invalid_file_raises(self, tmp_path):
        """Non-QXF XML should raise ValueError."""
        bad = tmp_path / "bad.qxf"
        bad.write_text('<?xml version="1.0"?><root><child/></root>')
        with pytest.raises(ValueError, match="Not a valid QXF"):
            parse_qxf(str(bad))

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_qxf("/nonexistent/file.qxf")


# ═══════════════════════════════════════════════════════════════════════════════
# Mapping table sanity checks
# ═══════════════════════════════════════════════════════════════════════════════

class TestMappingTables:
    def test_preset_groups_fine_channels_are_byte_1(self):
        """Every preset ending in 'Fine' should map to byte=1."""
        for preset, (group, byte) in PRESET_GROUPS.items():
            if preset.endswith("Fine"):
                assert byte == 1, f"{preset} should be byte=1, got {byte}"

    def test_preset_groups_coarse_channels_are_byte_0(self):
        """Every preset NOT ending in 'Fine' should map to byte=0."""
        for preset, (group, byte) in PRESET_GROUPS.items():
            if not preset.endswith("Fine"):
                assert byte == 0, f"{preset} should be byte=0, got {byte}"

    def test_colour_role_consistency(self):
        """Every colour role preset must also be in PRESET_GROUPS."""
        for preset in PRESET_COLOUR_ROLE:
            assert preset in PRESET_GROUPS, f"{preset} in COLOUR_ROLE but not in GROUPS"

    def test_colour_role_fine_same_as_coarse(self):
        """Fine variant should have same colour role as coarse."""
        for preset, role in PRESET_COLOUR_ROLE.items():
            if preset.endswith("Fine"):
                coarse = preset.removesuffix("Fine")
                if coarse in PRESET_COLOUR_ROLE:
                    assert PRESET_COLOUR_ROLE[coarse] == role


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
