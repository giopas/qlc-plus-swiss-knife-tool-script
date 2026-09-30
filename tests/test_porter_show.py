"""The Function Porter on the show in progress, and the QXW Merger folded in
(WORKPLAN 2.6): port into the show (a step), copy fixtures and groups."""
import os
import shutil
import xml.etree.ElementTree as ET

import pytest

import app
from core import porter, qxw_io, show

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    for f in ("Festival_14fix.qxw", "Pub_6fix.qxw"):
        shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    porter.clear()
    client.tmp = tmp_path
    return client


def _ok(r):
    assert r.status_code < 300, r.get_data(as_text=True)[:400]
    return r


def _plan(n=3):
    fns = [f for f in porter.list_source_functions() if f["type"] == "Scene"][:n]
    cl = porter.resolve_closure([f["id"] for f in fns])
    return dict(closure=cl, fixture_mapping=porter.auto_map(cl["fixture_ids"], "fan_in"),
                fanout_mode="fan_in", drop_unmapped=True)


def test_port_into_the_show_equals_the_old_export(c):
    pub = str(c.tmp / "Pub_6fix.qxw")
    before = open(pub, "rb").read()
    _ok(c.post("/api/load", json={"path": pub}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    d = _ok(c.post("/api/porter/target/show", json={})).get_json()
    assert d["show"] and porter.get_state()["tgt_show"]
    plan = _plan()
    old = _ok(c.post("/api/porter/execute", json=plan)).data         # export a copy
    r = _ok(c.post("/api/porter/apply", json=plan)).get_json()
    assert r["step"]["tool"] == "porter" and "3 functions from Festival_14fix" in r["step"]["title"]
    assert c.get("/api/show/file").data == old
    assert open(pub, "rb").read() == before
    # the report of the step is the port report
    assert "Function Porter — Port Report" in c.get("/api/show/report").get_data(as_text=True)


def test_apply_rereads_the_show_first(c):
    """A change made in another tool after choosing the target is kept."""
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    _ok(c.post("/api/vc/op", json={"op": "new_page", "caption": "Made meanwhile"}))
    _ok(c.post("/api/porter/apply", json=_plan(2)))
    root = qxw_io.loads_qxw(c.get("/api/show/file").data)
    assert any((el.get("Caption") == "Made meanwhile") for el in root.iter())
    assert [s["tool"] for s in c.get("/api/show/history").get_json()["steps"]] == ["vceditor", "porter"]


def test_apply_needs_the_show_as_target(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    assert c.post("/api/porter/apply", json=_plan()).status_code == 400


def test_copy_fixtures_and_groups_merger_style(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    tgt_before = porter.list_target_fixtures()
    src = porter.list_source_fixtures()
    groups = c.get("/api/porter/source/groups").get_json()
    assert groups and groups[0]["fixtures"]
    g = groups[0]
    plan = {"copy_fixtures": g["fixtures"], "copy_groups": [g["id"]],
            "closure": {}, "fixture_mapping": {}}
    v = _ok(c.post("/api/porter/validate", json=plan)).get_json()
    assert v["ok"] and v["info"][0].startswith(f"Copied from the source: {len(g['fixtures'])} fixture(s), 1 group(s)")
    r = _ok(c.post("/api/porter/apply", json=plan)).get_json()
    assert f"{len(g['fixtures'])} fixtures" in r["step"]["title"] and "1 group" in r["step"]["title"]
    root = qxw_io.strip_ns(qxw_io.loads_qxw(c.get("/api/show/file").data))
    eng = root.find("Engine")
    fx = eng.findall("Fixture")
    assert len(fx) == len(tgt_before) + len(g["fixtures"])
    new_ids = {f.findtext("ID") for f in fx} - {t["id"] for t in tgt_before}
    # no channel of a copied fixture overlaps another fixture
    spans = sorted((f.findtext("Universe"), int(f.findtext("Address")),
                    int(f.findtext("Address")) + int(f.findtext("Channels"))) for f in fx)
    for a, b in zip(spans, spans[1:]):
        assert a[0] != b[0] or a[2] <= b[1], (a, b)
    new_group = eng.findall("FixtureGroup")[-1]
    assert {h.get("Fixture") for h in new_group.findall("Head")} <= new_ids
    rep = c.get("/api/show/report").get_data(as_text=True)
    assert "COPIED FROM THE SOURCE" in rep and "→" in rep
    assert r["show"]["doctor"]["error"] == 0


def test_copy_fixtures_then_port_functions_onto_them(c):
    """Bring a fixture type the target doesn't have, with the looks that use it."""
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    plan = _plan(2)
    plan["copy_fixtures"] = plan["closure"]["fixture_ids"]
    plan["drop_unmapped"] = False
    _ok(c.post("/api/porter/apply", json=plan))
    root = qxw_io.strip_ns(qxw_io.loads_qxw(c.get("/api/show/file").data))
    eng = root.find("Engine")
    fixtures = eng.findall("Fixture")
    assert len(fixtures) == 6 + len(plan["copy_fixtures"])
    copied = {f.findtext("ID") for f in fixtures[6:]}
    ported = [f for f in eng.findall("Function") if f.get("Type") == "Scene"][-2:]
    used = {v.get("ID") for f in ported for v in f.findall("FixtureVal")}
    assert used and used <= copied            # the looks play on the copied fixtures


def test_copied_fixtures_keep_their_place_on_the_stage(c):
    """giopas's test (30 Sep): the copies had no 3D position, QLC+ stacked
    them top-left.  Now they get the source position, scaled to the stage."""
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    src = porter.source_root()
    before_ids = {f["id"] for f in porter.list_target_fixtures()}
    sgrid = src.find("Engine/Monitor/Grid")
    g = c.get("/api/porter/source/groups").get_json()[0]
    plan = {"copy_fixtures": g["fixtures"], "copy_groups": [g["id"]], "closure": {}, "fixture_mapping": {}}
    prev = c.get("/api/porter/stage/target?copy_fixtures=" + ",".join(g["fixtures"])).get_json()
    assert len(prev["copied"]) == len(g["fixtures"])
    _ok(c.post("/api/porter/apply", json=plan))
    root = qxw_io.strip_ns(qxw_io.loads_qxw(c.get("/api/show/file").data))
    tgrid = root.find("Engine/Monitor/Grid")
    items = {i.get("ID"): i for i in root.find("Engine/Monitor").findall("FxItem")}
    sitems = {i.get("ID"): i for i in src.find("Engine/Monitor").findall("FxItem")}
    new_ids = sorted(set(items) - before_ids, key=int)
    assert len(new_ids) == len(g["fixtures"])
    kx = float(tgrid.get("Width")) / float(sgrid.get("Width"))
    for sid, nid in zip(g["fixtures"], new_ids):
        assert abs(float(items[nid].get("XPos")) - float(sitems[sid].get("XPos")) * kx) < 1
    assert "3D positions:" in c.get("/api/show/report").get_data(as_text=True)
    # copying the same fixtures again is flagged
    _ok(c.post("/api/porter/target/show", json={}))
    v = _ok(c.post("/api/porter/validate", json=plan)).get_json()
    assert any("copied before" in w for w in v["warnings"])


def test_copies_are_pinned_whatever_the_fan_out(c):
    """giopas's test (30 Sep): with 'pattern repeat' the copied Ceiling
    fixtures' looks were tiled onto other targets (the drums…).  Copies are
    now always 1:1; the other sources share out the other targets."""
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    before = {f["id"] for f in porter.list_target_fixtures()}
    g = next(x for x in c.get("/api/porter/source/groups").get_json() if x["name"] == "Ceiling")
    fns = [f for f in porter.list_source_functions() if f["type"] == "Scene"]
    fn = next(f for f in fns if set(g["fixtures"]) & set(
        porter.resolve_closure([f["id"]])["fixture_ids"]))
    cl = porter.resolve_closure([fn["id"]])
    cand = _ok(c.post("/api/porter/fixture-candidates", json={
        "fixture_ids": cl["fixture_ids"], "copy_fixtures": g["fixtures"]})).get_json()
    assert set(cand["copied"]) == set(g["fixtures"])
    m = _ok(c.post("/api/porter/auto-map", json={"fixture_ids": cl["fixture_ids"], "strategy": "all",
                                                 "copy_fixtures": g["fixtures"]})).get_json()
    assert all(m[s] == [cand["copied"][s]] for s in g["fixtures"] if s in m)
    plan = dict(closure=cl, fixture_mapping={s: sorted(before) for s in cl["fixture_ids"]},
                fanout_mode="pattern_repeat", drop_unmapped=True, copy_fixtures=g["fixtures"])
    _ok(c.post("/api/porter/apply", json=plan))
    root = qxw_io.strip_ns(qxw_io.loads_qxw(c.get("/api/show/file").data))
    new_fn = root.find("Engine").findall("Function")[-1]
    lit = {v.get("ID") for v in new_fn.findall("FixtureVal")}
    src_ceiling = {s for s in cl["fixture_ids"] if s in g["fixtures"]}
    assert {cand["copied"][s] for s in src_ceiling} <= lit        # the copies play
    if set(cl["fixture_ids"]) <= set(g["fixtures"]):
        assert not (lit & before)                                   # nothing tiled onto the rig


def test_copies_preview_is_thread_safe(c):
    """Step 3 fires the candidates and the preview plan at once; the target
    must never be left with the copies in it, nor copy them twice."""
    import threading
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    n0 = len(porter.list_target_fixtures())
    g = c.get("/api/porter/source/groups").get_json()[0]
    q = "?copy_fixtures=" + ",".join(g["fixtures"])
    errors = []

    def hit():
        cl = app.create_app().test_client()
        for _ in range(10):
            d = cl.get("/api/porter/stage/target" + q).get_json()
            if len(d["copied"]) != len(g["fixtures"]):
                errors.append(d["copied"])
    ts = [threading.Thread(target=hit) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and len(porter.list_target_fixtures()) == n0
