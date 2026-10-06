"""Community library (v2.7.0): share and install templates as one plain file."""
import json
import os

import pytest

import app
from core import library as lib, look_builder as lb, profile as prof, qxw_io, vc_builder as vb, vc_ops
from core.quick_start import nomenclature as nm, vc_style as vs

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
FEST = os.path.join(CORPUS, "Festival_14fix.qxw")
STEP = {"title": "Check the show", "method": "POST", "path": "/api/doctor/apply", "body": {}}


@pytest.fixture(autouse=True)
def _stores(tmp_path, monkeypatch):
    for var, name in (("QSK_VC_TEMPLATES", "tpl"), ("QSK_LOOK_PRESETS", "presets.json"),
                      ("QSK_NOMENCLATURE", "nom"), ("QSK_VC_STYLES", "styles"), ("QSK_PROFILES", "profiles"),
                      ("QSK_LOOK_PALETTES", "pal.json")):
        monkeypatch.setenv(var, str(tmp_path / name))


def _fill():
    """One item of every kind, as a user would have made them."""
    r = qxw_io.load_qxw(FEST).getroot()
    vc_ops.fix_duplicate_ids(r)
    page = vb._pages(vc_ops._vc(r))[0].get("ID")
    vb.save_template(r, page, "My page")
    lb.save_palette("Sunset", [{"name": "Amber", "hex": "#FFBF00"}, {"name": "Rose", "hex": "#FF66AA"}])
    lb.save_preset({"name": "My drive", "pattern": "chase", "step_ms": 240})
    os.makedirs(nm.user_dir())
    json.dump({"id": "mine", "label": "My letters", "format": "{group}{effect} · {name}",
               "category_group": {"all": "A"}, "effect_letters": {"static": "S"}},
              open(os.path.join(nm.user_dir(), "mine.json"), "w"))
    os.makedirs(vs.user_dir())
    json.dump({"id": "tab", "label": "Tablet", "btn_w": 160, "btn_h": 70, "gap": 8},
              open(os.path.join(vs.user_dir(), "tab.json"), "w"))
    prof.save({"format": prof.FORMAT, "name": "Pub again", "description": "d", "steps": [STEP], "params": {}})


def _all_selection():
    return [{"kind": i["kind"], "name": i["name"]} for i in lib.inventory()]


def test_inventory_lists_every_kind_and_only_your_items():
    assert lib.inventory() == []
    _fill()
    inv = lib.inventory()
    assert {i["kind"] for i in inv} == {"vc_template", "palette", "look_preset", "nomenclature", "vc_style", "show_profile"}
    assert len(inv) == 6                                   # built-ins are not listed
    assert next(i for i in inv if i["kind"] == "palette")["summary"] == "2 colour(s)"


def test_round_trip_into_another_computer(tmp_path, monkeypatch):
    _fill()
    pack = lib.export_pack(_all_selection(), "Pub kit", "giopas", "what I use")
    path = lib.write_pack(pack, str(tmp_path / "out" / "kit"))
    assert path.endswith(".qsklib.json")
    # a fresh computer: empty stores
    for var, name in (("QSK_VC_TEMPLATES", "t2"), ("QSK_LOOK_PRESETS", "p2.json"), ("QSK_NOMENCLATURE", "n2"),
                      ("QSK_VC_STYLES", "s2"), ("QSK_PROFILES", "pr2"), ("QSK_LOOK_PALETTES", "pa2.json")):
        monkeypatch.setenv(var, str(tmp_path / name))
    assert lib.inventory() == []
    pv = lib.preview(lib.read_pack(path))
    assert [r["status"] for r in pv["items"]] == ["new"] * 6 and pv["title"] == "Pub kit" and pv["author"] == "giopas"
    res = lib.install(lib.read_pack(path))
    assert res["installed"] == 6 and res["refused"] == 0
    assert {(i["kind"], i["name"]) for i in lib.inventory()} == {(i["kind"], i["name"]) for i in pack["items"]}
    # the items work in the tools that use them
    nid = next(p["id"] for p in nm.list_profiles() if p["label"] == "My letters")
    sid = next(p["id"] for p in vs.list_styles() if p["label"] == "Tablet")
    assert nm.load_profile(nid).name("Red", "all", "static") == "AS · Red"
    assert vs.load_style(sid).btn_w == 160
    assert any(p["label"] == "Tablet" and not p["builtin"] for p in vs.list_styles())
    assert any(p["label"] == "My letters" and not p["builtin"] for p in nm.list_profiles())
    assert "own:Sunset" in lb.palettes()
    assert [p["name"] for p in lb.presets() if not p["builtin"]] == ["My drive"]
    assert prof.load("Pub again")["steps"][0]["path"] == "/api/doctor/apply"
    assert any(t["name"] == "My page" for t in vb.list_templates())
    # installing the same file again: nothing to do
    again = lib.install(lib.read_pack(path))
    assert again["installed"] == 0 and again["skipped"] == 6


def test_pack_is_plain_json_with_no_computer_data(tmp_path):
    _fill()
    p = lib.write_pack(lib.export_pack(_all_selection()), str(tmp_path / "k"))
    text = open(p, encoding="utf-8").read()
    data = json.loads(text)
    assert data["format"] == "qsk-library/1" and len(data["items"]) == 6
    assert str(tmp_path) not in text and "controllers" not in text


def test_write_pack_never_overwrites(tmp_path):
    _fill()
    pack = lib.export_pack(_all_selection()[:1])
    a = lib.write_pack(pack, str(tmp_path / "x.qsklib.json"))
    b = lib.write_pack(pack, str(tmp_path / "x.qsklib.json"))
    assert a != b and os.path.isfile(a) and os.path.isfile(b) and b.endswith("x_2.qsklib.json")


def test_export_errors():
    with pytest.raises(lib.LibraryError):
        lib.export_pack([])
    with pytest.raises(lib.LibraryError):
        lib.export_pack([{"kind": "palette", "name": "Nope"}])
    with pytest.raises(lib.LibraryError):
        lib.export_pack([{"kind": "controllers", "name": "SINCO"}])


def test_name_taken_policies():
    _fill()
    pack = lib.export_pack([{"kind": "palette", "name": "Sunset"}])
    other = json.loads(json.dumps(pack))
    other["items"][0]["data"]["colours"] = [{"name": "Blue", "hex": "#0000FF"}]
    pv = lib.preview(other)
    assert pv["items"][0]["status"] == "exists"
    assert lib.preview(pack)["items"][0]["status"] == "same"
    skip = lib.install(other)                              # default: keep mine
    assert skip["skipped"] == 1 and lb.palettes()["own:Sunset"]["colours"][0]["name"] == "Amber"
    rep = lib.install(other, {"0": "replace"})
    assert rep["replaced"] == 1 and lb.palettes()["own:Sunset"]["colours"][0]["name"] == "Blue"
    cp = lib.install(pack, {"0": "copy"})
    assert cp["copied"] == 1 and cp["items"][0]["as"] == "Sunset (2)"
    assert "own:Sunset (2)" in lb.palettes() and "own:Sunset" in lb.palettes()


def test_built_in_names_are_never_replaced():
    pack = {"format": lib.FORMAT, "items": [
        {"kind": "palette", "name": next(iter(lb._load_json("palettes.json")["palettes"].values()))["label"],
         "data": {"colours": [{"name": "X", "hex": "#101010"}]}},
        {"kind": "nomenclature", "name": "plain", "data": {"format": "{name} !"}}]}
    pv = lib.preview(pack)
    assert [r["status"] for r in pv["items"]] == ["reserved", "reserved"]
    res = lib.install(pack, {"0": "replace", "1": "replace"})
    assert res["copied"] == 2 and all(i["as"] != i["name"] for i in res["items"])
    assert nm.load_profile("plain").format == "{name}"            # untouched
    assert lib.install(pack)["skipped"] == 2


def test_leave_a_new_item_out():
    _fill()
    pack = lib.export_pack([{"kind": "palette", "name": "Sunset"}])
    lb.delete_palette("Sunset")
    res = lib.install(pack, {"0": "skip"})
    assert res["skipped"] == 1 and "own:Sunset" not in lb.palettes()


@pytest.mark.parametrize("item,why", [
    ({"kind": "vc_template", "name": "x", "data": {"xml": "<!DOCTYPE a [<!ENTITY e 'x'>]><VCFrame/>"}}, "DOCTYPE"),
    ({"kind": "vc_template", "name": "x", "data": {"xml": "<a><b></a>"}}, "XML"),
    ({"kind": "vc_template", "name": "x", "data": {"xml": "<Other/>"}}, "frame"),
    ({"kind": "palette", "name": "x", "data": {"colours": []}}, "colours"),
    ({"kind": "palette", "name": "x", "data": {"colours": [{"name": "a", "hex": "zzz"}]}}, "colour"),
    ({"kind": "look_preset", "name": "x", "data": {"pattern": "chase", "step_ms": 1}}, "preset"),
    ({"kind": "nomenclature", "name": "x", "data": {"format": "{name} {__class__}"}}, "format"),
    ({"kind": "nomenclature", "name": "x", "data": {"format": "{group}"}}, "format"),
    ({"kind": "vc_style", "name": "x", "data": {"btn_w": "wide"}}, "numbers"),
    ({"kind": "show_profile", "name": "x", "data": {"format": "nope"}}, "profile"),
    ({"kind": "show_profile", "name": "x", "data": {"format": prof.FORMAT, "steps": [
        {"method": "POST", "path": "/api/picker/pick", "body": {}}]}}, "may not"),
    ({"kind": "show_profile", "name": "x", "data": {"format": prof.FORMAT, "steps": [
        {"method": "GET", "path": "/api/doctor/apply", "body": {}}]}}, "may not"),
    ({"kind": "show_profile", "name": "x", "data": {"format": prof.FORMAT, "steps": []}}, "nothing"),
    ({"kind": "show_profile", "name": "x", "data": {"format": prof.FORMAT, "steps": [
        {"method": "POST", "path": "/api/library/install", "body": {}}]}}, "may not"),
    ({"kind": "controllers", "name": "x", "data": {}}, "kind"),
    ({"kind": "palette", "name": "", "data": {}}, "name"),
    ({"kind": "palette", "name": "x" * 200, "data": {}}, "80"),
    ({"kind": "palette", "name": "x", "data": "text"}, "content"),
])
def test_unsafe_or_broken_items_are_refused(item, why):
    pack = {"format": lib.FORMAT, "items": [item]}
    row = lib.preview(pack)["items"][0]
    assert row["status"] == "invalid" and why.lower() in row["reason"].lower(), row
    res = lib.install(pack)
    assert res["refused"] == 1 and res["installed"] == 0 and lib.inventory() == []


def test_one_bad_item_does_not_stop_the_good_ones():
    pack = {"format": lib.FORMAT, "items": [
        {"kind": "palette", "name": "Good", "data": {"colours": [{"name": "A", "hex": "#123456"}]}},
        {"kind": "vc_template", "name": "Bad", "data": {"xml": "<!DOCTYPE x>"}},
        {"kind": "palette", "name": "good", "data": {"colours": [{"name": "A", "hex": "#654321"}]}}]}
    res = lib.install(pack)
    assert (res["installed"], res["refused"]) == (1, 2)           # the duplicate name is refused too
    assert [i["name"] for i in lib.inventory()] == ["Good"]


def test_profile_with_a_folder_path_is_flagged():
    p = {"format": prof.FORMAT, "name": "p", "steps": [dict(STEP, body={"path": "/Users/someone/Shows/a.qxw"})]}
    pack = {"format": lib.FORMAT, "items": [{"kind": "show_profile", "name": "p", "data": p}]}
    assert "folder" in lib.preview(pack)["items"][0]["warning"]
    prof.save(p)
    assert lib.inventory()[0]["private"] is True


def test_read_pack_refuses_what_is_not_a_library(tmp_path):
    for text in ("not json", "[]", json.dumps({"format": "other"}), json.dumps({"format": lib.FORMAT, "items": []})):
        with pytest.raises(lib.LibraryError):
            lib.read_pack(text)
    big = tmp_path / "big.json"
    big.write_bytes(b" " * (lib.MAX_FILE + 1))
    with pytest.raises(lib.LibraryError):
        lib.read_pack(str(big))
    with pytest.raises(lib.LibraryError):
        lib.read_pack({"format": lib.FORMAT, "items": [{}] * (lib.MAX_ITEMS + 1)})


def test_routes_flow(tmp_path):
    _fill()
    c = app.create_app().test_client()
    st = c.get("/api/library/state").get_json()
    assert len(st["items"]) == 6 and len(st["kinds"]) == 6 and "Palettes" in st["folders"]
    sel = [{"kind": i["kind"], "name": i["name"]} for i in st["items"] if i["kind"] in ("palette", "vc_style")]
    r = c.post("/api/library/pack", json={"selection": sel, "title": "Two things"})
    assert r.status_code == 200
    pk = r.get_json()
    assert pk["filename"] == "Two_things.qsklib.json" and pk["items"] == 2
    assert c.post("/api/library/pack", json={"selection": []}).status_code == 400
    assert c.post("/api/library/install", json={}).status_code == 400            # nothing read yet
    f = tmp_path / "in.qsklib.json"
    f.write_text(json.dumps(pk["pack"]))
    pv = c.post("/api/library/read", json={"path": str(f)}).get_json()
    assert [i["status"] for i in pv["items"]] == ["same", "same"]
    lb.delete_palette("Sunset")
    pv = c.post("/api/library/read", json={"text": f.read_text()}).get_json()
    assert sorted(i["status"] for i in pv["items"]) == ["new", "same"]
    res = c.post("/api/library/install", json={"choices": {}, "default": "skip"}).get_json()
    assert res["installed"] == 1 and "own:Sunset" in lb.palettes()
    assert c.post("/api/library/install", json={}).status_code == 400            # consumed
    assert c.post("/api/library/read", json={"path": str(tmp_path / "missing.json")}).status_code == 400
    assert c.post("/api/library/read", json={"text": "{}"}).status_code == 400
    err = c.post("/api/library/read", json={"path": str(tmp_path)}).get_json()["error"]
    assert str(tmp_path) not in err


def test_library_calls_are_not_recorded_in_the_recipe():
    from core import recipe
    assert not recipe.recordable("POST", "/api/library/install")
