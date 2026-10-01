"""2.8 — Compare: two shows by what they do (core.compare, /api/compare)."""
import copy
import os
import shutil

import pytest

import app
from core import compare as cmp, qxw_io
from core.doctor import load_qxf_defs

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


def _load(name):
    return qxw_io.strip_ns(qxw_io.loads_qxw(open(os.path.join(CORPUS, name), "rb").read()))


@pytest.fixture(scope="module")
def defs():
    return load_qxf_defs([CORPUS])


def test_a_show_equals_itself(defs):
    r = cmp.compare(_load("Pub_6fix.qxw"), _load("Pub_6fix.qxw"), defs)
    assert r["identical"] and r["total"]["same"] > 100
    assert "functionally the same" in cmp.report(r)


def test_ids_do_not_matter(defs):
    """Renumber every function: still the same show."""
    a, b = _load("Pub_6fix.qxw"), _load("Pub_6fix.qxw")
    ids = {f.get("ID"): str(int(f.get("ID")) + 7000) for f in b.find("Engine").findall("Function")}
    for f in b.find("Engine").findall("Function"):
        f.set("ID", ids[f.get("ID")])
        for st in f.findall("Step"):
            if (st.text or "").strip() in ids:
                st.text = ids[st.text.strip()]
    for el in b.find("VirtualConsole").iter():
        if el.tag == "Function" and el.get("ID") in ids:          # VC buttons
            el.set("ID", ids[el.get("ID")])
        if el.tag == "Chaser" and (el.text or "").strip() in ids:  # cue lists
            el.text = ids[el.text.strip()]
    r = cmp.compare(a, b, defs)
    assert r["scenes"]["same"] > 50
    assert not r["scenes"]["different"] and not r["chasers"]["different"]
    assert not r["vc"]["different"]
    assert not r["setlist"]["different"]


def test_a_changed_colour_is_found_a_tiny_change_is_not(defs):
    a, b = _load("Pub_6fix.qxw"), _load("Pub_6fix.qxw")
    sc = next(f for f in b.find("Engine").findall("Function")
              if f.get("Type") == "Scene" and f.find("FixtureVal") is not None
              and any(int(v) > 100 for v in (f.find("FixtureVal").text or "0").split(",")[1::2]))
    fv = sc.find("FixtureVal")
    pairs = fv.text.split(",")
    # a tiny change (1/255) is the same look
    c2 = copy.deepcopy(b)
    vals = list(pairs)
    for i in range(1, len(vals), 2):
        if int(vals[i]) > 100:
            vals[i] = str(int(vals[i]) - 1)
            break
    next(f for f in c2.find("Engine").findall("Function") if f.get("ID") == sc.get("ID")).find("FixtureVal").text = ",".join(vals)
    assert cmp.compare(a, c2, defs)["identical"]
    # all channels to 0 = dark: a different look
    fv.text = ",".join(p if i % 2 == 0 else "0" for i, p in enumerate(pairs))
    r = cmp.compare(a, b, defs)
    assert any(sc.get("Name") in x for x in r["scenes"]["different"])


def test_festival_against_pub(defs):
    r = cmp.compare(_load("Festival_14fix.qxw"), _load("Pub_6fix.qxw"), defs)
    f = r["fixtures"]
    assert len(f["only_a"]) == 8 and not f["only_b"]                 # 6 ceiling + 2 PARs not in the pub
    assert len(f["different"]) == 6 and all("name" in x for x in f["different"])   # renamed
    assert any("Singer Pair" in x for x in r["groups"]["only_b"])
    assert not r["identical"]
    text = cmp.report(r, "Festival", "Pub")
    assert "Fixtures and patch" in text and "only in the other file" in text


def test_route(tmp_path):
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), tmp_path / "Pub_6fix.qxw")
    shutil.copy(os.path.join(CORPUS, "Festival_14fix.qxw"), tmp_path / "Festival_14fix.qxw")
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(tmp_path / "Pub_6fix.qxw")}).status_code == 200
    d = c.post("/api/compare/run", json={"path": str(tmp_path / "Pub_6fix.qxw")}).get_json()
    assert d["result"]["identical"]
    d = c.post("/api/compare/run", json={"path": str(tmp_path / "Festival_14fix.qxw")}).get_json()
    assert not d["result"]["identical"] and "RESULT" in d["report"]
    assert c.post("/api/compare/run", json={"path": "nope.txt"}).status_code == 400
    assert c.get("/api/compare/report").get_json()["b"] == "Festival_14fix.qxw"


def _cuelist_caption(root, old, new):
    for cl in root.iter("CueList"):
        if cl.get("Caption") == old:
            cl.set("Caption", new)


def test_setlist_pairs_cue_lists_by_their_songs(defs):
    """Pub-test run: 'Setlist: Band A' vs 'Pub Setlist', with a second cue
    list in this show — paired by the songs, not left as only-here."""
    a, b = _load("Pub_6fix.qxw"), _load("Pub_6fix.qxw")
    cap = next(cl.get("Caption") for cl in a.iter("CueList"))
    _cuelist_caption(a, cap, "Setlist: Band A")
    vc = a.find("VirtualConsole")
    extra = copy.deepcopy(next(a.iter("CueList")))
    extra.set("Caption", "Setlist: Band C")
    extra.find("Chaser").text = "999999"
    next(f for f in vc.iter("Frame")).append(extra)
    s = cmp.compare(a, b, defs)["setlist"]
    assert s["same"] == 1 and s["only_a"] == ["Setlist: Band C"] and not s["only_b"]


def test_unused_functions_are_listed_not_counted(defs):
    a, b = _load("Pub_6fix.qxw"), _load("Pub_6fix.qxw")
    import xml.etree.ElementTree as ET
    ET.SubElement(a.find("Engine"), "Function", {"ID": "88888", "Type": "Scene", "Name": "Nobody Plays Me"})
    r = cmp.compare(a, b, defs)
    assert r["identical"] and r["scenes"]["unused_a"] == ["Nobody Plays Me"]
    assert r["total"]["unused_a"] == 1 and "1 unused, only in this show" in cmp.report(r)


def test_a_look_can_be_scene_here_and_collection_there(defs):
    a, b = _load("Pub_6fix.qxw"), _load("Pub_6fix.qxw")
    col = next(f for f in b.find("Engine").findall("Function") if f.get("Type") == "Collection")
    twin = next(f for f in a.find("Engine").findall("Function") if f.get("ID") == col.get("ID"))
    twin.set("Type", "Scene")
    r = cmp.compare(a, b, defs)
    assert any("a Scene here, a Collection in the other" in x for x in r["scenes"]["different"])
