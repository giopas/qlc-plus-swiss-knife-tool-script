"""v2.5.0 Stage & Meshes: hide/show, tilt aiming, thumbnails, copy meshes in the Porter."""
import os

import pytest

from core import porter, qxw_io, stage3d as s3
from tests.test_stage3d import CUBE, PERSON, WS

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture()
def ws(tmp_path):
    (tmp_path / "person.obj").write_text(PERSON)
    p = tmp_path / "show.qxw"
    p.write_text(WS.replace("{stage}", "0"), encoding="utf-8")
    return str(p), qxw_io.strip_ns(qxw_io.load_qxw(str(p)).getroot())


def test_hide_and_show(ws):
    path, root = ws
    r = s3.set_hidden(root, ["0", "1"], True)
    assert r["ids"] == ["0", "1"]
    ms = {m["id"]: m for m in s3.meshes(root, path)}
    assert ms["0"]["hidden"] and ms["1"]["hidden"] and not ms["2"]["hidden"]
    before = ms["0"]["pos"]
    s3.set_hidden(root, ["0"], False)
    m0 = next(m for m in s3.meshes(root, path) if m["id"] == "0")
    assert not m0["hidden"] and m0["pos"] == before
    mon = s3._monitor(root)
    assert next(e for e in mon.findall("MeshItem") if e.get("ID") == "0").get("Hidden") is None
    # hidden survives a move
    s3.move_to(root, "1", x=1000, qxw_path=path)
    assert next(m for m in s3.meshes(root, path) if m["id"] == "1")["hidden"]


def test_tilt_for_geometry():
    assert s3.tilt_for((1000, 4000), (1000, 0)) == 0.0            # straight down
    assert s3.tilt_for((1000, 4000), (5000, 0)) == 45.0           # toward the front
    assert s3.tilt_for((5000, 4000), (1000, 0)) == -45.0          # toward the back
    assert s3.tilt_for((0, 3000), (3000, 3000)) == 90.0           # horizontal


def test_aim_at_point_and_mesh():
    root = qxw_io.strip_ns(qxw_io.load_qxw(os.path.join(CORPUS, "QuickStart_club.qxw")).getroot())
    fx = s3.fixtures(root)
    fid = fx[0]["id"]
    res = s3.aim_fixtures(root, [fid], point={"z": fx[0]["place"]["z"] + 2000, "height": 0})
    assert res["aimed"][0]["id"] == fid
    a = next(f for f in s3.fixtures(root) if f["id"] == fid)
    assert a["rot"][0] > 0                                         # toward the front
    ymid = (fx[0]["place"]["bottom"] + fx[0]["place"]["top"]) / 2
    assert a["rot"][0] == s3.tilt_for((fx[0]["place"]["z"], ymid), (fx[0]["place"]["z"] + 2000, 0))
    # pan/roll untouched
    assert a["rot"][1:] == fx[0]["rot"][1:]
    with pytest.raises(s3.StageError):
        s3.aim_fixtures(root, [fid])
    with pytest.raises(s3.StageError):
        s3.aim_fixtures(root, ["999"], point={"z": 0, "height": 0})


def test_aim_at_mesh(ws):
    path, root = ws
    # put a fixture on this stage
    eng = root.find("Engine")
    import xml.etree.ElementTree as ET
    fx = ET.SubElement(eng, "Fixture")
    ET.SubElement(fx, "ID").text = "0"
    ET.SubElement(fx, "Name").text = "Spot"
    mon = s3._monitor(root)
    ET.SubElement(mon, "FxItem", {"ID": "0", "XPos": "2350", "YPos": "2700", "ZPos": "1000"})
    person = next(m for m in s3.meshes(root, path) if m["id"] == "0")
    out = s3.aim_fixtures(root, ["0"], mesh="0", where="top", qxw_path=path)
    f = s3.fixtures(root)[0]
    assert out["target"] == person["label"]
    assert f["rot"][0] > 0                                         # person stands in front (z 2500 > 1150)
    s3.aim_fixtures(root, ["0"], mesh="0", where="floor", qxw_path=path)
    f2 = s3.fixtures(root)[0]
    assert f2["rot"][0] > f["rot"][0] - 90 and f2["rot"][0] != f["rot"][0]
    with pytest.raises(s3.StageError):
        s3.aim_fixtures(root, ["0"], mesh="2", qxw_path=path)      # model file not found


def test_thumb_svg(tmp_path):
    p = tmp_path / "c.obj"
    p.write_text(CUBE)
    svg = s3.thumb_svg(str(p))
    assert svg.startswith("<svg") and "<circle" in svg
    assert s3.thumb_svg(str(p)) is svg                              # cached


def test_routes_hide_aim_thumb(tmp_path, monkeypatch):
    import app
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "c.obj").write_text(CUBE)
    s3.set_library_dirs([str(lib)])
    c = app.create_app().test_client()
    r = c.get("/api/stage/thumb", query_string={"path": str(lib / "c.obj")})
    assert r.status_code == 200 and r.mimetype == "image/svg+xml"
    other = tmp_path / "x.obj"
    other.write_text(CUBE)
    assert c.get("/api/stage/thumb", query_string={"path": str(other)}).status_code == 404
    assert c.get("/api/stage/thumb", query_string={"path": str(lib / "c.txt")}).status_code == 404


def _mini(meshes_xml, w=5, d=5):
    import xml.etree.ElementTree as ET
    return ET.fromstring(
        f'<Workspace><Engine><Monitor DisplayMode="0"><Grid Width="{w}" Height="3" Depth="{d}" Units="0" POV="1"/>'
        f'<StageItem>0</StageItem>{meshes_xml}</Monitor></Engine></Workspace>')


def test_copy_meshes_into(tmp_path):
    (tmp_path / "person.obj").write_text(PERSON)
    src_path = str(tmp_path / "src.qxw")
    src = _mini('<MeshItem ID="3" XPos="325" YPos="-755" ZPos="2500" Res="person.obj" Hidden="True"/>'
                '<MeshItem ID="4" XPos="0" YPos="0" ZPos="0" Res="gone.obj"/>', w=5, d=5)
    tgt = _mini('<MeshItem ID="7" XPos="0" YPos="0" ZPos="0" Res="generic/cube.obj"/>', w=10, d=5)
    seen = s3.meshes(src, src_path)
    want = next(m for m in seen if m["id"] == "3")["place"]
    out = porter.copy_meshes_into(src, tgt, ["3", "4", "99"], src_path, str(tmp_path / "tgt.qxw"))
    assert [c["id"] for c in out["copied"]] == ["8", "9"] and out["skipped"] == ["99"]
    new = next(m for m in s3.meshes(tgt, str(tmp_path / "tgt.qxw")) if m["id"] == "8")
    assert os.path.isabs(new["res"]) and new["res"].endswith("person.obj")   # resolves anywhere now
    assert new["hidden"]
    assert new["place"]["x"] == round(want["x"] * 2) and new["place"]["z"] == want["z"]  # 10 m wide: x scaled ×2
    assert new["place"]["bottom"] == want["bottom"]
    assert any("not found" in x for x in out["log"])
    assert porter.copy_meshes_into(src, tgt, [], src_path)["copied"] == []


def test_porter_execute_with_meshes(tmp_path):
    (tmp_path / "person.obj").write_text(PERSON)
    for n in ("s", "t"):
        (tmp_path / f"{n}.qxw").write_text(WS.replace("{stage}", "0"), encoding="utf-8")
    porter.load_source(str(tmp_path / "s.qxw"))
    porter.load_target(str(tmp_path / "t.qxw"))
    assert [m["id"] for m in porter.list_source_meshes()] == ["0", "1", "2"]
    res = porter.port({"closure": {"seed_ids": [], "function_ids": [], "fixture_ids": []},
                       "copy_meshes": ["0"]})
    assert res["meshes"]["copied"][0]["id"] == "3"
    root = qxw_io.strip_ns(qxw_io.loads_qxw(res["bytes"]))
    assert len(root.findall("Engine/Monitor/MeshItem")) == 4
    assert "3D MESHES COPIED" in res["report"]
    porter.clear()
