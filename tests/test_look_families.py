"""Look & Chaser Builder 3.3.0: the QLC+ 5.3 wizard's families.

What a group can do, roles, places on the stage, the new looks (levels,
strobe, gobo × colour, blinder), movement effects (EFX), matrices on a group
with a grid, and buttons on a page per group.  Measured on the concert show
made with the QLC+ 5.3.0 Show Wizard (Sharpys, spots, side PARs, JDC1s) and
on the Quick Start club show (two moving heads in a mixed group).
"""

import copy
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter

import pytest

from core import look_builder as LB
from core import look_families as LF
from core import qxw_io, wizard_repair as W
from core.doctor import check, load_qxf_defs

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
VIDEO = os.path.join(CORPUS, "Wizard530_video.qxw")
CLUB = os.path.join(CORPUS, "QuickStart_club.qxw")


@pytest.fixture(scope="module")
def defs():
    return load_qxf_defs([CORPUS, os.path.join(HERE, "fixtures"), os.path.join(HERE, "fixtures", "wizard530")])


def _root(p):
    return qxw_io.load_qxw(p, strip_namespace=True).getroot()


def _gid(root, defs, name):
    return next(g["id"] for g in LB.groups(root, defs) if g["name"] == name)


def _fn(root, fid):
    return next(f for f in root.find("Engine").findall("Function") if f.get("ID") == str(fid))


def _new(before, after):
    b = Counter((f.code, f.severity) for f in before.findings)
    a = Counter((f.code, f.severity) for f in after.findings)
    return {k: v - b.get(k, 0) for k, v in a.items() if v > b.get(k, 0) and k[1] != "info"}


# ── what a group can do, roles ──────────────────────────────────────────────

def test_group_caps_and_roles(defs):
    gs = {g["name"]: g for g in LB.groups(_root(VIDEO), defs, caps=True)}
    back, par, strobe = gs["Back group"], gs["Par Group"], gs["Strobe Group"]
    assert {"wheel", "gobo", "strobe", "moves"} <= set(back["caps"]) and "mix" not in back["caps"]
    assert back["role"] == "Back" and back["gobos"] == 17           # the Sharpy's static gobos, no shakes
    assert set(par["caps"]) == {"mix", "dimmer", "grid"} and par["role"] == "Side"
    assert strobe["role"] == "Blinder" and "strobe" in strobe["caps"]
    assert gs["Front group"]["role"] == "Key"
    assert gs["All fixtures"]["grid"] == [0, 0] and "grid" not in gs["All fixtures"]["caps"]


@pytest.mark.parametrize("name,caps,role", [
    ("Back truss", ["mix"], "Back"), ("Floor_Singer", ["mix"], "Floor"), ("Blinders", ["dimmer"], "Blinder"),
    ("Group 7", ["moves", "wheel"], "Effect"), ("Group 8", ["mix", "grid"], "Strip"), ("Group 9", ["mix"], "Fill"),
])
def test_suggest_role(name, caps, role):
    assert LF.suggest_role(name, caps) == role


def test_places_from_the_stage():
    ps = {p["name"]: p for p in LF.places(_root(os.path.join(CORPUS, "Pub_6fix.qxw")))}
    assert list(ps)[:2] == ["Centre", "Audience"]
    assert {"Drummer", "Bassist", "Guitarist"} <= set(ps)                # the musician models placed on the stage
    assert ps["Centre"]["x"] == 3.0 and ps["Audience"]["z"] == pytest.approx(4.8)
    assert [p["name"] for p in LF.places(_root(CLUB))] == ["Centre", "Audience"]     # no models there


# ── the new looks ────────────────────────────────────────────────────────────

def test_old_plans_build_as_before(defs):
    """A 3.2.0 plan has none of the new keys: the output keeps its form (looks under
    <folder>/Looks, one VC page with solo frames)."""
    root = _root(os.path.join(CORPUS, "Pub_6fix.qxw"))
    res = LB.build(root, defs, {"looks": [{"group": "1", "colours": ["Red", "Blue"]}],
                                "chasers": [{"group": "all", "pattern": "chase", "colours": ["Red"], "bpm": 120}],
                                "vc_page": "Looks"})
    paths = {f.get("Path") for f in res["root"].find("Engine").findall("Function")
             if (f.get("Path") or "").startswith("Look Builder")}
    assert "Look Builder/Looks" in paths and "Look Builder/Chasers/Chase Red" in paths
    assert not any("Effects" in p for p in paths)
    page = next(p for p in res["root"].find("VirtualConsole") if p.get("Caption") == "Looks")
    assert page.findall("SoloFrame") and not page.findall("Frame")


def test_levels_strobe_gobo_blinder_every_channel(defs):
    root = _root(VIDEO)
    B, P_, S = (_gid(root, defs, n) for n in ("Back group", "Par Group", "Strobe Group"))
    plan = {"levels": [{"group": P_}], "strobes": [{"group": B}, {"group": P_}],
            "gobos": [{"group": B, "colours": ["Red", "Blue"], "gobos": [1, 2]}],
            "blinder": {"groups": [S, P_]}, "folders": "group", "vc": "pages"}
    res = LB.build(root, defs, plan)
    new = res["root"]
    info = LB._fixture_info(new, defs)
    fns = [f for f in new.find("Engine").findall("Function") if (f.get("Path") or "").startswith("Look Builder/")]
    names = [f.get("Name") for f in fns]
    assert names[:3] == ["Par Group · Full", "Par Group · Half", "Par Group · Off"]
    assert "Back group · Strobe slow" in names and "Back group · Strobe fast" in names
    assert not any("Par Group · Strobe" in n for n in names)          # the PARs have no strobe
    assert "Generic RGB" in " ".join(res["notes"]) or any("no fixture with a strobe" in n for n in res["notes"])
    assert [n for n in names if "Gobo" in n] == ["Back group · Gobo 1 · Red", "Back group · Gobo 2 · Red",
                                                  "Back group · Gobo 1 · Blue", "Back group · Gobo 2 · Blue"]
    # every look declares every channel of each of its fixtures
    for f in fns:
        for v in f.findall("FixtureVal"):
            fx = info[v.get("ID")]
            chans = [int(x) for x in v.text.split(",")[0::2]]
            assert chans == list(range(fx["channels"])), (f.get("Name"), fx["name"])
    # the gobo slot is the static gobo, not a shake
    g2 = next(f for f in fns if f.get("Name") == "Back group · Gobo 2 · Red")
    ch, val = LF.gobo_value(info["0"], 2)
    assert f"{ch},{val}" in g2.find("FixtureVal").text
    # the strobe sits inside the Sharpy's own strobe range
    fast = next(f for f in fns if f.get("Name") == "Back group · Strobe fast")
    slow = next(f for f in fns if f.get("Name") == "Back group · Strobe slow")
    assert fast.find("FixtureVal").text != slow.find("FixtureVal").text
    bl = next(f for f in fns if f.get("Name").endswith("Blinder hit"))
    assert len(bl.findall("FixtureVal")) == 18                        # 6 JDC1 + 12 PARs
    assert not _new(check(root, defs), check(new, defs))


def test_looks_aim_the_moving_heads_at_a_place(defs):
    root = _root(CLUB)
    res = LB.build(root, defs, {"looks": [{"group": "all", "colours": ["Blue"], "place": "Audience"},
                                          {"group": "all", "colours": ["Blue"]}]})
    new = res["root"]
    a, b = [f for f in new.find("Engine").findall("Function")][-2:]
    assert a.get("Name").endswith("Blue @ Audience")
    va = {v.get("ID"): v.text for v in a.findall("FixtureVal")}
    vb = {v.get("ID"): v.text for v in b.findall("FixtureVal")}
    movers = {f.findtext("ID") for f in new.find("Engine").findall("Fixture") if "Intimidator" in f.findtext("Model")}
    assert all(va[m] != vb[m] for m in movers)                         # the heads aim elsewhere
    assert all(va[f] == vb[f] for f in va if f not in movers)          # the PARs are the same
    aims = LF.place_values(new, defs, sorted(movers), next(p for p in LF.places(new) if p["name"] == "Audience"))
    for m in movers:
        for ch, val in aims[m].items():
            assert f"{ch},{val}" in va[m]
    with pytest.raises(ValueError):
        LB.build(root, defs, {"looks": [{"group": "all", "colours": ["Blue"], "place": "Nowhere"}]})


# ── movement effects ─────────────────────────────────────────────────────────

def test_efx_like_the_wizard(defs):
    root = _root(VIDEO)
    B, F = _gid(root, defs, "Back group"), _gid(root, defs, "Front group")
    res = LB.build(root, defs, {"efx": [{"group": B, "kind": k} for k in ("circle", "eight", "sweep", "fly_out", "fly_in")]
                                       + [{"group": F, "kind": "fly_out"}], "vc": "pages"})
    efx = [f for f in res["root"].find("Engine").findall("Function") if f.get("Type") == "EFX"
           and f.get("Path", "").startswith("Look Builder")]
    by = {f.get("Name"): f for f in efx}
    c = by["Back group · Circle"]
    # the wizard's circle on the Sharpy (QLC+ 5.3.0 video show): width 12, height 26, relative, serial
    assert (c.findtext("Algorithm"), c.findtext("Width"), c.findtext("Height"), c.findtext("IsRelative"),
            c.findtext("PropagationMode")) == ("Circle", "12", "26", "1", "Serial")
    assert c.find("DimmerControl") is None                            # QLC+ 5.2.2 has no dimmer control
    assert by["Back group · Figure eight"].findtext("Algorithm") == "Eight"
    sw = by["Back group · Audience sweep"]
    assert (sw.findtext("Algorithm"), sw.findtext("PropagationMode")) == ("Line", "Parallel")
    # fly out: absolute, the wizard's offsets, mirrored for the upstage Sharpys
    fo_back, fo_front = by["Back group · Fly out"], by["Front group · Fly out"]
    xb = fo_back.find("Axis[@Name='X']").findtext("Offset")
    xf = fo_front.find("Axis[@Name='X']").findtext("Offset")
    assert {xb, xf} == {"83", "172"} and fo_back.findtext("IsRelative") == "0"
    offs = [int(f.findtext("StartOffset")) for f in fo_back.findall("Fixture")]
    assert offs == [k * 45 for k in range(8)]
    assert by["Back group · Fly in"].findtext("Direction") == "Backward"
    # the same shape as the wizard's own EFX in that show
    wiz = next(f for f in res["root"].find("Engine").findall("Function") if f.get("Name") == "Back group – Circle Chase (motion)")
    assert [e.tag for e in c] == [e.tag for e in wiz if e.tag != "DimmerControl"]
    assert not _new(check(root, defs), check(res["root"], defs))


def test_efx_needs_a_moving_head(defs):
    root = _root(VIDEO)
    res = LB.build(root, defs, {"efx": [{"group": _gid(root, defs, "Par Group"), "kind": "circle"}]})
    assert res["created"].get("efx", 0) == 0 and any("no moving head" in n for n in res["notes"])
    with pytest.raises(ValueError):
        LB.build(root, defs, {"efx": [{"group": "all", "kind": "spin"}]})


# ── matrices on a group with a grid ──────────────────────────────────────────

def test_matrix_on_a_group(defs):
    root = _root(VIDEO)
    P_ = _gid(root, defs, "Par Group")
    res = LB.build(root, defs, {"matrices": [{"group": P_, "pattern": "Waves"}]})
    m = next(f for f in res["root"].find("Engine").findall("Function") if f.get("Type") == "RGBMatrix"
             and f.get("Path", "").startswith("Look Builder"))
    assert m.findtext("FixtureGroup") == P_ and m.findtext("ControlMode") == "RGB"
    with pytest.raises(ValueError):
        LB.build(root, defs, {"matrices": [{"group": "all", "pattern": "Waves"}]})


# ── a page per group ─────────────────────────────────────────────────────────

def _page_rects(frame):
    kids = [w for w in frame if w.find("WindowState") is not None]
    for pg in sorted({W._page_of(w) for w in kids}):
        yield pg, [(w, W._rect(w)) for w in kids if W._page_of(w) == pg]


def test_a_page_per_group(defs):
    root = _root(VIDEO)
    B, F, P_, S = (_gid(root, defs, n) for n in ("Back group", "Front group", "Par Group", "Strobe Group"))
    plan = {"looks": [{"group": g, "colours": ["Red", "Blue", "Amber"]} for g in (B, F, P_)],
            "gobos": [{"group": B, "colours": ["Red", "Blue", "Amber"], "gobos": list(range(1, 8))}],
            "strobes": [{"group": S}], "blinder": {"groups": [S]},
            "chasers": [{"group": P_, "pattern": "chase", "colours": ["Red", "Blue"], "bpm": 120}],
            "efx": [{"group": B, "kind": "circle"}], "vc": "pages", "vc_page": "Looks", "folders": "group"}
    res = LB.build(root, defs, plan)
    new = res["root"]
    page = next(p for p in new.find("VirtualConsole") if p.get("Caption") == "Looks")
    fr = page.find("Frame")
    assert fr.find("Multipage").get("PagesNum") == "4"
    assert [s.get("Name") for s in fr.findall("Shortcut")] == ["Back group", "Front group", "Par Group", "Strobe Group"]
    for pg, rects in _page_rects(fr):
        rr = [r for _w, r in rects if r]
        assert not any(W._overlap(a, b) for i, a in enumerate(rr) for b in rr[i + 1:]), pg
        tags = Counter(w.tag for w, _ in rects)
        assert tags["Slider"] == 1
    # Back: 3 colour + 21 gobo looks in one solo frame (one at a time), the circle, an XY pad
    back = [w for w in fr if W._page_of(w) == 0]
    solo = next(w for w in back if w.tag == "SoloFrame")
    assert len(solo.findall("Button")) == 24
    assert any(w.tag == "XYPad" for w in back)
    # the blinder flashes, effects toggle
    acts = {b.get("Caption"): b.findtext("Action") for b in fr.iter("Button")}
    assert acts["Blinder hit"] == "Flash" and acts["Circle"] == "Toggle"
    assert all(b.findtext("Action") == "Toggle" for b in solo.findall("Button"))
    # buttons wear the look's colour
    red = next(b for b in solo.findall("Button") if b.get("Caption") == "Red")
    assert red.find("Appearance/BackgroundColor").text == str(0xFFFF0000)
    assert not any("no room" in x for x in res["log"])
    assert not _new(check(root, defs), check(new, defs))


def test_deterministic_and_the_api(defs, tmp_path, monkeypatch):
    root = _root(VIDEO)
    plan = {"looks": [{"group": "2", "colours": ["Red"]}], "efx": [{"group": "2", "kind": "circle"}],
            "vc": "pages", "folders": "group"}
    a, b = LB.build(root, defs, plan), LB.build(root, defs, plan)
    assert ET.tostring(a["root"]) == ET.tostring(b["root"])


def test_options_route_keeps_the_show_namespace(tmp_path):
    """The options read a copy: the show in progress keeps its namespace (the VC
    editor finds its pages after the Look Builder opened)."""
    import shutil
    import app
    shutil.copy(VIDEO, tmp_path / "v.qxw")
    for q in os.listdir(os.path.join(HERE, "fixtures", "wizard530")):
        shutil.copy(os.path.join(HERE, "fixtures", "wizard530", q), tmp_path / q)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(tmp_path / "v.qxw")}).status_code == 200
    d = c.get("/api/looks/options").get_json()
    g = {x["name"]: x for x in d["groups"]}
    assert g["Back group"]["role"] == "Back" and len(g["Back group"]["gobo_names"]) == 17
    assert [p["name"] for p in d["places"]][:2] == ["Centre", "Audience"]
    assert {k["id"] for k in d["efx_kinds"]} == set(LF.EFX_KINDS)
    assert c.get("/api/vc/tree").status_code == 200
    r = c.post("/api/looks/check", json={"strobes": [{"group": g["Back group"]["id"]}], "vc": "pages"}).get_json()
    assert r["created"]["looks"] == 2 and not r["blocked"]
    assert c.get("/api/vc/tree").status_code == 200
