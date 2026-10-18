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


def bag(**extra):
    items = [P["enttec_usb_pro"], P["splitter_1x4"], P["adapter_5m_3f"], P["cable_3_3"],
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
