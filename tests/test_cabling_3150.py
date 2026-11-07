"""Cabling 3.15.0: single fixtures sent by radio.  One transmitter on a
splitter output, a receiver of its own by each fixture, the fixtures marked
as fed by radio, the cables and terminators that follow."""

import copy
import os

import pytest

from core import qxw_io
from core.cabling import kit, outputs, plan, rig
from core.doctor import load_qxf_defs

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")
FESTIVAL = os.path.join(CORPUS, "Festival_14fix.qxw")
P = kit.PRESETS
PAR = ("Generic", "7-Ch RGB LED PAR")


@pytest.fixture(scope="module")
def festival():
    root = qxw_io.load_qxw(FESTIVAL, strip_namespace=True).getroot()
    return rig.read_rig(root, load_qxf_defs([CORPUS]), FESTIVAL)


def radio_plan(receivers=2):
    items = [P["enttec_usb_pro"], P["lixada_1x8"],
             dict(P["cable_3_1.5"], count=2), dict(P["cable_3_3"], count=12), dict(P["cable_3_5"], count=4),
             dict(P["cable_3_10"], count=3), dict(P["cable_3_20"], count=1), dict(P["terminator_3"], count=6),
             copy.deepcopy(P["wireless_tx"]), dict(copy.deepcopy(P["wireless_rx"]), count=receivers),
             kit.fixture_item(*PAR, count=8)]
    p = plan.new_plan({"items": items})
    ids = {it["kind"]: it["id"] for it in p["tonight"]["items"]}
    p["owners"] = {str(i): "venue" for i in range(14)}
    tx, rx, sp = ids["wireless_tx"], ids["wireless_rx"], ids["splitter"]
    p["places"][sp] = {"x": 500, "z": 300}
    p["chains"] = [
        {"source": {"item": ids["interface"], "port": 0}, "devices": [{"item": sp}], "label": "Feed"},
        {"source": {"item": sp, "port": 1}, "devices": [{"fixture": str(i)} for i in range(1, 5)]},
        {"source": {"item": sp, "port": 2}, "devices": [{"fixture": str(i)} for i in range(6, 14)]},
        {"source": {"item": sp, "port": 3}, "devices": [{"item": tx}], "label": "Radio transmitter"},
        {"source": {"item": tx, "port": 0}, "devices": [{"item": rx}, {"fixture": "0"}], "label": "Radio"},
        {"source": {"item": tx, "port": 0}, "devices": [{"item": rx}, {"fixture": "5"}], "label": "Radio"},
    ]
    return plan.clean_plan(p), tx, rx


def test_fixtures_by_radio_are_marked(festival):
    p, tx, rx = radio_plan()
    ev = plan.evaluate(p, festival)
    fx = {f["id"]: f for f in ev["fixtures"]}
    assert fx["0"]["radio"]["chain"] == 5 and fx["5"]["radio"]["chain"] == 6
    assert fx["0"]["radio"]["rx"].startswith("Wireless DMX receiver")
    assert not any(fx[i].get("radio") for i in ("1", "6", "13"))
    assert set(plan.radio_feeds(p, {it["id"]: it for it in p["tonight"]["items"]})) == {"0", "5"}


def test_no_cable_by_radio_and_each_receiver_by_its_fixture(festival):
    p, tx, rx = radio_plan()
    ev = plan.evaluate(p, festival)
    by_n = {w["n"]: w for w in ev["chains"]}
    assert [w["n"] for w in ev["chains"]] == list(range(6))
    for n, fid in ((4, "0"), (5, "5")):
        w = by_n[n]
        assert w["links"][0]["conn"] == "wireless" and w["links"][0]["route"]["radio"] and not w["links"][0]["cables"]
        f = next(x for x in ev["fixtures"] if x["id"] == fid)
        rx_pt = w["points"][1]
        assert (rx_pt["x"], rx_pt["z"]) == (f["place"]["x"] + 300, f["place"]["z"])
        assert rx_pt["h"] == f["place"]["bottom"]          # hung with the fixture it feeds
        assert w["links"][1]["need_m"] <= 2            # a short cable from the receiver to the fixture
    tx_pt = by_n[3]["points"][1]                       # the transmitter stands by the splitter
    assert (tx_pt["x"], tx_pt["z"]) == (500, 700)
    assert by_n[4]["points"][0] == tx_pt and by_n[5]["points"][0] == tx_pt
    rxs = [u for u in ev["units"] if u["kind"] == "wireless_rx"]
    assert len(rxs) == 2 and {u["chain"] for u in rxs} == {5, 6}


def test_terminators_follow_the_radio_links(festival):
    p, tx, rx = radio_plan()
    ev = plan.evaluate(p, festival)
    by_n = {w["n"]: w for w in ev["chains"]}
    assert by_n[3]["terminator"] is None                # the transmitter ends its line
    assert not any(i["code"] == "C009" for i in by_n[3]["issues"])
    names = {f["id"]: f["name"] for f in ev["fixtures"]}
    assert by_n[4]["terminator"]["at"] == names["0"] and by_n[5]["terminator"]["at"] == names["5"]
    assert by_n[1]["terminator"]["at"] == names["4"]


def test_one_transmitter_many_receivers(festival):
    p, tx, rx = radio_plan(receivers=2)
    ev = plan.evaluate(p, festival)
    allis = ev["issues"] + [i for w in ev["chains"] for i in w["issues"]]
    assert not any(i["code"] == "C006" for i in allis)
    assert not any(i["code"] == "C005" and "receiver" in i["text"] for i in allis)
    bag = {b["what"]: b["count"] for b in outputs.pick_list(ev, p)["bag"]}
    assert bag["Wireless DMX receiver + power supply"] == 2
    p1, _, _ = radio_plan(receivers=1)                  # one receiver short: on the shopping list
    ev1 = plan.evaluate(p1, festival)
    assert any(i["code"] == "C005" and "uses 2" in i["text"] for i in ev1["issues"])
    assert {s["what"]: s["count"] for s in ev1["shopping"]}["Wireless DMX receiver"] == 1


def test_the_plot_and_the_load_in_show_the_radio(festival):
    p, tx, rx = radio_plan()
    ev = plan.evaluate(p, festival)
    svg = outputs.plot_svg(ev, p, plan.with_extras(festival, p))
    assert svg.count('<circle cx') and svg.count('r="250" fill="none" stroke="#7c3aed"') == 2 and ">RX<" in svg and ">TX<" in svg
    assert "By radio, no cable" in svg
    assert outputs.plot_pdf(ev, p, plan.with_extras(festival, p)).startswith(b"%PDF")
    steps = outputs.load_in(ev, p)
    assert sum(1 for s in steps if s.startswith("Wireless DMX receiver next to")) == 2
    assert any(s.startswith("Wireless DMX transmitter next to") for s in steps)


def test_wire_by_name_with_a_transmitter_as_source(festival):
    p, tx, rx = radio_plan()
    base = copy.deepcopy(p)
    base["chains"] = base["chains"][:4]
    new = plan.apply_wiring(base, festival, [{"from": tx, "port": 1, "devices": [f"item:{rx}", "0"]}], replace=False)
    assert new["chains"][-1]["source"] == {"item": tx, "port": 0}
    ev = plan.evaluate(new, festival)
    assert next(f for f in ev["fixtures"] if f["id"] == "0")["radio"]
