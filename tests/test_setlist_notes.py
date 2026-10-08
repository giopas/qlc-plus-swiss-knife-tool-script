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
    assert n0.startswith(f"↪ [{fn['Song 22']['id']}] ")                # the original's ID
    assert "Song 22" not in n0 or "button" in n0                   # the button, not the cue's name again
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
    first = re.search(r'Note="↪ \[\d+\][^"]*"', data).group(0)
    data = data.replace(first, 'Note="Smoke on!"', 1)
    data = re.sub(r' SwissKnifeClone="\d+"', "", data)
    out.write_text(data, encoding="utf-8")
    _ok(c.post("/api/load", json={"path": str(out)}))
    # the copies are still known as copies (the reference came back from the notes)
    assert len(workspace._state["clone_ids"]) >= 1
    _build(c, ["Song 22", "Song 07", "Song 19"])
    notes = [s.get("Note") for s in _steps(c, "1756")]
    assert notes[0] == "Smoke on!"
    assert notes[1].startswith("↪ [") and ("button" in notes[1] or "Song 07" in notes[1])
    assert notes[2].startswith("↪ [") and ("button" in notes[2] or "Song 19" in notes[2])


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


def test_quick_start_show_gets_a_setlist(tmp_path):
    """A Quick Start show has no CueList: the VC Editor adds one with a new,
    empty setlist chaser; the Setlist then sees its slot and fills it."""
    shutil.copy(os.path.join(CORPUS, "QuickStart_6fix.qxw"), tmp_path / "QS.qxw")
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    c = app.create_app().test_client()
    _ok(c.post("/api/load", json={"path": str(tmp_path / "QS.qxw")}))
    assert c.get("/api/setlist/slots").get_json() == []
    _ok(c.post("/api/vc/op", json={"op": "setlist_cuelist", "chaser_id": "__new__"}))
    slots = c.get("/api/setlist/slots").get_json()
    assert len(slots) == 1 and slots[0]["chaser_name"] == "Setlist"
    fn = {f["name"]: f for f in c.get("/api/functions").get_json()}
    looks = [n for n, f in fn.items() if f["type"] == "Scene"][:2]
    rows = [{"txt_name": n, "qxw_id": fn[n]["id"], "qxw_name": n} for n in looks]
    sid, cid = slots[0]["id"], slots[0]["chaser_id"]
    _ok(c.post(f"/api/setlist/{sid}/details", json={"rows": rows}))
    _ok(c.post("/api/setlist/apply-all", json={}))
    steps = _steps(c, cid)
    assert len(steps) == 2 and all(s.get("Note", "").startswith("↪ [") for s in steps)
    d = c.get("/api/doctor/check").get_json()
    assert d["summary"]["error"] == 0


def test_a_song_without_function_is_reported(c):
    """giopas's test (3 Oct): 'Song 3' had no look and silently vanished."""
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    fn = _funcs(c)
    rows = [{"txt_name": "Song 22", "qxw_id": fn["Song 22"]["id"], "qxw_name": "Song 22"},
            {"txt_name": "New song", "qxw_id": "", "qxw_name": ""}]
    _ok(c.post("/api/setlist/4001/details", json={"rows": rows}))
    d = _ok(c.post("/api/setlist/4001/apply", json={"target_chaser_id": "1756"})).get_json()
    assert d["skipped"] == ["New song"]
    rep = c.get("/api/show/report").get_data(as_text=True)
    assert "Left out (no function assigned): New song" in rep


def test_new_cuelist_is_wide_enough_for_the_notes():
    from core import vc_builder
    assert vc_builder.DEFAULT_SIZE["CueList"][0] >= 700


def test_selected_cuelist_gets_a_new_setlist_and_info_lists_cuelists(tmp_path):
    """3 Oct: the setlist CueList is now on top of 'Add & wire' and in the
    Selection of a CueList (▶ Use for a new setlist); the panel says how many
    CueLists the show has."""
    shutil.copy(os.path.join(CORPUS, "QuickStart_6fix.qxw"), tmp_path / "QS.qxw")
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    c = app.create_app().test_client()
    _ok(c.post("/api/load", json={"path": str(tmp_path / "QS.qxw")}))
    assert c.get("/api/vc/builder-info").get_json()["cuelists"] == []
    d = _ok(c.post("/api/vc/op", json={"op": "create", "parent_id": "0", "kind": "CueList",
                                         "caption": "Mine"})).get_json()
    cl = d["new_ids"][0]
    d = _ok(c.post("/api/vc/op", json={"op": "setlist_cuelist", "chaser_id": "__new__",
                                         "cuelist_id": cl})).get_json()
    info = c.get("/api/vc/builder-info").get_json()
    assert info["cuelists"] == [{"id": cl, "caption": "Mine", "chaser_id": d["chaser_id"]}]
    slots = c.get("/api/setlist/slots").get_json()
    assert [s["chaser_name"] for s in slots] == ["Setlist"]


def test_setlist_cuelist_does_not_cover_the_quick_start_buttons(tmp_path):
    from core import vc_builder
    from core.vc_ops import _vc
    root = qxw_io.load_qxw(os.path.join(CORPUS, "QuickStart_6fix.qxw"))
    d = vc_builder.setlist_cuelist(root, "__new__")
    vc = _vc(root)
    nid = d["new_ids"][0]
    page = next(p for p in vc for c in p if c.get("ID") == nid)
    el = next(c for c in page if c.get("ID") == nid)
    me = vc_builder._rect(el)
    others = [vc_builder._rect(c) for c in page if vc_builder._is_widget(c) and c is not el]
    assert not any(vc_builder._overlaps(me, r) for r in others)
    assert me[2] >= 400


def test_old_cue_lists_get_their_references(c):
    """giopas, 4 Oct: a show built before 2.0.1 (or by hand) — its setlist
    cues get the reference too; a note already there is kept."""
    src = (c.tmp / "Festival_14fix.qxw").read_text(encoding="utf-8")
    first = re.search(r'(<Function ID="4201" Type="Chaser"[^>]*>.*?<Step Number="0")', src, re.S)
    if first:
        src = src.replace(first.group(1), first.group(1) + ' Note="Smoke!"', 1)
    (c.tmp / "Old.qxw").write_text(src, encoding="utf-8")
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Old.qxw")}))
    n = c.get("/api/setlist/notes").get_json()["missing"]
    assert n > 0
    d = _ok(c.post("/api/setlist/notes")).get_json()
    assert d["added"] == n and d["show"]["steps"] == 1
    assert c.get("/api/setlist/notes").get_json()["missing"] == 0
    root = qxw_io.strip_ns(qxw_io.loads_qxw(c.get("/api/show/file").data))
    slots = {s["chaser_id"] for s in c.get("/api/setlist/slots").get_json()}
    notes = [st.get("Note") for f in root.find("Engine").findall("Function") if f.get("ID") in slots
             for st in f.findall("Step") if (st.text or "").strip()]
    assert notes and all(notes)
    assert sum(1 for x in notes if x.startswith("↪ [")) == len(notes) - (1 if first else 0)
    if first:
        assert "Smoke!" in notes
    assert any(" button" in x for x in notes)
    _ok(c.post("/api/show/undo", json={}))                       # one undoable step
    assert c.get("/api/setlist/notes").get_json()["missing"] == n
    assert _ok(c.post("/api/setlist/notes")).get_json()["added"] == n
    assert _ok(c.post("/api/setlist/notes")).get_json()["added"] == 0   # nothing twice


def test_the_copy_of_a_look_points_at_the_original(tmp_path):
    """A cue playing a copy whose marker QLC+ dropped: the original is the
    one function with the same content that a button plays."""
    root = qxw_io.loads_qxw((
        '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE Workspace>'
        '<Workspace xmlns="http://www.qlcplus.org/Workspace"><Engine>'
        '<Function ID="5" Type="Collection" Name="Red"><Step Number="0">1</Step></Function>'
        '<Function ID="9" Type="Collection" Name="Song 1"><Step Number="0">1</Step></Function>'
        '<Function ID="1" Type="Scene" Name="R"/>'
        '<Function ID="20" Type="Chaser" Name="Setlist"><Step Number="0">9</Step></Function>'
        '</Engine><VirtualConsole><Frame Caption=""><Frame Caption="Looks" ID="1">'
        '<Button Caption="Red" ID="2"><Function ID="5"/></Button>'
        '<CueList Caption="Setlist" ID="3"><Chaser>20</Chaser></CueList>'
        '</Frame></Frame></VirtualConsole></Workspace>').encode())
    workspace._reset()
    workspace._state.update(loaded=True, qxw_root=root)
    workspace._parse_shared_data(root)
    workspace._parse_cuelist_slots(root)
    todo = workspace.cue_notes_missing()
    assert [n for _, n, _, _ in todo] == ['↪ [5] button "Red" on Looks']


def test_an_out_of_date_note_of_ours_is_refreshed():
    """giopas, 8 Oct: notes kept an old ID ([4000]) after the show was
    renumbered, and repeated the cue's name instead of naming the button."""
    root = qxw_io.loads_qxw((
        '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE Workspace>'
        '<Workspace xmlns="http://www.qlcplus.org/Workspace"><Engine>'
        '<Function ID="1" Type="Scene" Name="Haze"/>'
        '<Function ID="2" Type="Scene" Name="Red"/>'
        '<Function ID="9" Type="Collection" Name="Song 1"><Step Number="0">1</Step></Function>'
        '<Function ID="20" Type="Chaser" Name="Setlist">'
        '<Step Number="0" Note="↪ [4000] Song 1">9</Step>'
        '<Step Number="1" Note="Smoke!">2</Step>'
        '<Step Number="2">2</Step></Function>'
        '</Engine><VirtualConsole><Frame Caption=""><Frame Caption="Looks" ID="1">'
        '<Button Caption="Big Red" ID="2"><Function ID="2"/></Button>'
        '<CueList Caption="Setlist" ID="3"><Chaser>20</Chaser></CueList>'
        '</Frame></Frame></VirtualConsole></Workspace>').encode())
    workspace._reset()
    workspace._state.update(loaded=True, qxw_root=root)
    workspace._parse_shared_data(root)
    workspace._parse_cuelist_slots(root)
    todo = {sid: n for _, n, sid, _ in workspace.cue_notes_missing()}
    assert todo == {"9": "↪ [9] no button · plays Haze", "2": '↪ [2] button "Big Red" on Looks'}
    workspace.fill_cue_notes()
    assert workspace.cue_notes_missing() == []          # nothing twice; "Smoke!" untouched


def test_saving_brings_the_cue_notes_up_to_date(c):
    """giopas, 8 Oct: buttons added for the songs after the notes were written
    must show in the notes of the saved file."""
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _build(c, ["Song 22", "Song 07"])
    first = _steps(c, "1756")[0]
    workspace.cue_notes_missing()                       # nothing pending after the build
    first_note = first.get("Note")
    root = workspace._state["qxw_root"]
    ch = workspace._find_by_id(root.find("q:Engine", workspace.NS), "Function", "1756")
    ch.findall("q:Step", workspace.NS)[0].set("Note", "↪ [999999] stale")
    out = c.tmp / "Saved.qxw"
    _ok(c.post("/api/show/save", json={"path": str(out)}))
    saved = qxw_io.strip_ns(qxw_io.loads_qxw(out.read_bytes()))
    f = next(x for x in saved.find("Engine").findall("Function") if x.get("ID") == "1756")
    assert f.findall("Step")[0].get("Note") == first_note
