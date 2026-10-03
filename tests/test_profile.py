"""3.1 — Show Profiles and the recipe on another show (core/retarget.py,
core/profile.py, core/recipe.replay_onto, routes/profile_routes.py)."""
import json
import os
import shutil

import pytest

import app
from core import porter, profile, qxw_io, recipe, retarget

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
LOOKS = {"looks": [{"group": "all", "colours": ["Amber", "Blue"]}], "vc_page": "Looks"}


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    monkeypatch.setenv("QSK_PROFILES", str(tmp_path / "profiles"))
    monkeypatch.setenv("QSK_VC_TEMPLATES", str(tmp_path / "templates"))
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")):
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    porter.clear()
    client.tmp = tmp_path
    return client


def _ok(r):
    assert r.status_code < 300, r.get_data(as_text=True)[:400]
    return r


def _pub_route(c):
    """Part of the Pub route on Festival: reduce, fix, a group, looks, a page."""
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/reducer/apply", json={"keep": ["6", "7", "8", "9", "11", "12"],
                                            "repatch": {"6": {"name": "DR: Drums"}}}))
    keys = [f["key"] for f in c.get("/api/doctor/check").get_json()["findings"] if f["default"]]
    _ok(c.post("/api/doctor/apply", json={"keys": keys}))
    _ok(c.post("/api/stage/op", json={"op": "group_new", "name": "Band Pair", "fixtures": ["7", "8"]}))
    _ok(c.post("/api/looks/apply", json=LOOKS))
    _ok(c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra"}))


def test_calls_are_recorded_by_meaning(c):
    _pub_route(c)
    rec = recipe.snapshot()
    assert rec["symbolic"]
    red = rec["calls"][0]["sym"]["body"]["keep"][0]
    assert red.startswith(retarget.REF) and "Silhouette (Drums)" in red
    assert rec["calls"][1]["sym"]["body"]["@doctor"]["codes"]


def test_onto_the_same_show_gives_the_same_file(c):
    _pub_route(c)
    d = _ok(c.post("/api/show/save", json={"path": str(c.tmp / "Out_v2.qxw")})).get_json()
    rec = json.load(open(d["recipe_path"], encoding="utf-8"))
    res = recipe.replay_onto(rec, str(c.tmp / "Festival_14fix.qxw"), str(c.tmp / "Again.qxw"),
                             recipe_dir=str(c.tmp))
    assert (res["applied"], res["skipped"], res["failed"]) == (5, 0, 0)
    assert (c.tmp / "Again.qxw").read_bytes() == (c.tmp / "Out_v2.qxw").read_bytes()


def test_onto_another_show_matches_by_meaning_and_says_so(c):
    _pub_route(c)
    d = _ok(c.post("/api/show/save", json={"path": str(c.tmp / "Out_v2.qxw")})).get_json()
    rec = json.load(open(d["recipe_path"], encoding="utf-8"))
    res = recipe.replay_onto(rec, str(c.tmp / "FloorShow_8fix.qxw"), str(c.tmp / "Floor_pub.qxw"),
                             recipe_dir=str(c.tmp))
    assert res["failed"] == 0 and res["applied"] == 5
    assert "same address" in res["steps"][0]["note"]                  # fixtures found by address
    assert "same kinds of fixes" in res["steps"][1]["note"]
    root = qxw_io.load_qxw(str(c.tmp / "Floor_pub.qxw"))
    idx = retarget.index(root)
    assert ("Band Pair", 0) in idx["grp"].values()
    assert any(p[-1][1] == "Extra" for p in idx["w"].values())
    assert (c.tmp / "FloorShow_8fix.qxw").read_bytes() == open(os.path.join(CORPUS, "FloorShow_8fix.qxw"), "rb").read()


def test_what_the_show_does_not_have_is_left_out(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    fid = next(f["id"] for f in c.get("/api/functions").get_json() if f["name"] == "Song 22")
    frame = c.get("/api/vc/pages").get_json()["pages"][0]["frames"][0]["id"]      # MANUAL CEILING
    _ok(c.post("/api/vc/op", json={"op": "create", "parent_id": frame, "kind": "Button",
                                     "caption": "S22", "func_id": fid}))
    _ok(c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra"}))
    rec = recipe.snapshot()
    res = recipe.replay_onto(rec, str(c.tmp / "Pub_6fix.qxw"))
    assert [s["status"] for s in res["steps"]] == ["skipped", "applied"]
    assert "MANUAL CEILING" in res["steps"][0]["why"]


def test_old_recipes_learn_their_meaning_from_their_show(c):
    _pub_route(c)
    d = _ok(c.post("/api/show/save", json={"path": str(c.tmp / "Out_v2.qxw")})).get_json()
    rec = json.load(open(d["recipe_path"], encoding="utf-8"))
    rec.pop("symbolic")
    for x in rec["calls"]:
        x.pop("sym", None)                                        # as recorded by 2.0.x
    assert recipe.needs_symbols(rec)
    res = recipe.replay_onto(rec, str(c.tmp / "FloorShow_8fix.qxw"), recipe_dir=str(c.tmp))
    assert res["failed"] == 0 and res["applied"] == 5


def test_profile_from_the_app_applied_to_another_show(c):
    _pub_route(c)
    r = _ok(c.post("/api/profile/save", json={"name": "Pub night", "description": "6 PARs"})).get_json()
    assert r["steps"] == 5 and r["file"] == "Pub_night.profile.json"
    p = profile.load("Pub night")
    assert str(c.tmp) not in json.dumps(p["steps"])                # no paths of this computer
    assert [x["name"] for x in c.get("/api/profile/list").get_json()["profiles"]] == ["Pub night"]
    _ok(c.post("/api/load", json={"path": str(c.tmp / "FloorShow_8fix.qxw")}))
    d = _ok(c.post("/api/profile/apply", json={"name": "Pub night"})).get_json()
    assert d["applied"] == 5 and d["show"]["steps"] >= 5
    _ok(c.post("/api/show/undo", json={}))                           # each step is undoable
    rec = recipe.snapshot()                                          # the calls are in its recipe
    assert [x["path"] for x in rec["calls"]][:2] == ["/api/reducer/apply", "/api/doctor/apply"]


def test_files_become_parameters(c, tmp_path_factory):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    fns = [f for f in porter.list_source_functions() if f["type"] == "Scene"][:2]
    cl = porter.resolve_closure([f["id"] for f in fns])
    _ok(c.post("/api/porter/apply", json=dict(closure=cl, fanout_mode="fan_in", drop_unmapped=True,
                                              fixture_mapping=porter.auto_map(cl["fixture_ids"], "fan_in"))))
    p = profile.make(recipe.snapshot(), "Port two looks")
    assert list(p["params"]) == ["Festival_14fix.qxw"]
    there = tmp_path_factory.mktemp("elsewhere")
    path = there / "Port.profile.json"
    path.write_text(json.dumps(p), encoding="utf-8")
    with pytest.raises(profile.ProfileError, match="Festival_14fix.qxw"):
        profile.build(profile.load(str(path)), str(c.tmp / "Pub_6fix.qxw"))
    shutil.copy(c.tmp / "Festival_14fix.qxw", there / "Festival_14fix.qxw")    # next to the profile
    res = profile.build(profile.load(str(path)), str(c.tmp / "Pub_6fix.qxw"), str(there / "Out.qxw"))
    assert res["failed"] == 0 and res["out"]


def test_cli_build(c, capsys):
    _pub_route(c)
    _ok(c.post("/api/profile/save", json={"name": "Pub"}))
    show = str(c.tmp / "FloorShow_8fix.qxw")
    assert profile.main(["build", "Pub", "--show", show]) == 0
    out = capsys.readouterr().out
    assert "5 applied, 0 left out, 0 failed" in out
    assert os.path.isfile(c.tmp / "FloorShow_8fix_v2.qxw")
    assert profile.main(["show", "Pub"]) == 0
    assert "Rig Reducer" in capsys.readouterr().out


def test_vc_templates_travel_with_the_profile(c, monkeypatch, tmp_path):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    pages = c.get("/api/vc/pages").get_json()["pages"]
    _ok(c.post("/api/vc/template", json={"action": "save", "page_id": pages[0]["id"], "name": "Pub page"}))
    _ok(c.post("/api/vc/op", json={"op": "apply_template", "name": "Pub page"}))
    p = profile.make(recipe.snapshot(), "With template")
    assert "Pub page" in p["assets"]["vc_templates"]
    shutil.rmtree(tmp_path / "templates")
    res = profile.build(p, str(c.tmp / "FloorShow_8fix.qxw"))
    assert res["templates"] == ["Pub page"] and res["failed"] == 0


def test_recipe_from_the_history_without_saving(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra"}))
    r = _ok(c.get("/api/profile/recipe"))
    assert r.headers["X-Suggested-Filename"] == "Pub_6fix.recipe.json" and r.headers["X-Calls"] == "1"
    rec = json.loads(r.data)
    assert rec["format"] == recipe.FORMAT and "result" not in rec
    assert not any(f.endswith(".recipe.json") for f in os.listdir(c.tmp))     # nothing written
