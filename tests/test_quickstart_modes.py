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
    assert _scene_vals(funcs, "Reset: neutral state")[sh] == 4


def test_panic_reset_stops_everything_then_neutral():
    """HTP channels can't be pulled down by a scene, so PANIC RESET is a
    Script: stop every function, then start the neutral scene."""
    from urllib.parse import unquote
    d = _defn("SlimPAR")
    mode = next(iter(d["modes"]))
    _, funcs, frame = _gen(d, mode)
    script = [f for f in funcs if f.get("Name") == "PANIC RESET"]
    assert len(script) == 1 and script[0].get("Type") == "Script"
    cmds = [unquote(c.text) for c in script[0].findall(f"{NS}Command")]
    neutral = next(f for f in funcs if f.get("Name") == "Reset: neutral state")
    # QLC+ scripts stop what they started when they end, unless told not to
    assert cmds[0] == "stoponexit:false"
    others = {f.get("ID") for f in funcs} - {script[0].get("ID"), neutral.get("ID")}
    assert {c.split(":")[1] for c in cmds[1:-3]} == others
    assert all(c.startswith("stopfunction:") for c in cmds[1:-3])
    assert cmds[-3] == f"startfunction:{neutral.get('ID')}"
    # QLC+ 5.2.2 drops queued commands if the script ends at once
    assert cmds[-2] == "wait:100ms"
    # ... and stops itself, or QLC+ 5 keeps it (and its button) running
    assert cmds[-1] == f"stopfunction:{script[0].get('ID')}"
    fid = script[0].get("ID")
    assert any(b.find(f"{NS}Function") is not None
               and b.find(f"{NS}Function").get("ID") == fid
               for b in frame.iter(f"{NS}Button")), "PANIC RESET must be on a VC button"
    assert all(v == 0 for v in _scene_vals(funcs, "Reset: neutral state").values())


def test_dimmer_slider_starts_at_zero():
    """A Level slider at 255 on the dimmers would hold them at full (HTP).
    (A Submaster slider made QLC+ 5 drop every widget after it.)"""
    d = _defn("SlimPAR")
    _, _, frame = _gen(d, next(iter(d["modes"])))
    sliders = list(frame.iter(f"{NS}Slider"))
    assert all(s.find(f"{NS}SliderMode").text == "Level" for s in sliders)
    dim = next(s for s in sliders if s.get("Caption") == "DIMMER")
    assert dim.find(f"{NS}Level").get("Value") == "0"
    assert list(dim.iter(f"{NS}Channel"))


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
