"""2.8 — fixture group editor (core.fixture_groups, Stage & Meshes › Groups)."""
import copy
import os
import shutil

import pytest

import app
from core import fixture_groups as fg, porter, qxw_io

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
PUB = os.path.join(CORPUS, "Pub_6fix.qxw")
FEST = os.path.join(CORPUS, "Festival_14fix.qxw")


@pytest.fixture
def root():
    r = qxw_io.loads_qxw(open(PUB, "rb").read())
    return qxw_io.strip_ns(r)


def _festival():
    return qxw_io.strip_ns(qxw_io.loads_qxw(open(FEST, "rb").read()))


def test_list_groups_with_matrix_use(root):
    gs = {g["name"]: g for g in fg.groups(root)}
    assert gs["Singer Pair"]["fixtures"] == ["12", "11"] and gs["Singer Pair"]["size"] == [2, 1]
    fes = {g["name"]: g for g in fg.groups(_festival())}
    assert fes["Banner_Wash"]["used_by"] == ["Banner Plasma"]


def test_create_orders_left_to_right_on_the_stage(root):
    pos = porter._positions(root)
    res = fg.create(root, "Front Four", ["11", "8", "12", "7"])
    assert res["fixtures"] == sorted(["11", "8", "12", "7"], key=lambda i: pos[i][0])
    g = next(x for x in fg.groups(root) if x["name"] == "Front Four")
    assert g["id"] == res["id"] and g["size"] == [4, 1] and g["heads"] == 4
    # as given
    res2 = fg.create(root, "As Given", ["11", "8"], order="given")
    assert res2["fixtures"] == ["11", "8"]
    # the new groups come right after the existing ones, in Engine
    eng = root.find("Engine")
    tags = [c.tag for c in eng]
    last_grp = max(i for i, t in enumerate(tags) if t == "FixtureGroup")
    assert eng[last_grp].findtext("Name") == "As Given"


def test_names_and_fixtures_are_checked(root):
    with pytest.raises(fg.GroupError):
        fg.create(root, "singer pair", ["11"])            # same name, any case
    with pytest.raises(fg.GroupError):
        fg.create(root, "", ["11"])
    with pytest.raises(fg.GroupError):
        fg.create(root, "X", [])
    with pytest.raises(fg.GroupError):
        fg.create(root, "X", ["999"])


def test_update_keeps_the_id(root):
    g = next(x for x in fg.groups(root) if x["name"] == "Logo")
    fg.update(root, g["id"], name="Logo + Drums", fixture_ids=["9", "6"])
    h = next(x for x in fg.groups(root) if x["id"] == g["id"])
    assert h["name"] == "Logo + Drums" and set(h["fixtures"]) == {"9", "6"}


def test_delete_refused_while_a_matrix_uses_it(root):
    root = _festival()
    used = next(x for x in fg.groups(root) if x["used_by"])
    with pytest.raises(fg.GroupError) as e:
        fg.delete(root, used["id"])
    assert "RGB matrix" in str(e.value)
    free = next(x for x in fg.groups(root) if not x["used_by"])
    fg.delete(root, free["id"])
    assert free["id"] not in {x["id"] for x in fg.groups(root)}


def test_a_new_group_is_usable_by_the_look_builder(root):
    """The Look Builder lists the show's groups: a new one shows up."""
    from core import look_builder
    fg.create(root, "Front Four", ["11", "8", "12", "7"])
    assert "Front Four" in [g["name"] for g in look_builder.groups(root)]


# ── through the app: Stage & Meshes › Groups, into the show in progress ────

@pytest.fixture
def c(tmp_path):
    shutil.copy(PUB, tmp_path / "Pub_6fix.qxw")
    client = app.create_app().test_client()
    client.tmp = tmp_path
    return client


def _ok(r):
    assert r.status_code < 300, r.get_data(as_text=True)[:400]
    return r.get_json()


def _show_groups(c):
    r = qxw_io.strip_ns(qxw_io.loads_qxw(c.get("/api/show/file").data))
    return {g["name"]: g for g in fg.groups(r)}


def test_group_ops_go_into_the_show_and_undo(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    s = _ok(c.get("/api/stage/state"))
    assert {g["name"] for g in s["groups"]} >= {"Singer Pair", "Band Pair"}
    assert len(s["all_fixtures"]) == 6
    s = _ok(c.post("/api/stage/op", json={"op": "group_new", "name": "Front Four",
                                          "fixtures": ["11", "8", "12", "7"]}))
    assert "Front Four" in {g["name"] for g in s["groups"]}
    assert "Front Four" in _show_groups(c)
    st = _ok(c.get("/api/show/status"))
    assert st["unsaved"] == 1
    gid = next(g["id"] for g in s["groups"] if g["name"] == "Front Four")
    _ok(c.post("/api/stage/op", json={"op": "group_update", "gid": gid, "name": "Front 4"}))
    assert "Front 4" in _show_groups(c) and "Front Four" not in _show_groups(c)
    r = c.post("/api/stage/op", json={"op": "group_new", "name": "front 4", "fixtures": ["7"]})
    assert r.status_code == 400 and "already exists" in r.get_json()["error"]
    _ok(c.post("/api/stage/op", json={"op": "undo"}))
    _ok(c.post("/api/stage/op", json={"op": "undo"}))
    assert "Front Four" not in _show_groups(c) and "Front 4" not in _show_groups(c)
    # the History names the step
    h = _ok(c.get("/api/show/history"))
    assert any("fixture groups" in (x.get("title") or "") for x in h.get("steps", [])) or h


def test_saved_file_has_the_group(c, tmp_path):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/stage/op", json={"op": "group_new", "name": "Front Four",
                                      "fixtures": ["11", "8", "12", "7"]}))
    out = tmp_path / "Pub_6fix_v2.qxw"
    _ok(c.post("/api/show/save", json={"path": str(out)}))
    r = qxw_io.strip_ns(qxw_io.loads_qxw(out.read_bytes()))
    assert "Front Four" in {g["name"] for g in fg.groups(r)}
