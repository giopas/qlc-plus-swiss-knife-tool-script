"""The show in progress (WORKPLAN Phase 2.6): every tool applies to one working
copy, each apply is a step with undo, one Save writes a new file + one report.

The key promise: applying a tool to the show gives exactly the file that the
tool's old "→ new file" export gave (byte for byte)."""
import os
import shutil

import pytest

import app
from core import qxw_io, show

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
FEST = os.path.join(CORPUS, "Festival_14fix.qxw")
LOOKS = {"looks": [{"group": "all", "colours": ["Amber", "Blue"]}],
         "chasers": [{"group": "0", "pattern": "pingpong", "colours": ["Red"], "bpm": 120,
                      "note": "1/8", "fade": "fade", "fade_pct": 50, "name": "Sweep"}],
         "vc_page": "Looks"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    p = tmp_path / "Fest.qxw"
    shutil.copy(FEST, p)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    return c, p


def _file(c):
    r = c.get("/api/show/file")
    assert r.status_code == 200
    return r.data


def _canon(data):
    """Same content, same indentation (Brightness never indented its export)."""
    import xml.etree.ElementTree as ET
    root = qxw_io.loads_qxw(data)
    ET.indent(root, space=" ")
    return qxw_io.qxw_bytes(root)


def _doctor_keys(c):
    return [f["key"] for f in c.get("/api/doctor/check").get_json()["findings"] if f["default"]]


def test_open_starts_a_clean_show(client):
    c, p = client
    st = c.get("/api/show/status").get_json()
    assert st["active"] and st["source_name"] == "Fest.qxw" and st["steps"] == 0 and st["unsaved"] == 0
    assert st["changed_tools"] == {} and st["suggested_name"] == "Fest_v2.qxw"
    assert st["doctor"]["error"] == 1


def test_each_apply_equals_the_old_export(client):
    """Doctor → Looks → Reducer → Brightness, each checked against the old export
    taken from the show as it was just before."""
    c, p = client
    before = p.read_bytes()

    keys = _doctor_keys(c)
    old = c.post("/api/doctor/fix", json={"keys": keys}).data
    r = c.post("/api/doctor/apply", json={"keys": keys}).get_json()
    assert r["step"]["tool"] == "doctor" and r["show"]["unsaved"] == 1
    assert r["show"]["doctor"]["error"] == 0
    assert _file(c) == old

    old = c.post("/api/looks/build", json=LOOKS).data
    r = c.post("/api/looks/apply", json=LOOKS).get_json()
    assert r["step"]["title"].endswith("1 chasers")
    assert _file(c) == old

    fx = c.get("/api/reducer/fixtures").get_json()["fixtures"]
    keep = [f["id"] for f in fx if "Slim Spot" not in f["model"]]
    plan = {"keep": keep, "repatch": {keep[0]: {"name": "Drums"}}}
    old = c.post("/api/reducer/reduce", json=plan).data
    r = c.post("/api/reducer/apply", json=plan).get_json()
    assert r["step"]["title"].startswith(f"kept {len(keep)} fixtures")
    assert _file(c) == old

    fid = str(c.get("/api/reducer/fixtures").get_json()["fixtures"][0]["id"])
    body = {"scales": {fid: 0.5}}
    old = c.post("/api/brightness/apply", json=body).data
    r = c.post("/api/brightness/apply-show", json=body).get_json()
    assert r["step"]["tool"] == "brightness"
    assert _file(c) == _canon(old)

    st = c.get("/api/show/status").get_json()
    assert st["steps"] == 4 and st["changed_tools"] == {"doctor": 1, "reducer": 1, "looks": 1,
                                                        "brightness": 1}
    assert p.read_bytes() == before                      # the opened file is never written


def test_undo_to_any_step(client):
    c, _ = client
    start = _file(c)
    n_start = len(c.get("/api/functions").get_json())
    c.post("/api/doctor/apply", json={"keys": _doctor_keys(c)})
    after_fix = _file(c)
    c.post("/api/looks/apply", json=LOOKS)
    assert c.get("/api/show/history").get_json()["steps"][1]["tool"] == "looks"
    st = c.post("/api/show/undo", json={}).get_json()["show"]          # the last step
    assert st["steps"] == 1 and _file(c) == after_fix
    c.post("/api/looks/apply", json=LOOKS)
    st = c.post("/api/show/undo", json={"n": 1}).get_json()["show"]    # back to the start
    assert st["steps"] == 0 and st["changed_tools"] == {} and _file(c) == start
    assert c.post("/api/show/undo", json={}).status_code == 400
    # the parsed tables follow the show: the looks' functions are gone again
    assert len(c.get("/api/functions").get_json()) == n_start


def test_save_writes_new_file_and_one_report(client, tmp_path):
    c, p = client
    before = p.read_bytes()
    c.post("/api/doctor/apply", json={"keys": _doctor_keys(c)})
    c.post("/api/looks/apply", json=LOOKS)
    assert c.post("/api/show/save", json={"path": str(p)}).status_code == 400   # never the original
    out = tmp_path / "Fest_v2.qxw"
    r = c.post("/api/show/save", json={"path": str(out)}).get_json()
    assert r["ok"] and out.exists() and p.read_bytes() == before
    rep = (tmp_path / "Fest_v2_report.txt").read_text(encoding="utf-8")
    assert "Opened:  Fest.qxw" in rep and "Saved as: Fest_v2.qxw" in rep
    assert "Step 1 — Workspace Doctor" in rep and "Step 2 — Look Builder" in rep and "── FIXES" in rep
    st = r["show"]
    assert st["unsaved"] == 0 and st["changed_tools"] == {} and st["suggested_name"] == "Fest_v3.qxw"
    # keep working after saving
    c.post("/api/brightness/apply-show", json={"scales": {"1": 0.8}})
    st = c.get("/api/show/status?doctor=0").get_json()
    assert st["unsaved"] == 1 and st["changed_tools"] == {"brightness": 1}
    # the saved file opens as a show of its own
    assert c.post("/api/load", json={"path": str(out)}).status_code == 200
    assert c.get("/api/show/status?doctor=0").get_json()["steps"] == 0


def test_saved_after_dialog_writes_report_next_to_file(client, tmp_path):
    c, _ = client
    c.post("/api/doctor/apply", json={"keys": _doctor_keys(c)})
    out = tmp_path / "picked.qxw"
    out.write_bytes(_file(c))                      # what the Save dialog does
    r = c.post("/api/show/saved", json={"qxw_path": str(out)}).get_json()
    assert r["report_name"] == "picked_report.txt" and (tmp_path / "picked_report.txt").exists()
    assert r["show"]["unsaved"] == 0


def test_stage_edits_are_part_of_the_show(client):
    """Stage & Meshes edits go straight into the show: one step while editing."""
    c, _ = client
    s = c.get("/api/stage/state").get_json()
    c.post("/api/stage/op", json={"op": "stage", "type": 1, "w": s["stage"]["w"] + 1000})
    c.post("/api/stage/op", json={"op": "stage", "d": s["stage"]["d"] + 500})
    h = c.get("/api/show/history").get_json()["steps"]
    assert [x["tool"] for x in h] == ["stage"] and h[0]["edits"] == 2
    old = c.post("/api/stage/save", json={}).data            # the old export
    assert _file(c) == old
    c.post("/api/stage/op", json={"op": "undo"})
    assert c.get("/api/show/history").get_json()["steps"][0]["edits"] == 1
    # another tool changes the show: the stage edits are kept
    c.post("/api/doctor/apply", json={"keys": _doctor_keys(c)})
    s = c.get("/api/stage/state").get_json()
    assert s["stage"]["type_name"] == "Simple box" and not s["dirty"]
    c.post("/api/stage/op", json={"op": "undo"})             # nothing left in this working copy
    assert [x["tool"] for x in c.get("/api/show/history").get_json()["steps"]] == ["stage", "doctor"]


def test_touch_counts_edits_of_one_tool_in_one_step(client):
    show.touch("triggers", "bindings edited")
    show.touch("triggers")
    st = show.status()
    assert st["steps"] == 1 and show.history()[0]["edits"] == 2
    show.touch("vceditor")
    show.touch("triggers")
    assert [s["tool"] for s in show.history()] == ["triggers", "vceditor", "triggers"]
    show.cancel_touch()
    assert show.status()["steps"] == 2


def test_live_edits_become_steps(client):
    c, _ = client
    items = c.get("/api/triggers/").get_json()
    items = items if isinstance(items, list) else items.get("items", items.get("triggers", []))
    uid = items[0]["uid"]
    c.patch(f"/api/triggers/{uid}", json={"key": "F12", "universe": "", "channel": ""})
    c.patch(f"/api/triggers/{uid}", json={"key": "F11", "universe": "", "channel": ""})
    c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra"})
    c.post("/api/vc/op", json={"op": "new_page", "caption": "Extra 2"})
    h = c.get("/api/show/history").get_json()["steps"]
    assert [(x["tool"], x["edits"]) for x in h] == [("triggers", 2), ("vceditor", 2)]
    c.post("/api/vc/undo", json={})
    h = c.get("/api/show/history").get_json()["steps"]
    assert h[-1]["edits"] == 1
    assert c.get("/api/show/status?doctor=0").get_json()["changed_tools"] == {"triggers": 1, "vceditor": 1}
    c.post("/api/show/undo", json={"n": 1})
    assert not any(t.get("key") == "F11" for t in _items(c))


def _items(c):
    items = c.get("/api/triggers/").get_json()
    return items if isinstance(items, list) else items.get("items", items.get("triggers", []))


def test_redo_brings_back_what_undo_took(client):
    c, _ = client
    c.post("/api/doctor/apply", json={"keys": _doctor_keys(c)})
    c.post("/api/looks/apply", json=LOOKS)
    full = _file(c)
    st = c.post("/api/show/undo", json={"n": 1}).get_json()["show"]
    assert st["steps"] == 0 and st["redo"] == 2
    st = c.post("/api/show/redo", json={}).get_json()["show"]
    assert st["steps"] == 2 and st["redo"] == 0 and _file(c) == full
    assert c.post("/api/show/redo", json={}).status_code == 400
    c.post("/api/show/undo", json={})
    c.post("/api/brightness/apply-show", json={"scales": {"1": 0.8}})     # a new change
    assert c.get("/api/show/status?doctor=0").get_json()["redo"] == 0
    assert c.post("/api/show/redo", json={}).status_code == 400
