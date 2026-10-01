"""2.9 — the recipe: every change recorded, replayed to the same .qxw
(core/recipe.py, `python -m core.recipe`)."""
import json
import os
import shutil

import pytest

import app
from core import porter, recipe

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
LOOKS = {"looks": [{"group": "all", "colours": ["Amber", "Blue"]}],
         "chasers": [{"group": "all", "pattern": "pingpong", "colours": ["Red"], "bpm": 120,
                      "note": "1/8", "fade": "fade", "fade_pct": 50, "name": "Sweep"}],
         "vc_page": "Looks"}


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
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


def _keys(c):
    return [f["key"] for f in c.get("/api/doctor/check").get_json()["findings"] if f["default"]]


def _save_and_replay(c, name="Out_v2.qxw", **kw):
    out = c.tmp / name
    d = _ok(c.post("/api/show/save", json={"path": str(out)})).get_json()
    assert d["recipe_name"] == name.replace(".qxw", ".recipe.json")
    rec = json.load(open(d["recipe_path"], encoding="utf-8"))
    res = recipe.replay(rec, recipe_dir=str(c.tmp), **kw)
    return rec, res


def test_the_pub_route_replays_to_the_same_file(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    keep = ["6", "7", "8", "9", "11", "12"]
    _ok(c.post("/api/reducer/apply", json={"keep": keep, "repatch": {"6": {"name": "DR: Drums"}}}))
    _ok(c.post("/api/doctor/apply", json={"keys": _keys(c)}))
    for name, fx in (("Singer Pair", ["12", "11"]), ("Band Pair", ["7", "8"])):
        _ok(c.post("/api/stage/op", json={"op": "group_new", "name": name, "fixtures": fx}))
    _ok(c.post("/api/looks/apply", json=LOOKS))
    _ok(c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra"}))
    _ok(c.post("/api/brightness/apply-show", json={"scales": {"1": 0.8}}))
    _ok(c.post("/api/show/undo", json={"n": 1}))            # undo is part of the recipe
    rec, res = _save_and_replay(c)
    assert [x["path"] for x in rec["calls"]][:2] == ["/api/reducer/apply", "/api/doctor/apply"]
    assert "/api/show/undo" in [x["path"] for x in rec["calls"]]
    assert res["identical"], res


def test_porter_with_another_show_as_input(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    fns = [f for f in porter.list_source_functions() if f["type"] == "Scene"][:3]
    cl = porter.resolve_closure([f["id"] for f in fns])
    plan = dict(closure=cl, fixture_mapping=porter.auto_map(cl["fixture_ids"], "fan_in"),
                fanout_mode="fan_in", drop_unmapped=True)
    _ok(c.post("/api/porter/apply", json=plan))
    rec, res = _save_and_replay(c)
    assert [i["name"] for i in rec["inputs"]] == ["Festival_14fix.qxw"]
    assert res["identical"], res


def test_inputs_are_found_next_to_the_recipe_elsewhere(c, tmp_path_factory):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    fns = [f for f in porter.list_source_functions() if f["type"] == "Scene"][:2]
    cl = porter.resolve_closure([f["id"] for f in fns])
    _ok(c.post("/api/porter/apply", json=dict(closure=cl, fanout_mode="fan_in", drop_unmapped=True,
                                              fixture_mapping=porter.auto_map(cl["fixture_ids"], "fan_in"))))
    out = c.tmp / "Moved_v2.qxw"
    d = _ok(c.post("/api/show/save", json={"path": str(out)})).get_json()
    # another computer: everything in one new folder, other paths gone
    there = tmp_path_factory.mktemp("elsewhere")
    for f in os.listdir(c.tmp):
        if f.endswith((".qxf", ".qxw", ".json")) and f != "p.json":
            shutil.copy(c.tmp / f, there / f)
    rec = json.load(open(there / "Moved_v2.recipe.json", encoding="utf-8"))
    for f in ("Pub_6fix.qxw", "Festival_14fix.qxw"):
        os.remove(c.tmp / f)
    res = recipe.replay(rec, recipe_dir=str(there))
    assert res["identical"], res
    assert d["recipe_path"]


def test_missing_input_is_named(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/brightness/apply-show", json={"scales": {"6": 0.5}}))
    out = c.tmp / "B_v2.qxw"
    d = _ok(c.post("/api/show/save", json={"path": str(out)})).get_json()
    rec = json.load(open(d["recipe_path"], encoding="utf-8"))
    rec["inputs"] = [{"path": "/nowhere/Setlist.txt", "name": "Setlist.txt", "sha256": "x"}]
    with pytest.raises(recipe.ReplayError, match="Setlist.txt"):
        recipe.replay(rec, recipe_dir=str(c.tmp))


def test_reads_and_exports_are_not_recorded():
    assert recipe.recordable("POST", "/api/reducer/apply")
    assert recipe.recordable("PATCH", "/api/triggers/abc")
    assert recipe.recordable("POST", "/api/stage/op")
    for p in ("/api/reducer/preview", "/api/show/save", "/api/porter/execute", "/api/compare/run",
              "/api/showbook/export/pdf", "/api/picker/pick", "/api/looks/build", "/api/doctor/fix"):
        assert not recipe.recordable("POST", p), p
    assert not recipe.recordable("GET", "/api/show/status")


def test_cli_replay(c, capsys):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/brightness/apply-show", json={"scales": {"6": 0.5}}))
    d = _ok(c.post("/api/show/save", json={"path": str(c.tmp / "C_v2.qxw")})).get_json()
    assert recipe.main(["replay", d["recipe_path"]]) == 0
    assert "RESULT: IDENTICAL" in capsys.readouterr().out
    out = c.tmp / "again.qxw"
    assert recipe.main(["replay", d["recipe_path"], "--out", str(out)]) == 0
    assert out.read_bytes() == (c.tmp / "C_v2.qxw").read_bytes()
    assert recipe.main(["show", d["recipe_path"]]) == 0
    assert "/api/brightness/apply-show" in capsys.readouterr().out


def test_live_edits_and_their_undo(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    items = c.get("/api/triggers/").get_json()
    items = items if isinstance(items, list) else items.get("items", items.get("triggers", []))
    _ok(c.patch(f"/api/triggers/{items[0]['uid']}", json={"key": "F12", "universe": "", "channel": ""}))
    _ok(c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra"}))
    _ok(c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra 2"}))
    _ok(c.post("/api/vc/undo", json={}))
    s = c.get("/api/stage/state").get_json()
    _ok(c.post("/api/stage/op", json={"op": "stage", "w": s["stage"]["w"] + 1}))
    _ok(c.post("/api/stage/op", json={"op": "stage", "d": s["stage"]["d"] + 1}))
    _ok(c.post("/api/stage/op", json={"op": "undo"}))
    rec, res = _save_and_replay(c, "Live_v2.qxw")
    assert len(rec["calls"]) == 7
    assert res["identical"], res
