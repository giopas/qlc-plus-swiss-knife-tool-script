"""
Tests for core/porter.py — Function Porter engine
==================================================
Uses small synthetic QXW files written to /tmp so the module can parse them.
"""

import os
import sys
import tempfile
import textwrap
import unittest
from xml.etree import ElementTree as ET

# Make the module importable from the cloud container
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import porter, qxw_io


# ─── Helpers: build minimal QXW XML ──────────────────────────────────────────

def _make_qxw(fixtures_xml: str = "", functions_xml: str = "",
               version: str = "4.13.1") -> str:
    """Return a complete QXW XML string (no leading whitespace on first line)."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE Workspace>\n'
        '<Workspace>\n'
        ' <Creator>\n'
        '  <Name>Q Light Controller Plus</Name>\n'
        f'  <Version>{version}</Version>\n'
        '  <Author>Test</Author>\n'
        ' </Creator>\n'
        ' <Engine>\n'
        f'  {fixtures_xml}\n'
        f'  {functions_xml}\n'
        ' </Engine>\n'
        '</Workspace>'
    )


def _write_qxw(content: str, suffix: str = ".qxw") -> str:
    """Write QXW content to a temp file; return path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, content.encode("utf-8"))
    os.close(fd)
    return path


# ─── Fixture XML fragments ──────────────────────────────────────────────────

SRC_FIXTURE_A = """
<Fixture>
 <Manufacturer>Chauvet</Manufacturer>
 <Model>Intimidator Spot 375Z IRC</Model>
 <Mode>15 channel</Mode>
 <ID>0</ID>
 <Name>Spot L</Name>
 <Universe>0</Universe>
 <Address>0</Address>
 <Channels>15</Channels>
</Fixture>"""

SRC_FIXTURE_B = """
<Fixture>
 <Manufacturer>Chauvet</Manufacturer>
 <Model>Intimidator Spot 375Z IRC</Model>
 <Mode>15 channel</Mode>
 <ID>1</ID>
 <Name>Spot R</Name>
 <Universe>0</Universe>
 <Address>15</Address>
 <Channels>15</Channels>
</Fixture>"""

TGT_FIXTURE_1 = """
<Fixture>
 <Manufacturer>Chauvet</Manufacturer>
 <Model>Intimidator Spot 375Z IRC</Model>
 <Mode>15 channel</Mode>
 <ID>10</ID>
 <Name>Spot 1</Name>
 <Universe>0</Universe>
 <Address>0</Address>
 <Channels>15</Channels>
</Fixture>"""

TGT_FIXTURE_2 = """
<Fixture>
 <Manufacturer>Chauvet</Manufacturer>
 <Model>Intimidator Spot 375Z IRC</Model>
 <Mode>15 channel</Mode>
 <ID>11</ID>
 <Name>Spot 2</Name>
 <Universe>0</Universe>
 <Address>15</Address>
 <Channels>15</Channels>
</Fixture>"""

TGT_FIXTURE_3 = """
<Fixture>
 <Manufacturer>Chauvet</Manufacturer>
 <Model>Intimidator Spot 375Z IRC</Model>
 <Mode>15 channel</Mode>
 <ID>12</ID>
 <Name>Spot 3</Name>
 <Universe>0</Universe>
 <Address>30</Address>
 <Channels>15</Channels>
</Fixture>"""

TGT_FIXTURE_4 = """
<Fixture>
 <Manufacturer>Chauvet</Manufacturer>
 <Model>Intimidator Spot 375Z IRC</Model>
 <Mode>15 channel</Mode>
 <ID>13</ID>
 <Name>Spot 4</Name>
 <Universe>0</Universe>
 <Address>45</Address>
 <Channels>15</Channels>
</Fixture>"""

TGT_FIXTURE_DIFF_MODEL = """
<Fixture>
 <Manufacturer>Chauvet</Manufacturer>
 <Model>SlimPAR 56</Model>
 <Mode>7 channel</Mode>
 <ID>20</ID>
 <Name>Par 1</Name>
 <Universe>0</Universe>
 <Address>100</Address>
 <Channels>7</Channels>
</Fixture>"""

TGT_FIXTURE_DIFF_MODE = """
<Fixture>
 <Manufacturer>Chauvet</Manufacturer>
 <Model>Intimidator Spot 375Z IRC</Model>
 <Mode>9 channel</Mode>
 <ID>21</ID>
 <Name>Spot 5 (9ch)</Name>
 <Universe>0</Universe>
 <Address>60</Address>
 <Channels>9</Channels>
</Fixture>"""


# ─── Function XML fragments ─────────────────────────────────────────────────

SCENE_A = """
<Function ID="0" Type="Scene" Name="Scene A">
 <FixtureVal ID="0">0,128,1,64</FixtureVal>
 <FixtureVal ID="1">0,200,1,100</FixtureVal>
</Function>"""

SCENE_B = """
<Function ID="1" Type="Scene" Name="Scene B">
 <FixtureVal ID="0">0,255,1,0</FixtureVal>
 <FixtureVal ID="1">0,0,1,255</FixtureVal>
</Function>"""

CHASER_AB = """
<Function ID="2" Type="Chaser" Name="Chase AB">
 <Step Number="0">0</Step>
 <Step Number="1">1</Step>
</Function>"""

COLLECTION_X = """
<Function ID="3" Type="Collection" Name="Collection X">
 <Step Number="0">0</Step>
</Function>"""

SEQUENCE_S = """
<Function ID="4" Type="Sequence" Name="Seq S" BoundScene="0">
 <Step Number="0">0,128</Step>
 <Step Number="1">0,255</Step>
</Function>"""

SCRIPT_F = """
<Function ID="5" Type="Script" Name="Script F">
 <Command>startfunction:0</Command>
 <Command>waitms:1000</Command>
 <Command>stopfunction:0</Command>
 <Command>startfunction:1</Command>
</Function>"""

EFX_G = """
<Function ID="6" Type="EFX" Name="EFX G">
 <EFXFixture>
  <ID>0</ID>
  <Head>0</Head>
  <Mode>0</Mode>
 </EFXFixture>
 <EFXFixture>
  <ID>1</ID>
  <Head>0</Head>
  <Mode>0</Mode>
 </EFXFixture>
</Function>"""

# Function with no fixture refs (pure chaser that chains others)
CHASER_META = """
<Function ID="7" Type="Chaser" Name="Meta Chaser">
 <Step Number="0">2</Step>
</Function>"""


# ═════════════════════════════════════════════════════════════════════════════
# Test classes
# ═════════════════════════════════════════════════════════════════════════════

class TestLoadAndState(unittest.TestCase):
    """Test load/clear/state operations."""

    def setUp(self):
        porter.clear()
        self.src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B,
            SCENE_A + SCENE_B + CHASER_AB))
        self.tgt_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2, ""))

    def tearDown(self):
        porter.clear()
        for p in (self.src_path, self.tgt_path):
            if os.path.exists(p):
                os.unlink(p)

    def test_initial_state(self):
        state = porter.get_state()
        self.assertFalse(state["src_loaded"])
        self.assertFalse(state["tgt_loaded"])

    def test_load_source(self):
        summary = porter.load_source(self.src_path)
        self.assertEqual(summary["fixtures"], 2)
        self.assertEqual(summary["functions"], 3)
        state = porter.get_state()
        self.assertTrue(state["src_loaded"])
        self.assertIn("4.13.1", summary["creator_version"])

    def test_load_target(self):
        summary = porter.load_target(self.tgt_path)
        self.assertEqual(summary["fixtures"], 2)
        self.assertEqual(summary["functions"], 0)
        state = porter.get_state()
        self.assertTrue(state["tgt_loaded"])

    def test_clear(self):
        porter.load_source(self.src_path)
        porter.load_target(self.tgt_path)
        porter.clear()
        state = porter.get_state()
        self.assertFalse(state["src_loaded"])
        self.assertFalse(state["tgt_loaded"])


class TestListHelpers(unittest.TestCase):
    """Test list_source_functions, list_source_fixtures, etc."""

    def setUp(self):
        porter.clear()
        self.src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B,
            SCENE_A + SCENE_B + CHASER_AB + EFX_G))
        porter.load_source(self.src_path)

    def tearDown(self):
        porter.clear()
        os.unlink(self.src_path)

    def test_list_source_functions(self):
        fns = porter.list_source_functions()
        self.assertEqual(len(fns), 4)
        names = {f["name"] for f in fns}
        self.assertIn("Scene A", names)
        self.assertIn("Chase AB", names)
        self.assertIn("EFX G", names)
        # Check type field
        chaser = [f for f in fns if f["name"] == "Chase AB"][0]
        self.assertEqual(chaser["type"], "Chaser")

    def test_list_source_fixtures(self):
        fixes = porter.list_source_fixtures()
        self.assertEqual(len(fixes), 2)
        ids = {f["id"] for f in fixes}
        self.assertIn("0", ids)
        self.assertIn("1", ids)
        spot_l = [f for f in fixes if f["name"] == "Spot L"][0]
        self.assertEqual(spot_l["model"], "Intimidator Spot 375Z IRC")
        self.assertEqual(spot_l["channels"], "15")

    def test_list_not_loaded(self):
        porter.clear()
        self.assertEqual(porter.list_source_functions(), [])
        self.assertEqual(porter.list_source_fixtures(), [])
        self.assertEqual(porter.list_target_fixtures(), [])


class TestDependencyResolution(unittest.TestCase):
    """Test resolve_closure — the recursive dependency walker."""

    def setUp(self):
        porter.clear()

    def tearDown(self):
        porter.clear()

    def _load_src(self, fixtures_xml, functions_xml, version="4.13.1"):
        path = _write_qxw(_make_qxw(fixtures_xml, functions_xml, version))
        porter.load_source(path)
        self._paths = getattr(self, '_paths', [])
        self._paths.append(path)
        return path

    def _cleanup_paths(self):
        for p in getattr(self, '_paths', []):
            if os.path.exists(p):
                os.unlink(p)

    # ── Single function, no deps ─────────────────────────────────────────
    def test_single_scene(self):
        self._load_src(SRC_FIXTURE_A + SRC_FIXTURE_B, SCENE_A)
        result = porter.resolve_closure(["0"])
        self.assertEqual(result["function_ids"], ["0"])
        self.assertIn("0", result["fixture_ids"])
        self.assertIn("1", result["fixture_ids"])
        self.assertEqual(result["cycles"], [])
        self.assertEqual(result["unresolved"], [])
        self._cleanup_paths()

    # ── Chaser pulling in its Scenes ─────────────────────────────────────
    def test_chaser_pulls_scenes(self):
        self._load_src(SRC_FIXTURE_A + SRC_FIXTURE_B,
                        SCENE_A + SCENE_B + CHASER_AB)
        result = porter.resolve_closure(["2"])
        # Chaser 2 depends on Scene 0 and Scene 1
        self.assertIn("2", result["function_ids"])
        self.assertIn("0", result["function_ids"])
        self.assertIn("1", result["function_ids"])
        self.assertEqual(len(result["function_ids"]), 3)
        # Dep map
        self.assertIn("0", result["dep_map"]["2"])
        self.assertIn("1", result["dep_map"]["2"])
        # Fixtures come from the scenes
        self.assertIn("0", result["fixture_ids"])
        self.assertIn("1", result["fixture_ids"])
        self._cleanup_paths()

    # ── Meta-chaser (chaser of chaser) ───────────────────────────────────
    def test_nested_deps(self):
        self._load_src(SRC_FIXTURE_A + SRC_FIXTURE_B,
                        SCENE_A + SCENE_B + CHASER_AB + CHASER_META)
        result = porter.resolve_closure(["7"])
        # 7 → 2 → (0, 1)
        self.assertEqual(len(result["function_ids"]), 4)
        self.assertIn("7", result["function_ids"])
        self.assertIn("2", result["function_ids"])
        self.assertIn("0", result["function_ids"])
        self.assertIn("1", result["function_ids"])
        self._cleanup_paths()

    # ── Collection ───────────────────────────────────────────────────────
    def test_collection_deps(self):
        self._load_src(SRC_FIXTURE_A + SRC_FIXTURE_B,
                        SCENE_A + COLLECTION_X)
        result = porter.resolve_closure(["3"])
        # Collection 3 → Scene 0
        self.assertIn("3", result["function_ids"])
        self.assertIn("0", result["function_ids"])
        self._cleanup_paths()

    # ── Sequence with BoundScene ─────────────────────────────────────────
    def test_sequence_bound_scene(self):
        self._load_src(SRC_FIXTURE_A + SRC_FIXTURE_B,
                        SCENE_A + SEQUENCE_S)
        result = porter.resolve_closure(["4"])
        # Sequence 4 → BoundScene 0
        self.assertIn("4", result["function_ids"])
        self.assertIn("0", result["function_ids"])
        self._cleanup_paths()

    # ── Script function refs ─────────────────────────────────────────────
    def test_script_func_refs(self):
        self._load_src(SRC_FIXTURE_A + SRC_FIXTURE_B,
                        SCENE_A + SCENE_B + SCRIPT_F)
        result = porter.resolve_closure(["5"])
        # Script 5 → startfunction:0, stopfunction:0, startfunction:1
        self.assertIn("0", result["function_ids"])
        self.assertIn("1", result["function_ids"])
        self._cleanup_paths()

    # ── EFX fixture refs ─────────────────────────────────────────────────
    def test_efx_fixture_refs(self):
        self._load_src(SRC_FIXTURE_A + SRC_FIXTURE_B, EFX_G)
        result = porter.resolve_closure(["6"])
        self.assertIn("0", result["fixture_ids"])
        self.assertIn("1", result["fixture_ids"])
        self._cleanup_paths()

    # ── Unresolved reference ─────────────────────────────────────────────
    def test_unresolved_ref(self):
        # Chaser references functions 0 and 1, but only 0 exists
        self._load_src(SRC_FIXTURE_A, SCENE_A + CHASER_AB)
        result = porter.resolve_closure(["2"])
        self.assertIn("1", result["unresolved"])
        self._cleanup_paths()

    # ── Multiple seeds ───────────────────────────────────────────────────
    def test_multiple_seeds(self):
        self._load_src(SRC_FIXTURE_A + SRC_FIXTURE_B,
                        SCENE_A + SCENE_B + CHASER_AB)
        result = porter.resolve_closure(["0", "1"])
        self.assertEqual(result["seed_ids"], ["0", "1"])
        # Seeds come first in function_ids
        self.assertEqual(result["function_ids"][0], "0")
        self.assertEqual(result["function_ids"][1], "1")
        self._cleanup_paths()

    # ── Not loaded raises ────────────────────────────────────────────────
    def test_not_loaded_raises(self):
        with self.assertRaises(RuntimeError):
            porter.resolve_closure(["0"])


class TestFixtureCompatibility(unittest.TestCase):
    """Test build_fixture_candidates and auto_map."""

    def setUp(self):
        porter.clear()
        src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B, SCENE_A))
        tgt_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2 + TGT_FIXTURE_3 +
            TGT_FIXTURE_DIFF_MODE + TGT_FIXTURE_DIFF_MODEL, ""))
        porter.load_source(src_path)
        porter.load_target(tgt_path)
        self._paths = [src_path, tgt_path]

    def tearDown(self):
        porter.clear()
        for p in self._paths:
            if os.path.exists(p):
                os.unlink(p)

    def test_tier1_exact_match(self):
        info = porter.build_fixture_candidates(["0", "1"])
        # Source fixture 0 (Chauvet/375Z/15ch) should find tier1 matches
        # in target fixtures 10, 11, 12 (same model+mode)
        tier1_ids = {t["id"] for t in info["candidates"]["0"]["tier1"]}
        self.assertIn("10", tier1_ids)
        self.assertIn("11", tier1_ids)
        self.assertIn("12", tier1_ids)
        # Should NOT include the 9ch mode fixture
        self.assertNotIn("21", tier1_ids)

    def test_tier2_same_model_diff_mode(self):
        info = porter.build_fixture_candidates(["0"])
        tier2_ids = {t["id"] for t in info["candidates"]["0"]["tier2"]}
        self.assertIn("21", tier2_ids)  # Same model, 9ch mode

    def test_tier3_different_model(self):
        info = porter.build_fixture_candidates(["0"])
        tier3_ids = {t["id"] for t in info["candidates"]["0"]["tier3"]}
        self.assertIn("20", tier3_ids)  # SlimPAR 56

    def test_auto_map(self):
        mapping = porter.auto_map(["0", "1"])
        # Both source fixtures map to the same tier1 targets
        self.assertEqual(set(mapping["0"]), {"10", "11", "12"})
        self.assertEqual(set(mapping["1"]), {"10", "11", "12"})


class TestFanout(unittest.TestCase):
    """Test compute_fanout modes."""

    def test_pattern_repeat(self):
        # 2 source fixtures, 4 targets
        src_ids = ["0", "1"]
        mapping = {"0": ["10", "11", "12", "13"], "1": ["10", "11", "12", "13"]}
        result = porter.compute_fanout(src_ids, mapping, "pattern_repeat")
        # Targets cycle: 10→0, 11→1, 12→0, 13→1
        self.assertEqual(result["10"], "0")
        self.assertEqual(result["11"], "1")
        self.assertEqual(result["12"], "0")
        self.assertEqual(result["13"], "1")

    def test_clone(self):
        src_ids = ["0", "1"]
        mapping = {"0": ["10", "11"], "1": ["12", "13"]}
        result = porter.compute_fanout(src_ids, mapping, "clone")
        # Each target gets its mapped source
        self.assertEqual(result["10"], "0")
        self.assertEqual(result["11"], "0")
        self.assertEqual(result["12"], "1")
        self.assertEqual(result["13"], "1")

    def test_block(self):
        src_ids = ["0", "1"]
        mapping = {"0": ["10", "11", "12", "13"], "1": ["10", "11", "12", "13"]}
        result = porter.compute_fanout(src_ids, mapping, "block")
        # 4 targets / 2 sources = block of 2: first 2→src[0], last 2→src[1]
        self.assertEqual(result["10"], "0")
        self.assertEqual(result["11"], "0")
        self.assertEqual(result["12"], "1")
        self.assertEqual(result["13"], "1")

    def test_manual(self):
        src_ids = ["0", "1"]
        mapping = {"0": ["10"], "1": ["13"]}
        result = porter.compute_fanout(src_ids, mapping, "manual")
        self.assertEqual(result["10"], "0")
        self.assertEqual(result["13"], "1")
        self.assertEqual(len(result), 2)

    def test_empty(self):
        result = porter.compute_fanout([], {}, "pattern_repeat")
        self.assertEqual(result, {})

    def test_no_targets(self):
        result = porter.compute_fanout(["0"], {"0": []}, "clone")
        self.assertEqual(result, {})


class TestMirrorPan(unittest.TestCase):
    """Test 16-bit and 8-bit Pan mirror math."""

    def test_8bit_inversion(self):
        # Channel 0 is Pan coarse, value 128
        result = porter.mirror_pan_values("0,128,1,64", pan_ch_index=0)
        # 255 - 128 = 127
        parts = result.split(",")
        pair_dict = {int(parts[i]): int(parts[i+1])
                     for i in range(0, len(parts), 2)}
        self.assertEqual(pair_dict[0], 127)
        self.assertEqual(pair_dict[1], 64)  # Tilt untouched

    def test_16bit_inversion(self):
        # Pan coarse=0, Pan fine=1
        # Coarse=128, Fine=0 → combined = 128*256 + 0 = 32768
        # Inverted = 65535 - 32768 = 32767
        # New coarse = 32767 >> 8 = 127, new fine = 32767 & 0xFF = 255
        result = porter.mirror_pan_values(
            "0,128,1,0,2,100", pan_ch_index=0, pan_fine_ch_index=1)
        parts = result.split(",")
        pair_dict = {int(parts[i]): int(parts[i+1])
                     for i in range(0, len(parts), 2)}
        self.assertEqual(pair_dict[0], 127)
        self.assertEqual(pair_dict[1], 255)
        self.assertEqual(pair_dict[2], 100)  # Other channel untouched

    def test_16bit_full_left(self):
        # Pan=0,0 → combined=0, inverted=65535
        # coarse=255, fine=255
        result = porter.mirror_pan_values(
            "0,0,1,0", pan_ch_index=0, pan_fine_ch_index=1)
        parts = result.split(",")
        pair_dict = {int(parts[i]): int(parts[i+1])
                     for i in range(0, len(parts), 2)}
        self.assertEqual(pair_dict[0], 255)
        self.assertEqual(pair_dict[1], 255)

    def test_16bit_full_right(self):
        # Pan=255,255 → combined=65535, inverted=0
        # coarse=0, fine=0
        result = porter.mirror_pan_values(
            "0,255,1,255", pan_ch_index=0, pan_fine_ch_index=1)
        parts = result.split(",")
        pair_dict = {int(parts[i]): int(parts[i+1])
                     for i in range(0, len(parts), 2)}
        self.assertEqual(pair_dict[0], 0)
        self.assertEqual(pair_dict[1], 0)

    def test_16bit_midpoint(self):
        # Pan=127,255 → combined=32767, inverted=32768
        # coarse=128, fine=0
        result = porter.mirror_pan_values(
            "0,127,1,255", pan_ch_index=0, pan_fine_ch_index=1)
        parts = result.split(",")
        pair_dict = {int(parts[i]): int(parts[i+1])
                     for i in range(0, len(parts), 2)}
        self.assertEqual(pair_dict[0], 128)
        self.assertEqual(pair_dict[1], 0)

    def test_no_pan_present(self):
        # If the pan channel isn't in the value string, nothing changes
        result = porter.mirror_pan_values("2,100,3,200", pan_ch_index=0)
        parts = result.split(",")
        pair_dict = {int(parts[i]): int(parts[i+1])
                     for i in range(0, len(parts), 2)}
        self.assertEqual(pair_dict[2], 100)
        self.assertEqual(pair_dict[3], 200)


class TestValidation(unittest.TestCase):
    """Test validate() with various plan shapes."""

    def setUp(self):
        porter.clear()
        src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B,
            SCENE_A + SCENE_B + CHASER_AB))
        tgt_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2, ""))
        porter.load_source(src_path)
        porter.load_target(tgt_path)
        self._paths = [src_path, tgt_path]

    def tearDown(self):
        porter.clear()
        for p in self._paths:
            if os.path.exists(p):
                os.unlink(p)

    def _make_plan(self, **overrides):
        closure = porter.resolve_closure(["2"])
        plan = {
            "closure": closure,
            "fixture_mapping": {"0": ["10"], "1": ["11"]},
            "fanout_mode": "clone",
            "mirror_fixtures": [],
            "pan_channel_map": {},
        }
        plan.update(overrides)
        return plan

    def test_valid_plan(self):
        plan = self._make_plan()
        v = porter.validate(plan)
        self.assertTrue(v["ok"])
        self.assertEqual(v["errors"], [])

    def test_no_functions_error(self):
        plan = self._make_plan()
        plan["closure"]["function_ids"] = []
        v = porter.validate(plan)
        self.assertFalse(v["ok"])
        self.assertTrue(any("No functions" in e for e in v["errors"]))

    def test_unmapped_fixture_error(self):
        plan = self._make_plan(fixture_mapping={"0": ["10"]})
        # Fixture 1 is referenced but has no mapping
        v = porter.validate(plan)
        self.assertFalse(v["ok"])
        self.assertTrue(any("no target" in e for e in v["errors"]))

    def test_name_collision_warning(self):
        # Load target that already has a function named "Scene A"
        porter.clear()
        tgt_with_fn = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2,
            '<Function ID="50" Type="Scene" Name="Scene A">'
            '<FixtureVal ID="10">0,100</FixtureVal></Function>'))
        src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B,
            SCENE_A + SCENE_B + CHASER_AB))
        porter.load_source(src_path)
        porter.load_target(tgt_with_fn)
        self._paths.extend([tgt_with_fn, src_path])

        plan = self._make_plan()
        v = porter.validate(plan)
        self.assertTrue(any("already exists" in w for w in v["warnings"]))

    def test_info_summary(self):
        plan = self._make_plan()
        v = porter.validate(plan)
        self.assertTrue(len(v["info"]) >= 2)
        # Should mention number of functions
        self.assertTrue(any("3 functions" in i for i in v["info"]))

    def test_mirror_without_pan_map_warns(self):
        plan = self._make_plan(mirror_fixtures=["10"])
        v = porter.validate(plan)
        self.assertTrue(any("Mirror" in w or "Pan" in w for w in v["warnings"]))


class TestExecute(unittest.TestCase):
    """Test execute() — the full import pipeline."""

    def setUp(self):
        porter.clear()
        self.src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B,
            SCENE_A + SCENE_B + CHASER_AB))
        self.tgt_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2, ""))
        porter.load_source(self.src_path)
        porter.load_target(self.tgt_path)

    def tearDown(self):
        porter.clear()
        for p in (self.src_path, self.tgt_path):
            if os.path.exists(p):
                os.unlink(p)

    def _make_plan(self, **overrides):
        closure = porter.resolve_closure(["2"])
        plan = {
            "closure": closure,
            "fixture_mapping": {"0": ["10"], "1": ["11"]},
            "fanout_mode": "clone",
            "mirror_fixtures": [],
            "pan_channel_map": {},
        }
        plan.update(overrides)
        return plan

    def test_basic_import(self):
        plan = self._make_plan()
        filename, xml_bytes = porter.execute(plan)

        # Parse the result
        root = qxw_io.strip_ns(ET.fromstring(xml_bytes))
        engine = root.find("Engine")
        functions = engine.findall("Function")

        # Should have 3 new functions
        self.assertEqual(len(functions), 3)

        # All function IDs should be > max existing target ID (11)
        for fn in functions:
            fid = int(fn.get("ID"))
            self.assertGreater(fid, 11)

        # The chaser's Steps should reference the new IDs, not 0 and 1
        chaser = [fn for fn in functions if fn.get("Type") == "Chaser"][0]
        steps = chaser.findall("Step")
        step_ids = [s.text.strip() for s in steps]
        for sid in step_ids:
            self.assertGreater(int(sid), 11, "Chaser step IDs should be rebased")

        # The scenes should reference target fixture IDs
        scenes = [fn for fn in functions if fn.get("Type") == "Scene"]
        for scene in scenes:
            for fv in scene.findall("FixtureVal"):
                fix_id = fv.get("ID")
                self.assertIn(fix_id, ["10", "11"],
                              "Scene FixtureVal should reference target fixtures")

    def test_filename_suggestion(self):
        plan = self._make_plan()
        filename, _ = porter.execute(plan)
        self.assertTrue(filename.endswith(".qxw"))
        self.assertTrue(filename.endswith("_v2.qxw"))  # qxw_io.next_version_name

    def test_name_prefix(self):
        plan = self._make_plan(name_prefix="SHOW2 / ")
        _, xml_bytes = porter.execute(plan)
        root = qxw_io.strip_ns(ET.fromstring(xml_bytes))
        engine = root.find("Engine")
        for fn in engine.findall("Function"):
            self.assertTrue(fn.get("Name", "").startswith("SHOW2 / "),
                            f"Function name should be prefixed: {fn.get('Name')}")

    def test_name_collision_prefixed(self):
        # Target already has "Scene A"
        porter.clear()
        tgt_with_fn = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2,
            '<Function ID="50" Type="Scene" Name="Scene A">'
            '<FixtureVal ID="10">0,100</FixtureVal></Function>'))
        porter.load_source(self.src_path)
        porter.load_target(tgt_with_fn)

        plan = self._make_plan()
        _, xml_bytes = porter.execute(plan)
        root = qxw_io.strip_ns(ET.fromstring(xml_bytes))
        engine = root.find("Engine")

        names = [fn.get("Name") for fn in engine.findall("Function")]
        # The original "Scene A" should remain, and the imported one
        # should be prefixed with [imported]
        imported_a = [n for n in names if "imported" in n and "Scene A" in n]
        self.assertTrue(len(imported_a) >= 1, f"Expected [imported] prefix, got names: {names}")
        os.unlink(tgt_with_fn)

    def test_fanout_duplication(self):
        # Map source fixture 0 to targets 10,11 and source 1 to 12
        # (need fixture 12 in target)
        porter.clear()
        tgt3_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2 + TGT_FIXTURE_3, ""))
        porter.load_source(self.src_path)
        porter.load_target(tgt3_path)

        closure = porter.resolve_closure(["0"])  # Just Scene A
        plan = {
            "closure": closure,
            "fixture_mapping": {"0": ["10", "11"], "1": ["12"]},
            "fanout_mode": "clone",
            "mirror_fixtures": [],
            "pan_channel_map": {},
        }
        _, xml_bytes = porter.execute(plan)
        root = qxw_io.strip_ns(ET.fromstring(xml_bytes))
        engine = root.find("Engine")
        scene = engine.findall("Function")[0]
        fvals = scene.findall("FixtureVal")
        # Original had 2 FixtureVals (fix 0 and fix 1).
        # Fix 0 → [10, 11] = 2 FixtureVals; Fix 1 → [12] = 1 FixtureVal
        # Total = 3
        fv_ids = [fv.get("ID") for fv in fvals]
        self.assertIn("10", fv_ids)
        self.assertIn("11", fv_ids)
        self.assertIn("12", fv_ids)
        self.assertEqual(len(fvals), 3)
        os.unlink(tgt3_path)

    def test_efx_fixture_remap(self):
        porter.clear()
        src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B, EFX_G))
        tgt_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2, ""))
        porter.load_source(src_path)
        porter.load_target(tgt_path)

        closure = porter.resolve_closure(["6"])
        plan = {
            "closure": closure,
            "fixture_mapping": {"0": ["10"], "1": ["11"]},
            "fanout_mode": "clone",
            "mirror_fixtures": [],
            "pan_channel_map": {},
        }
        _, xml_bytes = porter.execute(plan)
        root = qxw_io.strip_ns(ET.fromstring(xml_bytes))
        engine = root.find("Engine")
        efx = engine.findall("Function")[0]
        efx_fixtures = efx.findall("EFXFixture")
        efx_ids = [ef.findtext("ID", "").strip() for ef in efx_fixtures]
        self.assertIn("10", efx_ids)
        self.assertIn("11", efx_ids)
        self.assertEqual(len(efx_ids), 2)
        os.unlink(src_path)
        os.unlink(tgt_path)

    def test_script_func_remap(self):
        porter.clear()
        src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B,
            SCENE_A + SCENE_B + SCRIPT_F))
        tgt_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2, ""))
        porter.load_source(src_path)
        porter.load_target(tgt_path)

        closure = porter.resolve_closure(["5"])
        plan = {
            "closure": closure,
            "fixture_mapping": {"0": ["10"], "1": ["11"]},
            "fanout_mode": "clone",
            "mirror_fixtures": [],
            "pan_channel_map": {},
        }
        _, xml_bytes = porter.execute(plan)
        root = qxw_io.strip_ns(ET.fromstring(xml_bytes))
        engine = root.find("Engine")
        script_fn = [fn for fn in engine.findall("Function")
                     if fn.get("Type") == "Script"][0]
        commands = [cmd.text for cmd in script_fn.findall("Command")]
        # startfunction and stopfunction should reference new IDs (>11)
        for cmd in commands:
            if cmd and "function:" in cmd:
                m = porter._SCRIPT_FUNC_RE.search(cmd)
                if m:
                    self.assertGreater(int(m.group(1)), 11)
        os.unlink(src_path)
        os.unlink(tgt_path)

    def test_mirror_in_execute(self):
        """Test that mirror flag applies Pan inversion during execute."""
        porter.clear()
        src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B,
            SCENE_A))  # Scene A has FixtureVal "0,128,1,64"
        tgt_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2, ""))
        porter.load_source(src_path)
        porter.load_target(tgt_path)

        closure = porter.resolve_closure(["0"])
        plan = {
            "closure": closure,
            "fixture_mapping": {"0": ["10"], "1": ["11"]},
            "fanout_mode": "clone",
            "mirror_fixtures": ["11"],  # Mirror target 11
            "pan_channel_map": {"1": {"coarse": 0, "fine": 1}},
        }
        _, xml_bytes = porter.execute(plan)
        root = qxw_io.strip_ns(ET.fromstring(xml_bytes))
        engine = root.find("Engine")
        scene = engine.findall("Function")[0]

        # Find the FixtureVal for target 11 (mirrored)
        fv_11 = None
        for fv in scene.findall("FixtureVal"):
            if fv.get("ID") == "11":
                fv_11 = fv
                break
        self.assertIsNotNone(fv_11, "Should have FixtureVal for fixture 11")

        # Original was "0,200,1,100" (src fixture 1 mapped to tgt 11)
        # 16-bit: coarse=200, fine=100 → combined=51300
        # inverted = 65535-51300 = 14235
        # new_coarse = 14235>>8 = 55, new_fine = 14235&0xFF = 155 (actually 14235 = 55*256+155)
        val_text = (fv_11.text or "").strip()
        parts = val_text.split(",")
        pair_dict = {int(parts[i]): int(parts[i+1])
                     for i in range(0, len(parts), 2)}
        self.assertEqual(pair_dict[0], 55)
        self.assertEqual(pair_dict[1], 155)

        os.unlink(src_path)
        os.unlink(tgt_path)

    def test_does_not_mutate_target(self):
        """Execute should work on a deep copy — original target is untouched."""
        plan = self._make_plan()
        porter.execute(plan)

        # Original target should still have 0 functions
        engine = porter._engine(porter._tgt["root"])
        self.assertEqual(len(engine.findall("Function")), 0)


class TestSequenceBoundSceneRemap(unittest.TestCase):
    """Test that Sequence BoundScene attribute gets remapped."""

    def setUp(self):
        porter.clear()
        src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B,
            SCENE_A + SEQUENCE_S))
        tgt_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2, ""))
        porter.load_source(src_path)
        porter.load_target(tgt_path)
        self._paths = [src_path, tgt_path]

    def tearDown(self):
        porter.clear()
        for p in self._paths:
            if os.path.exists(p):
                os.unlink(p)

    def test_bound_scene_remapped(self):
        closure = porter.resolve_closure(["4"])
        plan = {
            "closure": closure,
            "fixture_mapping": {"0": ["10"], "1": ["11"]},
            "fanout_mode": "clone",
            "mirror_fixtures": [],
            "pan_channel_map": {},
        }
        _, xml_bytes = porter.execute(plan)
        root = qxw_io.strip_ns(ET.fromstring(xml_bytes))
        engine = root.find("Engine")
        seq = [fn for fn in engine.findall("Function")
               if fn.get("Type") == "Sequence"][0]
        bound_scene = seq.get("BoundScene", "")
        self.assertTrue(bound_scene.isdigit())
        self.assertGreater(int(bound_scene), 11,
                           "BoundScene should reference the new Scene ID")
        # The bound scene ID should match the new ID of the imported Scene A
        scene = [fn for fn in engine.findall("Function")
                 if fn.get("Type") == "Scene"][0]
        self.assertEqual(bound_scene, scene.get("ID"),
                         "BoundScene should point to the imported Scene")


class TestReport(unittest.TestCase):
    """Test generate_report."""

    def setUp(self):
        porter.clear()
        src_path = _write_qxw(_make_qxw(
            SRC_FIXTURE_A + SRC_FIXTURE_B,
            SCENE_A + SCENE_B + CHASER_AB))
        tgt_path = _write_qxw(_make_qxw(
            TGT_FIXTURE_1 + TGT_FIXTURE_2, ""))
        porter.load_source(src_path)
        porter.load_target(tgt_path)
        self._paths = [src_path, tgt_path]

    def tearDown(self):
        porter.clear()
        for p in self._paths:
            if os.path.exists(p):
                os.unlink(p)

    def test_report_contains_key_info(self):
        closure = porter.resolve_closure(["2"])
        plan = {
            "closure": closure,
            "fixture_mapping": {"0": ["10"], "1": ["11"]},
            "fanout_mode": "clone",
            "mirror_fixtures": [],
            "pan_channel_map": {},
        }
        validation = porter.validate(plan)
        report = porter.generate_report(plan, validation)
        self.assertIn("Function Porter", report)
        self.assertIn("Source:", report)
        self.assertIn("Target:", report)
        self.assertIn("clone", report)


if __name__ == "__main__":
    unittest.main()
