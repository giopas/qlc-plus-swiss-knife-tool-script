"""Cabling planner, part 1 (3.6.0): kit model, inventory, the show's rig,
the connector walk and the plan file — on the Festival show."""

import copy
import json
import os

import pytest

from core import qxw_io
from core.cabling import chain, kit, plan, rig
from core.doctor import load_qxf_defs

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")
FESTIVAL = os.path.join(CORPUS, "Festival_14fix.qxw")
P = kit.PRESETS
PAR = ("Generic", "7-Ch RGB LED PAR")


@pytest.fixture(scope="module")
def festival():
    root = qxw_io.load_qxw(FESTIVAL, strip_namespace=True).getroot()
    return rig.read_rig(root, load_qxf_defs([CORPUS]), FESTIVAL)


CABLE_BAG = [dict(P["cable_3_1.5"], count=2), dict(P["cable_3_3"], count=12), dict(P["cable_3_5"], count=4),
             dict(P["cable_3_10"], count=3), dict(P["cable_3_20"], count=1)]


def bag(**extra):
    items = [P["enttec_usb_pro"], P["splitter_1x4"], P["adapter_5m_3f"]] + CABLE_BAG + [
             dict(P["terminator_3"], count=2), kit.fixture_item(*PAR, count=8)]
    items += extra.get("more", [])
    return kit.tonight_from({"items": items})


def first_out(dev):
    return next(p for p in dev["ports"] if p["role"] == "out")


# ── kit model ───────────────────────────────────────────────────────────────

def test_connectors_from_qxf():
    assert kit.connectors_from_qxf("3-pin") == (["xlr3"], True)
    assert kit.connectors_from_qxf("3-pin and 5-pin") == (["xlr3", "xlr5"], True)
    assert kit.connectors_from_qxf("5-pin IP65") == (["xlr5"], True)
    assert kit.connectors_from_qxf("Other") == (["xlr3"], False)
    assert kit.connectors_from_qxf("") == (["xlr3"], False)


def test_mates_needs_same_connector_and_opposite_gender():
    assert kit.mates(kit.end("xlr3", "m"), kit.port("in", "xlr3", "f"))
    assert not kit.mates(kit.end("xlr3", "m"), kit.port("in", "xlr3", "m"))
    assert not kit.mates(kit.end("xlr3", "m"), kit.port("out", "xlr5", "f"))
    assert kit.mates(kit.end("usb"), kit.port("in", "usb"))
    assert kit.label(kit.end("xlr5", "f")) == "5-pin ♀"


def test_every_preset_is_a_valid_item():
    for p in kit.presets():
        assert kit.clean_item(p["item"])["kind"] == p["item"]["kind"]


@pytest.mark.parametrize("bad", [
    {"kind": "rocket", "name": "x"},
    {"kind": "cable", "name": "", "a": kit.end("xlr3", "m"), "b": kit.end("xlr3", "f"), "length": 3},
    {"kind": "cable", "name": "c", "a": kit.end("xlr3", "m"), "b": kit.end("xlr3", "f"), "length": 0},
    {"kind": "cable", "name": "c", "a": kit.end("xlr9", "m"), "b": kit.end("xlr3", "f"), "length": 3},
    {"kind": "splitter", "name": "s", "ports": []},
    {"kind": "fixture", "name": "f", "ports": [kit.port("in", "xlr3", "m")]},
])
def test_clean_item_refuses(bad):
    with pytest.raises(kit.KitError):
        kit.clean_item(bad)


def test_inventory_drops_bad_items_and_numbers_the_rest():
    inv = kit.clean_inventory({"items": [P["cable_3_3"], {"kind": "nope"}, P["cable_3_5"]]})
    assert [i["id"] for i in inv["items"]] == ["cable1", "cable2"]
    assert inv["dropped"][0]["index"] == 1


def test_base_inventory_round_trip_is_stable(tmp_path):
    kit.save_base({"items": [P["enttec_usb_pro"], P["cable_3_3"]]})
    first = open(kit.kit_path(), encoding="utf-8").read()
    kit.save_base(kit.load_base())
    assert open(kit.kit_path(), encoding="utf-8").read() == first
    assert str(tmp_path) in kit.kit_path()          # the test never touches the real settings
    assert [i["name"] for i in kit.load_base()["items"]] == ["Enttec DMX USB Pro", "3-pin DMX cable 3 m"]


def test_tonight_is_a_copy_owned_by_me():
    base = {"items": [P["cable_3_3"]]}
    t = kit.tonight_from(base)
    assert t["items"][0]["owner"] == "mine"
    assert "owner" not in base["items"][0]


# ── the show ────────────────────────────────────────────────────────────────

def test_festival_rig(festival):
    fx = festival["fixtures"]
    assert len(fx) == 14
    assert festival["stage"]["w"] == 6000 and festival["stage"]["d"] == 4000
    assert [f["name"] for f in fx if f["hung"] and f["place"]["bottom"] > 2800] == [f"Ceiling {i}" for i in range(1, 7)]
    assert all(f["conns"] == ["xlr3"] and f["connector_known"] for f in fx)
    assert festival["fixtures"][0]["address"] == 101          # shown 1-based
    assert rig.used_universes(festival) == ["0"]


def test_universe_output_matches_the_enttec(festival):
    uni = festival["universes"][0]
    assert uni["output"]["plugin"] == "DMX USB"
    assert rig.interface_for(uni, bag())["name"] == "Enttec DMX USB Pro"
    assert rig.interface_for(uni, kit.tonight_from({"items": [P["artnet_node_2"]]})) is None


def test_match_inventory_mine_and_missing(festival):
    m = {x["id"]: x for x in rig.match_inventory(festival, bag())}
    assert [m[str(i)]["owner"] for i in range(6, 14)] == ["mine"] * 8
    assert [m[str(i)]["reason"] for i in range(6)] == ["missing"] * 6


def test_match_inventory_counts_and_owner_choices(festival):
    inv = kit.tonight_from({"items": [kit.fixture_item(*PAR, count=5)]})
    m = rig.match_inventory(festival, inv, {"0": "venue", "13": "borrowed"})
    by = {x["id"]: x for x in m}
    assert by["0"]["owner"] == "venue"
    assert sum(1 for x in m if x["owner"] == "mine") == 5
    assert by["13"]["owner"] == "borrowed" or by["13"]["reason"] == "matched"
    assert any(x["reason"] == "count" for x in m)


# ── the connector walk ──────────────────────────────────────────────────────

def test_enttec_to_3pin_splitter_takes_the_adapter():
    inv = bag()
    en, sp = kit.by_kind(inv, "interface")[0], kit.by_kind(inv, "splitter")[0]
    w = chain.walk(en, first_out(en), [sp], inv)
    assert [a["name"] for a in w["links"][0]["adapters"]] == ["Adapter 5-pin ♂ → 3-pin ♀"]
    assert [i["code"] for i in w["issues"]] == ["C009"]       # splitter input termination unknown
    assert w["terminator"] is None


def test_no_adapter_is_c001_with_the_fix():
    inv = kit.tonight_from({"items": [P["enttec_usb_pro"], P["splitter_1x4"], P["cable_3_3"]]})
    en, sp = kit.by_kind(inv, "interface")[0], kit.by_kind(inv, "splitter")[0]
    w = chain.walk(en, first_out(en), [sp], inv)
    c001 = [i for i in w["issues"] if i["code"] == "C001"]
    assert c001 and "5-pin ♂ → 3-pin ♀" in c001[0]["fix"]


def test_splitter_with_a_switch_needs_no_terminator():
    inv = bag()
    en = kit.by_kind(inv, "interface")[0]
    sp = dict(kit.by_kind(inv, "splitter")[0], termination="switch")
    assert chain.walk(en, first_out(en), [sp], inv)["issues"] == []


def test_fixture_chains_and_terminators(festival):
    inv = bag()
    sp = kit.by_kind(inv, "splitter")[0]
    outs = [p for p in sp["ports"] if p["role"] == "out"]
    fx = {f["id"]: f for f in festival["fixtures"]}
    chs = [chain.walk(sp, o, [chain.fixture_device(fx[i]) for i in ids], inv)
           for o, ids in zip(outs, (["0", "1", "2"], ["6", "7"], ["8", "9"]))]
    assert [c["terminator"]["at"] for c in chs] == ["Ceiling 3", "Wing Left", "Banner Center"]
    extra = chain.check(chs, inv)
    assert [i["code"] for i in extra] == ["C002", "C103"]
    assert "Banner Center" in extra[0]["text"]
    assert "Adapter 5-pin" in extra[1]["text"]          # not used without the feed


def test_auto_termination_mid_chain_is_c008(festival):
    inv = bag()
    sp = kit.by_kind(inv, "splitter")[0]
    fx = {f["id"]: f for f in festival["fixtures"]}
    a = dict(chain.fixture_device(fx["6"]), termination="auto")
    w = chain.walk(sp, first_out(sp), [a, chain.fixture_device(fx["7"])], inv)
    assert "C008" in [i["code"] for i in w["issues"]]


def test_too_many_devices_is_c003(festival):
    inv = bag()
    sp = copy.deepcopy(kit.by_kind(inv, "splitter")[0])
    out = first_out(sp)
    out["drive"] = 2
    fx = {f["id"]: f for f in festival["fixtures"]}
    w = chain.walk(sp, out, [chain.fixture_device(fx[i]) for i in ("6", "7", "8")], inv)
    assert "C003" in [i["code"] for i in w["issues"]]


def test_mic_cable_is_c010(festival):
    inv = kit.tonight_from({"items": [P["splitter_1x4"], dict(P["cable_3_5"], type="mic", name="Mic 5 m")]})
    sp = kit.by_kind(inv, "splitter")[0]
    fx = {f["id"]: f for f in festival["fixtures"]}
    cab = kit.by_kind(inv, "cable")[0]
    w = chain.walk(sp, first_out(sp), [chain.fixture_device(fx["6"])], inv, [cab])
    assert "C010" in [i["code"] for i in w["issues"]]


def test_unknown_connector_is_one_c101_per_chain(festival):
    inv = bag()
    sp = kit.by_kind(inv, "splitter")[0]
    fxs = [dict(f, connector_known=False) for f in festival["fixtures"][6:9]]
    w = chain.walk(sp, first_out(sp), [chain.fixture_device(f) for f in fxs], inv)
    assert [i["code"] for i in w["issues"]].count("C101") == 1


# ── the plan ────────────────────────────────────────────────────────────────

def festival_plan():
    p = plan.new_plan({"items": bag()["items"]})
    p["owners"] = {str(i): "venue" for i in range(6)}
    p["chains"] = [
        {"source": {"item": "interface1", "port": 0}, "devices": [{"item": "splitter1"}], "label": "Feed"},
        {"source": {"item": "splitter1", "port": 1}, "devices": [{"fixture": str(i)} for i in range(6)]},
        {"source": {"item": "splitter1", "port": 2}, "devices": [{"fixture": i} for i in ("7", "12", "10", "6")]},
        {"source": {"item": "splitter1", "port": 3}, "devices": [{"fixture": i} for i in ("8", "11", "9", "13")]},
    ]
    return p


def test_sidecar_path_drops_the_version():
    assert plan.sidecar_path("/a/Festival_14fix_v7.qxw") == os.path.abspath("/a/Festival_14fix.cabling.json")


def test_plan_round_trip_is_deterministic(tmp_path):
    path = str(tmp_path / "Festival_14fix.cabling.json")
    plan.save_plan(festival_plan(), path)
    first = open(path, encoding="utf-8").read()
    plan.save_plan(plan.load_plan(path), path)
    assert open(path, encoding="utf-8").read() == first
    assert json.loads(first)["controller"]["mode"] == "stand"


def test_clean_controller():
    c = plan.clean_controller({"mode": "foh", "distance_m": "15", "route": "wall"})
    assert c == {"mode": "foh", "side": "stage-left", "distance_m": 15.0, "route": "wall"}
    assert plan.clean_controller({"mode": "space", "distance_m": -1})["mode"] == "stand"


def test_evaluate_festival(festival):
    e = plan.evaluate(festival_plan(), festival)
    assert [f["owner"] for f in e["fixtures"]] == ["venue"] * 6 + ["mine"] * 8
    assert [i["code"] for i in e["issues"]] == ["C002"]      # 3 chain ends, 2 terminators
    assert e["summary"]["error"] == 1
    assert [c["name"] for c in e["chains"]][0] == "Feed"


def test_evaluate_finds_unchained_and_missing_interface(festival):
    p = festival_plan()
    p["chains"] = p["chains"][:2]
    p["tonight"]["items"] = [i for i in p["tonight"]["items"] if i["kind"] != "interface"]
    codes = [i["code"] for i in plan.evaluate(p, festival)["issues"]]
    assert "C014" in codes and "C006" in codes


def test_evaluate_two_universes_on_a_chain(festival):
    r = copy.deepcopy(festival)
    r["fixtures"][7]["universe"] = "1"
    e = plan.evaluate(festival_plan(), r)
    assert any(i["code"] == "C004" for c in e["chains"] for i in c["issues"])


def test_not_in_inventory_groups_by_model(festival):
    p = plan.new_plan({"items": bag()["items"]})
    groups = plan.not_in_inventory(p, festival)
    assert len(groups) == 1 and groups[0]["model"] == "LED 4C-12 Silent Slim Spot"
    assert groups[0]["ids"] == [str(i) for i in range(6)]
    p["owners"] = {str(i): "venue" for i in range(6)}
    assert plan.not_in_inventory(p, festival) == []


def test_evaluate_does_not_change_the_show():
    before = open(FESTIVAL, "rb").read()
    root = qxw_io.load_qxw(FESTIVAL, strip_namespace=True).getroot()
    plan.evaluate(festival_plan(), rig.read_rig(root, load_qxf_defs([CORPUS])))
    assert open(FESTIVAL, "rb").read() == before


# ── through the Flask routes ─────────────────────────────────────────────────

def _client(tmp_path):
    import shutil
    import app
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    p = tmp_path / "Festival_14fix_v3.qxw"
    shutil.copy(FESTIVAL, p)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    return c, p


def test_routes_kit_state_evaluate_and_save(tmp_path):
    c, p = _client(tmp_path)
    k = c.get("/api/cabling/kit").get_json()
    assert k["kit"]["items"] == [] and len(k["presets"]) >= 15
    r = c.post("/api/cabling/kit", json={"kit": {"items": bag()["items"]}})
    assert r.status_code == 200 and len(r.get_json()["kit"]["items"]) == 10
    assert c.post("/api/cabling/kit", json={"kit": {"items": [{"kind": "nope"}]}}).status_code == 400

    s = c.get("/api/cabling/state").get_json()
    assert len(s["rig"]["fixtures"]) == 14 and not s["saved"]
    assert s["found"][0]["model"] == "LED 4C-12 Silent Slim Spot"
    assert s["sidecar"] == "Festival_14fix.cabling.json"

    fp = festival_plan()
    e = c.post("/api/cabling/evaluate", json={"plan": fp}).get_json()
    assert [i["code"] for i in e["evaluation"]["issues"]] == ["C002"] and e["found"] == []

    before = p.read_bytes()
    r = c.post("/api/cabling/plan", json={"plan": fp}).get_json()
    assert r["saved"] and (tmp_path / "Festival_14fix.cabling.json").is_file()
    assert p.read_bytes() == before                   # the show is never written
    assert c.get("/api/cabling/state").get_json()["saved"]


def test_routes_check_one_item(tmp_path):
    c, _ = _client(tmp_path)
    ok = c.post("/api/cabling/kit/item", json={"item": P["cable_3_5"]}).get_json()
    assert ok["item"]["length"] == 5
    bad = c.post("/api/cabling/kit/item", json={"item": {"kind": "cable", "name": "x"}})
    assert bad.status_code == 400 and "end A" in bad.get_json()["error"]


def test_routes_need_a_show(monkeypatch):
    import app
    from core import workspace
    monkeypatch.setitem(workspace._state, "loaded", False)
    c = app.create_app().test_client()
    assert c.get("/api/cabling/state").status_code == 400


# ── routes on the floor, cables, the automatic plan (parts 3 and 4) ─────────

from core.cabling import auto, cables, route  # noqa: E402


def lixada_kit():
    return {"items": [P["enttec_usb_pro"], P["lixada_1x8"], P["adapter_5m_3f"]] + CABLE_BAG
            + [dict(P["terminator_3"], count=3), kit.fixture_item(*PAR, count=8)]}


def test_lixada_preset():
    it = kit.clean_item(P["lixada_1x8"])
    roles = [(p["role"], p["conn"], p["gender"]) for p in it["ports"]]
    assert roles[:2] == [("in", "xlr3", "m"), ("thru", "xlr3", "f")]
    assert roles.count(("out", "xlr3", "f")) == 8
    assert it["termination"] == "none"


def test_the_truss_is_found(festival):
    ts = route.trusses(festival["fixtures"])
    assert len(ts) == 1 and ts[0]["fixtures"] == [str(i) for i in range(6)]
    assert 2800 < ts[0]["h"] < 3000


def test_routes_avoid_the_keep_out_and_add_the_climb(festival):
    p = plan.new_plan(lixada_kit())
    floor, router, trs = plan.floor_for(p, festival)
    a = {"x": 0, "z": 2000, "h": 0}
    b = {"x": 6000, "z": 2000, "h": 0}
    h = router.hop(a, b)
    assert h["length"] >= 6000 and h["climb"] == 0
    up = router.hop(a, {"x": 900, "z": 140, "h": 2900})
    assert up["climb"] == 2900
    on = router.hop({"x": 892, "z": 142, "h": 2900, "truss": "truss1"}, {"x": 1792, "z": 142, "h": 2900, "truss": "truss1"})
    assert on["length"] == 900 and on["truss"] == "truss1"


def test_walkway_crossing_is_c007(festival):
    p = plan.new_plan(lixada_kit())
    p["walkways"] = [{"x0": 6000, "z0": -1000, "x1": 6600, "z1": 6000, "label": "wing"}]
    p["places"] = {"splitter1": {"x": 3000, "z": 150}}
    p["chains"] = [{"source": {"item": "interface1", "port": 0}, "devices": [{"item": "splitter1"}]}]
    ev = plan.evaluate(p, festival)
    assert any(i["code"] == "C007" for i in ev["chains"][0]["issues"])
    p["walkways"][0]["ramp"] = True
    assert not any(i["code"] == "C007" for i in plan.evaluate(p, festival)["chains"][0]["issues"])


def test_cables_longest_first_shortest_that_fits():
    inv = kit.tonight_from({"items": [dict(P["cable_3_3"], count=2), P["cable_3_10"], P["cable_3_5"]]})
    r = cables.assign([{"key": "a", "need": 4, "conn": "xlr3"}, {"key": "b", "need": 2, "conn": "xlr3"},
                       {"key": "c", "need": 9, "conn": "xlr3"}], inv)
    got = {k: [c["length"] for c in v["cables"]] for k, v in r["by_hop"].items()}
    assert got == {"c": [10.0], "a": [5.0], "b": [3.0]}


def test_cables_join_two_then_say_what_is_missing():
    inv = kit.tonight_from({"items": [dict(P["cable_3_3"], count=1), P["cable_3_10"]]})
    r = cables.assign([{"key": "a", "need": 12, "conn": "xlr3"}, {"key": "b", "need": 2, "conn": "xlr3"}], inv)
    assert r["by_hop"]["a"]["joined"] and r["by_hop"]["b"]["missing"] == 3
    assert r["missing"] == [{"conn": "xlr3", "length": 3, "count": 1}]


def test_mic_cable_only_when_nothing_else_fits():
    inv = kit.tonight_from({"items": [dict(P["cable_3_5"], type="mic", name="Mic 5 m"), P["cable_3_3"]]})
    r = cables.assign([{"key": "a", "need": 2, "conn": "xlr3"}, {"key": "b", "need": 4, "conn": "xlr3"}], inv)
    assert r["by_hop"]["b"]["mic"] and not r["by_hop"]["a"]["mic"]


def test_order_is_exact_for_small_groups():
    pts = {"S": 0, "a": 1, "b": 5, "c": 2, "d": 9}
    dist = lambda x, y: abs(pts[x] - pts[y])
    path, c = auto.order("S", ["d", "b", "a", "c"], dist)
    assert path == ["a", "c", "b", "d"] and c == 9


def test_order_large_groups_still_visit_all():
    pts = {"S": 0, **{str(i): (i * 7) % 23 for i in range(12)}}
    dist = lambda x, y: abs(pts[x] - pts[y])
    path, _ = auto.order("S", [str(i) for i in range(12)], dist)
    assert sorted(path) == sorted(str(i) for i in range(12))


def _alts(festival, mode):
    p = plan.new_plan(lixada_kit())
    p["controller"]["mode"] = mode
    return auto.alternatives(p, festival)


def test_alternatives_where_i_stand(festival):
    alts = _alts(festival, "stand")
    names = [a["name"] for a in alts]
    assert sorted(names) == ["One daisy chain", "Splitter at the computer", "Splitter on stage"]
    assert alts[0]["best"] and [a["key"] for a in alts] == ["A", "B", "C"]
    daisy = next(a for a in alts if a["name"] == "One daisy chain")
    assert any(i["code"] == "C012" for c in daisy["evaluation"]["chains"] for i in c["issues"])
    best = alts[0]["evaluation"]
    truss = next(c for c in best["chains"] if c["links"] and c["links"][0]["to"].startswith("Ceiling"))
    assert sorted(l["to"] for l in truss["links"]) == [f"Ceiling {i}" for i in range(1, 7)]
    # every fixture on exactly one chain, the Enttec takes its adapter
    tos = [l["to"] for c in best["chains"] for l in c["links"]]
    assert sum(1 for t in tos if not t.startswith("Lixada")) == 14
    assert best["totals"]["adapters"] == 1


def test_alternatives_are_deterministic(festival):
    a = [(x["name"], x["cable_m"], x["plan"]["chains"]) for x in _alts(festival, "stand")]
    b = [(x["name"], x["cable_m"], x["plan"]["chains"]) for x in _alts(festival, "stand")]
    assert a == b


def test_front_of_house(festival):
    alts = _alts(festival, "foh")
    by = {a["name"]: a for a in alts}
    feed = by["One long DMX feed"]["evaluation"]
    assert any(i["code"] == "C017" for c in feed["chains"] for i in c["issues"])
    node = by["Node on the network"]
    assert any(s["what"].startswith("Art-Net") for s in node["missing"])     # proposed, not owned
    assert alts[0]["name"] == "One long DMX feed"                            # the feasible one first


def test_planner_chooses_the_computer(festival):
    alts = _alts(festival, "auto")
    assert len(alts) == 3 and all(a["name"].startswith("Computer ") for a in alts)
    assert all("controller" in a["plan"]["places"] for a in alts)
    assert any(i["code"] == "C016" for i in alts[0]["evaluation"]["issues"])   # no outlet marked


def test_route_auto(tmp_path):
    c, _ = _client(tmp_path)
    p = plan.new_plan(lixada_kit())
    alts = c.post("/api/cabling/auto", json={"plan": p}).get_json()["alternatives"]
    assert [a["key"] for a in alts] == ["A", "B", "C"]
    assert alts[0]["evaluation"]["chains"]


# ── outputs (part 5) ────────────────────────────────────────────────────────

from core.cabling import outputs  # noqa: E402


@pytest.fixture(scope="module")
def best(festival):
    a = auto.alternatives(plan.new_plan(lixada_kit()), festival)[0]
    return a["evaluation"], a["plan"], festival


def test_numbered_cables_feed_first(best):
    ev, p, _ = best
    nums = outputs.numbered(ev, p)
    assert nums[0]["chain"] == "Feed" and nums[0]["from"] == "Enttec" and nums[0]["to"] == "Lixada"
    assert [c["n"] for c in nums] == list(range(1, len(nums) + 1))
    assert len({c["colour"] for c in nums}) >= 3


def test_lixada_without_a_switch_needs_a_terminator_on_its_thru(best):
    ev, _p, _ = best
    feed = next(w for w in ev["chains"] if w["name"] == "Feed")
    assert feed["terminator"]["at"].startswith("Lixada")
    assert not any(i["code"] == "C009" for i in feed["issues"])


def test_pick_list_and_shopping(best):
    ev, p, _ = best
    pl = outputs.pick_list(ev, p)
    whats = [r["what"] for r in pl["bag"]]
    assert "Enttec DMX USB Pro" in whats and "Adapter 5-pin ♂ → 3-pin ♀" in whats
    assert any(w.startswith("Lixada") and "power supply" in w for w in whats)
    assert pl["buy"] == [{"what": "Terminator 3-pin ♂", "count": 2}]      # 5 ends, 3 in the kit
    csv_text = outputs.pick_list_csv(pl)
    assert csv_text.startswith("Section,Item,Count\n") and "To buy,Terminator" in csv_text
    assert "IN THE BAG" in outputs.pick_list_text(pl, "Festival", "2026-10-18")


def test_venue_items_are_labelled_house_and_not_packed(festival):
    p = plan.new_plan(lixada_kit())
    p["owners"] = {str(i): "venue" for i in range(6)}
    a = auto.alternatives(p, festival)[0]
    nums = outputs.numbered(a["evaluation"], a["plan"])
    assert any(c["house"] for c in nums) and "(HOUSE)" in outputs.labels_text(nums)


def test_plot_and_pdfs_are_deterministic(best):
    ev, p, r = best
    svg = outputs.plot_svg(ev, p, r, "Festival")
    assert svg.startswith("<svg") and "Ceiling 1" in svg and "Computer" in svg
    assert outputs.plot_svg(ev, p, r, "Festival") == svg
    for b in (outputs.plot_pdf(ev, p, r, "Festival"), outputs.labels_pdf(outputs.numbered(ev, p), "Festival"),
              outputs.pick_list_pdf(outputs.pick_list(ev, p), "Festival", "2026-10-18")):
        assert b.startswith(b"%PDF")


def test_load_in_order(best):
    ev, p, _ = best
    steps = outputs.load_in(ev, p)
    assert steps[0].startswith("Computer and Enttec DMX USB Pro at the stage left wing")
    assert any("Terminator on Lixada" in s for s in steps)
    assert steps[-1].startswith("Start QLC+ and run PANIC RESET")


def test_fixture_found_on_the_day(festival):
    p = plan.new_plan(lixada_kit())
    p["extras"] = [{"name": "Spare PAR", "manufacturer": "Generic", "model": "7-Ch RGB LED PAR",
                    "x": 3000, "z": 3800, "h": 0}]
    alts = auto.alternatives(p, festival)
    ev = alts[0]["evaluation"]
    assert any(i["code"] == "C015" and "Spare PAR" in i["text"] for i in ev["issues"])
    tos = [l["to"] for c in ev["chains"] for l in c["links"]]
    assert tos.count("Spare PAR") == 1                       # cabled once, not twice
    assert plan.clean_plan(alts[0]["plan"])["extras"][0]["id"] == "x1"


def test_route_exports_and_crew_checklist(tmp_path):
    c, p = _client(tmp_path)
    alts = c.post("/api/cabling/auto", json={"plan": plan.new_plan(lixada_kit())}).get_json()["alternatives"]
    assert alts[0]["svg"].startswith("<svg")
    best = alts[0]["plan"]
    for what, head in (("plot_pdf", b"%PDF"), ("plot_svg", b"<svg"), ("pick_pdf", b"%PDF"), ("pick_csv", b"Section"),
                       ("pick_txt", b"FESTIVAL"), ("labels_pdf", b"%PDF"), ("labels_txt", b"#1"), ("loadin_txt", b"1. ")):
        r = c.post("/api/cabling/export", json={"plan": best, "what": what})
        assert r.status_code == 200 and r.data.startswith(head), what
        assert r.headers["X-Suggested-Filename"].startswith("Festival_14fix_")
    assert c.post("/api/cabling/export", json={"plan": best, "what": "nope"}).status_code == 400
    # once kept next to the show, the crew checklist carries it
    c.post("/api/cabling/plan", json={"plan": best})
    doc = c.post("/api/showbook/preview", json={"presets": ["checklist"]}).get_json()
    cab = doc["document"]["sections"]["cabling"]
    assert cab["steps"][0].startswith("Computer") and cab["svg"].startswith("<svg")
    pdf = c.post("/api/showbook/export/pdf", json={"presets": ["checklist"]})
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")


@pytest.mark.parametrize("show", ["Pub_6fix.qxw", "FloorShow_8fix.qxw", "QuickStart_multiuni.qxw"])
@pytest.mark.parametrize("mode", ["stand", "foh", "auto"])
def test_other_shows_plan_in_every_mode(show, mode):
    """Every fixture lands on a chain, whatever the show and the controller."""
    path = os.path.join(CORPUS, show)
    r = rig.read_rig(qxw_io.load_qxw(path, strip_namespace=True).getroot(), load_qxf_defs([CORPUS]), path)
    p = plan.new_plan(lixada_kit())
    p["controller"]["mode"] = mode
    alts = auto.alternatives(p, r)
    assert alts and alts[0]["best"]
    ev = alts[0]["evaluation"]
    for a in alts:
        if a["name"] != "Node on the network":     # a node output per universe; 64 fixtures do not fit one
            assert not [i for i in a["evaluation"]["issues"] if i["code"] in ("C004", "C006")], a["name"]
    assert outputs.plot_svg(ev, alts[0]["plan"], r, show).startswith("<svg")
    assert outputs.load_in(ev, alts[0]["plan"])


def test_a_second_universe_gets_its_own_interface():
    """One Enttec has one output: universe 2 needs a second one (missing, to buy)."""
    path = os.path.join(CORPUS, "QuickStart_multiuni.qxw")
    r = rig.read_rig(qxw_io.load_qxw(path, strip_namespace=True).getroot(), load_qxf_defs([CORPUS]), path)
    a = next(a for a in auto.alternatives(plan.new_plan(lixada_kit()), r) if a["name"] == "Splitter on stage")
    srcs = {(c["source"]["item"], c["source"]["port"]) for c in a["plan"]["chains"]}
    assert len(srcs) == len(a["plan"]["chains"])            # one chain per socket
    assert any("(universe 2)" in i["text"] and i["code"] == "C005" for i in a["evaluation"]["issues"])
    # two chains from one socket are reported
    p = copy.deepcopy(a["plan"])
    p["chains"].append(copy.deepcopy(p["chains"][-1]))
    p["chains"][-1]["devices"] = []
    ev = plan.evaluate(p, r)
    assert any(i["code"] == "C006" and "one socket" in i["text"] for i in ev["issues"])
