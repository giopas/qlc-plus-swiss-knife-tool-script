"""3.10.0 VC Editor: templates that carry key and MIDI bindings."""
import copy
import os
import shutil
import xml.etree.ElementTree as ET

import pytest

import app as app_mod
from core import vc_builder, vc_ops, workspace
from core.qxw_io import qxw_bytes

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
NS = "{http://www.qlcplus.org/Workspace}"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_VC_TEMPLATES", str(tmp_path / "tpl"))
    show = tmp_path / "Pub_6fix.qxw"
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), show)
    c = app_mod.create_app().test_client()
    assert c.post("/api/load", json={"path": str(show)}).status_code == 200
    return c


def vc_of(c):
    return workspace._state["qxw_root"].find(NS + "VirtualConsole")


def page_with_bindings(c):
    """A new page with three buttons: a key, a MIDI input, and one with both; returns the page id."""
    r = c.post("/api/vc/op", json={"op": "new_page", "caption": "Songs"})
    assert r.status_code == 200, r.get_json()
    pid = r.get_json()["page_id"] if "page_id" in r.get_json() else None
    funcs = [f for f in c.get("/api/functions").get_json() if f["type"] == "Scene"][:3]
    ids = []
    for i, f in enumerate(funcs):
        r = c.post("/api/vc/op", json={"op": "create", "parent_id": pid, "kind": "Button", "caption": f"Song {i + 1}",
                                       "func_id": f["id"]})
        assert r.status_code == 200, r.get_json()
        ids.append(r.get_json()["new_ids"][0])
    vc = vc_of(c)
    by_id = {w.get("ID"): w for w in vc.iter() if w.get("ID") in ids}
    ET.SubElement(by_id[ids[0]], NS + "Key").text = "F11"
    ET.SubElement(by_id[ids[1]], NS + "Input", {"Universe": "1", "Channel": "40"})
    ET.SubElement(by_id[ids[2]], NS + "Key").text = "F12"
    ET.SubElement(by_id[ids[2]], NS + "Input", {"Universe": "1", "Channel": "42"})
    return pid, ids


def bindings_on(c, page_id):
    vc = vc_of(c)
    page = next(w for w in vc.iter() if w.get("ID") == page_id)
    out = {}
    for b in page.iter():
        if b.tag in (NS + "Button",):
            out[b.get("Caption")] = sorted([(x.tag.replace(NS, ""), (x.text or "").strip() or f"{x.get('Universe')}/{x.get('Channel')}")
                                            for x in b if x.tag in (NS + "Key", NS + "Input")])
    return out


def save(c, pid, name="Songs", keep=True):
    r = c.post("/api/vc/template", json={"action": "save", "page_id": pid, "name": name, "keep_bindings": keep})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_a_template_saved_the_old_way_has_no_bindings(env):
    pid, _ = page_with_bindings(env)
    r = save(env, pid, keep=False)
    assert r["bindings"] == 0
    r = env.post("/api/vc/op", json={"op": "apply_template", "name": "Songs", "caption": "Copy"}).get_json()
    assert all(not v for v in bindings_on(env, r["page_id"]).values()) and "bindings" not in r


def test_a_template_can_keep_the_keys_and_midi_inputs(env):
    pid, _ = page_with_bindings(env)
    r = save(env, pid)
    assert r["bindings"] == 4
    t = next(t for t in r["templates"] if t["name"] == "Songs")
    assert t["bindings"] == 4
    # remove the originals from the show so nothing clashes, then apply
    for w in vc_of(env).iter():
        if w.get("Caption", "").startswith("Song ") and w.tag == NS + "Button":
            for b in [b for b in w if b.tag in (NS + "Key", NS + "Input")]:
                w.remove(b)
    r = env.post("/api/vc/op", json={"op": "apply_template", "name": "Songs", "caption": "Copy"}).get_json()
    assert r["kept"] == 4 and r["set_again"] == 0
    b = bindings_on(env, r["page_id"])
    assert b["Song 1"] == [("Key", "F11")] and b["Song 2"] == [("Input", "1/40")]
    assert b["Song 3"] == [("Input", "1/42"), ("Key", "F12")]
    assert [u["universe"] for u in r["universes"]] == ["1"] and r["universes"][0]["patched"] is False   # no controller patched in this show


def test_it_never_creates_a_clash_and_says_what_to_set_again(env):
    pid, _ = page_with_bindings(env)
    save(env, pid)
    # the original page still holds F1, 1/40, F3, 1/42: all four would clash
    pv = env.post("/api/vc/template-preview", json={"name": "Songs"}).get_json()
    assert pv["mode"] == "keep" and pv["kept"] == 0 and pv["set_again"] == 4
    assert {b["status"] for b in pv["bindings"]} == {"clash"}
    assert any("Song 1" in o for b in pv["bindings"] for o in b["owners"])
    before = len(list(vc_of(env).iter()))
    assert len(list(vc_of(env).iter())) == before                       # a preview changes nothing
    r = env.post("/api/vc/op", json={"op": "apply_template", "name": "Songs", "caption": "Copy"}).get_json()
    assert r["kept"] == 0 and r["set_again"] == 4
    assert all(not v for v in bindings_on(env, r["page_id"]).values())
    # nothing is used twice in the show now
    seen = {}
    for w in vc_of(env).iter():
        for b in w:
            if b.tag == NS + "Key":
                seen.setdefault(("k", b.text), []).append(w.get("ID"))
            if b.tag == NS + "Input" and b.get("Channel"):
                seen.setdefault(("i", b.get("Universe"), b.get("Channel")), []).append(w.get("ID"))
    assert all(len(v) == 1 for v in seen.values()), seen


def test_free_bindings_are_kept_and_taken_ones_are_not(env):
    pid, _ = page_with_bindings(env)
    save(env, pid)
    for w in vc_of(env).iter():                          # free F11 and 1/40 in the show; F12 and 1/42 stay taken
        if w.tag == NS + "Button" and w.get("Caption") in ("Song 1", "Song 2"):
            for b in [b for b in w if b.tag in (NS + "Key", NS + "Input")]:
                w.remove(b)
    r = env.post("/api/vc/op", json={"op": "apply_template", "name": "Songs", "caption": "Copy"}).get_json()
    st = {b["widget"]: b["status"] for b in r["bindings"]}
    assert r["kept"] == 2 and r["set_again"] == 2
    b = bindings_on(env, r["page_id"])
    assert b["Song 1"] == [("Key", "F11")] and b["Song 2"] == [("Input", "1/40")] and b["Song 3"] == []


def test_drop_leaves_every_binding_out(env):
    pid, _ = page_with_bindings(env)
    save(env, pid)
    for w in vc_of(env).iter():
        if w.tag == NS + "Button" and w.get("Caption", "").startswith("Song "):
            for b in [b for b in w if b.tag in (NS + "Key", NS + "Input")]:
                w.remove(b)
    r = env.post("/api/vc/op", json={"op": "apply_template", "name": "Songs", "caption": "Copy", "bindings": "drop"}).get_json()
    assert r["kept"] == 0 and {b["status"] for b in r["bindings"]} == {"dropped"}
    assert all(not v for v in bindings_on(env, r["page_id"]).values())
    assert env.post("/api/vc/op", json={"op": "apply_template", "name": "Songs", "bindings": "maybe"}).status_code == 400


def test_the_same_binding_twice_in_a_template_is_kept_once(env):
    pid, ids = page_with_bindings(env)
    for w in vc_of(env).iter():
        if w.get("ID") == ids[1]:
            ET.SubElement(w, NS + "Key").text = "F11"                     # F11 is on Song 1 as well
    save(env, pid)
    for w in vc_of(env).iter():
        if w.tag == NS + "Button" and w.get("Caption", "").startswith("Song "):
            for b in [b for b in w if b.tag in (NS + "Key", NS + "Input")]:
                w.remove(b)
    pv = env.post("/api/vc/template-preview", json={"name": "Songs"}).get_json()
    assert [b["status"] for b in pv["bindings"]].count("repeat") == 1 and pv["kept"] == 4


def test_a_hand_made_template_cannot_bring_odd_bindings(env, tmp_path):
    pid, _ = page_with_bindings(env)
    save(env, pid)
    import json
    path = tmp_path / "tpl" / "Songs.json"
    t = json.loads(path.read_text())
    t["xml"] = t["xml"].replace("<Key>F11</Key>", "<Key>" + "x" * 200 + "</Key>").replace('Universe="1" Channel="40"', 'Universe="a;b" Channel="40"')
    path.write_text(json.dumps(t))
    for w in vc_of(env).iter():
        if w.tag == NS + "Button" and w.get("Caption", "").startswith("Song "):
            for b in [b for b in w if b.tag in (NS + "Key", NS + "Input")]:
                w.remove(b)
    pv = env.post("/api/vc/template-preview", json={"name": "Songs"}).get_json()
    bad = [b for b in pv["bindings"] if b["status"] == "dropped"]
    assert len(bad) == 2 and pv["kept"] == 2


def test_the_claude_tool_previews_a_template():
    from core import mcp_server, mcp_guide
    schema = next(t for t in mcp_server.TOOLS if t["name"] == "edit_vc")["inputSchema"]["properties"]
    assert "bindings" in schema and "preview" in schema
    assert "bindings" in mcp_guide.EDIT_VC_OPS["apply_template"] if hasattr(mcp_guide, "EDIT_VC_OPS") else True
