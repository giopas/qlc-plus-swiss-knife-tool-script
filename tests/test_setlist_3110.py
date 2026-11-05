"""3.11.0 Setlist Manager: a CueList can be renamed, and a show opens with the
songs its CueList already plays."""
import os
import shutil

import pytest

import app
from core import qxw_io

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")) and " 2." not in f:
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    client.tmp = tmp_path
    r = client.post("/api/load", json={"path": str(tmp_path / "Festival_14fix.qxw")})
    assert r.status_code < 300, r.get_data(as_text=True)[:300]
    return client


def _root(c):
    return qxw_io.strip_ns(qxw_io.loads_qxw(c.get("/api/show/file").data))


def test_existing_cuelist_songs_are_loaded_and_matched(c):
    rows = c.get("/api/setlist/4001/details").get_json()
    root = _root(c)
    eng = root.find("Engine")
    ch = next(f for f in eng.findall("Function") if f.get("ID") == "1756")
    steps = ch.findall("Step")
    assert rows and len(rows) == len(steps)
    by_id = {f.get("ID"): f for f in eng.findall("Function")}
    for row, st in zip(rows, steps):
        fn = by_id[st.text.strip()]
        base = fn.get("SwissKnifeClone")
        assert row["qxw_id"] == (base if base in by_id else st.text.strip())
        assert row["txt_name"]
        assert row["hold"] == st.get("Hold")


def test_rows_typed_by_the_user_win_over_the_cuelist(c):
    c.post("/api/setlist/4001/details", json={"rows": []})
    assert c.get("/api/setlist/4001/details").get_json() == []


def test_empty_cuelist_gives_no_rows(c):
    c.post("/api/vc/op", json={"op": "fix_ids"})
    before = {s["id"] for s in c.get("/api/setlist/slots").get_json()}
    r = c.post("/api/vc/op", json={"op": "setlist_cuelist", "chaser_id": "__new__"})
    assert r.status_code == 200, r.get_json()
    new = next(s for s in c.get("/api/setlist/slots").get_json() if s["id"] not in before)
    assert c.get(f"/api/setlist/{new['id']}/details").get_json() == []


def test_rename_cuelist_and_its_chaser(c):
    r = c.post("/api/vc/op", json={"op": "rename_widget", "widget_id": "4001",
                                   "caption": "Friday set", "chaser_too": True})
    d = r.get_json()
    assert r.status_code == 200, d
    assert d["chaser_renamed"] is True
    slot = next(s for s in c.get("/api/setlist/slots").get_json() if s["id"] == "4001")
    assert slot["caption"] == "Friday set"
    assert slot["chaser_name"] == "Friday set"
    root = _root(c)
    cl = next(e for e in root.iter("CueList") if e.get("ID") == "4001")
    assert cl.get("Caption") == "Friday set"


def test_rename_keeps_chaser_name_when_taken(c):
    fns = c.get("/api/functions").get_json()
    taken = next(f["name"] for f in fns if f["id"] != "1756")
    d = c.post("/api/vc/op", json={"op": "rename_widget", "widget_id": "4001",
                                   "caption": taken, "chaser_too": True}).get_json()
    assert d["chaser_renamed"] is False and "chaser_note" in d


def test_rename_refuses_an_empty_name(c):
    r = c.post("/api/vc/op", json={"op": "rename_widget", "widget_id": "4001", "caption": "  "})
    assert r.status_code == 400


def test_rename_is_undoable(c):
    c.post("/api/vc/op", json={"op": "rename_widget", "widget_id": "4001", "caption": "X"})
    c.post("/api/vc/undo")
    slot = next(s for s in c.get("/api/setlist/slots").get_json() if s["id"] == "4001")
    assert slot["caption"] == "Setlist: Band A"
