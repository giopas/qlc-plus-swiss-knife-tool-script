"""QLC+ 5.3 Show Wizard shows (3.1.0).

Two shows made with the Show Wizard of QLC+ 5.3.0 (``tests/corpus/Wizard530_*``,
scrubbed) and their fixture definitions (``tests/fixtures/wizard530``):

* small: 4 RGBW washes (back), 4 RGB bars (front), 2 gobo scanners (Singer),
  4 page-switch dimmers on a Loopback universe;
* video: 8 Sharpy (back), 8 Intimidator Spot 400 (front), 12 Generic RGB on
  the side columns, 6 GLP JDC1 strobes, 5 page-switch dimmers.

What Swiss Knife 3.0.3 got wrong on them, measured on 14 October 2026, is
pinned here: palette scenes read as empty, layer scenes flagged as LTP bleed,
the Porter and the Rig Reducer leaving broken references, page dimmers in
the paperwork.
"""

import copy
import os
import xml.etree.ElementTree as ET
from collections import Counter

import pytest

from core import compare, palettes, qxw_io, rig_reducer, wizard_repair
from core.doctor import check, load_qxf_defs
from core.doctor import fixes

HERE = os.path.dirname(os.path.abspath(__file__))
SMALL = os.path.join(HERE, "corpus", "Wizard530_small.qxw")
VIDEO = os.path.join(HERE, "corpus", "Wizard530_video.qxw")
DEFS = os.path.join(HERE, "fixtures", "wizard530")


@pytest.fixture(scope="module")
def defs():
    return load_qxf_defs([DEFS])


def _root(path):
    return qxw_io.load_qxw(path, strip_namespace=True).getroot()


def _codes(rep):
    return Counter(f.code for f in rep.findings)


def _fn(root, name):
    return next(f for f in root.find("Engine").findall("Function") if f.get("Name") == name)


# ── round trip ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [SMALL, VIDEO])
def test_round_trip_keeps_everything(path, tmp_path):
    a = _root(path)
    out = str(tmp_path / "rt.qxw")
    qxw_io.write_qxw(qxw_io.qualify_ns(copy.deepcopy(a)), out)
    b = _root(out)

    def sig(r):
        return sorted((e.tag, tuple(sorted(e.attrib.items())), (e.text or "").strip()) for e in r.iter())
    assert sig(a) == sig(b)


# ── palettes ─────────────────────────────────────────────────────────────────

def test_palettes_are_read():
    pals = palettes.read_palettes(_root(VIDEO))
    assert Counter(p.type for p in pals.values()) == {"Color": 11, "Position3D": 6, "Shutter": 4, "Dimmer": 3}
    red = next(p for p in pals.values() if p.name == "Red")
    assert red.colours() == ((255, 0, 0), (0, 0, 0))


def test_palette_scene_resolves_like_qlc(defs):
    root = _root(VIDEO)
    R = palettes.Resolver(root, defs)
    # Par Group – Red: Color palette on 12 Generic RGB (R, G, B, dimmer)
    vals = R.resolve(_fn(root, "Par Group – Red"))
    assert len(vals) == 12 and all(v == {0: 255, 1: 0, 2: 0} for v in vals.values())
    # Dimmer Full on the Sharpys: the dimmer channel (2) at 255
    vals = R.resolve(_fn(root, "Back group – Dimmer Full"))
    assert len(vals) == 8 and all(v == {2: 255} for v in vals.values())
    # Shutter Open on the Sharpy: the middle of the first ShutterOpen range (104-107)
    vals = R.resolve(_fn(root, "Back group – Shutter Open"))
    assert all(v == {1: 105} for v in vals.values())


def test_shutter_palette_with_another_preset_does_nothing(defs):
    """QLC+ matches the exact preset: a Sharpy strobe is StrobeFreqRange, so
    the wizard's Strobe Slow (StrobeSlowToFast) sets nothing on it."""
    root = _root(VIDEO)
    R = palettes.Resolver(root, defs)
    fn = _fn(root, "Back group – Strobe Slow")
    assert R.resolve(fn) == {}
    assert R.unresolved(fn) == [palettes.scene_palettes(fn)[0]]


def test_position3d_aims_the_heads(defs):
    root = _root(VIDEO)
    vals = palettes.Resolver(root, defs).resolve(_fn(root, "Back group – Position Centre"))
    assert len(vals) == 8
    # pan / tilt coarse and fine set on every Sharpy, all different from the centre
    assert all(set(v) == {9, 10, 11, 12} for v in vals.values())
    assert len({(v[9], v[11]) for v in vals.values()}) > 1


def test_layer_scenes(defs):
    root = _root(VIDEO)
    R = palettes.Resolver(root, defs)
    assert palettes.scene_layer(_fn(root, "Back group – Red"), R) == "colour"       # colour wheel only
    assert palettes.scene_layer(_fn(root, "Back group – Gobo 3"), R) == "gobo"
    assert palettes.scene_layer(_fn(root, "Par Group – Rainbow Red"), R) == "colour"  # dimmer at 0 adds nothing


def test_page_switch_fixtures():
    assert palettes.infrastructure_fixtures(_root(SMALL)) == ["10", "11", "12", "13"]
    assert palettes.infrastructure_fixtures(_root(VIDEO)) == ["34", "35", "36", "37", "38"]


# ── Doctor ───────────────────────────────────────────────────────────────────

def test_doctor_reads_the_wizard_show(defs):
    c = _codes(check(_root(VIDEO), defs))
    assert c["D004"] == 0               # 3.0.3: 65 palette scenes reported empty
    assert c["D005"] == 0               # 3.0.3: 764 (layer scenes)
    assert c["D016"] == 0               # 3.0.3: 87 (wizard building blocks)
    assert c["I003"] == 0               # built-in generic dimmers need no .qxf
    assert c["D020"] == 8               # Sharpy / JDC1 shutter palettes, white on colour wheels
    assert c["I004"] == c["I006"] == 1
    assert c["I007"] == 7               # chasers the wizard lost
    assert c["D007"] == 25              # true: gobo chasers share the gobo scenes
    assert not check(_root(VIDEO), defs).errors


def test_doctor_default_fixes_leave_layer_scenes_alone(defs):
    root = _root(VIDEO)
    res = fixes.fix(root, defs, codes=fixes.DEFAULT_CODES)
    white = _fn(res.root, "Back group – White")
    assert white.find("FixtureVal").text == "0,2"             # 3.0.3 filled all 16 channels


def test_doctor_d019_broken_palette_and_group(defs):
    root = _root(SMALL)
    fn = _fn(root, "RGB Front – Red")
    fn.find("Palette").set("ID", "999")
    fn.find("FixtureGroup").set("ID", "77")
    rep = check(root, defs)
    d019 = [f for f in rep.findings if f.code == "D019"]
    assert {f.message for f in d019} == {"uses missing palette 999", "uses missing fixture group 77"}
    res = fixes.fix(root, defs, codes={"D019"})
    assert not [f for f in res.after.findings if f.code == "D019"]
    assert _fn(res.root, "RGB Front – Red").find("Palette") is None


# ── Wizard Repair ────────────────────────────────────────────────────────────

def test_missing_chasers():
    names = [c["name"] for c in wizard_repair.missing_chasers(_root(VIDEO))]
    assert names == ["All Groups – Color Rainbow", "All Groups – Strobe Chase", "Back group – Strobe Chase",
                     "Front group – Strobe Chase", "Par Group – Color Rainbow",
                     "Strobe Group – Color Rainbow", "Strobe Group – Strobe Chase"]


def test_side_columns_become_rows():
    root = _root(VIDEO)
    by = {g["name"]: g for g in wizard_repair.grid_changes(root)}
    assert set(by) == {"Par Group", "All Groups"}
    assert by["Par Group"]["new"] == [6, 2]
    left, right = by["Par Group"]["rows"]
    assert left == ["26", "24", "22", "20", "18", "16"]       # left column, front to back
    assert right == ["27", "25", "23", "21", "19", "17"]
    assert by["All Groups"]["new"] == [8, 5]
    assert by["All Groups"]["rows"][0] == ["32", "28", "29", "30", "31", "33"]   # strobes, at the front
    assert wizard_repair.grid_changes(_root(SMALL)) == []          # straight trusses: the wizard got it


def test_repair_video_show(defs):
    root = _root(VIDEO)
    new, acts = wizard_repair.repair(root, defs)
    steps = Counter(a["step"] for a in acts)
    assert steps["chasers"] == 7 and steps["palettes"] == 11 and steps["grids"] == 2
    rep = check(new, defs)
    c = _codes(rep)
    assert not rep.errors
    assert c["I007"] == 0 and c["I005"] == 0
    assert c["D020"] == 1           # JDC1 has no closed shutter: true, nothing to give it
    # every page of the frame has a PANIC RESET button, next to Blackout
    fr = wizard_repair.wizard_frame(new)
    pid = next(f.get("ID") for f in new.find("Engine").findall("Function") if f.get("Name") == "PANIC RESET")
    pages = {wizard_repair._page_of(b) for b in fr.findall("Button") if b.find("Function").get("ID") == pid}
    assert pages == {0, 1, 2, 3, 4}
    # nothing overlaps on any page
    for p in range(5):
        rects = [wizard_repair._rect(w) for w in fr if w.find("WindowState") is not None
                 and wizard_repair._page_of(w) == p and w.tag != "Shortcut"]
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                assert not wizard_repair._overlap(a, b), (p, a, b)


def test_repair_is_deterministic_and_adds_only(defs):
    root = _root(SMALL)
    a, _ = wizard_repair.repair(root, defs, wizard_repair.STEPS)
    b, _ = wizard_repair.repair(root, defs, wizard_repair.STEPS)
    assert qxw_io.qxw_bytes(a) == qxw_io.qxw_bytes(b)
    before = {f.get("ID") for f in root.find("Engine").findall("Function")}
    after = {f.get("ID") for f in a.find("Engine").findall("Function")}
    assert before < after


def test_repair_on_a_plain_show_does_nothing(defs):
    root = _root(os.path.join(HERE, "corpus", "Pub_6fix.qxw"))
    a = wizard_repair.analyse(root, defs)
    assert not a["wizard"]
    _new, acts = wizard_repair.repair(root, defs)
    assert acts == []


# ── Rig Reducer, Porter, Compare, paperwork ─────────────────────────────────

def test_reducer_cleans_palette_scenes_pads_and_pages(defs):
    root = _root(VIDEO)
    res = rig_reducer.reduce(root, [str(i) for i in range(16, 34)])   # PARs and strobes
    new = res["root"]
    rep = check(new, defs)
    assert not rep.errors                       # 3.0.3: 31 dangling groups, 3 broken pads
    assert "34" in {f.findtext("ID") for f in new.find("Engine").findall("Fixture")}   # page dimmer kept
    fr = wizard_repair.wizard_frame(new)
    assert fr.find("Multipage").get("PagesNum") == "3"
    assert [s.get("Name") for s in fr.findall("Shortcut")] == ["All Groups", "Par Group", "Strobe Group"]
    assert not [b for b in fr.iter("Button") if b.get("Caption") in ("Back group", "Front group")]
    for pad in new.iter("XYPad"):
        assert pad.findall("Fixture") or pad.findall("Group")


def test_reducer_offers_no_page_dimmers():
    ids = {f["id"] for f in rig_reducer.fixtures(_root(SMALL))}
    assert not ids & {"10", "11", "12", "13"}


def test_porter_brings_palettes_and_maps_groups(defs):
    from core import porter
    porter.load_target(SMALL)
    porter.load_source(VIDEO)
    clos = porter.resolve_closure(["97"])                          # Par Group – Red
    assert clos["palette_ids"] == ["14"] and clos["group_ids"] == ["2"]
    assert set(clos["fixture_ids"]) == {str(i) for i in range(16, 28)}


def test_compare_reads_palette_scenes(defs):
    a = _root(VIDEO)
    b, _ = wizard_repair.repair(a, defs, ["palettes"])
    res = compare.report(compare.compare(a, b, defs))
    assert "Back group – Strobe Slow" in res               # values added for the Sharpys
    assert "Par Group – Red" not in res                     # the same look in both


def test_compare_leaves_page_dimmers_out():
    fx = compare._fixtures(_root(VIDEO))
    assert "34" not in fx and len(fx) == 34


# ── the app: Wizard Repair as a step of the show in progress ────────────────

def test_wizard_routes_apply_a_history_step(tmp_path, monkeypatch):
    import shutil

    import app
    # the definitions are found next to the workspace, as on a user's disk
    for f in os.listdir(DEFS):
        shutil.copy(os.path.join(DEFS, f), tmp_path / f)
    show = tmp_path / "Wizard530_video.qxw"
    shutil.copy(VIDEO, show)
    monkeypatch.setenv("QLCPLUS_FIXTURES", "")          # no installed library: only the folder
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(show)}).status_code == 200
    a = c.get("/api/wizard/analyse").get_json()
    assert a["wizard"] and {s["id"]: s["count"] for s in a["steps"]}["chasers"] == 7
    assert c.post("/api/wizard/repair", json={"steps": []}).status_code == 400
    r = c.post("/api/wizard/repair", json={"steps": ["chasers", "panic"]}).get_json()
    assert r["step"]["tool"] == "wizard" and r["step"]["tool_title"] == "Wizard Repair"
    again = c.get("/api/wizard/analyse").get_json()
    assert {s["id"]: s["count"] for s in again["steps"]}["chasers"] == 0
