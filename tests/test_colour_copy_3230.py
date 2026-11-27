"""3.23.0 Copy Colours: one fixture takes another's colours in every look
(core.colour_copy), its route and Claude's tool."""
import copy
import os
import xml.etree.ElementTree as ET

import pytest

from core import capability_map as cm
from core import colour_copy as cc
from core import qxw_io
from core.doctor import load_qxf_defs

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
FIXT = os.path.join(HERE, "fixtures")


@pytest.fixture(scope="module")
def defs():
    return load_qxf_defs([CORPUS, FIXT])


def _root(name):
    return qxw_io.strip_ns(ET.parse(os.path.join(CORPUS, name)).getroot())


def _vals(fn, fid):
    fv = next((f for f in fn.findall("FixtureVal") if f.get("ID") == fid), None)
    return None if fv is None else cm._pairs(fv.text or "")


def _scenes(root):
    return [f for f in root.find("Engine").findall("Function") if f.get("Type") == "Scene"]


def _hue(v, r=1, g=2, b=3):
    rgb = (v.get(r, 0), v.get(g, 0), v.get(b, 0))
    m = max(rgb)
    return None if not m else tuple(round(x / m, 2) for x in rgb)


# Pub_6fix: six generic 7-ch PARs (0 dimmer, 1 R, 2 G, 3 B …); ids 6 and 7
SRC, TGT = "6", "7"


def test_keep_takes_the_hue_and_keeps_the_dimmer(defs):
    root = _root("Pub_6fix.qxw")
    before = {f.get("ID"): (_vals(f, SRC), _vals(f, TGT)) for f in _scenes(root)}
    rep = cc.copy_colours(root, {TGT: SRC}, defs)
    assert not rep["problems"] and rep["pairs"][TGT]["scenes"] > 0
    checked = 0
    for fn in _scenes(root):
        s, t0 = before[fn.get("ID")]
        t = _vals(fn, TGT)
        if not s or not t0:
            continue
        if s.get(0, 0) and _hue(s) and t0.get(0, 0) and max(t0.get(c, 0) for c in (1, 2, 3)):
            assert t[0] == t0[0], fn.get("Name")               # own dimmer kept
            # the source's hue, to one DMX step of rounding on a dimmer peak
            assert all(abs(a - b) <= 0.02 for a, b in zip(_hue(t), _hue(s))), fn.get("Name")
            assert max(t[c] for c in (1, 2, 3)) == max(t0[c] for c in (1, 2, 3))  # own peak
            checked += 1
    assert checked > 10


def test_source_brightness_makes_the_target_look_like_the_source(defs):
    root = _root("Pub_6fix.qxw")
    cc.copy_colours(root, {TGT: SRC}, defs, brightness="source")
    for fn in _scenes(root):
        s, t = _vals(fn, SRC), _vals(fn, TGT)
        if s and t and "PANIC" not in (fn.get("Name") or "").upper():
            for c in (0, 1, 2, 3):
                assert t.get(c, 0) == s.get(c, 0), fn.get("Name")


def test_other_channels_untouched_and_every_channel_declared(defs):
    root = _root("Pub_6fix.qxw")
    strobe0 = {f.get("ID"): (_vals(f, TGT) or {}).get(4) for f in _scenes(root)}
    cc.copy_colours(root, {TGT: SRC}, defs)
    for fn in _scenes(root):
        t = _vals(fn, TGT)
        if t is not None and t:
            assert sorted(t) == list(range(7))
            if strobe0[fn.get("ID")] is not None:
                assert t[4] == strobe0[fn.get("ID")]


def test_panic_reset_is_left_alone(defs):
    root = _root("Pub_6fix.qxw")
    panic = {f.get("ID"): ET.tostring(f) for f in _scenes(root) if "PANIC" in (f.get("Name") or "").upper()}
    assert panic
    cc.copy_colours(root, {TGT: SRC}, defs, brightness="source", add=True)
    for f in _scenes(root):
        if f.get("ID") in panic:
            assert ET.tostring(f) == panic[f.get("ID")]


def test_add_puts_the_target_where_only_the_source_plays(defs):
    root = _root("Festival_14fix.qxw")       # 0 = Ceiling 1 (RGBW spot), 13 = Front Fill (PAR)
    only_src = [f.get("ID") for f in _scenes(root) if _vals(f, "0") is not None and _vals(f, "13") is None]
    assert only_src
    plain = cc.copy_colours(copy.deepcopy(root), {"13": "0"}, defs)
    assert plain["pairs"]["13"]["absent"] >= 1 and plain["pairs"]["13"]["added"] == 0
    rep = cc.copy_colours(root, {"13": "0"}, defs, add=True)
    assert rep["pairs"]["13"]["added"] >= 1
    got = [i for i in only_src if _vals(next(f for f in _scenes(root) if f.get("ID") == i), "13")]
    assert got


def test_rgbw_to_rgb_translates_the_colour(defs):
    root = _root("Festival_14fix.qxw")
    cc.copy_colours(root, {"13": "0"}, defs, brightness="source")
    n = 0
    for fn in _scenes(root):
        s, t = _vals(fn, "0"), _vals(fn, "13")
        if s and t and "PANIC" not in (fn.get("Name") or "").upper():
            want = cm._pairs(cm.translate_text(defs[("eurolite", "led 4c-12 silent slim spot")], "9 Channel",
                                               defs[("generic", "7-ch rgb led par")], "7 Channel",
                                               ",".join(f"{c},{v}" for c, v in s.items()))[0])
            assert [t[c] for c in (0, 1, 2, 3)] == [want[c] for c in (0, 1, 2, 3)]
            n += 1
    assert n


WHEEL_SHOW = """<?xml version="1.0" encoding="UTF-8"?>
<Workspace><Engine>
 <Fixture><Manufacturer>Generic</Manufacturer><Model>7-Ch RGB LED PAR</Model><Mode>7 Channel</Mode>
  <ID>0</ID><Name>PAR</Name><Universe>0</Universe><Address>0</Address><Channels>7</Channels></Fixture>
 <Fixture><Manufacturer>Chauvet</Manufacturer><Model>Intimidator Spot 110</Model><Mode>6 Channel</Mode>
  <ID>1</ID><Name>Spot</Name><Universe>0</Universe><Address>10</Address><Channels>6</Channels></Fixture>
 <Function ID="0" Type="Scene" Name="Blue"><Speed FadeIn="0" FadeOut="0" Duration="0"/>
  <FixtureVal ID="0">0,255,1,0,2,0,3,255,4,0,5,0,6,0</FixtureVal>
  <FixtureVal ID="1">0,40,1,200,2,0,3,0,4,180,5,0</FixtureVal></Function>
 <Function ID="1" Type="Scene" Name="PAR dark"><Speed FadeIn="0" FadeOut="0" Duration="0"/>
  <FixtureVal ID="0">0,0,1,0,2,0,3,0,4,0,5,0,6,0</FixtureVal>
  <FixtureVal ID="1">0,40,1,200,2,32,3,0,4,180,5,0</FixtureVal></Function>
 <Function ID="2" Type="Sequence" Name="Seq" BoundScene="0"><Speed FadeIn="0" FadeOut="0" Duration="0"/>
  <Step Number="0" FadeIn="0" Hold="0" FadeOut="0" Values="13">0:0,255,1,255,2,0,3,0,4,0,5,0,6,0:1:0,40,1,200,2,0,3,0,4,90,5,0</Step></Function>
</Engine></Workspace>"""


def test_rgb_to_colour_wheel_keeps_position_and_dimmer(defs):
    root = ET.fromstring(WHEEL_SHOW)
    rep = cc.copy_colours(root, {"1": "0"}, defs)
    assert not rep["problems"], rep["problems"]
    fns = root.find("Engine").findall("Function")
    v = _vals(fns[0], "1")
    assert (v[0], v[1], v[4]) == (40, 200, 180)       # pan, tilt, dimmer kept
    assert v[2] == 96                                 # wheel: Color 3 (blue)
    assert _vals(fns[1], "1")[2] == 32                # PAR dark: the spot stays as it was
    assert rep["pairs"]["1"]["dark"] == 1
    step = cm._pairs(fns[2].find("Step").text.split(":")[3])
    assert step[4] == 90 and step[2] == cm.nearest_wheel_value(
        next(cd for _i, _n, cd in cm._layout(defs[("chauvet", "intimidator spot 110")], "6 Channel")
             if cm._is_wheel(cd)), (1, 0, 0))
    assert rep["pairs"]["1"]["steps"] == 1


def test_problems_are_said_not_guessed(defs):
    root = ET.fromstring(WHEEL_SHOW)
    rep = cc.copy_colours(root, {"1": "1", "9": "0"}, {})
    assert "own colours" in rep["problems"]["1"]
    assert "not in the show" in rep["problems"]["9"]
    rep = cc.copy_colours(ET.fromstring(WHEEL_SHOW), {"1": "0"}, {})
    assert ".qxf" in rep["problems"]["1"]
    with pytest.raises(ValueError):
        cc.copy_colours(ET.fromstring(WHEEL_SHOW), {"1": "0"}, defs, brightness="loud")


def test_run_is_deterministic_and_passes_the_doctor(defs):
    root = _root("Festival_14fix.qxw")
    a = cc.run(root, {"13": "0", "12": "1"}, defs, add=True)
    b = cc.run(root, {"13": "0", "12": "1"}, defs, add=True)
    assert ET.tostring(a["root"]) == ET.tostring(b["root"])
    assert not a["blocked"] and not a["doctor"]["new_warnings"]
    assert ET.tostring(root) == ET.tostring(_root("Festival_14fix.qxw"))   # the original untouched
    assert any("takes the colours of" in ln for ln in a["lines"])


def test_twice_changes_nothing_more(defs):
    root = _root("Pub_6fix.qxw")
    cc.copy_colours(root, {TGT: SRC}, defs)
    rep = cc.copy_colours(root, {TGT: SRC}, defs)
    assert rep["total"] == 0


def test_palette_looks_are_reported(defs):
    root = _root("Wizard530_small.qxw")
    ids = [f["id"] for f in cc.fixtures(root, defs)]
    lines = cc.not_changed(root, {ids[0]: ids[1]})
    assert any("palette look" in ln for ln in lines)


# ── the route: preview changes nothing, apply is one History step ───────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    import shutil
    import app
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    p = tmp_path / "Fest.qxw"
    shutil.copy(os.path.join(CORPUS, "Festival_14fix.qxw"), p)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    return c


def test_route_preview_then_apply_then_undo(client):
    c = client
    fx = c.get("/api/colours/fixtures").get_json()["fixtures"]
    assert len(fx) == 14 and all(f["colour"] for f in fx)
    body = {"pairs": [{"target": "13", "source": "0"}], "brightness": "keep", "add": False}
    before = c.get("/api/show/status").get_json()
    pv = c.post("/api/colours/preview", json=body).get_json()
    assert pv["total"] > 0 and not pv["blocked"]
    assert c.get("/api/show/status").get_json().get("version") == before.get("version")
    r = c.post("/api/colours/apply", json=body)
    assert r.status_code == 200, r.get_json()
    r = r.get_json()
    assert r["step"]["title"] == "'Front Fill (Center)' takes the colours of 'Ceiling 1'"
    assert r["total"] == pv["total"]
    again = c.post("/api/colours/apply", json=body)
    assert again.status_code == 400 and "Nothing to change" in again.get_json()["error"]
    assert c.post("/api/show/undo", json={}).status_code == 200
    assert c.post("/api/colours/preview", json=body).get_json()["total"] == pv["total"]


def test_route_says_what_is_missing(client):
    c = client
    assert c.post("/api/colours/preview", json={"pairs": []}).status_code == 400
    r = c.post("/api/colours/preview", json={"pairs": [{"target": "1", "source": "0"}],
                                             "brightness": "loud"})
    assert r.status_code == 400


def test_recipe_replays_the_copy_by_meaning():
    from core import retarget
    assert retarget.known("POST", "/api/colours/apply")


# ── Claude's tool ───────────────────────────────────────────────────────────

def test_claude_tool_preview_then_apply(tmp_path, monkeypatch):
    import shutil
    from tests.test_mcp import Client
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    monkeypatch.delenv("QSK_MCP_FOLDERS", raising=False)
    folder = tmp_path / "shows"
    folder.mkdir()
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf") or f == "Pub_6fix.qxw":
            shutil.copy(os.path.join(CORPUS, f), folder)
    c = Client([str(folder)])
    c.ok("open_show", path=str(folder / "Pub_6fix.qxw"))
    pre = c.ok("copy_colours", pairs={TGT: SRC}, preview=True)
    assert pre["total"] > 0 and pre["lines"]
    assert c.ok("show_history")["steps"] == [] or len(c.ok("show_history")["steps"]) == 0
    r = c.ok("copy_colours", pairs={TGT: SRC})
    assert r["step"]["tool"] == "colours" and r["lines"]
    err, msg = c.tool("copy_colours", pairs={})
    assert err and "rig_fixtures" in str(msg)
    g = c.ok("guide", topic="copy_colours")
    assert "brightness" in json.dumps(g)


import json  # noqa: E402
