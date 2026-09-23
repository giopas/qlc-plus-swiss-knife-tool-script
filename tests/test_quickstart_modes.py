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


def test_master_and_group_sliders_are_submasters():
    """Submasters scale the looks; they never hold a channel up.  (They are
    safe in QLC+ 5.2.2 only because the file is indented — see qxw_builder.)"""
    d = _defn("SlimPAR")
    _, _, frame = _gen(d, next(iter(d["modes"])))
    sliders = list(frame.iter(f"{NS}Slider"))
    assert [s.get("Caption") for s in sliders] == ["MASTER", "F"]
    assert all(s.find(f"{NS}SliderMode").text == "Submaster" for s in sliders)
    assert not any(list(s.iter(f"{NS}Channel")) for s in sliders)


def test_every_function_button_is_inside_the_show_soloframe():
    """One button at a time: looks, effects and group buttons all live in
    the SHOW SoloFrame; only the PANIC buttons are outside."""
    d = _defn("SlimPAR")
    _, _, page = _gen(d, next(iter(d["modes"])))
    show = page.find(f"{NS}SoloFrame")
    inside = {b.get("ID") for b in show.iter(f"{NS}Button")}
    outside = [b.get("Caption") for b in page.iter(f"{NS}Button") if b.get("ID") not in inside]
    assert sorted(outside) == ["PANIC\nBLACKOUT", "PANIC\nRESET"]


def test_matrix_effects_open_the_dimmers():
    """RGB-mode matrices don't drive the master dimmer in QLC+, so each
    matrix button runs a Collection: dimmer scene + RGBMatrix."""
    d = _defn("SlimPAR")
    key = f"{d['manufacturer']}::{d['model']}"
    mode = next(iter(d["modes"]))
    rig = [{"key": key, "mode": mode, "ch_count": d["modes"][mode], "name": f"Par {i}",
            "universe": 0, "address": i * 7} for i in range(3)]
    qxf = {key: d}
    gen = VCLayoutGenerator(rig, qxf, RigCapabilityAnalysis(rig, qxf))
    funcs, page, groups = gen.generate()
    by_id = {f.get("ID"): f for f in funcs}
    colls = [f for f in funcs if f.get("Type") == "Collection"]
    assert colls, "matrix effects expected with 3 RGB fixtures"
    for c in colls:
        kinds = sorted(by_id[s.text].get("Type") for s in c.findall(f"{NS}Step"))
        assert kinds == ["RGBMatrix", "Scene"]
    algos = {f.find(f"{NS}Algorithm").text for f in funcs if f.get("Type") == "RGBMatrix"}
    assert algos <= {"One By One", "Even/Odd", "Gradient", "Plasma", "Waves", "Stripes"}
    assert "Full Row" not in algos


def test_custom_groups_scope_their_scenes():
    d = _defn("SlimPAR")
    key = f"{d['manufacturer']}::{d['model']}"
    mode = next(iter(d["modes"]))
    rig = [{"key": key, "mode": mode, "ch_count": d["modes"][mode], "name": f"Par {i}",
            "universe": 0, "address": i * 7} for i in range(4)]
    qxf = {key: d}
    gen = VCLayoutGenerator(rig, qxf, RigCapabilityAnalysis(rig, qxf),
                            groups=[{"name": "Front", "fixtures": [0, 1]},
                                    {"name": "Back", "fixtures": [2, 3]}])
    funcs, page, _ = gen.generate()
    caps = [f.get("Caption") for f in page.iter(f"{NS}Frame")]
    assert "GROUP · Front" in caps and "GROUP · Back" in caps
    front_red = next(f for f in funcs if f.get("Name") == "Front Red")
    assert sorted(v.get("ID") for v in front_red.findall(f"{NS}FixtureVal")) == ["0", "1"]


def test_output_is_indented_like_qlcplus():
    """QLC+ 5.2.2 drops VC widgets after an empty <Level/> with no
    whitespace behind it — the builder must indent."""
    from core.quick_start.qxw_builder import build_qxw
    d = _defn("SlimPAR")
    gen, funcs, frame = _gen(d, next(iter(d["modes"])))
    key = f"{d['manufacturer']}::{d['model']}"
    rig = [{"key": key, "mode": next(iter(d["modes"])), "ch_count": 7, "name": "F",
            "universe": 0, "address": 0, "manufacturer": d["manufacturer"], "model": d["model"]}]
    data = build_qxw(rig, funcs, frame, gen.fixture_groups).decode()
    import re
    assert re.search(r"<Level [^>]*/>\s*\n\s*</Slider>", data)


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
