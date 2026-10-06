"""v2.6.0 — Inputs & MIDI: patch, re-patch, simulate, controllers."""
import copy
import xml.etree.ElementTree as ET

import pytest

import app
from core import input_manager as im, qxw_io

XML = """<Workspace><Engine>
<InputOutputMap>
 <Universe Name="Universe 1" ID="0"><Output Plugin="DMX USB" Line="0"/><Input Plugin="MIDI" Name="BCF2000" UID="BCF2000" Line="0" Profile="Behringer BCF2000"/></Universe>
 <Universe Name="Universe 2" ID="1"><Output Plugin="Dummy" Line="0"/></Universe>
</InputOutputMap>
<Function ID="0" Type="Scene" Name="Red"/><Function ID="1" Type="Scene" Name="Blue"/>
</Engine>
<VirtualConsole><Frame Caption="Main" ID="0">
 <Button Caption="Red" ID="1"><Function ID="0"/><Input Universe="0" Channel="130"/></Button>
 <Button Caption="Blue" ID="2"><Function ID="1"/><Input Universe="1" Channel="130"/></Button>
 <Button Caption="Other" ID="3"><Function ID="1"/><Input Universe="1" Channel="5"/></Button>
 <Button Caption="Omni" ID="4"><Function ID="0"/><Input Universe="0" Channel="4226"/></Button>
</Frame></VirtualConsole></Workspace>"""


@pytest.fixture(autouse=True)
def _ctl(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_CONTROLLERS", str(tmp_path / "ctl.json"))


def root():
    return ET.fromstring(XML)


def test_encode_decode():
    assert im.encode("note", 60) == 188 and im.encode("cc", 7) == 7
    assert im.encode("program", 3) == 387 and im.encode("pitch") == 513
    assert im.encode("note", 2, midi_channel=2) == 4096 + 130
    d = im.decode(188)
    assert d["kind"] == "note" and d["number"] == 60 and "C4" in d["text"]
    d = im.decode(4096 + 130)
    assert d["midi_channel"] == 2 and d["number"] == 2
    assert im.decode(7)["text"].startswith("Control change 7")
    with pytest.raises(im.InputError):
        im.encode("note", 200)
    with pytest.raises(im.InputError):
        im.encode("bogus", 1)


def test_universes_status():
    u = {x["id"]: x for x in im.universes(root())}
    assert u["0"]["status"] == "ok" and u["0"]["input"]["profile"] == "Behringer BCF2000"
    assert u["1"]["status"] == "no_input" and u["1"]["bindings"] == 2


def test_set_and_clear_input():
    r = root()
    im.set_input(r, "1", plugin="MIDI", device="BCF2000", line=0, profile="Behringer BCF2000", feedback=True)
    u = {x["id"]: x for x in im.universes(r)}["1"]
    assert u["status"] == "ok" and u["feedback"]["device"] == "BCF2000"
    ET.indent(r)
    # QLC+ order: Input before Output
    uni = r.find("Engine/InputOutputMap/Universe[@ID='1']")
    assert [c.tag for c in uni] == ["Input", "Output", "Feedback"]
    im.clear_input(r, "1")
    assert {x["id"]: x for x in im.universes(r)}["1"]["status"] == "no_input"
    with pytest.raises(im.InputError):
        im.set_input(r, "1", device="")
    im.set_input(r, "4", device="X")                                # a new universe is created
    assert any(x["id"] == "4" for x in im.universes(r))


def test_move_and_swap():
    r = root()
    res = im.move_bindings(r, "1", "2", shift=1)
    assert res["moved"] == 2
    chans = sorted((e.get("Universe"), e.get("Channel")) for e in r.iter("Input") if e.get("Channel"))
    assert ("2", "131") in chans and ("2", "6") in chans
    r = root()
    with pytest.raises(im.InputError):
        im.move_bindings(r, "1", "0")                               # 130 already bound on U0 -> clash
    with pytest.raises(im.InputError):
        im.move_bindings(r, "5", "0")                               # nothing there
    r = root()
    im.swap_universes(r, "0", "1")
    byid = {w["id"]: w["bindings"][0]["universe"] for w in im.widgets_with_input(r)}
    assert byid == {"1": "1", "2": "0", "3": "0", "4": "1"}


def test_simulate():
    r = root()
    s = im.simulate(r, "0", im.encode("note", 2))
    assert [h["caption"] for h in s["hits"]] == ["Red"] and s["hits"][0]["function"] == "Red"
    s = im.simulate(r, "0", im.encode("note", 2, midi_channel=3))   # omni on another channel
    assert not s["hits"] and s["near"] and any("another MIDI channel" in n for n in s["notes"])
    s = im.simulate(r, "1", im.encode("note", 2))
    assert s["hits"] and any("no input device" in n for n in s["notes"])
    s = im.simulate(r, "0", 99)
    assert not s["hits"] and any("Nothing" in n for n in s["notes"])


def test_controllers_roundtrip():
    assert im.controllers() == []
    im.remember_controller("Stage BCF", device="BCF2000", profile="Behringer BCF2000")
    im.remember_controller("Stage BCF", device="BCF2000 v2")        # same name replaces
    c = im.controllers()
    assert len(c) == 1 and c[0]["device"] == "BCF2000 v2"
    with pytest.raises(im.InputError):
        im.remember_controller("", device="x")
    assert im.forget_controller("stage bcf") == []


def test_profiles(tmp_path):
    (tmp_path / "a.qxi").write_text("<InputProfile><Manufacturer>Behringer</Manufacturer><Model>BCF2000</Model></InputProfile>")
    (tmp_path / "bad.qxi").write_text("not xml")
    assert im.profiles([str(tmp_path)]) == ["Behringer BCF2000"]


def test_routes_on_show_in_progress(tmp_path):
    from core import workspace
    p = tmp_path / "s.qxw"
    p.write_text('<?xml version="1.0"?>\n<!DOCTYPE Workspace>\n<Workspace xmlns="http://www.qlcplus.org/Workspace">'
                 + XML[len("<Workspace>"):], encoding="utf-8")
    workspace.load_qxw(str(p))
    c = app.create_app().test_client()
    st = c.get("/api/inputs/state").get_json()
    assert {u["id"]: u["status"] for u in st["universes"]} == {"0": "ok", "1": "no_input"}
    r = c.post("/api/inputs/op", json={"op": "set_input", "universe": "1", "device": "BCF2000",
                                        "profile": "Behringer BCF2000", "feedback": True})
    assert r.status_code == 200
    assert {u["id"]: u["status"] for u in r.get_json()["universes"]} == {"0": "ok", "1": "ok"}
    r = c.post("/api/inputs/op", json={"op": "move", "src": "1", "dst": "2"})
    assert r.status_code == 200 and r.get_json()["message"].startswith("2 binding")
    sim = c.post("/api/inputs/simulate", json={"universe": "2", "kind": "note", "number": 2}).get_json()
    assert [h["caption"] for h in sim["hits"]] == ["Blue"]
    assert c.post("/api/inputs/op", json={"op": "move", "src": "9", "dst": "0"}).status_code == 400
    assert c.post("/api/inputs/op", json={"op": "nope"}).status_code == 400
    assert c.get("/api/inputs/decode", query_string={"channel": "188"}).get_json()["kind"] == "note"


# ── the three real forms QLC+ writes (from giopas's shows) ──────────────────

def _show(inp_xml: str, tmp_path, name="s.qxw"):
    p = tmp_path / name
    p.write_text('<?xml version="1.0"?>\n<!DOCTYPE Workspace>\n<Workspace xmlns="http://www.qlcplus.org/Workspace"><Engine>'
                 '<InputOutputMap><Universe Name="Universe 1" ID="0"><Output Plugin="DMX USB" Line="0"/></Universe>'
                 f'<Universe Name="Universe 2" ID="1">{inp_xml}</Universe></InputOutputMap></Engine>'
                 '<VirtualConsole><Frame Caption="P" ID="0"><Button Caption="B" ID="1"><Function ID="0"/>'
                 '<Input ID="0" Universe="1" Channel="20"/></Button></Frame></VirtualConsole></Workspace>', encoding="utf-8")
    return str(p)


GOOD = '<Input Plugin="MIDI" Name="SINCO" UID="528145425" Line="0"><PluginParameters mode="Program Change"/></Input>'
OLD = '<Input Plugin="MIDI" UID="SINCO" Line="0"/>'
NONE = '<Input Plugin="MIDI" Name="None" UID="None" Line="0"/>'


def _unis(path):
    r = qxw_io.strip_ns(qxw_io.load_qxw(path).getroot())
    return r, {u["id"]: u for u in im.universes(r)}


def test_real_forms_are_read(tmp_path):
    _, u = _unis(_show(GOOD, tmp_path))
    assert u["1"]["status"] == "ok" and u["1"]["input"]["device"] == "SINCO"
    assert u["1"]["input"]["uid"] == "528145425" and u["1"]["input"]["mode"] == "Program Change"
    _, u = _unis(_show(OLD, tmp_path, "old.qxw"))
    assert u["1"]["status"] == "ok" and u["1"]["input"]["device"] == "SINCO"      # QLC+ 5.2.1: UID is the name
    _, u = _unis(_show(NONE, tmp_path, "none.qxw"))
    assert u["1"]["status"] == "no_input" and u["1"]["bindings"] == 1             # the "saved as None" case


def test_learn_then_repair_a_none_show(tmp_path):
    good, bad = _show(GOOD, tmp_path, "good.qxw"), _show(NONE, tmp_path, "bad.qxw")
    assert im.learn_from_file(bad) == []                                          # nothing to learn from None
    found = im.learn_from_file(good)
    assert found[0]["device"] == "SINCO" and found[0]["uid"] == "528145425" and found[0]["mode"] == "Program Change"
    c = im.controllers()[0]
    assert c["uid"] == "528145425"
    r, _ = _unis(bad)
    im.set_input(r, "1", plugin=c["plugin"], device=c["device"], line=c["line"], profile=c["profile"],
                 device_uid=c["uid"], mode=c["mode"])
    inp = r.find("Engine/InputOutputMap/Universe[@ID='1']/Input")
    assert inp.get("Name") == "SINCO" and inp.get("UID") == "528145425"
    assert inp.find("PluginParameters").get("mode") == "Program Change"
    assert {x["id"]: x for x in im.universes(r)}["1"]["status"] == "ok"


def test_uid_rules(tmp_path):
    r, _ = _unis(_show(GOOD, tmp_path))
    im.set_input(r, "1", device="SINCO", line=0)                                  # same device again: keeps the real UID and the mode
    inp = r.find("Engine/InputOutputMap/Universe[@ID='1']/Input")
    assert inp.get("UID") == "528145425" and inp.find("PluginParameters").get("mode") == "Program Change"
    im.set_input(r, "0", device="Other", line=0)                                  # unknown device: the name (the 5.2.1 form)
    assert r.find("Engine/InputOutputMap/Universe[@ID='0']/Input").get("UID") == "Other"
    # bindings keep their slot ID when moved
    im.move_bindings(r, "1", "0")
    b = r.find(".//Button/Input")
    assert b.get("ID") == "0" and b.get("Universe") == "0" and b.get("Channel") == "20"


def test_simulate_warns_about_the_line_mode(tmp_path):
    r, _ = _unis(_show(GOOD, tmp_path))
    s = im.simulate(r, "1", 20)
    assert [h["caption"] for h in s["hits"]] == ["B"]
    assert any("Program Change' mode" in n for n in s["notes"])
