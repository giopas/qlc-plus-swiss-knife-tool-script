"""Nomenclature profiles and VC style cloning (WORKPLAN 1.1, principle 7)."""
import os

import pytest

from core.quick_start.nomenclature import list_profiles, load_profile
from core.quick_start.vc_style import VCStyle, extract_style_file, list_styles, load_style

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")


# ── nomenclature ─────────────────────────────────────────────────────────────

def test_builtin_profiles_listed_plain_first():
    ids = [p["id"] for p in list_profiles()]
    assert ids[0] == "plain" and "20minutes" in ids


def test_plain_keeps_names():
    n = load_profile("plain")
    assert n.name("Red") == "Red"
    assert n.prefix_of("Red") == ""


@pytest.mark.parametrize("base,cat,kind,expected", [
    ("Red", "all", "static", "AS · Red"),
    ("Color Fade", "all", "dynamic", "AD · Color Fade"),
    ("Dimmer Sweep", "all", "pulse", "AP · Dimmer Sweep"),
    ("Strobe Fast", "all", "fx", "A* · Strobe Fast"),
    ("Plasma", "all", "matrix", "AM · Plasma"),
    # unmapped category / kind → no prefix rather than a wrong one
    ("Moving Heads", "moving_heads", "static", "Moving Heads"),
    ("PANIC RESET", "all", "utility", "PANIC RESET"),
])
def test_20minutes_names(base, cat, kind, expected):
    assert load_profile("20minutes").name(base, cat, kind) == expected


def test_20minutes_legend():
    n = load_profile("20minutes")
    assert set(n.groups) == set("AFSBRDLX")
    assert set(n.effects) == set("SDPM*")
    assert n.prefix_of("AS · Red") == "AS · "
    assert n.prefix_of("Ice Arena") == ""


def test_profile_from_path(tmp_path):
    p = tmp_path / "mine.json"
    p.write_text('{"id":"mine","format":"{group}{effect}-{name}",'
                 '"category_group":{"all":"Z"},"effect_letters":{"static":"s"}}')
    assert load_profile(str(p)).name("Red") == "Zs-Red"


def test_unknown_profile():
    with pytest.raises(ValueError):
        load_profile("nope")


# ── VC style ─────────────────────────────────────────────────────────────────

def test_extract_style_pub():
    st = extract_style_file(os.path.join(CORPUS, "Pub_6fix.qxw"))
    assert (st.page_w, st.page_h) == (1650, 884)
    assert (st.btn_w, st.btn_h) == (164, 42)
    assert st.gap == 8
    assert st.font_button.startswith("Roboto,10")
    assert st.source == "Pub_6fix.qxw"


def test_builtin_compact_equals_extracted():
    built = load_style("compact").to_dict()
    ext = extract_style_file(os.path.join(CORPUS, "Pub_6fix.qxw")).to_dict()
    for k in ("page_w", "page_h", "btn_w", "btn_h", "gap", "header_h", "slider_w",
              "font_button", "font_frame", "font_page"):
        assert built[k] == ext[k], k


def test_style_defaults_and_list():
    assert load_style(None).btn_w == 130
    assert {s["id"] for s in list_styles()} >= {"default", "compact"}
    assert VCStyle({"btn_w": 5}).btn_w == 40        # clamped


def test_unknown_style():
    with pytest.raises(ValueError):
        load_style("nope")


# ── routes ───────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    import app
    c = app.create_app().test_client()
    c.post("/api/quickstart/clear")
    yield c
    c.post("/api/quickstart/clear")


def test_options_roundtrip(client):
    d = client.get("/api/quickstart/options").get_json()
    assert d["nomenclature"] == "plain" and d["style"] == "default"
    d = client.post("/api/quickstart/options",
                    json={"nomenclature": "20minutes", "style": "compact"}).get_json()
    assert d["nomenclature"] == "20minutes" and d["style_data"]["btn_w"] == 164
    d = client.post("/api/quickstart/options",
                    json={"style_path": os.path.join(CORPUS, "Festival_14fix.qxw")}).get_json()
    assert d["style"] == "custom" and d["style_data"]["source"] == "Festival_14fix.qxw"
    r = client.post("/api/quickstart/options", json={"nomenclature": "nope"})
    assert r.status_code == 400
    client.post("/api/quickstart/clear")
    assert client.get("/api/quickstart/options").get_json()["nomenclature"] == "plain"


def test_preview_uses_options(client):
    q = os.path.join(CORPUS, "Generic-7Ch-RGB-PAR.qxf")
    d = client.post("/api/quickstart/load-qxf", json={"path": q}).get_json()["definition"]
    client.post("/api/quickstart/add-fixture",
                json={"key": d.get("key") or f"{d['manufacturer']}::{d['model']}", "quantity": 2})
    client.post("/api/quickstart/options", json={"nomenclature": "20minutes"})
    tree = client.get("/api/quickstart/preview").get_json()["vc_layout"]

    def caps(n):
        yield n.get("caption", "")
        for c in n.get("children", []):
            yield from caps(c)
    assert "AS · Red" in set(caps(tree))


def test_doctor_gates_export(client, monkeypatch):
    """Doctor errors block the Quick Start export (WORKPLAN principle 4)."""
    import core.doctor as doctor
    from core.doctor.report import Finding, make_report
    q = os.path.join(CORPUS, "Generic-7Ch-RGB-PAR.qxf")
    d = client.post("/api/quickstart/load-qxf", json={"path": q}).get_json()["definition"]
    client.post("/api/quickstart/add-fixture",
                json={"key": d.get("key") or f"{d['manufacturer']}::{d['model']}"})
    assert client.post("/api/quickstart/generate", json={}).status_code == 200
    monkeypatch.setattr(doctor, "check", lambda *a, **k: make_report(
        "x", [Finding("D002", "error", "Workspace", "boom", {})], {}))
    r = client.post("/api/quickstart/generate", json={})
    assert r.status_code == 422 and "D002" in r.get_json()["findings"][0]


def test_options_style_upload(client):
    with open(os.path.join(CORPUS, "Pub_6fix.qxw"), "rb") as fh:
        data = {"style_file": (fh, "Pub_6fix.qxw")}
        d = client.post("/api/quickstart/options", data=data,
                        content_type="multipart/form-data").get_json()
    assert d["style"] == "custom" and d["style_data"]["btn_w"] == 164


def test_20minutes_group_letter_from_name():
    n = load_profile("20minutes")
    assert n.name("Front Red", "group:Front", "static") == "FS · Front Red"
    assert n.prefix_of("FS · Front Red") == "FS · "
    assert load_profile("plain").name("Front Red", "group:Front") == "Front Red"


def _load_pars(client, n=4):
    q = os.path.join(CORPUS, "Generic-7Ch-RGB-PAR.qxf")
    d = client.post("/api/quickstart/load-qxf", json={"path": q}).get_json()["definition"]
    client.post("/api/quickstart/add-fixture",
                json={"key": f"{d['manufacturer']}::{d['model']}", "quantity": n})


def test_groups_route(client):
    _load_pars(client)
    d = client.get("/api/quickstart/groups").get_json()
    assert d["auto"] is True and d["groups"][0]["fixtures"] == [0, 1, 2, 3]
    d = client.post("/api/quickstart/groups", json={"groups": [
        {"name": "Front", "fixtures": [0, 1]}, {"name": "Back", "fixtures": [2, 3, 99]}]}).get_json()
    assert d["auto"] is False and d["groups"][1] == {"name": "Back", "fixtures": [2, 3]}
    assert client.post("/api/quickstart/groups", json={"groups": [
        {"name": "A", "fixtures": [0]}, {"name": "a", "fixtures": [1]}]}).status_code == 400
    # removing a fixture renumbers the groups
    client.post("/api/quickstart/remove-fixture", json={"idx": 1})
    d = client.get("/api/quickstart/groups").get_json()
    assert d["groups"] == [{"name": "Front", "fixtures": [0]}, {"name": "Back", "fixtures": [1, 2]}]
    tree = client.get("/api/quickstart/preview").get_json()["vc_layout"]

    def caps(node):
        yield node.get("caption", "")
        for c in node.get("children", []):
            yield from caps(c)
    assert {"GROUP · Front", "GROUP · Back"} <= set(caps(tree))
    assert client.post("/api/quickstart/groups", json={"auto": True}).get_json()["auto"] is True


def test_save_qxf_next_to_workspace(client, tmp_path):
    """QLC+ loads unknown fixtures from '<Mfr>-<Model>.qxf' next to the .qxw."""
    _load_pars(client, 2)
    qxw = tmp_path / "show.qxw"
    qxw.write_bytes(client.post("/api/quickstart/generate", json={}).data)
    d = client.post("/api/quickstart/save-qxf", json={"qxw_path": str(qxw)}).get_json()
    assert d["files"] == ["Generic-7-Ch-RGB-LED-PAR.qxf"]
    assert (tmp_path / "Generic-7-Ch-RGB-LED-PAR.qxf").read_bytes() == \
        open(os.path.join(CORPUS, "Generic-7Ch-RGB-PAR.qxf"), "rb").read()
