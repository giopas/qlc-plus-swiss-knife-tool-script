"""3.11.0 Brightness: room to go brighter, earlier changes (read from the
recipes next to each version), values cut at full, fixture groups."""
import json
import os
import shutil

import pytest

import app
from core import brightness

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")) and " 2." not in f:
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    shutil.copy(tmp_path / "Festival_14fix.qxw", tmp_path / "Gig_v1.qxw")
    client = app.create_app().test_client()
    client.tmp = tmp_path
    r = client.post("/api/load", json={"path": str(tmp_path / "Gig_v1.qxw")})
    assert r.status_code < 300
    return client


def _dimmable(c):
    fx = [f for f in c.get("/api/brightness/fixtures").get_json() if f.get("dimmer_offset") is not None]
    assert fx
    return fx


def test_baseline_says_the_room(c):
    rows = {b["id"]: b for b in c.get("/api/brightness/baseline").get_json()}
    for f in _dimmable(c):
        b = rows[f["id"]]
        if b["peak"]:
            assert b["room_pct"] == round(255 / b["peak"] * 100)
            assert b["at_full"] >= 0


def test_preview_counts_values_cut_at_full(c):
    f = _dimmable(c)[0]
    hi = c.post("/api/brightness/preview", json={"scales": {f["id"]: 2.0}}).get_json()
    lo = c.post("/api/brightness/preview", json={"scales": {f["id"]: 0.9}}).get_json()
    assert hi["clipped"] > 0 and lo["clipped"] == 0


def test_no_history_for_a_file_without_recipe(c):
    h = c.get("/api/brightness/history").get_json()
    assert h["changes"] == [] and h["session"] == {} and h["ends"] == "no_recipe"


def test_history_follows_the_recipes_back(c):
    f = _dimmable(c)[0]
    r = c.post("/api/brightness/apply-show", json={"scales": {f["id"]: 0.75}})
    assert r.status_code == 200, r.get_json()
    assert c.get("/api/brightness/history").get_json()["session"] == {f["id"]: 0.75}
    out = str(c.tmp / "Gig_v2.qxw")
    assert c.post("/api/show/save", json={"path": out}).status_code == 200
    assert os.path.isfile(c.tmp / "Gig_v2.recipe.json")
    c.post("/api/load", json={"path": out})
    h = c.get("/api/brightness/history").get_json()
    assert [x["file"] for x in h["changes"]] == ["Gig_v2.qxw"]
    assert h["changes"][0]["made_from"] == "Gig_v1.qxw"
    assert h["total"] == {f["id"]: 0.75}
    assert h["edited_after"] is False
    # a second round from v2 multiplies
    c.post("/api/brightness/apply-show", json={"scales": {f["id"]: 0.8}})
    c.post("/api/show/save", json={"path": str(c.tmp / "Gig_v3.qxw")})
    c.post("/api/load", json={"path": str(c.tmp / "Gig_v3.qxw")})
    h = c.get("/api/brightness/history").get_json()
    assert [x["file"] for x in h["changes"]] == ["Gig_v3.qxw", "Gig_v2.qxw"]
    assert h["total"][f["id"]] == pytest.approx(0.6)


def test_history_sees_a_file_changed_after_saving(c):
    f = _dimmable(c)[0]
    c.post("/api/brightness/apply-show", json={"scales": {f["id"]: 0.5}})
    out = c.tmp / "Gig_v2.qxw"
    c.post("/api/show/save", json={"path": str(out)})
    with open(out, "a", encoding="utf-8") as fh:
        fh.write("\n")
    c.post("/api/load", json={"path": str(out)})
    assert c.get("/api/brightness/history").get_json()["edited_after"] is True


def test_undo_takes_a_change_back():
    calls = [{"method": "POST", "path": "/api/brightness/apply-show", "body": {"scales": {"1": 0.5}}},
             {"method": "POST", "path": "/api/show/undo", "body": {}}]
    assert brightness._live_scales(calls) == ({}, True)
    calls.append({"method": "POST", "path": "/api/show/redo", "body": {}})
    assert brightness._live_scales(calls)[0] == {"1": 0.5}
    calls.append({"method": "POST", "path": "/api/show/travel", "body": {}})
    assert brightness._live_scales(calls)[1] is False


def test_history_stops_at_a_loop(tmp_path):
    (tmp_path / "A.qxw").write_text("x")
    (tmp_path / "A.recipe.json").write_text(json.dumps({"source": {"name": "A.qxw"}, "calls": []}))
    h = brightness.history(str(tmp_path / "A.qxw"))
    assert h["ends"] == "start" and h["checked"] == ["A.qxw"]


def test_groups_route(c):
    g = c.get("/api/brightness/groups").get_json()
    assert isinstance(g, list)
    for x in g:
        assert set(x) == {"id", "name", "fixtures"}
