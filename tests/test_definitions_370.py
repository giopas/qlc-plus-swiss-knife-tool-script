"""Fixture definitions that travel (3.7.0): Doctor D021 to D023, I009, and the
*Take the show elsewhere* zip."""
import io
import os
import shutil
import zipfile

import pytest

import app
from core import definitions, qxw_io, workspace
from core.doctor import check, load_qxf_defs
from core.quick_start import qlc_library
from tests.test_doctor import CORPUS, DEFS, FULL, PAR, scene, ws

PAR_NAME = "Generic-7-Ch RGB LED PAR.qxf"          # the name QLC+ looks for
CORPUS_PAR = "Generic-7Ch-RGB-PAR.qxf"               # the name of the file in the corpus


def _par(mode="7 Channel", channels=7, fid=0, addr=0):
    return PAR.format(id=fid, addr=addr).replace("<Mode>7 Channel</Mode>", f"<Mode>{mode}</Mode>") \
        .replace("<Channels>7</Channels>", f"<Channels>{channels}</Channels>")


def test_d021_mode_not_in_definition():
    rep = check(ws(fixtures=_par(mode="9 Channel", channels=9)), DEFS)
    f = rep.by_code("D021")
    assert len(f) == 1 and f[0].severity == "warning" and "9 Channel" in f[0].message
    assert not check(ws(), DEFS).by_code("D021")


def test_d022_channel_count_differs_from_mode():
    rep = check(ws(fixtures=_par(channels=5)), DEFS)
    f = rep.by_code("D022")
    assert len(f) == 1 and "5" in f[0].message and "7" in f[0].message
    assert not rep.by_code("D021")
    assert not check(ws(), DEFS).by_code("D022")


def test_d023_scene_sets_channel_beyond_the_fixture():
    beyond = FULL + ",9,255"                       # channel 10 of a 7-channel fixture
    rep = check(ws(functions=scene("401", beyond)), DEFS)
    f = rep.by_code("D023")
    assert len(f) == 1 and "10" in f[0].message
    assert not check(ws(functions=scene("401")), DEFS).by_code("D023")


def test_i009_only_when_a_stock_library_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("QLCPLUS_FIXTURES", raising=False)
    monkeypatch.setattr(qlc_library, "_candidates", lambda: [])
    assert not check(ws(), DEFS).by_code("I009")                 # no QLC+ here: nothing can be said
    stock = tmp_path / "stock"
    stock.mkdir()
    monkeypatch.setattr(qlc_library, "_candidates", lambda: [(str(stock), "stock")])
    qlc_library.clear_cache()
    rep = check(ws(), DEFS)                                      # the PAR is not in this stock library
    assert len(rep.by_code("I009")) == 1 and rep.by_code("I009")[0].severity == "info"
    shutil.copy(os.path.join(CORPUS, CORPUS_PAR), stock / CORPUS_PAR)
    qlc_library.clear_cache()
    assert not check(ws(), DEFS).by_code("I009")                 # now it is stock
    qlc_library.clear_cache()


def test_source_of(tmp_path, monkeypatch):
    stock, user, show = tmp_path / "s", tmp_path / "u", tmp_path / "show"
    for d in (stock, user, show):
        d.mkdir()
    monkeypatch.setattr(qlc_library, "_candidates", lambda: [(str(stock), "stock"), (str(user), "user")])
    f = "Generic-X.qxf"
    assert definitions.source_of(str(stock / f), str(show)) == definitions.LIBRARY
    assert definitions.source_of(str(user / f), str(show)) == definitions.USER
    assert definitions.source_of(str(show / f), str(show)) == definitions.SHOW
    other = tmp_path / "other"
    other.mkdir()
    assert definitions.source_of(str(other / f), str(show)) == ""
    assert definitions.source_of(str(other / f), str(show), [str(other)]) == definitions.CHOSEN


def _rows(tmp_path, monkeypatch, stock_has_par=False):
    stock = tmp_path / "stock"
    stock.mkdir(exist_ok=True)
    monkeypatch.setattr(qlc_library, "_candidates", lambda: [(str(stock), "stock")])
    if stock_has_par:
        shutil.copy(os.path.join(CORPUS, CORPUS_PAR), stock / CORPUS_PAR)
    qlc_library.clear_cache()
    show = tmp_path / "Pub.qxw"
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), show)
    shutil.copy(os.path.join(CORPUS, CORPUS_PAR), tmp_path / CORPUS_PAR)       # next to the show
    defs = load_qxf_defs([str(tmp_path)])
    root = qxw_io.load_qxw(str(show)).getroot()
    return str(show), root, definitions.describe(root, defs, str(show))


def test_describe_says_where_each_definition_was_found(tmp_path, monkeypatch):
    _show, _root, rows = _rows(tmp_path, monkeypatch)
    assert [r["model"] for r in rows] == ["7-Ch RGB LED PAR"]
    r = rows[0]
    assert r["fixtures"] == 6 and r["source"] == definitions.SHOW and r["travels"]
    assert r["file"] == PAR_NAME and r["modes"] == ["7 Channel"]


def test_zip_carries_show_definition_side_files_and_text(tmp_path, monkeypatch):
    show, root, rows = _rows(tmp_path, monkeypatch)
    (tmp_path / "Pub.stage.json").write_text("{}", encoding="utf-8")
    (tmp_path / "Pub.cabling.json").write_text("{}", encoding="utf-8")
    data = definitions.build_zip("Pub_v2.qxw", b"<Workspace/>", rows, show)
    z = zipfile.ZipFile(io.BytesIO(data))
    assert z.namelist() == sorted(["Pub_v2.qxw", PAR_NAME, "Pub.stage.json", "Pub.cabling.json", "READ ME.txt"])
    assert z.read(PAR_NAME) == (tmp_path / CORPUS_PAR).read_bytes()
    text = z.read("READ ME.txt").decode()
    assert "Application Support/QLC+/Fixtures" in text and ".qlcplus/fixtures" in text and PAR_NAME in text
    assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in z.infolist())
    assert data == definitions.build_zip("Pub_v2.qxw", b"<Workspace/>", rows, show)   # same input, same zip


def test_zip_leaves_out_stock_definitions(tmp_path, monkeypatch):
    show, _root, rows = _rows(tmp_path, monkeypatch, stock_has_par=True)
    # found next to the show AND in stock: the stock one is a library definition
    stock_defs = load_qxf_defs([str(tmp_path / "stock")])
    root = qxw_io.load_qxw(show).getroot()
    rows = definitions.describe(root, stock_defs, show)
    assert rows[0]["source"] == definitions.LIBRARY and not rows[0]["travels"]
    z = zipfile.ZipFile(io.BytesIO(definitions.build_zip("Pub.qxw", b"x", rows, show)))
    assert PAR_NAME not in z.namelist() and "every definition is in QLC+'s stock library" in z.read("READ ME.txt").decode()


def test_missing_definition_is_named_in_the_text(tmp_path, monkeypatch):
    show, root, _rows_ = _rows(tmp_path, monkeypatch)
    rows = definitions.describe(root, {}, show)
    assert rows[0]["found"] is False and not rows[0]["travels"]
    text = zipfile.ZipFile(io.BytesIO(definitions.build_zip("Pub.qxw", b"x", rows, show))).read("READ ME.txt").decode()
    assert "Not found on the computer" in text and "7-Ch RGB LED PAR" in text


def test_travel_zip_route(tmp_path, monkeypatch):
    show = tmp_path / "Pub_6fix.qxw"
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), show)
    shutil.copy(os.path.join(CORPUS, CORPUS_PAR), tmp_path / CORPUS_PAR)
    monkeypatch.setattr(qlc_library, "_candidates", lambda: [])
    client = app.create_app().test_client()
    from core import show as show_mod
    show_mod._show.clear()                      # no show left open by an earlier test
    assert client.get("/api/show/travel").status_code == 400                      # no show open
    assert client.post("/api/load", json={"path": str(show)}).status_code == 200
    r = client.get("/api/show/travel")
    assert r.status_code == 200 and r.headers["X-Suggested-Filename"].endswith("_to_go.zip")
    names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
    assert PAR_NAME in names and "READ ME.txt" in names and any(n.endswith(".qxw") for n in names)
    info = client.get("/api/show/definitions").get_json()
    assert info["definitions"][0]["travels"] is True
    out = tmp_path / "out" / "x_to_go.zip"
    out.parent.mkdir()
    assert client.post("/api/show/travel", json={"path": str(out)}).status_code == 200
    assert out.is_file()
    assert client.post("/api/show/travel", json={"path": str(out)}).status_code == 400      # never overwrites
