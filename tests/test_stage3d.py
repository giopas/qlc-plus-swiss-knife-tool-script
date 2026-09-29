"""Stage and meshes (WORKPLAN Phase 2.5)."""
import os
import shutil

import pytest

import app
from core import qxw_io, stage3d as s3

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
FEST = os.path.join(CORPUS, "Festival_14fix.qxw")

WS = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Workspace>
<Workspace xmlns="http://www.qlcplus.org/Workspace" CurrentWindow="FIXANDFUNC">
 <Creator><Name>Q Light Controller Plus</Name><Version>5.2.2</Version><Author>t</Author></Creator>
 <Engine>
  <InputOutputMap><Universe Name="Universe 1" ID="0"/></InputOutputMap>
  <Monitor DisplayMode="0" ShowLabels="0">
   <Grid Width="5" Height="3" Depth="5" Units="0" POV="1"/>
   <StageItem>{stage}</StageItem>
   <MeshItem ID="0" XPos="325" YPos="-755" ZPos="2500" Res="person.obj"/>
   <MeshItem ID="1" XPos="2450" YPos="155" ZPos="-60" Res="generic/cube.obj"/>
   <MeshItem ID="2" XPos="0" YPos="0" ZPos="0" Res="missing.obj"/>
  </Monitor>
 </Engine>
 <VirtualConsole><Frame Caption="Page 1" ID="0"><WindowState Visible="True" X="0" Y="0" Width="1920" Height="1080"/></Frame></VirtualConsole>
</Workspace>
"""

# a "person": feet at y = 0, 1.8 m tall, not centred in X (like character models)
PERSON = "\n".join(f"v {x} {y} {z}" for x in (-0.5, 0.55) for y in (0.0, 1.8) for z in (-0.4, 0.4)) + "\n"
CUBE = "\n".join(f"v {x} {y} {z}" for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)) + "\n"


@pytest.fixture()
def show(tmp_path):
    (tmp_path / "person.obj").write_text(PERSON)

    def make(stage=0):
        p = tmp_path / f"show{stage}.qxw"
        p.write_text(WS.replace("{stage}", str(stage)), encoding="utf-8")
        return str(p), qxw_io.strip_ns(qxw_io.load_qxw(str(p)).getroot())
    return make


def _m(root, path, mid):
    return next(m for m in s3.meshes(root, path) if m["id"] == mid)


def test_read_obj_and_resolve(tmp_path):
    (tmp_path / "a.obj").write_text("# x\nvn 0 1 0\n" + PERSON + "f 1 2 3\n")
    info = s3.read_obj(str(tmp_path / "a.obj"))
    assert info["min"] == (-0.5, 0.0, -0.4) and info["max"] == (0.55, 1.8, 0.4) and info["count"] == 8
    assert s3.resolve("a.obj", str(tmp_path / "s.qxw")) == str(tmp_path / "a.obj")
    assert s3.resolve(str(tmp_path / "a.obj")) == str(tmp_path / "a.obj")
    assert s3.resolve("nope.obj", str(tmp_path / "s.qxw")) is None
    # QLC+'s built-in cube is known even when its folder isn't here
    info, path = s3.mesh_info("generic/cube.obj")
    assert info["ext"] == (2.0, 2.0, 2.0) and path is None
    assert s3.mesh_info("/Users/x/QLC+/Meshes/generic/cube.obj")[0]["ext"] == (2.0, 2.0, 2.0)


def test_placement_matches_qlc(show):
    path, r = show(0)                                     # Simple ground: floor top at 0.1 m
    st = s3.stage(r)
    assert st["floor"] == 0.1 and (st["w"], st["d"]) == (5.0, 5.0)
    p = _m(r, path, "0")["place"]
    # QLC+: y = YPos/1000 + ext/2 = -0.755 + 0.9 → feet at 0.145 m = 45 mm above the 0.1 m floor
    assert p["bottom"] == 45 and p["top"] == 1845 and p["h"] == 1800
    # x: world min = −0.5 + XPos/1000 − 2.5 + 1.05/2 → 350 mm from the left edge
    assert p["x0"] == 350 and p["x"] == 350 + 525
    c = _m(r, path, "1")["place"]
    assert c["bottom"] == 55 and c["w"] == 2000                 # the cube floats 55 mm
    assert _m(r, path, "2")["found"] is False and _m(r, path, "2")["place"] is None


def test_on_floor_and_box_stage(show):
    path, r = show(0)
    res = s3.on_floor(r, qxw_path=path)
    assert sorted(x["id"] for x in res["moved"]) == ["0", "1"] and res["skipped"] == ["2"]
    assert _m(r, path, "0")["pos"][1] == -800 and _m(r, path, "0")["place"]["bottom"] == 0
    assert _m(r, path, "1")["pos"][1] == 100
    path1, r1 = show(1)                                   # Simple box: floor at 0
    s3.on_floor(r1, ["0"], qxw_path=path1)
    assert _m(r1, path1, "0")["pos"][1] == -900
    assert _m(r1, path1, "1")["pos"][1] == 155            # not asked


def test_festival_meshes_close_to_the_floor():
    r = qxw_io.strip_ns(qxw_io.load_qxw(FEST).getroot())
    cubes = [m for m in s3.meshes(r, FEST) if m["res"] == "generic/cube.obj"]
    assert len(cubes) == 6 and all(0 <= m["place"]["bottom"] <= 80 for m in cubes)   # placed by eye in QLC+
    s3.on_floor(r, qxw_path=FEST)
    assert all(m["place"]["bottom"] == 0 for m in s3.meshes(r, FEST) if m["found"])


def test_move_rotate_scale_keep_place(show):
    path, r = show(1)
    s3.move_to(r, "0", x=1000, z=2000, bottom=0, qxw_path=path)
    p = _m(r, path, "0")["place"]
    assert (p["x"], p["z"], p["bottom"]) == (1000, 2000, 0)
    s3.set_transform(r, "0", rot=[0, 90, 0], scale=[0.5, 0.5, 0.5], qxw_path=path)
    m = _m(r, path, "0")
    assert (m["place"]["x"], m["place"]["z"], m["place"]["bottom"]) == (1000, 2000, 0)
    assert m["place"]["h"] == 900 and m["place"]["w"] == 400        # rotated 90°: depth becomes width
    s3.set_transform(r, "0", rot=[90, 0, 0], qxw_path=path)           # lying down
    assert _m(r, path, "0")["place"]["bottom"] == 0
    with pytest.raises(s3.StageError):
        s3.set_transform(r, "0", scale=[0, 1, 1], qxw_path=path)
    el = next(e for e in r.iter("MeshItem") if e.get("ID") == "0")
    assert el.get("XRot") == "90" and el.get("YRot") is None and el.get("XScale") == "0.5"
    assert list(el.attrib)[:4] == ["ID", "XPos", "YPos", "ZPos"] and el.get("Res") == "person.obj"


def test_add_duplicate_remove(show, tmp_path):
    path, r = show(0)
    d = s3.add_mesh(r, str(tmp_path / "person.obj"), name="Singer", qxw_path=path)
    m = _m(r, path, d["id"])
    assert d["id"] == "3" and m["name"] == "Singer"
    assert (m["place"]["x"], m["place"]["z"], m["place"]["bottom"]) == (2500, 2500, 0)
    dup = s3.duplicate_mesh(r, d["id"], qxw_path=path)
    assert _m(r, path, dup["id"])["place"]["x"] == 3000
    s3.remove_mesh(r, d["id"])
    assert [x["id"] for x in s3.meshes(r, path)] == ["0", "1", "2", "4"]
    with pytest.raises(s3.StageError):
        s3.add_mesh(r, "nowhere.obj", qxw_path=path)


def test_stage_change_keeps_meshes(show):
    path, r = show(0)
    s3.on_floor(r, qxw_path=path)
    before = {m["id"]: m["place"] for m in s3.meshes(r, path) if m["place"]}
    s3.set_stage(r, type=2, w=8, d=6, qxw_path=path)
    st = s3.stage(r)
    assert (st["type"], st["w"], st["d"], st["floor"]) == (2, 8.0, 6.0, 0.0)
    after = {m["id"]: m["place"] for m in s3.meshes(r, path) if m["place"]}
    for k in before:
        assert (after[k]["x"], after[k]["z"], after[k]["bottom"]) == (before[k]["x"], before[k]["z"], 0)


def test_library(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    lib = tmp_path / "Meshes"
    (lib / "band").mkdir(parents=True)
    (lib / "band" / "Bassist.obj").write_text(PERSON)
    (lib / "riser.obj").write_text(CUBE)
    (lib / "notes.txt").write_text("x")
    assert s3.set_library_dirs([str(lib)]) == [str(lib)]
    items = s3.library()
    assert [(i["folder"], i["name"]) for i in items] == [("", "riser"), ("band", "Bassist")]
    with pytest.raises(s3.StageError):
        s3.set_library_dirs([str(tmp_path / "nope")])


def test_api(show, tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    path, _ = show(0)
    before = open(path, "rb").read()
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": path}).status_code == 200
    s = c.get("/api/stage/state").get_json()
    assert len(s["meshes"]) == 3 and not s["dirty"] and s["stage"]["type_name"] == "Simple ground"
    s = c.post("/api/stage/op", json={"op": "floor"}).get_json()
    assert s["dirty"] and s["undo"] == 1 and "2 mesh(es) put on the floor" in s["message"]
    s = c.post("/api/stage/op", json={"op": "move", "id": "0", "x": 1200}).get_json()
    assert next(m for m in s["meshes"] if m["id"] == "0")["place"]["x"] == 1200
    assert c.post("/api/stage/op", json={"op": "move", "id": "2", "x": 5}).status_code == 400
    s = c.post("/api/stage/op", json={"op": "undo"}).get_json()
    assert s["undo"] == 1
    r = c.post("/api/stage/save", json={})
    assert r.status_code == 200 and r.headers["X-Suggested-Filename"] == "show0_v2.qxw"
    out = tmp_path / "show0_v2.qxw"
    out.write_bytes(r.data)
    root = qxw_io.strip_ns(qxw_io.loads_qxw(r.data))
    assert _m(root, str(out), "0")["pos"][1] == -800
    rp = c.post("/api/stage/save-report", json={"qxw_path": str(out)}).get_json()
    txt = open(rp["path"], encoding="utf-8").read()
    assert "bottom 45 → 0 mm" in txt and "missing" in txt
    assert open(path, "rb").read() == before
    s = c.post("/api/stage/op", json={"op": "reset"}).get_json()
    assert not s["dirty"] and s["undo"] == 0


# ── arrange (edges, align, distribute, nudge) ────────────────────────────────

def _band(show, stage=1):
    """Box stage 5 × 5 m; three people + a cube riser, all on the floor."""
    path, r = show(stage)
    s3.remove_mesh(r, "2")
    s3.add_mesh(r, os.path.join(os.path.dirname(path), "person.obj"), x=3500, z=1000, qxw_path=path)
    s3.on_floor(r, qxw_path=path)
    s3.set_transform(r, "1", scale=[0.25, 0.25, 0.25], qxw_path=path)   # a 500 mm cube
    return path, r


def _p(r, path):
    return {m["id"]: m["place"] for m in s3.meshes(r, path)}


def test_arrange_edges_group_and_margin(show):
    path, r = _band(show)
    before = _p(r, path)
    res = s3.arrange(r, ["0", "2"], "left", margin=100, qxw_path=path)
    after = _p(r, path)
    assert min(after[i]["x0"] for i in ("0", "2")) == 100
    # moved together: the spacing between them is kept
    assert after["2"]["x"] - after["0"]["x"] == before["2"]["x"] - before["0"]["x"]
    assert sorted(res["moved"]) == ["0", "2"] and res["outside"] == []
    s3.arrange(r, ["0", "2"], "right", qxw_path=path)
    assert max(p["x0"] + p["w"] for i, p in _p(r, path).items() if i in ("0", "2")) == 5000
    s3.arrange(r, ["1"], "back", qxw_path=path)
    assert _p(r, path)["1"]["z0"] == 0
    s3.arrange(r, ["1"], "front", margin=200, qxw_path=path)
    assert _p(r, path)["1"]["z0"] + _p(r, path)["1"]["d"] == 4800
    s3.arrange(r, ["1"], "centre", qxw_path=path)
    assert (_p(r, path)["1"]["x"], _p(r, path)["1"]["z"]) == (2500, 2500)


def test_arrange_floor_ceiling(show):
    path, r = _band(show)
    s3.arrange(r, ["0", "1"], "ceiling", qxw_path=path)             # stage height 3 m
    p = _p(r, path)
    assert p["0"]["top"] == 3000 and p["1"]["top"] == 3000 and p["1"]["bottom"] == 2500
    s3.arrange(r, ["0", "1"], "floor", qxw_path=path)
    assert _p(r, path)["0"]["bottom"] == 0 == _p(r, path)["1"]["bottom"]


def test_arrange_align(show):
    path, r = _band(show)
    s3.arrange(r, ["0", "1", "2"], "align_back", qxw_path=path)
    p = _p(r, path)
    assert p["0"]["z0"] == p["1"]["z0"] == p["2"]["z0"]
    s3.arrange(r, ["0", "1"], "align_centre_x", qxw_path=path)
    p = _p(r, path)
    assert abs(p["0"]["x"] - p["1"]["x"]) <= 1
    s3.move_to(r, "1", bottom=400, qxw_path=path)
    s3.arrange(r, ["0", "1"], "align_top", qxw_path=path)
    p = _p(r, path)
    assert p["0"]["top"] == p["1"]["top"] == 1800
    with pytest.raises(s3.StageError):
        s3.arrange(r, ["0"], "align_left", qxw_path=path)
    with pytest.raises(s3.StageError):
        s3.arrange(r, ["0"], "sideways", qxw_path=path)


def test_arrange_distribute_and_spread(show):
    path, r = _band(show)
    s3.add_mesh(r, os.path.join(os.path.dirname(path), "person.obj"), x=1500, z=3000, qxw_path=path)   # id 3
    ids = ["0", "1", "2", "3"]
    s3.arrange(r, ids, "spread_x", margin=0, qxw_path=path)
    p = _p(r, path)
    order = sorted(ids, key=lambda i: p[i]["x"])
    edges = [0] + [x for i in order for x in (p[i]["x0"], p[i]["x0"] + p[i]["w"])] + [5000]
    gaps = [edges[k + 1] - edges[k] for k in range(0, len(edges), 2)]
    assert max(gaps) - min(gaps) <= 2                                # equal gaps, edges included
    s3.move_to(r, order[1], x=p[order[1]]["x"] - 300, qxw_path=path)
    s3.arrange(r, ids, "distribute_x", qxw_path=path)
    q = _p(r, path)
    assert q[order[0]]["x0"] == p[order[0]]["x0"] and q[order[-1]]["x0"] == p[order[-1]]["x0"]   # outer two stay
    inner = [q[order[k + 1]]["x0"] - (q[order[k]]["x0"] + q[order[k]]["w"]) for k in range(3)]
    assert max(inner) - min(inner) <= 2
    with pytest.raises(s3.StageError):
        s3.arrange(r, ["0", "1"], "distribute_z", qxw_path=path)


def test_arrange_nudge_and_skip_missing(show):
    path, r = show(1)
    before = _p(r, path)["0"]
    res = s3.arrange(r, ["0", "2"], "nudge", dx=100, dz=-50, dy=20, qxw_path=path)
    p = _p(r, path)["0"]
    assert (p["x"], p["z"], p["bottom"]) == (before["x"] + 100, before["z"] - 50, before["bottom"] + 20)
    assert res["skipped"] == ["2"]
    with pytest.raises(s3.StageError):
        s3.arrange(r, ["2"], "left", qxw_path=path)


def test_api_arrange(show, tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    path, _ = show(1)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": path}).status_code == 200
    s = c.post("/api/stage/op", json={"op": "arrange", "ids": ["0", "1"], "action": "left", "margin": 50}).get_json()
    assert "placed" in s["message"] and min(m["place"]["x0"] for m in s["meshes"] if m["id"] in ("0", "1")) == 50
    assert c.post("/api/stage/op", json={"op": "arrange", "ids": ["0"], "action": "align_left"}).status_code == 400
