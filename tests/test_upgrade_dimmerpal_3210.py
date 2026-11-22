"""3.21.0 Upgrade to QLC+ 5.3, step *dimmerpal*: looks whose lit lights share
one dimmer level take it from a Dimmer palette, only where the look plays
exactly the same; and the tools that read looks keep working on the result
(Doctor D005, Brightness, Function Porter)."""
import collections
import copy
import os
import shutil
import xml.etree.ElementTree as ET  # nosec B405

import pytest

import app
from core import palettes as P
from core import porter, qxw_io
from core import upgrade53 as U
from core.doctor import check, load_qxf_defs

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
DEFS = load_qxf_defs([CORPUS])


def _root(name):
    return qxw_io.strip_ns(qxw_io.load_qxw(os.path.join(CORPUS, name + ".qxw")).getroot())


def _step(a):
    return next(s for s in a["steps"] if s["id"] == "dimmerpal")


def _scenes(root):
    return {f.get("ID"): f for f in root.find("Engine").findall("Function") if f.get("Type") == "Scene"}


def _lit(d):
    return {k: {c: v for c, v in vals.items() if v} for k, vals in d.items()}


def test_never_ticked_by_default_and_53_only():
    a = U.analyse(_root("Festival_14fix"), DEFS)
    assert "dimmerpal" not in a["defaults"]
    st = _step(a)
    assert st["only53"] and st["count"] == 23
    assert st["items"][0] == "Dimmer Full: 16 look(s)"
    assert any(i.startswith("Stay as they are: 112 look(s)") for i in st["items"])
    assert st["note"] == "23 of 139 looks can take their dimmer from a palette; the other 116 stay as they are."
    assert "dimmerpal" not in U.upgrade(_root("Festival_14fix"), DEFS, target="5.2.2",
                                        steps=["dimmerpal"])[1].__repr__()


@pytest.mark.parametrize("show", ["Festival_14fix", "Pub_6fix", "FloorShow_8fix"])
def test_every_look_plays_the_same(show):
    root = _root(show)
    new, acts = U.upgrade(root, DEFS, steps=["dimmerpal"])
    r0, r1 = P.Resolver(root, DEFS), P.Resolver(new, DEFS)
    old = _scenes(root)
    moved = 0
    for sid, fn in _scenes(new).items():
        if P.scene_palettes(fn) and not P.scene_palettes(old[sid]):
            moved += 1
        assert _lit(r1.resolve(fn)) == _lit(r0.resolve(old[sid])), fn.get("Name")
    assert moved == _step(U.analyse(root, DEFS))["count"] > 0
    assert acts and all(a["step"] == "dimmerpal" for a in acts)


def test_palettes_are_reused_or_named_by_level():
    new, _ = U.upgrade(_root("Festival_14fix"), DEFS, steps=["dimmerpal"])
    dims = {p.get("Name"): p.get("Value") for p in new.find("Engine").findall("Palette") if p.get("Type") == "Dimmer"}
    assert dims == {"Dimmer Full": "255", "Dimmer 90%": "230"}
    # run it again: nothing left to move, no new palette
    again, acts = U.upgrade(new, DEFS, steps=["dimmerpal"])
    assert len([p for p in again.find("Engine").findall("Palette")]) == len(new.find("Engine").findall("Palette"))
    assert not acts


def test_doctor_counts_do_not_change():
    root = _root("FloorShow_8fix")
    new, _ = U.upgrade(root, DEFS, steps=["dimmerpal"])
    before = collections.Counter(f.code for f in check(root, DEFS).findings)
    after = collections.Counter(f.code for f in check(new, DEFS).findings)
    assert before == after


def test_a_moved_look_keeps_its_dark_lights_dark():
    root = _root("FloorShow_8fix")
    new, _ = U.upgrade(root, DEFS, steps=["dimmerpal"])
    r1 = P.Resolver(new, DEFS)
    for fn in _scenes(new).values():
        if not P.scene_palettes(fn):
            continue
        for v in fn.findall("FixtureVal"):
            f = v.get("ID")
            nums = (v.text or "").split(",")
            if "0" in nums[0::2]:                         # the dimmer is still declared: it is 0
                assert r1.resolve(fn)[f].get(0) == 0


@pytest.fixture
def migrated(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    new, _ = U.upgrade(_root("FloorShow_8fix"), DEFS, steps=["dimmerpal"])
    path = tmp_path / "Floor_migrated.qxw"
    path.write_bytes(qxw_io.qxw_bytes(new))
    return path


def test_brightness_sees_and_scales_the_moved_looks(migrated):
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(migrated)}).status_code < 300
    fx = [f["id"] for f in c.get("/api/brightness/fixtures").get_json() if f.get("dimmer_offset") is not None]
    pl = c.post("/api/brightness/preview", json={"scales": {f: 0.5 for f in fx}}).get_json()["palette_looks"]
    assert pl["scenes"] > 50
    after = {b["id"]: (b["peak"], b["scene_count"]) for b in c.get("/api/brightness/baseline").get_json()}
    c2 = app.create_app().test_client()
    shutil.copy(os.path.join(CORPUS, "FloorShow_8fix.qxw"), migrated.parent / "Floor.qxw")
    c2.post("/api/load", json={"path": str(migrated.parent / "Floor.qxw")})
    before = {b["id"]: (b["peak"], b["scene_count"]) for b in c2.get("/api/brightness/baseline").get_json()}
    assert after == before                               # the moved looks still count, once each
    c.post("/api/load", json={"path": str(migrated)})
    r = c.post("/api/brightness/apply", json={"scales": {f: 0.5 for f in fx}, "scale_palettes": True})
    vals = {p.get("Name"): p.get("Value") for p in qxw_io.strip_ns(qxw_io.loads_qxw(r.data)).iter("Palette")
            if p.get("Type") == "Dimmer"}
    assert vals["Dimmer Full"] == "128"


def test_porter_writes_the_palette_into_a_ported_look(migrated):
    porter.load_source(str(migrated))
    porter.load_target(os.path.join(CORPUS, "FloorShow_8fix.qxw"))
    src = qxw_io.strip_ns(qxw_io.load_qxw(str(migrated)).getroot())
    moved = next(f for f in _scenes(src).values() if P.scene_palettes(f))
    fn = copy.deepcopy(moved)
    assert porter._inline_palettes(fn, src, DEFS, {})
    assert not fn.findall("Palette")
    r = P.Resolver(src, DEFS)
    assert _lit(r.resolve(fn)) == _lit(r.resolve(moved))


def test_port_from_a_migrated_show_keeps_the_looks(migrated):
    porter.load_source(str(migrated))
    porter.load_target(os.path.join(CORPUS, "FloorShow_8fix.qxw"))
    src = porter.source_root()
    moved = [f.get("ID") for f in src.find("Engine").findall("Function")
             if f.get("Type") == "Scene" and f.findall("Palette")][:8]
    assert moved
    cl = porter.resolve_closure(moved)
    plan = dict(closure=cl, fixture_mapping=porter.auto_map(cl["fixture_ids"], "same_id"),
                fanout_mode="manual", drop_unmapped=True, qxf_paths=[CORPUS], vc=dict(enabled=False))
    res = porter.port(plan)
    assert res["doctor"]["errors"] == []
    assert set(res["inlined"]) == set(moved)
    out = qxw_io.strip_ns(ET.fromstring(res["bytes"]))
    rs, ro = P.Resolver(qxw_io.strip_ns(src), DEFS), P.Resolver(out, DEFS)
    fns = {f.get("ID"): f for f in out.find("Engine").findall("Function")}
    srcf = {f.get("ID"): f for f in qxw_io.strip_ns(src).find("Engine").findall("Function")}
    for s in moved:
        n = fns[res["func_id_map"][s]]
        assert not n.findall("Palette")
        assert _lit(ro.resolve(n)) == _lit(rs.resolve(srcf[s]))
