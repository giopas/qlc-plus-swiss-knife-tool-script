"""v2.5.0 — Look Builder: beats tempo, moving-head positions, own palettes, pixel-bar matrices."""
import copy
import os
import xml.etree.ElementTree as ET

import pytest

import app
from core import look_builder as lb, qxw_io
from core.doctor import check, load_qxf_defs
from core.qxf_parser import parse_qxf

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
DEFS = load_qxf_defs([CORPUS, FIX])
QS_CLUB = os.path.join(CORPUS, "QuickStart_club.qxw")      # 2 × Spot 110 (pan/tilt) + 4 × SlimPAR 56

BAR = """<?xml version="1.0"?>
<FixtureDefinition xmlns="http://www.qlcplus.org/FixtureDefinition">
 <Manufacturer>Test</Manufacturer><Model>PixBar</Model><Type>LED Bar (Pixels)</Type>
 <Channel Name="Master Dimmer"><Group Byte="0">Intensity</Group><Capability Min="0" Max="255">Dimmer</Capability></Channel>
 <Channel Name="Red 1"><Group Byte="0">Intensity</Group><Colour>Red</Colour><Capability Min="0" Max="255">Red</Capability></Channel>
 <Channel Name="Green 1"><Group Byte="0">Intensity</Group><Colour>Green</Colour><Capability Min="0" Max="255">Green</Capability></Channel>
 <Channel Name="Blue 1"><Group Byte="0">Intensity</Group><Colour>Blue</Colour><Capability Min="0" Max="255">Blue</Capability></Channel>
 <Channel Name="Red 2"><Group Byte="0">Intensity</Group><Colour>Red</Colour><Capability Min="0" Max="255">Red</Capability></Channel>
 <Channel Name="Green 2"><Group Byte="0">Intensity</Group><Colour>Green</Colour><Capability Min="0" Max="255">Green</Capability></Channel>
 <Channel Name="Blue 2"><Group Byte="0">Intensity</Group><Colour>Blue</Colour><Capability Min="0" Max="255">Blue</Capability></Channel>
 <Mode Name="7ch">
  <Channel Number="0">Master Dimmer</Channel><Channel Number="1">Red 1</Channel><Channel Number="2">Green 1</Channel>
  <Channel Number="3">Blue 1</Channel><Channel Number="4">Red 2</Channel><Channel Number="5">Green 2</Channel>
  <Channel Number="6">Blue 2</Channel>
  <Head><Channel>1</Channel><Channel>2</Channel><Channel>3</Channel></Head>
  <Head><Channel>4</Channel><Channel>5</Channel><Channel>6</Channel></Head>
 </Mode>
 <Physical><Focus Type="Fixed" PanMax="0" TiltMax="0"/></Physical>
</FixtureDefinition>"""

WS = """<?xml version="1.0"?>
<Workspace xmlns="http://www.qlcplus.org/Workspace"><Engine>
<Fixture><Manufacturer>Test</Manufacturer><Model>PixBar</Model><Mode>7ch</Mode><ID>0</ID><Name>Bar 1</Name><Universe>0</Universe><Address>0</Address><Channels>7</Channels></Fixture>
<Fixture><Manufacturer>Test</Manufacturer><Model>PixBar</Model><Mode>7ch</Mode><ID>1</ID><Name>Bar 2</Name><Universe>0</Universe><Address>7</Address><Channels>7</Channels></Fixture>
</Engine><VirtualConsole/></Workspace>"""


@pytest.fixture
def bars(tmp_path):
    q = tmp_path / "Test-PixBar.qxf"
    q.write_text(BAR)
    w = tmp_path / "bars.qxw"
    w.write_text(WS)
    defs = load_qxf_defs([str(tmp_path)])
    return qxw_io.load_qxw(str(w)).getroot(), defs


def _root(p=QS_CLUB):
    return qxw_io.load_qxw(p).getroot()


def _fns(root, t=None):
    return [f for f in root.find("Engine").findall("Function") if t is None or f.get("Type") == t]


# ── beats tempo ──────────────────────────────────────────────────────────────

def test_beats_chaser_is_stored_in_thousandths_of_a_beat():
    gid = next(g["id"] for g in lb.groups(_root(), DEFS) if g["id"] != "all")
    plan = {"chasers": [{"group": gid, "pattern": "chase", "tempo": "beats", "note": "1/8",
                         "fade": "fade", "fade_pct": 50, "colours": ["Red"]}]}
    r = lb.build(_root(), DEFS, plan)
    ch = _fns(r["root"], "Chaser")[-1]
    assert ch.findtext("TempoType") == "Beats"
    sp = ch.find("Speed")
    assert sp.get("Duration") == "500" and sp.get("FadeIn") == "250"      # 1/8 = half a beat, fade 50 %
    st = ch.find("Step")
    assert (st.get("Hold"), st.get("FadeIn")) == ("250", "250")
    assert "follows the QLC+ tempo" in " ".join(r["log"])
    assert not check(r["root"], DEFS).errors


def test_time_chaser_is_unchanged():
    gid = next(g["id"] for g in lb.groups(_root(), DEFS) if g["id"] != "all")
    r = lb.build(_root(), DEFS, {"chasers": [{"group": gid, "pattern": "chase", "bpm": 120, "colours": ["Red"]}]})
    ch = _fns(r["root"], "Chaser")[-1]
    assert ch.find("TempoType") is None and ch.find("Speed").get("Duration") == "500"


# ── positions ────────────────────────────────────────────────────────────────

def test_position_aims_moving_heads_and_names_the_look():
    r = lb.build(_root(), DEFS, {"looks": [{"group": "all", "colours": ["Red"], "position": "Left"}]})
    sc = _fns(r["root"], "Scene")[-1]
    assert "@ Left" in sc.get("Name")
    # fixture 0 is a Spot 110: pan is channel 0 at 30 % of the range, tilt 50 %
    fv = next(v for v in sc.findall("FixtureVal") if v.get("ID") == "0")
    vals = [int(x) for x in fv.text.split(",")]
    d = dict(zip(vals[0::2], vals[1::2]))
    assert abs(d[0] - round(0.3 * 255)) <= 1 and abs(d[1] - 127) <= 1
    assert "position Left" in " ".join(r["log"])


def test_position_validation():
    assert lb.position("left")["pan"] == 30
    assert lb.position({"pan": 10, "tilt": 90})["name"] == "Pan 10% Tilt 90%"
    assert lb.position(None) is None
    for bad in ("sideways", {"pan": 120, "tilt": 0}, {"pan": "x", "tilt": 1}):
        with pytest.raises(ValueError):
            lb.position(bad)


def test_fixtures_without_pan_tilt_ignore_the_position():
    a = lb.build(_root(), DEFS, {"looks": [{"group": "1", "colours": ["Red"]}]})        # the 4 PARs
    b = lb.build(_root(), DEFS, {"looks": [{"group": "1", "colours": ["Red"], "position": "Right"}]})
    fa, fb = _fns(a["root"], "Scene")[-1], _fns(b["root"], "Scene")[-1]
    assert [v.text for v in fa.findall("FixtureVal")] == [v.text for v in fb.findall("FixtureVal")]


# ── own palettes ─────────────────────────────────────────────────────────────

def test_own_palettes_are_saved_listed_and_deleted():
    lb.save_palette("Pub night", [{"name": "Pub Red", "hex": "#CC0000"}, "Amber"])
    p = lb.palettes()
    assert p["own:Pub night"]["builtin"] is False and p["warm"]["builtin"] is True
    assert [c["name"] for c in p["own:Pub night"]["colours"]] == ["Pub Red", "Amber"]
    assert lb.colour("Pub Red")["hex"] == "#CC0000"
    with pytest.raises(ValueError):
        lb.save_palette("warm", ["Red"])
    with pytest.raises(ValueError):
        lb.save_palette("", ["Red"])
    assert lb.delete_palette("pub night") and "own:Pub night" not in lb.palettes()
    assert not lb.delete_palette("pub night")


def test_palette_routes():
    c = app.create_app().test_client()
    r = c.post("/api/looks/palettes", json={"name": "X", "colours": [{"name": "C", "hex": "#112233"}]})
    assert r.status_code == 200 and "own:X" in r.get_json()["palettes"]
    assert c.post("/api/looks/palettes/delete", json={"name": "X"}).status_code == 200
    assert c.post("/api/looks/palettes/delete", json={"name": "X"}).status_code == 404


# ── pixel-bar matrices ───────────────────────────────────────────────────────

def test_qxf_parser_reads_heads(bars):
    root, defs = bars
    d = next(iter(defs.values()))
    assert d["mode_heads"]["7ch"] == [[1, 2, 3], [4, 5, 6]]
    assert [b["heads"] for b in lb.pixel_bars(root, defs)] == [2, 2]


def test_matrix_pattern_on_two_bars(bars):
    root, defs = bars
    plan = {"matrices": [{"fixtures": ["0", "1"], "pattern": "Stripes", "colours": ["Red", "Blue"], "duration": 700}],
            "vc_page": "FX"}
    res = lb.run(root, defs, plan)
    assert not res["blocked"], res["doctor"]
    w = res["root"]
    eng = w.find("Engine")
    g = eng.find("FixtureGroup")
    assert g.find("Size").attrib == {"X": "2", "Y": "2"} and len(g.findall("Head")) == 4
    assert [(h.get("X"), h.get("Y"), h.get("Fixture"), h.text) for h in g.findall("Head")][:3] == \
        [("0", "0", "0", "0"), ("1", "0", "0", "1"), ("0", "1", "1", "0")]
    m = _fns(w, "RGBMatrix")[0]
    assert m.findtext("Algorithm") == "Stripes" and m.find("Speed").get("Duration") == "700"
    assert m.findtext("FixtureGroup") == g.get("ID")
    assert {(p.get("Name"), p.get("Value")) for p in m.findall("Property")} == {("orientation", "Horizontal")}
    coll = _fns(w, "Collection")[0]                                  # dimmers opened by the button
    assert [s.text for s in coll.findall("Step")] == [_fns(w, "Scene")[0].get("ID"), m.get("ID")]
    btn = next(b for b in w.find("VirtualConsole").iter("Button"))
    assert btn.find("Function").get("ID") == coll.get("ID")
    assert res["created"]["matrices"] == 1


def test_matrix_needs_a_pixel_bar(bars):
    root, defs = bars
    with pytest.raises(ValueError):
        lb.build(root, defs, {"matrices": [{"fixtures": ["99"], "pattern": "Chase"}]})
    with pytest.raises(ValueError):
        lb.build(root, defs, {"matrices": [{"fixtures": ["0"], "pattern": "Nope"}]})


def test_options_route_lists_the_new_things():
    c = app.create_app().test_client()
    c.post("/api/load", json={"path": QS_CLUB})
    d = c.get("/api/looks/options").get_json()
    assert [p["name"] for p in d["positions"]][:2] == ["Centre", "Left"]
    assert "Stripes" in [m["name"] for m in d["matrix_patterns"]] and d["pixel_bars"] == []
