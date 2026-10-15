"""Upgrade to QLC+ 5.3 (3.2.0).

Older shows from the test data (QLC+ 5.2.2, and Quick Start output) get what
QLC+ 5.3 offers, step by step, without anything being removed or rewritten
unless a step says so.  The moving-head steps run on the 5.3 wizard show with
its folders and wizard frame taken out, so it reads as an older show, and a
singer model placed on the stage.
"""

import copy
import os
import xml.etree.ElementTree as ET
from collections import Counter

import pytest

from core import qxw_io, upgrade53 as U, wizard_repair as W
from core.doctor import check, load_qxf_defs

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
FESTIVAL = os.path.join(CORPUS, "Festival_14fix.qxw")
PUB = os.path.join(CORPUS, "Pub_6fix.qxw")
QUICK = os.path.join(CORPUS, "QuickStart_6fix.qxw")
VIDEO = os.path.join(CORPUS, "Wizard530_video.qxw")


@pytest.fixture(scope="module")
def defs():
    return load_qxf_defs([CORPUS, os.path.join(HERE, "fixtures", "wizard530")])


def _root(path):
    return qxw_io.load_qxw(path, strip_namespace=True).getroot()


def _counts(a):
    return {s["id"]: s["count"] for s in a["steps"]}


def _mover_show():
    """The wizard video show as an older show: no folders, no wizard frame,
    a singer model and a cube on the stage."""
    r = _root(VIDEO)
    fr = W.wizard_frame(r)
    for p in r.find("VirtualConsole"):
        if fr in list(p):
            p.remove(fr)
    for f in r.find("Engine").findall("Function"):
        f.attrib.pop("Path", None)
    mon = r.find("Engine/Monitor")
    ET.SubElement(mon, "MeshItem", {"ID": "0", "XPos": "5000", "YPos": "-900", "ZPos": "6000",
                                    "Res": "generic/Meshy_AI_Bandana_Drummer.obj"})
    ET.SubElement(mon, "MeshItem", {"ID": "1", "XPos": "2000", "YPos": "0", "ZPos": "3000",
                                    "Res": "generic/cube.obj"})
    return r


# ── analyse ──────────────────────────────────────────────────────────────────

def test_analyse_an_older_show(defs):
    a = U.analyse(_root(FESTIVAL), defs)
    assert a["version"] == "5.2.2" and not a["wizard"]
    c = _counts(a)
    assert c["folders"] == 286                       # no function had a folder
    assert c["palettes"] == 21 and c["grids"] == 6 and c["lock"] == 14
    assert c["allgroup"] == 0                        # All_Fixtures_Master holds the rig
    assert c["positions"] == 0 and "moving heads" in next(s for s in a["steps"] if s["id"] == "positions")["note"]
    assert c["frame"] == 12                          # 13 groups, two hold the same fixtures
    assert a["defaults"] == ["folders", "palettes", "allgroup", "positions", "hide"]


def test_target_522_leaves_out_the_53_steps(defs):
    root = _root(QUICK)
    a = U.analyse(root, defs, "5.2.2")
    assert "positions" not in a["defaults"]
    assert {s["id"] for s in a["steps"] if s["only53"]} == {"positions", "lock"}
    _new, acts = U.upgrade(root, defs, U.STEPS, "5.2.2")
    assert not [x for x in acts if x["step"] in ("positions", "lock")]


# ── upgrade: deterministic, additive, a second run finds nothing ────────────

@pytest.mark.parametrize("path", [FESTIVAL, PUB, QUICK])
def test_upgrade_is_deterministic_and_idempotent(path, defs):
    root = _root(path)
    a, acts = U.upgrade(root, defs, U.STEPS)
    b, _ = U.upgrade(root, defs, U.STEPS)
    assert acts and qxw_io.qxw_bytes(a) == qxw_io.qxw_bytes(b)
    _c, again = U.upgrade(a, defs, U.STEPS)
    assert again == []
    assert not [s for s in U.analyse(a, defs)["steps"] if s["count"]]


@pytest.mark.parametrize("path", [FESTIVAL, PUB, QUICK])
def test_upgrade_removes_nothing_and_adds_no_doctor_findings(path, defs):
    root = _root(path)
    new, _ = U.upgrade(root, defs, U.STEPS)
    ids = lambda r, tag: {e.get("ID") for e in r.find("Engine").findall(tag)}      # noqa: E731
    for tag in ("Function", "FixtureGroup", "Fixture", "Palette"):
        assert ids(root, tag) <= ids(new, tag)
    before = Counter(f.code for f in check(root, defs).findings)
    after = Counter(f.code for f in check(new, defs).findings)
    for code, n in after.items():
        if code == "I008":                           # what QLC+ 5.2.2 ignores: the point of it
            continue
        assert n <= before.get(code, 0), code       # D016 goes down: functions got buttons


def test_upgrade_round_trips(defs, tmp_path):
    new, _ = U.upgrade(_root(FESTIVAL), defs, U.STEPS)
    out = str(tmp_path / "up.qxw")
    qxw_io.write_qxw(qxw_io.qualify_ns(copy.deepcopy(new)), out)
    back = _root(out)
    assert qxw_io.qxw_bytes(back) == qxw_io.qxw_bytes(new)


# ── the steps ────────────────────────────────────────────────────────────────

def test_folders(defs):
    new, _ = U.upgrade(_root(QUICK), defs, ["folders"])
    fns = {f.get("ID"): f for f in new.find("Engine").findall("Function")}
    assert all(f.get("Path") for f in fns.values())
    assert fns["89"].get("Path") == fns["90"].get("Path") == "Safety"           # PANIC RESET and its scene
    paths = Counter(f.get("Path") for f in fns.values())
    assert paths["Chasers/Color Fade"] == 6                                      # a chaser's own steps
    assert any(p.startswith("Looks/") for p in paths)
    fest, _ = U.upgrade(_root(FESTIVAL), defs, ["folders"])
    cl = {f.get("ID"): f.get("Path") for f in fest.find("Engine").findall("Function")}
    assert cl["1756"] == cl["1782"] == cl["1803"] == "Setlist"                  # the CueList chasers
    assert any(p.startswith("Setlist/") for p in cl.values())                   # the songs, under them


def test_folders_keep_an_existing_path(defs):
    root = _root(QUICK)
    root.find("Engine").find("Function").set("Path", "Mine/Here")
    new, _ = U.upgrade(root, defs, ["folders"])
    assert new.find("Engine").find("Function").get("Path") == "Mine/Here"


def test_palettes_are_the_wizards_and_only_those_that_work(defs):
    new, _ = U.upgrade(_root(QUICK), defs, ["palettes"])
    pals = {p.get("Name"): (p.get("Type"), p.get("Value")) for p in new.find("Engine").findall("Palette")}
    assert pals["Dimmer Half"] == ("Dimmer", "128")
    assert pals["Strobe Fast"] == ("Shutter", "9,85")
    assert pals["Red"] == ("Color", "#ff0000000000")
    assert "Shutter Closed" not in pals             # no fixture has a "shutter closed" preset
    assert "Amber" not in pals                      # no look uses amber
    eng = [c.tag for c in new.find("Engine")]
    assert eng.index("Palette") > max(i for i, t in enumerate(eng) if t == "FixtureGroup")
    assert eng.index("Palette") < eng.index("Function")


def test_all_fixtures_group_when_none_holds_the_rig(defs):
    root = _root(FESTIVAL)
    eng = root.find("Engine")
    for g in eng.findall("FixtureGroup"):
        if g.findtext("Name") == "All_Fixtures_Master":
            eng.remove(g)
    assert _counts(U.analyse(root, defs))["allgroup"] == 1
    new, acts = U.upgrade(root, defs, ["allgroup"])
    g = next(g for g in new.find("Engine").findall("FixtureGroup") if g.findtext("Name") == U.ALL_GROUP)
    assert len(g.findall("Head")) == 14
    cells = {(h.get("X"), h.get("Y")) for h in g.findall("Head")}
    assert len(cells) == 14                         # no two heads in one cell
    sz = g.find("Size")
    assert all(int(h.get("X")) < int(sz.get("X")) and int(h.get("Y")) < int(sz.get("Y")) for h in g.findall("Head"))


def test_grids_are_not_ticked_by_default(defs):
    root = _root(FESTIVAL)
    new, _ = U.upgrade(root, defs)
    sizes = lambda r: {g.get("ID"): (g.find("Size").get("X"), g.find("Size").get("Y"))  # noqa: E731
                       for g in r.find("Engine").findall("FixtureGroup")}
    assert sizes(new) == sizes(root)
    new, acts = U.upgrade(root, defs, ["grids"])
    assert len(acts) == 6 and sizes(new) != sizes(root)


def test_frame_page_per_group(defs):
    new, acts = U.upgrade(_root(QUICK), defs, ["frame"])
    fr = U.groups_frame(new)
    assert fr is not None and fr.find("Multipage").get("PagesNum") == "3"
    assert [s.get("Name") for s in fr.findall("Shortcut")] == ["All Fixtures", "QS · Ceiling", "QS · Floor"]
    page = next(p for p in new.find("VirtualConsole") if p.get("Caption") == U.FRAME_CAPTION)
    assert fr in list(page)
    # PANIC RESET on every page, a solo frame of looks, effects as toggles
    pid = W._panic_script(new)
    assert {W._page_of(b) for b in fr.findall("Button") if b.find("Function").get("ID") == pid} == {0, 1, 2}
    assert len(fr.findall("SoloFrame")) == 3
    # a button and a chaser step never share a scene (principle 5, D007)
    before = Counter(f.code for f in check(_root(QUICK), defs).findings)
    after = Counter(f.code for f in check(new, defs).findings)
    assert after["D007"] == before["D007"] == 0
    _assert_layout(fr)


def _assert_layout(fr):
    fw = W._rect(fr)
    for pg in range(int(fr.find("Multipage").get("PagesNum"))):
        rs = [W._rect(w) for w in fr if w.find("WindowState") is not None and W._page_of(w) == pg]
        rs = [r for r in rs if r]
        for i, a in enumerate(rs):
            assert a[0] + a[2] <= fw[2] and a[1] + a[3] <= fw[3], (pg, a)
            for b in rs[i + 1:]:
                assert not W._overlap(a, b), (pg, a, b)


# ── moving heads ─────────────────────────────────────────────────────────────

def test_positions_and_xy_pads_for_moving_heads(defs):
    root = _mover_show()
    a = U.analyse(root, defs)
    assert not a["wizard"]
    pos = next(s for s in a["steps"] if s["id"] == "positions")
    assert pos["items"] == ["Centre (5.5,0,4.5 m)", "Audience (5.5,0,10.8 m)", "Drummer (5.25,0,6.25 m)"]
    new, acts = U.upgrade(root, defs, U.STEPS)
    p3 = {p.get("Name"): p.get("Value") for p in new.find("Engine").findall("Palette")
          if p.get("Type") == "Position3D" and "–" not in (p.get("Name") or "")}
    assert p3 == {"Centre": "5.5,0,4.5", "Audience": "5.5,0,10.8", "Drummer": "5.25,0,6.25"}
    fr = U.groups_frame(new)
    pads = fr.findall("XYPad")
    # Back (8 Sharpy), Front (8 Intimidator) and the mixed All Groups page (its 16 movers)
    assert sorted(len(p.findall("Fixture")) for p in pads) == [8, 8, 16]
    for pad in pads:
        assert pad.get("FloorControl") == "1"
        assert not pad.findall("Group")                   # fixtures one by one: works in 5.2.2 too
        assert pad.find("FloorPosition").attrib == {"X": "5.5", "Y": "0", "Z": "4.5"}
    _assert_layout(fr)
    assert not check(new, defs).errors
    i008 = [f for f in check(new, defs).findings if f.code == "I008"]
    assert len(i008) == 1 and "XY pad(s) in floor mode" in i008[0].message


def test_mesh_names():
    assert U._mesh_name({"res": "generic/Meshy_AI_Midnight_Bassist.obj"}) == "Bassist"
    assert U._mesh_name({"res": "generic/Meshy_AI_Singer_Guitarist_Char.obj"}) == "Singer Guitarist"
    assert U._mesh_name({"res": "generic/cube.obj"}) is None
    assert U._mesh_name({"res": "generic/riser.obj"}) is None
    assert U._mesh_name({"name": "Anna", "res": "generic/cube.obj"}) is None    # a cube is a set piece…
    assert U._mesh_name({"name": "Singer", "res": "generic/cube.obj"}) == "Singer"   # …unless named as a person
    assert U._mesh_name({"res": "generic/Meshy_AI_Bandana_Drummer.obj"}) == "Drummer"
    assert U._mesh_name({"name": "Lead vocal", "res": "x.obj"}) == "Lead vocal"


# ── a Show Wizard show goes to Wizard Repair ─────────────────────────────────

def test_wizard_show_points_to_wizard_repair(defs):
    root = _root(VIDEO)
    a = U.analyse(root, defs)
    assert a["wizard"]
    assert all(s["count"] == 0 and s["note"] for s in a["steps"] if s["id"] in U.WIZARD_OWN)
    new, acts = U.upgrade(root, defs, U.STEPS)
    assert {x["step"] for x in acts} <= {"hide", "lock"}


# ── Doctor I008 ──────────────────────────────────────────────────────────────

def test_i008_lists_what_522_ignores(defs):
    assert not [f for f in check(_root(FESTIVAL), defs).findings if f.code == "I008"]
    msg = next(f for f in check(_root(VIDEO), defs).findings if f.code == "I008").message
    assert "6 Position3D palette(s)" in msg and "10 scene(s) aiming with a Position3D palette" in msg
    new, _ = U.upgrade(_root(QUICK), defs, ["lock"])
    msg = next(f for f in check(new, defs).findings if f.code == "I008").message
    assert "6 fixture(s) locked in 2D/3D" in msg


# ── the app ──────────────────────────────────────────────────────────────────

def test_upgrade_routes_apply_a_history_step(tmp_path, monkeypatch):
    import shutil

    import app
    for f in ("Eurolite-LED-4C-12-Silent-Slim-Spot.qxf", "Generic-7Ch-RGB-PAR.qxf"):
        shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    show = tmp_path / "QuickStart_6fix.qxw"
    shutil.copy(QUICK, show)
    monkeypatch.setenv("QLCPLUS_FIXTURES", "")
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(show)}).status_code == 200
    a = c.get("/api/upgrade/analyse?target=5.3").get_json()
    assert _counts(a)["palettes"] == 15 and a["target"] == "5.3"
    assert c.post("/api/upgrade/apply", json={"steps": []}).status_code == 400
    r = c.post("/api/upgrade/apply", json={"steps": ["folders", "palettes"], "target": "5.3"}).get_json()
    assert r["step"]["tool"] == "upgrade" and r["step"]["tool_title"] == "Upgrade to QLC+ 5.3"
    again = c.get("/api/upgrade/analyse").get_json()
    assert _counts(again)["palettes"] == 0 and _counts(again)["folders"] == 0


def test_xy_pad_on_a_mixed_group():
    """Quick Start club: the two moving heads share *All Fixtures* with the PARs.
    The page still gets a pad, for the moving heads only."""
    d = load_qxf_defs([os.path.join(HERE, "corpus"), os.path.join(HERE, "fixtures")])
    root = qxw_io.load_qxw(os.path.join(HERE, "corpus", "QuickStart_club.qxw"), strip_namespace=True).getroot()
    new, _ = U.upgrade(root, d, U.STEPS)
    fr = U.groups_frame(new)
    pads = fr.findall("XYPad")
    assert len(pads) == 1
    movers = {f.findtext("ID") for f in new.find("Engine").findall("Fixture")
              if "Intimidator" in (f.findtext("Model") or "")}
    assert {f.get("ID") for f in pads[0].findall("Fixture")} == movers and len(movers) == 2
    _assert_layout(fr)
