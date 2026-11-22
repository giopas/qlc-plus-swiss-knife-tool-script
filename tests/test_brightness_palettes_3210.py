"""3.21.0 Brightness and QLC+ palette looks: the looks that take their dimmer
from a Dimmer palette are shown, and can follow the sliders (the palette
scaled, or a scaled copy when other lights share it)."""
import os
import re
import shutil

import pytest

import app
from core import palettes as P
from core import qxw_io

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
WASH = ["0", "1", "2", "3"]          # the four MHL-74 washes of Wizard530_small


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")) and " 2." not in f:
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    r = client.post("/api/load", json={"path": str(tmp_path / "Wizard530_small.qxw")})
    assert r.status_code < 300
    return client


def _dimmers(xml: bytes):
    return {m.group(2): int(m.group(3)) for m in re.finditer(
        r'<Palette ID="(\d+)" Type="Dimmer" Name="([^"]+)" Value="(\d+)"', xml.decode("utf-8"))}


def test_preview_lists_the_palette_looks(c):
    pl = c.post("/api/brightness/preview", json={"scales": {f: 0.7 for f in WASH}}).get_json()["palette_looks"]
    assert pl["scenes"] > 0
    names = {p["name"] for p in pl["palettes"]}
    assert "Dimmer Full" in names and "Dimmer Off" not in names
    full = next(p for p in pl["palettes"] if p["name"] == "Dimmer Full")
    assert full["new_values"] == [178] and full["in_place"] is False   # other lights share it


def test_no_palette_looks_at_100(c):
    pl = c.post("/api/brightness/preview", json={"scales": {f: 1.0 for f in WASH}}).get_json()["palette_looks"]
    assert pl["scenes"] == 0 and pl["palettes"] == []


def test_left_alone_without_the_option(c):
    r = c.post("/api/brightness/apply", json={"scales": {f: 0.7 for f in WASH}})
    assert r.status_code == 200
    d = _dimmers(r.data)
    assert d == {"Dimmer Full": 255, "Dimmer Half": 128, "Dimmer Off": 0}


def test_shared_palette_gets_a_scaled_copy(c):
    r = c.post("/api/brightness/apply", json={"scales": {f: 0.7 for f in WASH}, "scale_palettes": True})
    assert r.status_code == 200
    d = _dimmers(r.data)
    assert d["Dimmer Full"] == 255 and d["Dimmer Full 70%"] == 178
    assert d["Dimmer Half 70%"] == 90 and d["Dimmer Off"] == 0
    root = qxw_io.loads_qxw(r.data)
    pals = P.read_palettes(root)
    groups = P.groups_by_id(root)
    copy_id = next(k for k, v in pals.items() if v.name == "Dimmer Full 70%")
    for fn in P._children(P._engine(root), "Function"):
        if copy_id in P.scene_palettes(fn):
            fx = {f for g in P.scene_groups(fn) for f in P.group_fixture_ids(groups[g])}
            assert fx and fx <= set(WASH) | {"4", "5", "6", "7"}   # only wash looks (bars have no dimmer)
    assert not any(p.get("ID") == copy_id for p in P._children(P._engine(root), "Palette")
                   if p.get("Name") == "Dimmer Full")


def test_every_light_scaled_scales_the_palette_itself(c):
    fx = [f["id"] for f in c.get("/api/brightness/fixtures").get_json() if f.get("dimmer_offset") is not None]
    r = c.post("/api/brightness/apply", json={"scales": {f: 0.5 for f in fx}, "scale_palettes": True})
    d = _dimmers(r.data)
    assert d == {"Dimmer Full": 128, "Dimmer Half": 64, "Dimmer Off": 0}


def test_apply_to_the_show_says_what_followed(c):
    r = c.post("/api/brightness/apply-show", json={"scales": {f: 0.7 for f in WASH}, "scale_palettes": True})
    assert r.status_code == 200, r.get_json()
    assert "palette look" in r.get_json()["step"]["detail"]


def test_doctor_finds_no_broken_palette_reference(c):
    r = c.post("/api/brightness/apply-show", json={"scales": {f: 0.7 for f in WASH}, "scale_palettes": True})
    doctor = r.get_json()["show"]["doctor"]
    assert doctor["error"] == 0 and "D019" not in doctor["rules"]


def test_a_limit_names_the_copy_and_caps_the_value(c):
    r = c.post("/api/brightness/apply", json={"scales": {}, "caps": {f: 60 for f in WASH}, "scale_palettes": True})
    assert r.status_code == 200, r.get_json()
    d = _dimmers(r.data)
    assert d["Dimmer Full limit 60%"] == 153          # 60% of 255
    assert "Dimmer Half limit 60%" not in d            # 128 is already under the limit
