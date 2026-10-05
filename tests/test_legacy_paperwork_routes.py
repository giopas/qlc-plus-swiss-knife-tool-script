"""v2.3 — /api/checklist/* and /api/techrider/* are thin wrappers over Show
Paperwork; the QXW Merger routes are gone (the Porter does it all)."""
import os

import pytest

import app

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture
def c():
    client = app.create_app().test_client()
    r = client.post("/api/load", json={"path": os.path.join(CORPUS, "Pub_6fix.qxw")})
    assert r.status_code == 200
    return client


def test_checklist_wrappers(c):
    assert len(c.get("/api/checklist/fixtures").get_json()) == 6
    txt = c.post("/api/checklist/export-txt").get_data(as_text=True)
    assert "Setup Checklist" in txt and txt.count("☐") == 6
    pdf = c.post("/api/checklist/export-pdf", json={"show_name": "Pub", "paper": "A4 Portrait"})
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF") and "Checklist" in pdf.headers["Content-Disposition"]
    bp = c.post("/api/checklist/export-blueprint-pdf", json={})
    assert bp.status_code == 200 and bp.data.startswith(b"%PDF")


def test_techrider_wrappers(c):
    d = c.get("/api/techrider/summary").get_json()
    assert d["total_fixtures"] == 6 and d["types"] and {"quantity", "patch_range", "dmx_channels"} <= set(d["types"][0])
    assert d["fixture_groups"]
    r = c.post("/api/techrider/export-pdf", json={"show_name": "Pub"})
    assert r.status_code == 200 and r.data.startswith(b"%PDF") and "TechRider" in r.headers["Content-Disposition"]


def test_rider_wrapper_never_carries_the_show_internals(c):
    # same rule as Show Paperwork: the venue preset has no function / VC / MIDI data
    from core import showbook
    doc = showbook.generate(presets=["rider"])
    assert not ({"functions", "scenes", "vc_layout", "doctor"} & set(doc["sections"]))


def test_no_workspace_is_a_clean_400():
    from core import workspace
    client = app.create_app().test_client()
    workspace._state["loaded"] = False
    for url in ("/api/checklist/fixtures", "/api/techrider/summary"):
        assert client.get(url).status_code == 400


def test_the_merger_is_gone(c):
    assert c.post("/api/merger/src/load", json={}).status_code == 404
    with pytest.raises(ImportError):
        __import__("core.merger")
