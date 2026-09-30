"""Show Paperwork (WORKPLAN 2.6): Show Book, Checklist and Tech Rider in one
tool, with presets by reader.  The tech rider leaves your hands, so a venue
document never carries function names, key / MIDI maps, the VC or the Doctor."""
import io
import os
import shutil
import zipfile

import pytest

import app
from core import showbook

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    p = tmp_path / "Pub_6fix.qxw"
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), p)
    client = app.create_app().test_client()
    assert client.post("/api/load", json={"path": str(p)}).status_code == 200
    return client


def _pdf_text(data: bytes) -> str:
    import re
    import zlib
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            out.append(zlib.decompress(m.group(1)).decode("latin-1"))
        except zlib.error:
            pass
    return "\n".join(out)


def test_presets_pick_sections():
    assert showbook.resolve_sections(["rider"], None) == (["rider", "stage_plan"], "Tech Rider")
    assert showbook.resolve_sections(["checklist"], None)[0] == ["stage_plan", "checklist"]
    secs, title = showbook.resolve_sections(["rider", "checklist"], None)
    assert secs == ["rider", "stage_plan", "checklist"] and title == "Tech Rider + Crew Checklist"


def test_rider_never_carries_show_internals(c):
    """Rule, not a tick box: ticking functions / VC / Doctor with the rider does nothing."""
    body = {"presets": ["rider"], "sections": ["functions", "vc_layout", "doctor", "summary",
                                               "scenes", "chasers"], "date": "2026-09-30"}
    doc = c.post("/api/showbook/preview", json=body).get_json()["document"]
    assert set(doc["sections"]) == {"rider", "stage_plan"}
    r = c.post("/api/showbook/export/pdf", json=body)
    assert r.status_code == 200 and r.headers["X-Suggested-Filename"] == "Pub_6fix_TechRider.pdf"
    text = _pdf_text(r.data)
    assert "Tech Rider" in text and "7-Ch RGB LED PAR" in text
    # nothing from the show itself: no function / widget names, no MIDI, no Doctor
    fn = next(f for f in showbook.generate(presets=["operator"])["sections"]["functions"])
    assert fn["name"] not in text and "MIDI" not in text and "Doctor" not in text
    z = zipfile.ZipFile(io.BytesIO(c.post("/api/showbook/export/csv", json=body).data))
    assert sorted(z.namelist()) == ["rider.csv", "stage_plan.csv"]


def test_rider_content(c):
    doc = c.post("/api/showbook/preview", json={"presets": ["rider"]}).get_json()["document"]
    r = doc["sections"]["rider"]
    assert r["total_fixtures"] == 6 and r["total_channels"] == 42 and r["universes"] == [1]
    t = r["types"][0]
    assert (t["quantity"], t["channels"], t["mode"]) == (6, 7, "7 Channel")


def test_crew_checklist_and_show_name(c):
    body = {"presets": ["checklist"], "show_name": "Pub night", "date": "2026-10-03"}
    doc = c.post("/api/showbook/preview", json=body).get_json()["document"]
    rows = doc["sections"]["checklist"]
    assert len(rows) == 6 and rows[0]["position"].endswith(" m")
    assert [(r["universe"], r["address"]) for r in rows] == sorted((r["universe"], r["address"]) for r in rows)
    assert doc["show_name"] == "Pub night" and doc["date"] == "2026-10-03"
    text = _pdf_text(c.post("/api/showbook/export/pdf", json=body).data)
    assert "Load-in checklist" in text and "Pub night" in text and "[ ]" in text
    assert "UPSTAGE" in text                                   # the stage plot page


def test_combined_presets_one_pdf(c):
    r = c.post("/api/showbook/export/pdf", json={"presets": ["rider", "checklist"], "date": "2026-09-30"})
    text = _pdf_text(r.data)
    assert "Lighting - fixtures" in text and "Load-in checklist" in text
    assert r.headers["X-Suggested-Filename"] == "Pub_6fix_TechRider_CrewChecklist.pdf"


def test_operator_book_unchanged(c):
    """The operator preset is the Show Book as before (same sections, same bytes)."""
    a = showbook.export_pdf(showbook.generate(presets=["operator"], date="2026-09-30"))
    b = showbook.export_pdf(showbook.generate(date="2026-09-30"))
    assert len(a) > 10000 and a.replace(b"Show Book", b"") == b.replace(b"Show Book", b"")
    assert c.get("/api/showbook/presets").get_json()["venue_safe"] == ["checklist", "patch", "rider", "stage_plan"]


@pytest.mark.parametrize("paper,size", [("A3 Landscape", b"1190 842"), ("US Letter Portrait", b"612 792"),
                                        ("A4 Landscape", b"842 595"), ("nonsense", b"842 595")])
def test_paper_sizes(c, paper, size):
    r = c.post("/api/showbook/export/pdf", json={"presets": ["rider", "checklist"], "paper": paper})
    assert r.status_code == 200
    import re
    boxes = set(re.findall(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", r.data))
    w, h = size.split()
    assert boxes == {(w, h)} or {(float(a), float(b)) for a, b in boxes} == {(float(w), float(h))}
    # the module default is back afterwards
    assert (showbook._W, showbook._H) == (842.0, 595.0)
