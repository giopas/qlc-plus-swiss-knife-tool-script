"""Cabling 3.11.0: cable marks (buy, borrowed, venue), the preferred plan,
the meshes hidden on the plot, the terminator inside the last fixture, and
wiring from a description (Claude's cabling action=wire)."""

import os
import shutil

import pytest

import app
from core import qxw_io
from core.cabling import outputs, plan, rig
from core.doctor import load_qxf_defs
from tests.test_cabling import CORPUS, FESTIVAL, festival_plan


@pytest.fixture(scope="module")
def festival():
    root = qxw_io.load_qxw(FESTIVAL, strip_namespace=True).getroot()
    return rig.read_rig(root, load_qxf_defs([CORPUS]), FESTIVAL)


def _link_to(ev, key):
    return next(l for w in ev["chains"] for l in w["links"] if l.get("dest") == key)


def test_marks_are_kept_and_cleaned():
    p = festival_plan()
    p["cable_marks"] = {"f:7": "venue", "f:8": "buy", "f:9": "stolen", "bad key": "buy", "i:splitter1": "borrowed"}
    c = plan.clean_plan(p)
    assert c["cable_marks"] == {"f:7": "venue", "f:8": "buy", "i:splitter1": "borrowed"}
    assert "cable_marks" not in plan.clean_plan(festival_plan())


def test_venue_and_borrowed_cables_are_not_from_the_kit(festival):
    base = plan.evaluate(festival_plan(), festival)
    p = festival_plan()
    p["cable_marks"] = {"f:7": "venue", "f:12": "borrowed"}
    ev = plan.evaluate(p, festival)
    l7 = _link_to(ev, "f:7")
    assert l7["mark"] == "venue" and l7["cables"][0]["source"] == "venue"
    pk = outputs.pick_list(ev, p)
    assert sum(r["count"] for r in pk["venue"]) == 1
    assert sum(r["count"] for r in pk["borrowed"]) == 1
    bag_n = lambda pl: sum(r["count"] for r in pl["bag"] if "cable" in r["what"].lower() or "m" in r["what"])
    assert bag_n(pk) <= bag_n(outputs.pick_list(base, festival_plan()))
    assert "(venue)" in outputs.plot_svg(ev, p, festival)


def test_a_cable_marked_to_buy_goes_on_the_shopping_list(festival):
    p = festival_plan()
    p["cable_marks"] = {"f:8": "buy"}
    ev = plan.evaluate(p, festival)
    l8 = _link_to(ev, "f:8")
    assert not l8["cables"] and l8["missing_m"] >= l8["need_m"]
    assert ev["shopping"] and sum(s["count"] for s in ev["shopping"]) >= 1
    assert not any(i["code"] == "C005" and "missing" in i["text"] for i in ev["issues"])


def test_preferred_is_kept():
    p = festival_plan()
    p["preferred"] = {"key": "B", "name": "Splitter"}
    assert plan.clean_plan(p)["preferred"] == {"key": "B", "name": "Splitter"}
    p["preferred"] = {"key": "bb"}
    assert "preferred" not in plan.clean_plan(p)


def test_hidden_meshes_are_not_drawn_but_still_avoided(festival):
    if not festival.get("keep_out"):
        pytest.skip("the Festival show has no meshes")
    p = festival_plan()
    shown = outputs.plot_svg(plan.evaluate(p, festival), p, festival)
    p["hide_band"] = True
    p = plan.clean_plan(p)
    ev = plan.evaluate(p, festival)
    hidden = outputs.plot_svg(ev, p, festival)
    assert "#fee2e2" in shown and 'fill="#fee2e2" stroke="#ef4444"' not in hidden
    assert ev["keep_out"]                     # the router still knows them


def test_terminator_is_drawn_on_the_last_fixture_after_it(festival):
    p = festival_plan()
    ev = plan.evaluate(p, festival)
    sh, _box = outputs._drawing(ev, p, festival)
    t_idx = [i for i, s in enumerate(sh) if s[0] == "text" and s[3] == "T"]
    fx_idx = [i for i, s in enumerate(sh) if s[0] == "circle" and s[3] == 170]
    assert t_idx and min(t_idx) > max(fx_idx)
    ends = [w["links"][-1]["route"]["points"][-1] for w in ev["chains"] if w.get("terminator") and w["links"]]
    circles = [(s[1], s[2]) for s in sh if s[0] == "circle" and s[3] == 120]
    assert sorted(map(tuple, ends)) == sorted(circles)


def test_layout_lists_fixtures_and_outputs(festival):
    lay = plan.layout(festival_plan(), festival)
    assert len(lay["fixtures"]) == 14 and lay["fixtures"][7]["chain"] == 3
    assert any(s["kind"] == "splitter" and len(s["outputs"]) >= 4 for s in lay["sources"])
    assert lay["chains"][0]["from"]


def test_wire_by_names(festival):
    names = {f["id"]: f["name"] for f in festival["fixtures"]}
    p = plan.apply_wiring(festival_plan(), festival, chains=[
        {"from": "splitter1", "port": 2, "devices": [names["13"], "9"]},
    ], replace=False, marks={names["13"]: "venue"})
    on = [c for c in p["chains"] if c["source"] == {"item": "splitter1", "port": 1}]
    assert on[-1]["devices"] == [{"fixture": "13"}, {"fixture": "9"}]
    assert all({"fixture": "13"} not in c["devices"] for c in p["chains"][:-1])
    assert p["cable_marks"] == {"f:13": "venue"}


def test_wire_replace_and_errors(festival):
    p = plan.apply_wiring(festival_plan(), festival, chains=[{"from": "splitter1", "port": 1, "devices": ["0", "1"]}])
    assert len(p["chains"]) == 1
    with pytest.raises(plan.WiringError):
        plan.apply_wiring(festival_plan(), festival, chains=[{"from": "nothing", "devices": ["0"]}])
    with pytest.raises(plan.WiringError):
        plan.apply_wiring(festival_plan(), festival, chains=[{"from": "splitter1", "port": 9, "devices": ["0"]}])
    with pytest.raises(plan.WiringError):
        plan.apply_wiring(festival_plan(), festival, chains=[{"from": "splitter1", "devices": ["No such PAR"]}])


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")) and " 2." not in f:
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    r = client.post("/api/load", json={"path": str(tmp_path / "Festival_14fix.qxw")})
    assert r.status_code < 300
    client.tmp = tmp_path
    return client


def test_wire_route_keeps_the_plan_and_changes_rev(c):
    assert c.post("/api/cabling/plan", json={"plan": festival_plan()}).status_code == 200
    st = c.get("/api/cabling/state").get_json()
    rev0 = c.get("/api/cabling/rev").get_json()["rev"]
    import time; time.sleep(0.01)
    src = next(i for i in st["plan"]["tonight"]["items"] if i["kind"] in ("interface", "splitter"))
    fx = st["rig"]["fixtures"][0]
    r = c.post("/api/cabling/wire", json={"chains": [{"from": src["id"], "port": 1, "devices": [fx["id"]]}]})
    d = r.get_json()
    assert r.status_code == 200, d
    assert d["saved"] and os.path.isfile(c.tmp / d["sidecar"])
    assert c.get("/api/cabling/rev").get_json()["rev"] != rev0
    assert c.get("/api/cabling/state").get_json()["plan"]["chains"][0]["devices"] == [{"fixture": fx["id"]}]
    assert c.post("/api/cabling/wire", json={"chains": [{"from": "nope", "devices": []}]}).status_code == 400
    lay = c.get("/api/cabling/layout").get_json()
    assert lay["fixtures"] and lay["chains"]
