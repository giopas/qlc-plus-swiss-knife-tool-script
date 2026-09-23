"""Quick Start on real fixtures: channel indices follow the selected mode and
unused channels get capability-aware neutral values (WORKPLAN Phase 1.1)."""
import os
import xml.etree.ElementTree as ET

import pytest

from core.qxf_parser import parse_qxf
from core.quick_start.channel_model import neutral_value, mode_channels
from core.quick_start.fixture_analyzer import RigCapabilityAnalysis
from core.quick_start.vc_generator import VCLayoutGenerator

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
NS = "{http://www.qlcplus.org/Workspace}"


def _defn(name):
    for f in os.listdir(FIX):
        if name in f and f.endswith(".qxf"):
            return parse_qxf(os.path.join(FIX, f))
    pytest.skip(f"{name} QXF not in tests/fixtures")


def _gen(defn, mode):
    key = f"{defn['manufacturer']}::{defn['model']}"
    rig = [{"key": key, "mode": mode, "ch_count": defn["modes"][mode],
            "name": "F", "universe": 0, "address": 0}]
    qxf = {key: defn}
    gen = VCLayoutGenerator(rig, qxf, RigCapabilityAnalysis(rig, qxf))
    funcs, frame, _ = gen.generate()
    return gen, funcs, frame


def _scene_vals(funcs, name):
    f = next(f for f in funcs if f.get("Name") == name)
    fv = f.find(f"{NS}FixtureVal")
    nums = [int(x) for x in fv.text.split(",")]
    return dict(zip(nums[0::2], nums[1::2]))


def test_spot110_6ch_uses_mode_order():
    d = _defn("Spot-110")
    names = mode_channels({"mode": "6 Channel"}, d)
    gen, funcs, _ = _gen(d, "6 Channel")
    dim = names.index(next(n for n in names if "Dimmer" in n))
    assert gen._dimmer_index(0) == dim
    vals = _scene_vals(funcs, "ALL ON")
    assert len(vals) == 6
    assert vals[dim] == 255
    # Pan/Tilt centred, not 0
    assert vals[names.index("Pan")] == 127
    assert vals[names.index("Tilt")] == 127


def test_spot375z_shutter_open_in_looks_closed_in_nothing():
    d = _defn("375Z")
    mode = next(iter(d["modes"]))
    names = mode_channels({"mode": mode}, d)
    sh = names.index("Shutter")
    _, funcs, _ = _gen(d, mode)
    assert _scene_vals(funcs, "ALL ON")[sh] == 4          # Open, not Closed (0)
    assert _scene_vals(funcs, "PANIC RESET")[sh] == 4


def test_panic_reset_scene_and_button():
    d = _defn("SlimPAR")
    mode = next(iter(d["modes"]))
    _, funcs, frame = _gen(d, mode)
    reset = [f for f in funcs if f.get("Name") == "PANIC RESET"]
    assert len(reset) == 1
    fid = reset[0].get("ID")
    buttons = [b for b in frame.iter(f"{NS}Button")
               if (b.find(f"{NS}Function") is not None
                   and b.find(f"{NS}Function").get("ID") == fid)]
    assert buttons, "PANIC RESET must be on a VC button"
    vals = _scene_vals(funcs, "PANIC RESET")
    assert all(v == 0 for v in vals.values())


@pytest.mark.parametrize("caps,expected", [
    ([{"min": 0, "max": 3, "label": "Closed", "preset": "ShutterClose"},
      {"min": 4, "max": 7, "label": "Open", "preset": "ShutterOpen"}], 4),
    ([{"min": 0, "max": 15, "label": "No function", "preset": None}], 0),
    ([{"min": 0, "max": 9, "label": "Blackout", "preset": None},
      {"min": 10, "max": 19, "label": "Open", "preset": None}], 10),
    ([{"min": 0, "max": 255, "label": "Intensity", "preset": None}], 0),
])
def test_neutral_value_rules(caps, expected):
    assert neutral_value("X", {"group": "Shutter", "capabilities": caps}) == expected


def test_pan_fine_is_zero():
    assert neutral_value("Pan fine", {"group": "Pan", "byte": 1}) == 0
    assert neutral_value("Pan", {"group": "Pan", "byte": 0}) == 127
