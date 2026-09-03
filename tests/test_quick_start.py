"""
tests/test_quick_start.py
==========================
Unit tests for the Quick Start QXW feature.

Covers:
  - FixtureCapabilities (single-fixture analysis)
  - RigCapabilityAnalysis (whole-rig grouping)
  - VCLayoutGenerator (function + VC XML generation)
  - build_qxw (standalone QXW builder)
  - template_library
  - Quick Start API routes
"""

import json
import os
import sys
import xml.etree.ElementTree as ET

import pytest

# ── ensure project root is importable ──────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.quick_start.fixture_analyzer import (
    FixtureCapabilities,
    RigCapabilityAnalysis,
)
from core.quick_start.vc_generator import VCLayoutGenerator
from core.quick_start.qxw_builder import build_qxw
from core.quick_start.template_library import list_templates, get_template


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures (pytest)
# ═════════════════════════════════════════════════════════════════════════════

MOVING_HEAD_CHANNELS = [
    "Pan", "Pan Fine", "Tilt", "Tilt Fine",
    "Dimmer", "Strobe", "Red", "Green", "Blue", "White",
    "Gobo", "Colour",
]

RGB_PAR_CHANNELS = ["Dimmer", "Red", "Green", "Blue", "Strobe"]

DIMMER_CHANNELS = ["Dimmer"]

SIMPLE_OTHER_CHANNELS = ["Speed", "Mode"]


@pytest.fixture
def moving_head_caps():
    return FixtureCapabilities(MOVING_HEAD_CHANNELS)


@pytest.fixture
def rgb_par_caps():
    return FixtureCapabilities(RGB_PAR_CHANNELS)


@pytest.fixture
def dimmer_caps():
    return FixtureCapabilities(DIMMER_CHANNELS)


@pytest.fixture
def other_caps():
    return FixtureCapabilities(SIMPLE_OTHER_CHANNELS)


def _make_rig_entry(name, key, ch_count, universe=0, address=0):
    """Helper to build a rig entry dict."""
    return {
        "name": name,
        "key": key,
        "manufacturer": key.split("::")[0] if "::" in key else "Generic",
        "model": key.split("::")[-1] if "::" in key else key,
        "mode": "Default",
        "ch_count": ch_count,
        "universe": universe,
        "address": address,
        "x_mm": 0, "z_mm": 0, "y_mm": 0,
    }


def _make_qxf_defs(entries_channels):
    """Build a qxf_defs dict from {key: [channel_names]}."""
    return {key: {"channels": chs} for key, chs in entries_channels.items()}


# ═════════════════════════════════════════════════════════════════════════════
# FixtureCapabilities
# ═════════════════════════════════════════════════════════════════════════════

class TestFixtureCapabilities:

    def test_moving_head_has_pan_tilt(self, moving_head_caps):
        assert moving_head_caps.has_pan_tilt() is True

    def test_moving_head_has_rgb(self, moving_head_caps):
        assert moving_head_caps.has_rgb() is True

    def test_moving_head_has_strobe(self, moving_head_caps):
        assert moving_head_caps.has_strobe() is True

    def test_moving_head_has_dimmer(self, moving_head_caps):
        assert moving_head_caps.has_dimmer() is True

    def test_moving_head_has_gobo(self, moving_head_caps):
        assert moving_head_caps.has_gobo() is True

    def test_moving_head_has_color_wheel(self, moving_head_caps):
        assert moving_head_caps.has_color_wheel() is True

    def test_moving_head_has_white(self, moving_head_caps):
        assert moving_head_caps.has_white() is True

    def test_rgb_par_no_pan_tilt(self, rgb_par_caps):
        assert rgb_par_caps.has_pan_tilt() is False

    def test_rgb_par_has_rgb(self, rgb_par_caps):
        assert rgb_par_caps.has_rgb() is True

    def test_rgb_par_has_strobe(self, rgb_par_caps):
        assert rgb_par_caps.has_strobe() is True

    def test_rgb_par_no_gobo(self, rgb_par_caps):
        assert rgb_par_caps.has_gobo() is False

    def test_dimmer_only(self, dimmer_caps):
        assert dimmer_caps.has_dimmer() is True
        assert dimmer_caps.has_pan_tilt() is False
        assert dimmer_caps.has_rgb() is False
        assert dimmer_caps.has_strobe() is False

    def test_other_no_capabilities(self, other_caps):
        assert other_caps.has_dimmer() is False
        assert other_caps.has_pan_tilt() is False
        assert other_caps.has_rgb() is False

    def test_channels_by_category(self, moving_head_caps):
        cats = moving_head_caps.channels_by_category()
        assert "Pan" in cats["pan_tilt"]
        assert "Tilt" in cats["pan_tilt"]
        assert "Red" in cats["rgb"]
        assert "Dimmer" in cats["dimmer"]
        assert "Gobo" in cats["gobo"]

    def test_dimmer_channel_name(self, moving_head_caps):
        assert moving_head_caps.dimmer_channel_name() == "Dimmer"

    def test_dimmer_channel_name_none(self, other_caps):
        assert other_caps.dimmer_channel_name() is None

    def test_rgb_channel_names(self, rgb_par_caps):
        rgb = rgb_par_caps.rgb_channel_names()
        assert rgb is not None
        assert rgb["red"] == "Red"
        assert rgb["green"] == "Green"
        assert rgb["blue"] == "Blue"

    def test_rgb_channel_names_none(self, dimmer_caps):
        assert dimmer_caps.rgb_channel_names() is None

    def test_strobe_channel_name(self, rgb_par_caps):
        assert rgb_par_caps.strobe_channel_name() == "Strobe"

    def test_strobe_channel_name_none(self, dimmer_caps):
        assert dimmer_caps.strobe_channel_name() is None

    def test_summary_keys(self, moving_head_caps):
        s = moving_head_caps.summary()
        expected_keys = {
            "has_pan_tilt", "has_rgb", "has_color_wheel", "has_strobe",
            "has_dimmer", "has_gobo", "has_white", "has_amber", "has_uv",
            "channel_count",
        }
        assert set(s.keys()) == expected_keys

    def test_summary_channel_count(self, moving_head_caps):
        assert moving_head_caps.summary()["channel_count"] == len(MOVING_HEAD_CHANNELS)

    def test_case_insensitive(self):
        caps = FixtureCapabilities(["pan", "TILT", "dimmer", "RED", "Green", "blue"])
        assert caps.has_pan_tilt() is True
        assert caps.has_rgb() is True
        assert caps.has_dimmer() is True

    def test_empty_channels(self):
        caps = FixtureCapabilities([])
        assert caps.has_dimmer() is False
        assert caps.has_pan_tilt() is False
        assert caps.has_rgb() is False
        assert caps.summary()["channel_count"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# RigCapabilityAnalysis
# ═════════════════════════════════════════════════════════════════════════════

class TestRigCapabilityAnalysis:

    def _make_mixed_rig(self):
        rig = [
            _make_rig_entry("MH 1", "Chauvet::Spot110", len(MOVING_HEAD_CHANNELS)),
            _make_rig_entry("PAR 1", "Generic::RGBPar", len(RGB_PAR_CHANNELS)),
            _make_rig_entry("DIM 1", "Generic::Dimmer", len(DIMMER_CHANNELS)),
            _make_rig_entry("FX 1", "Generic::FX", len(SIMPLE_OTHER_CHANNELS)),
        ]
        qxf = _make_qxf_defs({
            "Chauvet::Spot110": MOVING_HEAD_CHANNELS,
            "Generic::RGBPar": RGB_PAR_CHANNELS,
            "Generic::Dimmer": DIMMER_CHANNELS,
            "Generic::FX": SIMPLE_OTHER_CHANNELS,
        })
        return rig, qxf

    def test_group_by_type_mixed(self):
        rig, qxf = self._make_mixed_rig()
        analysis = RigCapabilityAnalysis(rig, qxf)
        groups = analysis.group_by_type()
        assert 0 in groups["moving_heads"]
        assert 1 in groups["color_fixtures"]
        assert 2 in groups["dimmers_only"]
        assert 3 in groups["other"]

    def test_has_any_rgb(self):
        rig, qxf = self._make_mixed_rig()
        analysis = RigCapabilityAnalysis(rig, qxf)
        assert analysis.has_any_rgb() is True

    def test_has_any_strobe(self):
        rig, qxf = self._make_mixed_rig()
        analysis = RigCapabilityAnalysis(rig, qxf)
        assert analysis.has_any_strobe() is True

    def test_has_any_dimmer(self):
        rig, qxf = self._make_mixed_rig()
        analysis = RigCapabilityAnalysis(rig, qxf)
        assert analysis.has_any_dimmer() is True

    def test_summary(self):
        rig, qxf = self._make_mixed_rig()
        analysis = RigCapabilityAnalysis(rig, qxf)
        s = analysis.summary()
        assert s["total_fixtures"] == 4
        assert s["moving_heads"] == 1
        assert s["color_fixtures"] == 1
        assert s["dimmers_only"] == 1
        assert s["other"] == 1
        assert s["has_rgb"] is True
        assert s["has_strobe"] is True

    def test_dimmers_only_rig(self):
        rig = [
            _make_rig_entry("DIM 1", "G::D", 1),
            _make_rig_entry("DIM 2", "G::D", 1),
        ]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        analysis = RigCapabilityAnalysis(rig, qxf)
        groups = analysis.group_by_type()
        assert len(groups["dimmers_only"]) == 2
        assert len(groups["moving_heads"]) == 0
        assert analysis.has_any_rgb() is False
        assert analysis.has_any_strobe() is False

    def test_empty_rig(self):
        analysis = RigCapabilityAnalysis([], {})
        groups = analysis.group_by_type()
        assert all(len(v) == 0 for v in groups.values())
        assert analysis.has_any_rgb() is False
        s = analysis.summary()
        assert s["total_fixtures"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# VCLayoutGenerator
# ═════════════════════════════════════════════════════════════════════════════

class TestVCLayoutGenerator:

    def _make_gen(self, rig, qxf):
        analysis = RigCapabilityAnalysis(rig, qxf)
        return VCLayoutGenerator(rig, qxf, analysis), analysis

    def test_generate_returns_tuple(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        result = gen.generate()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_generate_functions_list(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, vc_frame = gen.generate()
        assert isinstance(functions, list)
        assert len(functions) > 0

    def test_generate_vc_frame_element(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, vc_frame = gen.generate()
        assert isinstance(vc_frame, ET.Element)
        assert "Frame" in vc_frame.tag

    def test_all_on_off_scenes_created(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        names = [f.get("Name") for f in functions]
        assert "ALL ON" in names
        assert "ALL OFF" in names
        assert "BLACKOUT" in names

    def test_warm_cold_white_scenes(self):
        rig = [_make_rig_entry("PAR", "G::P", len(RGB_PAR_CHANNELS))]
        qxf = _make_qxf_defs({"G::P": RGB_PAR_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        names = [f.get("Name") for f in functions]
        assert "Warm White" in names
        assert "Cold White" in names

    def test_color_fade_chaser_when_rgb(self):
        rig = [_make_rig_entry("PAR", "G::P", len(RGB_PAR_CHANNELS))]
        qxf = _make_qxf_defs({"G::P": RGB_PAR_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        names = [f.get("Name") for f in functions]
        assert "Color Fade" in names
        assert "Colors" in names

    def test_no_color_fade_without_rgb(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        names = [f.get("Name") for f in functions]
        assert "Color Fade" not in names

    def test_strobe_effects_when_strobe(self):
        rig = [_make_rig_entry("PAR", "G::P", len(RGB_PAR_CHANNELS))]
        qxf = _make_qxf_defs({"G::P": RGB_PAR_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        names = [f.get("Name") for f in functions]
        assert "Strobe Low" in names
        assert "Strobe High" in names

    def test_no_strobe_without_strobe_channel(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        names = [f.get("Name") for f in functions]
        assert "Strobe Low" not in names
        assert "Strobe High" not in names

    def test_custom_slots_always_present(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        names = [f.get("Name") for f in functions]
        for i in range(1, 5):
            assert f"Custom {i}" in names

    def test_dimmer_sweep_chaser(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        names = [f.get("Name") for f in functions]
        assert "Dimmer Sweep" in names

    def test_function_ids_unique(self):
        rig = [
            _make_rig_entry("MH", "C::S", len(MOVING_HEAD_CHANNELS)),
            _make_rig_entry("PAR", "G::P", len(RGB_PAR_CHANNELS)),
        ]
        qxf = _make_qxf_defs({
            "C::S": MOVING_HEAD_CHANNELS,
            "G::P": RGB_PAR_CHANNELS,
        })
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        ids = [f.get("ID") for f in functions]
        assert len(ids) == len(set(ids)), "Function IDs must be unique"

    def test_function_ids_start_after_fixtures(self):
        rig = [
            _make_rig_entry("DIM", "G::D", 1),
            _make_rig_entry("DIM2", "G::D", 1),
        ]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        functions, _ = gen.generate()
        min_fid = min(int(f.get("ID")) for f in functions)
        assert min_fid >= len(rig), "Function IDs should start at or above fixture count"

    def test_vc_frame_contains_subframes(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        _, vc_frame = gen.generate()
        ns = "http://www.qlcplus.org/Workspace"
        subframes = vc_frame.findall(f"{{{ns}}}Frame")
        # Should have Macros, Fixture Groups, Scenes, Effects
        assert len(subframes) == 4

    def test_stats_after_generate(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        gen, _ = self._make_gen(rig, qxf)
        gen.generate()
        st = gen.stats()
        assert st["functions"] > 0
        assert st["scenes"] >= 0
        assert st["chasers"] >= 0


# ═════════════════════════════════════════════════════════════════════════════
# build_qxw
# ═════════════════════════════════════════════════════════════════════════════

class TestBuildQxw:

    def _generate(self, rig, qxf):
        analysis = RigCapabilityAnalysis(rig, qxf)
        gen = VCLayoutGenerator(rig, qxf, analysis)
        return gen.generate()

    def test_returns_bytes(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        funcs, vc = self._generate(rig, qxf)
        result = build_qxw(rig, funcs, vc)
        assert isinstance(result, bytes)

    def test_valid_xml(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        funcs, vc = self._generate(rig, qxf)
        xml_bytes = build_qxw(rig, funcs, vc)
        root = ET.fromstring(xml_bytes)
        assert root is not None

    def test_contains_xml_declaration(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        funcs, vc = self._generate(rig, qxf)
        xml_bytes = build_qxw(rig, funcs, vc)
        text = xml_bytes.decode("utf-8")
        assert text.startswith('<?xml version="1.0"')
        assert '<!DOCTYPE Workspace>' in text

    def test_contains_workspace_root(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        funcs, vc = self._generate(rig, qxf)
        xml_bytes = build_qxw(rig, funcs, vc)
        root = ET.fromstring(xml_bytes)
        assert "Workspace" in root.tag

    def test_contains_creator(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        funcs, vc = self._generate(rig, qxf)
        xml_bytes = build_qxw(rig, funcs, vc)
        root = ET.fromstring(xml_bytes)
        ns = "http://www.qlcplus.org/Workspace"
        creator = root.find(f"{{{ns}}}Creator")
        assert creator is not None

    def test_contains_fixtures(self):
        rig = [
            _make_rig_entry("DIM1", "G::D", 1, universe=0, address=0),
            _make_rig_entry("DIM2", "G::D", 1, universe=0, address=1),
        ]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        funcs, vc = self._generate(rig, qxf)
        xml_bytes = build_qxw(rig, funcs, vc)
        root = ET.fromstring(xml_bytes)
        ns = "http://www.qlcplus.org/Workspace"
        engine = root.find(f"{{{ns}}}Engine")
        fixtures = engine.findall(f"{{{ns}}}Fixture")
        assert len(fixtures) == 2

    def test_contains_virtual_console(self):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        funcs, vc = self._generate(rig, qxf)
        xml_bytes = build_qxw(rig, funcs, vc)
        root = ET.fromstring(xml_bytes)
        ns = "http://www.qlcplus.org/Workspace"
        vc_el = root.find(f"{{{ns}}}VirtualConsole")
        assert vc_el is not None

    def test_multi_universe_rig(self):
        rig = [
            _make_rig_entry("F1", "G::D", 1, universe=0, address=0),
            _make_rig_entry("F2", "G::D", 1, universe=1, address=0),
        ]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        funcs, vc = self._generate(rig, qxf)
        xml_bytes = build_qxw(rig, funcs, vc)
        root = ET.fromstring(xml_bytes)
        ns = "http://www.qlcplus.org/Workspace"
        engine = root.find(f"{{{ns}}}Engine")
        iom = engine.find(f"{{{ns}}}InputOutputMap")
        universes = iom.findall(f"{{{ns}}}Universe")
        assert len(universes) == 2

    def test_export_to_file(self, tmp_path):
        rig = [_make_rig_entry("DIM", "G::D", 1)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})
        funcs, vc = self._generate(rig, qxf)
        xml_bytes = build_qxw(rig, funcs, vc)
        out = tmp_path / "test_output.qxw"
        out.write_bytes(xml_bytes)
        assert out.exists()
        assert out.stat().st_size > 0
        # Verify it parses back
        root = ET.parse(str(out)).getroot()
        assert "Workspace" in root.tag


# ═════════════════════════════════════════════════════════════════════════════
# Template library
# ═════════════════════════════════════════════════════════════════════════════

class TestTemplateLibrary:

    def test_list_templates(self):
        templates = list_templates()
        assert isinstance(templates, list)
        assert len(templates) >= 1

    def test_default_template_exists(self):
        templates = list_templates()
        ids = [t["id"] for t in templates]
        assert "default" in ids

    def test_get_template_default(self):
        t = get_template("default")
        assert t["name"] == "Default"
        assert "description" in t

    def test_get_template_unknown_returns_default(self):
        t = get_template("nonexistent_template_xyz")
        assert t["name"] == "Default"


# ═════════════════════════════════════════════════════════════════════════════
# API routes (Flask test client)
# ═════════════════════════════════════════════════════════════════════════════

class TestQuickStartRoutes:

    @pytest.fixture
    def client(self):
        """Create a Flask test client."""
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_status_endpoint(self, client):
        resp = client.get("/api/quickstart/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "rig" in data

    def test_clear_endpoint(self, client):
        resp = client.post("/api/quickstart/clear")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["rig"] == []

    def test_add_fixture_no_qxf(self, client):
        """Adding a fixture without loading a QXF first should error."""
        resp = client.post("/api/quickstart/add-fixture",
                           json={"name": "Test", "quantity": 1})
        assert resp.status_code == 200
        data = resp.get_json()
        # Should either error or add with minimal info
        assert "error" in data or "rig" in data

    def test_analyse_empty_rig(self, client):
        client.post("/api/quickstart/clear")
        resp = client.get("/api/quickstart/analyse")
        assert resp.status_code == 200

    def test_auto_dmx_empty_rig(self, client):
        client.post("/api/quickstart/clear")
        resp = client.post("/api/quickstart/auto-dmx")
        assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# Integration: end-to-end generation
# ═════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:

    def test_complex_rig_export(self, tmp_path):
        """Full pipeline: mixed rig → analysis → VC gen → QXW export."""
        rig = [
            _make_rig_entry("MH 1", "C::MH", len(MOVING_HEAD_CHANNELS), 0, 0),
            _make_rig_entry("MH 2", "C::MH", len(MOVING_HEAD_CHANNELS), 0, 12),
            _make_rig_entry("PAR 1", "G::PAR", len(RGB_PAR_CHANNELS), 0, 24),
            _make_rig_entry("PAR 2", "G::PAR", len(RGB_PAR_CHANNELS), 0, 29),
            _make_rig_entry("DIM 1", "G::DIM", 1, 0, 34),
            _make_rig_entry("DIM 2", "G::DIM", 1, 0, 35),
        ]
        qxf = _make_qxf_defs({
            "C::MH": MOVING_HEAD_CHANNELS,
            "G::PAR": RGB_PAR_CHANNELS,
            "G::DIM": DIMMER_CHANNELS,
        })

        # Analysis
        analysis = RigCapabilityAnalysis(rig, qxf)
        groups = analysis.group_by_type()
        assert len(groups["moving_heads"]) == 2
        assert len(groups["color_fixtures"]) == 2
        assert len(groups["dimmers_only"]) == 2

        # Generate
        gen = VCLayoutGenerator(rig, qxf, analysis)
        functions, vc_frame = gen.generate()
        assert len(functions) > 10  # Should have many functions for complex rig

        # Build QXW
        xml_bytes = build_qxw(rig, functions, vc_frame)
        out = tmp_path / "complex_rig.qxw"
        out.write_bytes(xml_bytes)
        assert out.exists()

        # Parse and verify structure
        root = ET.parse(str(out)).getroot()
        ns = "http://www.qlcplus.org/Workspace"
        engine = root.find(f"{{{ns}}}Engine")
        assert len(engine.findall(f"{{{ns}}}Fixture")) == 6
        assert len(engine.findall(f"{{{ns}}}Function")) == len(functions)

    def test_dimmers_only_export(self, tmp_path):
        """Simplest case: dimmers only → minimal VC."""
        rig = [_make_rig_entry(f"DIM {i}", "G::D", 1, 0, i) for i in range(8)]
        qxf = _make_qxf_defs({"G::D": DIMMER_CHANNELS})

        analysis = RigCapabilityAnalysis(rig, qxf)
        assert analysis.has_any_rgb() is False
        assert analysis.has_any_strobe() is False

        gen = VCLayoutGenerator(rig, qxf, analysis)
        functions, vc_frame = gen.generate()

        # No color fade or strobe effects
        names = [f.get("Name") for f in functions]
        assert "Color Fade" not in names
        assert "Strobe Low" not in names

        xml_bytes = build_qxw(rig, functions, vc_frame)
        root = ET.fromstring(xml_bytes)
        assert "Workspace" in root.tag
