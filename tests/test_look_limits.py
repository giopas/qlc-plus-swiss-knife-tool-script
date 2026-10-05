"""v2.4.0 — whole-rig looks on fixtures without a dimmer; profile folder."""
import os
import pytest
import app

SCANNER = """<?xml version="1.0"?>
<FixtureDefinition xmlns="http://www.qlcplus.org/FixtureDefinition">
 <Manufacturer>Test</Manufacturer><Model>Scan</Model><Type>Scanner</Type>
 <Channel Name="Pan"><Group Byte="0">Pan</Group></Channel>
 <Channel Name="Tilt"><Group Byte="0">Tilt</Group></Channel>
 <Channel Name="Color"><Group Byte="0">Colour</Group>
  <Capability Min="0" Max="9">White</Capability>
  <Capability Min="10" Max="19">Red</Capability>
  <Capability Min="20" Max="29">Amber</Capability>
  <Capability Min="30" Max="39">Light Blue</Capability>
 </Channel>
 <Channel Name="Shutter"><Group Byte="0">Shutter</Group>
  <Capability Min="0" Max="9">Closed</Capability>
  <Capability Min="10" Max="255">Open</Capability>
 </Channel>
 <Mode Name="4ch"><Channel Number="0">Pan</Channel><Channel Number="1">Tilt</Channel>
  <Channel Number="2">Color</Channel><Channel Number="3">Shutter</Channel></Mode>
</FixtureDefinition>"""
PRESET_ONLY = SCANNER.replace("Scan<", "Plain<").replace(
    """<Group Byte="0">Colour</Group>
  <Capability Min="0" Max="9">White</Capability>
  <Capability Min="10" Max="19">Red</Capability>
  <Capability Min="20" Max="29">Amber</Capability>
  <Capability Min="30" Max="39">Light Blue</Capability>""", """<Group Byte="0">Colour</Group>""").replace(
    """<Group Byte="0">Shutter</Group>
  <Capability Min="0" Max="9">Closed</Capability>
  <Capability Min="10" Max="255">Open</Capability>""", """<Group Byte="0">Gobo</Group>""")


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_PROFILES", str(tmp_path / "profiles"))
    cl = app.create_app().test_client()
    cl.tmp = tmp_path
    cl.post("/api/quickstart/clear")
    return cl


def _add(c, text, model):
    f = c.tmp / f"{model}.qxf"
    f.write_text(text)
    d = c.post("/api/quickstart/load-qxf", json={"path": str(f)}).get_json()["definition"]
    key = d.get("key") or f"{d['manufacturer']}::{d['model']}"
    assert c.post("/api/quickstart/add-fixture", json={"key": key, "quantity": 1}).status_code < 300
    c.post("/api/quickstart/auto-dmx")


def test_wheel_slots_make_the_looks_differ(c):
    _add(c, SCANNER, "Scan")
    st = c.get("/api/quickstart/status").get_json()
    assert st["look_limits"] == []
    from routes import quick_start_routes as qs
    gen = qs._make_generator()[1]
    assert gen._light(0, (255, 255, 255)) == {2: 4}          # White slot
    assert gen._light(0, (255, 160, 60)) == {2: 24}          # Amber
    assert gen._light(0, (200, 220, 255)) == {2: 34}         # Light Blue
    assert gen._dark(0) == {3: 0}                            # shutter closed


def test_fixture_that_cannot_make_a_look_is_reported(c):
    _add(c, PRESET_ONLY, "Plain")
    st = c.get("/api/quickstart/status").get_json()
    assert len(st["look_limits"]) == 1 and "will look the same" in st["look_limits"][0]


def test_profile_folder_route(c):
    d = c.get("/api/profile/folder").get_json()
    assert d["path"] == str(c.tmp / "profiles")
