"""3.3 (v2.3.0) — a Show Profile that starts a show from nothing (its own
Quick Start rig), the profile step editor, fixture files written at the first save."""
import json
import os

import pytest

import app
from core import profile
from routes import quick_start_routes as qs

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
PAR = os.path.join(CORPUS, "Generic-7Ch-RGB-PAR.qxf")
LOOKS = {"looks": [{"group": "all", "colours": ["Amber", "Blue"]}], "vc_page": "Looks"}


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_PROFILES", str(tmp_path / "profiles"))
    # whatever QLC+ is installed on this machine: pretend its fixture library is empty
    (tmp_path / "qlc_fixtures").mkdir()
    monkeypatch.setenv("QLCPLUS_FIXTURES", str(tmp_path / "qlc_fixtures"))
    monkeypatch.setenv("QSK_VC_TEMPLATES", str(tmp_path / "templates"))
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    client = app.create_app().test_client()
    client.tmp = tmp_path
    client.post("/api/quickstart/clear")
    return client


def _ok(r):
    assert r.status_code < 300, r.get_data(as_text=True)[:400]
    return r


def _rig(c, n=4):
    d = _ok(c.post("/api/quickstart/load-qxf", json={"path": PAR})).get_json()["definition"]
    _ok(c.post("/api/quickstart/add-fixture", json={"key": d.get("key") or f"{d['manufacturer']}::{d['model']}",
                                                    "quantity": n}))
    _ok(c.post("/api/quickstart/auto-dmx"))
    _ok(c.post("/api/quickstart/options", json={"nomenclature": "prefix"}))


def test_snapshot_restore_builds_the_same_show(c):
    _rig(c)
    first = _ok(c.get("/api/quickstart/generate")).data
    snap = _ok(c.post("/api/quickstart/snapshot", json={})).get_json()
    json.dumps(snap)                                    # plain JSON
    assert snap["format"] == "qsk-quickstart/1" and len(snap["rig"]) == 4 and snap["qxf"]
    c.post("/api/quickstart/clear")
    assert c.get("/api/quickstart/generate").status_code == 400      # empty rig
    _ok(c.post("/api/quickstart/restore", json=snap))
    assert _ok(c.get("/api/quickstart/generate")).data == first


def test_empty_rig_has_no_snapshot(c):
    assert c.post("/api/quickstart/snapshot", json={}).status_code == 400
    r = c.post("/api/profile/save", json={"name": "Nothing", "include_rig": True, "steps": False})
    assert r.status_code == 400 and "empty" in r.get_json()["error"]


def test_rig_only_profile_starts_a_show(c):
    _rig(c)
    d = _ok(c.post("/api/profile/save", json={"name": "Club rig", "include_rig": True, "steps": False})).get_json()
    assert d["rig"] and d["steps"] == 0
    assert [p for p in c.get("/api/profile/list").get_json()["profiles"] if p["name"] == "Club rig"][0]["fixtures"] == 4
    c.post("/api/quickstart/clear")                      # a fresh app: nothing in Quick Start
    r = _ok(c.post("/api/profile/start", json={"name": "Club rig"})).get_json()
    assert r["started"]["fixtures"] == 4 and r["show"]["active"]
    chk = c.get("/api/doctor/check").get_json()
    assert chk["summary"]["error"] == 0
    assert len(c.get("/api/rig").get_json()) == 4 if c.get("/api/rig").status_code == 200 else True


def test_profile_with_steps_and_rig_starts_and_applies(c):
    _rig(c)
    path = str(c.tmp / "Start_v1.qxw")
    _ok(c.post("/api/load", data={"file": (__import__("io").BytesIO(_ok(c.get("/api/quickstart/generate")).data),
                                           "Start_v1.qxw")}, content_type="multipart/form-data"))
    _ok(c.post("/api/looks/apply", json=LOOKS))
    _ok(c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra"}))
    _ok(c.post("/api/profile/save", json={"name": "Club night", "include_rig": True}))
    c.post("/api/quickstart/clear")
    r = _ok(c.post("/api/profile/start", json={"name": "Club night"})).get_json()
    assert r["failed"] == 0 and r["applied"] >= 2, r
    page_caps = [s["title"] for s in r["steps"]]
    assert any("ook" in t for t in page_caps)
    assert c.get("/api/show/status").get_json()["active"]


def test_cli_build_without_a_show_and_fixture_files(c, capsys):
    _rig(c)
    _ok(c.post("/api/profile/save", json={"name": "Club rig", "include_rig": True, "steps": False}))
    out = str(c.tmp / "Built_v1.qxw")
    rc = profile.main(["build", "Club rig", "--out", out])
    assert rc == 0 and os.path.isfile(out)
    assert os.path.isfile(str(c.tmp / "Generic-7-Ch-RGB-LED-PAR.qxf"))     # the fixture file QLC+ lacks
    assert "its own rig" in capsys.readouterr().out
    # a profile with changes only still needs a show
    _rig(c)
    _ok(c.post("/api/load", json={"path": out}))
    _ok(c.post("/api/looks/apply", json=LOOKS))
    _ok(c.post("/api/profile/save", json={"name": "Only changes"}))
    assert profile.main(["build", "Only changes", "--out", str(c.tmp / "x.qxw")]) == 1


def test_start_saves_fixture_files_next_to_the_first_save(c):
    _rig(c)
    _ok(c.post("/api/profile/save", json={"name": "Club rig", "include_rig": True, "steps": False}))
    _ok(c.post("/api/profile/start", json={"name": "Club rig"}))
    folder = c.tmp / "saved"
    folder.mkdir()
    r = _ok(c.post("/api/show/save", json={"path": str(folder / "Show_v1.qxw")})).get_json()
    assert r["fixture_files"] == ["Generic-7-Ch-RGB-LED-PAR.qxf"]
    assert (folder / "Generic-7-Ch-RGB-LED-PAR.qxf").is_file()


def test_step_editor_drop_reorder_rename(c):
    _ok(c.post("/api/load", json={"path": os.path.join(CORPUS, "Festival_14fix.qxw")}))
    _ok(c.post("/api/looks/apply", json=LOOKS))
    _ok(c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra"}))
    _ok(c.post("/api/stage/op", json={"op": "group_new", "name": "Pair", "fixtures": ["7", "8"]}))
    _ok(c.post("/api/profile/save", json={"name": "Three"}))
    st = _ok(c.get("/api/profile/steps?name=Three")).get_json()
    n = len(st["steps"])
    assert n >= 3
    order = list(range(n))[::-1][: n - 1]                # reversed, the first one dropped
    d = _ok(c.post("/api/profile/edit", json={"name": "Three", "order": order,
                                              "titles": {str(order[0]): "Renamed step"}})).get_json()
    assert d["steps"] == n - 1
    st2 = c.get("/api/profile/steps?name=Three").get_json()
    assert st2["steps"][0]["title"] == "Renamed step"
    assert [s["path"] for s in st2["steps"]] == [st["steps"][i]["path"] for i in order]
    assert c.post("/api/profile/edit", json={"name": "Three", "order": [0, 0]}).status_code == 400
    assert c.post("/api/profile/edit", json={"name": "Three", "order": []}).status_code == 400
    assert c.post("/api/profile/edit", json={"name": "Three", "order": [99]}).status_code == 400
