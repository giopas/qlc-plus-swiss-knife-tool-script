"""v3.8.0 — stage layouts (idea: the stage layouts and band members of mjcmatrix's fork of QLC+)."""
import json
import os
import shutil

import pytest

import app
from core import library as lib, look_families as LF, qxw_io, stage3d as s3, stage_layouts as sl

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
FEST = os.path.join(CORPUS, "Festival_14fix.qxw")
PAR = os.path.join(CORPUS, "Generic-7Ch-RGB-PAR.qxf")


@pytest.fixture(autouse=True)
def _stores(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_STAGE_LAYOUTS", str(tmp_path / "layouts"))
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "mesh_dirs.json"))


def _root():
    return qxw_io.strip_ns(qxw_io.loads_qxw(open(FEST, "rb").read()))


def _by_name(root):
    return {m["label"]: m for m in s3.meshes(root)}


# ── the layout ──────────────────────────────────────────────────────────────

def test_builtin_layouts_are_valid_and_listed_first():
    rows = sl.list_layouts()
    assert [r["label"] for r in rows[:3]] == ["Full band", "Acoustic", "Festival"] and all(r["builtin"] for r in rows[:3])
    full = rows[0]
    assert full["members"] == 5 and full["roles"]["wedge"] == 2 and full["stage"] == {"type": 2, "w": 8.0, "h": 4.0, "d": 6.0}
    assert sl.get("builtin:full_band")["name"] == "Full band" and sl.get("Festival")["walkways"]


@pytest.mark.parametrize("name,role", [
    ("Drums", "drums"), ("Singer", "vocals"), ("Lead vocals", "vocals"), ("Bass", "bass"), ("Guitar", "guitar"),
    ("Keys", "keys"), ("Synth", "keys"), ("Riser", "riser"), ("Drum riser", "riser"), ("Wedge 2", "wedge"),
    ("Guitar amp", "backline"), ("Amp 1", "backline"), ("Backdrop", "backdrop"), ("Catwalk", "walkway"), ("Table", "other")])
def test_role_from_a_name(name, role):
    assert sl.role_of(name) == role


def test_clean_refuses_what_cannot_be_shared_or_used():
    base = {"name": "X", "stage": {"type": 2, "w": 8, "h": 4, "d": 6}, "items": [{"name": "A", "model": "generic/cube.obj"}]}
    assert sl.clean(base)["items"][0]["role"] == "other"
    for bad, why in [({"name": ""}, "name"),
                     ({"items": [{"model": "/Users/me/Drums.obj"}]}, "path"),
                     ({"items": [{"model": "C:\\x\\Drums.obj"}]}, "path"),
                     ({"items": [{"model": "../Drums.obj"}]}, "path"),
                     ({"items": [{"model": "notes.txt"}]}, ".obj"),
                     ({"items": [{"scale": [0, 1, 1]}]}, "scale"),
                     ({"items": [{"x": "left"}]}, "number"),
                     ({"stage": {"type": 9}}, "type"),
                     ({"items": ["x"]}, "valid")]:
        with pytest.raises(sl.LayoutError, match=why):
            sl.clean({**base, **bad})
    with pytest.raises(sl.LayoutError):
        sl.clean({**base, "items": [{"name": str(i)} for i in range(sl.MAX_ITEMS + 1)]})


def test_save_get_delete_and_built_in_names_are_kept():
    lay = sl.get("Acoustic")
    got = sl.save(lay, name="Acoustic at the Pub")
    assert got["id"] == "Acoustic_at_the_Pub" and sl.get("Acoustic at the Pub")["name"] == "Acoustic at the Pub"
    assert [r["label"] for r in sl.list_layouts() if not r["builtin"]] == ["Acoustic at the Pub"]
    with pytest.raises(sl.LayoutError, match="built-in"):
        sl.save(lay, name="full band")
    assert sl.delete("Acoustic_at_the_Pub") and sl.get("Acoustic at the Pub") is None
    assert not sl.delete("../x")


# ── in a show ───────────────────────────────────────────────────────────────

def test_apply_replaces_the_meshes_and_sets_the_stage():
    root = _root()
    assert len(s3.meshes(root)) == 11
    rep = sl.apply(root, sl.get("Full band"))
    assert rep["added"] == 11 and rep["replaced"] == 11 and rep["missing"] == [] and rep["outside"] == []
    st = s3.stage(root)
    assert (st["type"], st["w"], st["d"]) == (2, 8.0, 6.0)
    m = _by_name(root)
    assert m["Singer"]["place"]["x"] == 4000 and m["Singer"]["place"]["z"] == 3400       # on the centre line, 3.4 m from the back
    assert m["Guitar"]["place"]["x"] == 4000 - 1900 and m["Bass"]["place"]["x"] == 4000 + 1900
    assert m["Drums"]["place"]["bottom"] == 400 and m["Riser"]["place"]["bottom"] == 0   # the drummer stands on the riser
    assert (m["Riser"]["place"]["w"], m["Riser"]["place"]["h"], m["Riser"]["place"]["d"]) == (2400, 400, 2000)


def test_apply_add_keeps_what_is_there_and_no_set_stage_keeps_the_stage():
    root = _root()
    before = s3.stage(root)
    rep = sl.apply(root, sl.get("Acoustic"), mode="add", set_stage=False)
    assert rep["replaced"] == 0 and len(s3.meshes(root)) == 11 + 5
    assert s3.stage(root) == before                      # members keep their distance from the centre line
    m = _by_name(root)
    assert m["Singer"]["place"]["x"] == before["w"] * 500


def test_a_member_past_the_edge_is_reported():
    root = _root()
    rep = sl.apply(root, sl.get("Festival"), set_stage=False)          # a 12 m layout on a 6 m stage
    assert "Keys" in rep["outside"]


def test_the_look_builder_and_cabling_see_the_members():
    root = _root()
    sl.apply(root, sl.get("Full band"))
    names = [p["name"] for p in LF.places(root)]
    assert {"Drums", "Bass", "Guitar", "Keys", "Singer"} <= set(names)
    assert not {"Riser", "Amp 1", "Wedge 1", "Backdrop"} & set(names)       # only people are places
    from core.cabling import rig as rig_mod
    keep = rig_mod.read_rig(root)["keep_out"]
    assert len(keep) == 11                                                  # the band floor is the meshes


def test_save_as_layout_and_back_gives_the_same_stage():
    a = _root()
    sl.apply(a, sl.get("Full band"))
    got = sl.from_root(a, "My band")
    assert got["skipped"] == [] and len(got["layout"]["items"]) == 11
    roles = {i["name"]: i["role"] for i in got["layout"]["items"]}
    assert roles["Singer"] == "vocals" and roles["Riser"] == "riser" and roles["Amp 2"] == "backline" and roles["Wedge 1"] == "wedge"
    b = _root()
    sl.apply(b, got["layout"])
    pa = {k: (v["place"]["x"], v["place"]["z"], v["place"]["bottom"], v["place"]["w"]) for k, v in _by_name(a).items()}
    pb = {k: (v["place"]["x"], v["place"]["z"], v["place"]["bottom"], v["place"]["w"]) for k, v in _by_name(b).items()}
    assert pa == pb


def test_a_model_this_computer_lacks_is_a_block_of_the_same_size():
    lay = sl.clean({"name": "Mine", "stage": {"type": 2, "w": 8, "h": 4, "d": 6},
                    "items": [{"name": "Drummer", "model": "People/Drummer.obj", "x": 0, "z": 2000,
                               "rot": [0, 90, 0], "scale": [1, 1, 1], "size": [600, 1500, 600]}]})
    root = _root()
    rep = sl.apply(root, lay)
    assert rep["missing"] == ["People/Drummer.obj"]
    m = _by_name(root)["Drummer"]
    assert m["res"] == sl.CUBE and (m["place"]["w"], m["place"]["h"], m["place"]["d"]) == (600, 1500, 600)


def test_a_model_in_your_mesh_folder_is_found(tmp_path, monkeypatch):
    folder = tmp_path / "meshes"
    (folder / "People").mkdir(parents=True)
    (folder / "People" / "Drummer.obj").write_text("v 0 0 0\nv 1 0 0\nv 0 2 0\nv 1 2 1\n")
    json.dump({"dirs": [str(folder)]}, open(tmp_path / "mesh_dirs.json", "w"))
    lay = sl.clean({"name": "Mine", "stage": {"type": 2, "w": 8, "h": 4, "d": 6},
                    "items": [{"name": "Drummer", "model": "People/Drummer.obj", "x": 0, "z": 2000}]})
    root = _root()
    rep = sl.apply(root, lay)
    assert rep["missing"] == []
    m = _by_name(root)["Drummer"]
    assert m["res"].endswith("People/Drummer.obj") and m["found"]
    # a layout kept from this stage names the model inside the folder, never the full path
    kept = sl.from_root(root, "Back")["layout"]["items"][0]
    assert kept["model"] == "People/Drummer.obj"


def test_walkways_for_tonights_stage_width():
    fest = sl.get("Festival")
    w = sl.walkways_for(fest, 10000)
    assert w == [{"x0": 4400, "z0": 6700, "x1": 5600, "z1": 8000, "ramp": True, "label": "Front walkway"}]


# ── the Library ─────────────────────────────────────────────────────────────

def test_layouts_travel_through_the_library(tmp_path, monkeypatch):
    sl.save(sl.get("Festival"), name="Festival at Zinal")
    inv = [i for i in lib.inventory() if i["kind"] == "stage_layout"]
    assert [i["name"] for i in inv] == ["Festival at Zinal"] and "12" in inv[0]["summary"]
    pack = lib.export_pack([{"kind": "stage_layout", "name": "Festival at Zinal"}], "Layouts")
    assert pack["items"][0]["data"]["items"]
    monkeypatch.setenv("QSK_STAGE_LAYOUTS", str(tmp_path / "other"))
    pv = lib.preview(pack)
    assert pv["items"][0]["status"] == "new"
    res = lib.install(pack, default="skip", choices={})
    assert res["installed"] == 1 and sl.get("Festival at Zinal")["stage"]["w"] == 12.0
    # a layout carrying a path on someone's computer is refused
    bad = json.loads(json.dumps(pack))
    bad["items"][0]["data"]["items"][0]["model"] = "/Users/someone/Drums.obj"
    assert lib.preview(bad)["items"][0]["status"] == "invalid"
    # a built-in name is never replaced
    named = json.loads(json.dumps(pack))
    named["items"][0]["name"] = "Full band"
    named["items"][0]["data"]["name"] = "Full band"
    assert lib.preview(named)["items"][0]["status"] == "reserved"


# ── routes ──────────────────────────────────────────────────────────────────

@pytest.fixture
def c(tmp_path):
    shutil.copy(FEST, tmp_path / "Festival_14fix.qxw")
    client = app.create_app().test_client()
    client.tmp = tmp_path
    return client


def _ok(r):
    assert r.status_code < 300, r.get_data(as_text=True)[:400]
    return r.get_json()


def test_stage_route_uses_a_layout_and_undoes_it(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    lst = _ok(c.get("/api/stage/layouts"))
    assert lst["layouts"][0]["id"] == "builtin:full_band"
    d = _ok(c.post("/api/stage/op", json={"op": "layout", "layout": "builtin:full_band"}))
    assert "Full band" in d["message"] and len(d["meshes"]) == 11 and d["stage"]["w"] == 8.0
    assert {"Singer", "Drums"} <= {m["label"] for m in d["meshes"]}
    d = _ok(c.post("/api/stage/op", json={"op": "undo"}))
    assert d["stage"]["w"] == 6.0
    err = c.post("/api/stage/op", json={"op": "layout", "layout": "nope"})
    assert err.status_code == 400


def test_keep_and_delete_a_layout_from_the_stage(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    d = _ok(c.post("/api/stage/layouts/save", json={"name": "Festival band"}))
    assert d["items"] + len(d["skipped"]) <= 11 and d["items"] >= 1 and any(not r["builtin"] and r["label"] == "Festival band" for r in d["layouts"])
    assert c.post("/api/stage/layouts/save", json={"name": "Full band"}).status_code == 400
    assert c.post("/api/stage/layouts/save", json={"name": ""}).status_code == 400
    one = _ok(c.get("/api/stage/layouts/Festival_band?w=9000"))
    assert one["layout"]["name"] == "Festival band"
    assert c.post("/api/stage/layouts/delete", json={"id": "builtin:full_band"}).status_code == 400
    d = _ok(c.post("/api/stage/layouts/delete", json={"id": "Festival_band"}))
    assert not any(not r["builtin"] for r in d["layouts"])


def test_quick_start_starts_from_a_layout(c):
    c.post("/api/quickstart/clear")
    key = _ok(c.post("/api/quickstart/load-qxf", json={"path": PAR}))["definition"]["key"]
    _ok(c.post("/api/quickstart/add-fixture", json={"key": key, "quantity": 2}))
    _ok(c.post("/api/quickstart/auto-dmx"))
    r = c.get("/api/quickstart/generate?project_name=Band&stage_w=8000&stage_d=6000&stage_h=4000&stage_layout=builtin:full_band")
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    root = qxw_io.strip_ns(qxw_io.loads_qxw(r.data))
    names = {m["label"] for m in s3.meshes(root)}
    assert {"Riser", "Drums", "Singer", "Backdrop"} <= names and s3.stage(root)["type"] == 2
    assert s3.stage(root)["w"] == 8.0                                   # the size is the one of the rig
    r = c.get("/api/quickstart/generate?project_name=Band&stage_layout=unknown")
    assert r.status_code == 400
    r = c.get("/api/quickstart/generate?project_name=Band")
    assert s3.meshes(qxw_io.strip_ns(qxw_io.loads_qxw(r.data))) == []     # no layout: as before
