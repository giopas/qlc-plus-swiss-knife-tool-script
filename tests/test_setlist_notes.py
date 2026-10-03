"""Setlist: each cue's note names the original function and its button
(QLC+ keeps step notes: <Step … Note="…">)."""
import os
import re
import shutil

import pytest

import app
from core import qxw_io, workspace

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")):
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    client.tmp = tmp_path
    return client


def _ok(r):
    assert r.status_code < 300, r.get_data(as_text=True)[:400]
    return r


def _funcs(c):
    return {f["name"]: f for f in c.get("/api/functions").get_json()}


def _steps(c, chaser_id):
    root = qxw_io.strip_ns(qxw_io.loads_qxw(c.get("/api/show/file").data))
    ch = next(f for f in root.find("Engine").findall("Function") if f.get("ID") == chaser_id)
    return ch.findall("Step")


def _build(c, songs):
    fn = _funcs(c)
    rows = [{"txt_name": s, "qxw_id": fn[s]["id"], "qxw_name": s} for s in songs]
    _ok(c.post("/api/setlist/4001/details", json={"rows": rows}))
    _ok(c.post("/api/setlist/4001/apply", json={"target_chaser_id": "1756"}))
    return fn


def test_each_cue_names_the_original_and_its_button(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    fn = _build(c, ["Song 22", "Song 07"])
    steps = _steps(c, "1756")
    assert len(steps) == 2
    n0 = steps[0].get("Note")
    assert n0.startswith(f"↪ [{fn['Song 22']['id']}] Song 22")
    assert steps[0].text != fn["Song 22"]["id"]                   # the cue plays a copy
    refs = workspace._button_refs(workspace._state["qxw_root"]).get(fn["Song 22"]["id"])
    if refs:
        assert "button" in n0 and refs[0][1] in n0


def test_a_note_typed_in_qlc_is_kept(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _build(c, ["Song 22", "Song 07"])
    # the user types a note in QLC+ and saves: QLC+ also drops SwissKnifeClone
    out = c.tmp / "Edited.qxw"
    data = c.get("/api/show/file").data.decode("utf-8")
    first = re.search(r'Note="↪ \[\d+\] Song 22[^"]*"', data).group(0)
    data = data.replace(first, 'Note="Smoke on!"', 1)
    data = re.sub(r' SwissKnifeClone="\d+"', "", data)
    out.write_text(data, encoding="utf-8")
    _ok(c.post("/api/load", json={"path": str(out)}))
    # the copies are still known as copies (the reference came back from the notes)
    assert len(workspace._state["clone_ids"]) >= 1
    _build(c, ["Song 22", "Song 07", "Song 19"])
    notes = [s.get("Note") for s in _steps(c, "1756")]
    assert notes[0] == "Smoke on!"
    assert notes[1].startswith("↪ [") and "Song 07" in notes[1]
    assert notes[2].startswith("↪ [") and "Song 19" in notes[2]


def test_reference_read_back_from_the_note():
    root = qxw_io.loads_qxw((
        '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE Workspace>'
        '<Workspace xmlns="http://www.qlcplus.org/Workspace"><Engine>'
        '<Function ID="5" Type="Scene" Name="Song 1"/>'
        '<Function ID="9" Type="Scene" Name="Song 1"/>'
        '<Function ID="20" Type="Chaser" Name="Setlist">'
        '<Step Number="0" Note="↪ [5] Song 1">9</Step></Function>'
        '</Engine></Workspace>').encode())
    workspace._reset()
    workspace._parse_shared_data(root)
    assert workspace._state["clone_base_map"].get("9") == "5"
