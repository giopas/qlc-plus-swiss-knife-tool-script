"""v2.6.0 — the tech rider lists the patch, position / tilt and the set pieces."""
import os
import re
import zlib

import pytest

import app
from core import showbook, workspace

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


@pytest.fixture()
def club(tmp_path, monkeypatch):
    monkeypatch.setenv("QLCPLUS_FIXTURES", str(tmp_path / "none"))
    src = open(os.path.join(CORPUS, "QuickStart_club.qxw"), encoding="utf-8").read()
    (tmp_path / "person.obj").write_text("\n".join(
        f"v {x} {y} {z}" for x in (-0.5, 0.5) for y in (0, 1.8) for z in (-0.3, 0.3)) + "\n")
    mesh = ('<MeshItem ID="0" XPos="2000" YPos="-900" ZPos="1500" Res="person.obj" Name="Singer"/>'
            '<MeshItem ID="1" XPos="0" YPos="0" ZPos="0" Res="person.obj" Name="Hidden one" Hidden="True"/>')
    assert "</Monitor>" in src
    p = tmp_path / "club.qxw"
    p.write_text(src.replace("</Monitor>", mesh + "</Monitor>", 1), encoding="utf-8")
    workspace.load_qxw(str(p))
    return p


def _text(pdf: bytes) -> bytes:
    """All the page streams of a PDF, decompressed."""
    out = b""
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            out += zlib.decompress(m.group(1))
        except zlib.error:
            out += m.group(1)
    return out


def test_tilt_text():
    assert showbook.tilt_text(0) == "straight down"
    assert showbook.tilt_text(45) == "45° to the front"
    assert showbook.tilt_text(315) == "45° to the back"
    assert showbook.tilt_text(90) == "horizontal, to the front"
    assert showbook.tilt_text(270) == "horizontal, to the back"
    assert showbook.tilt_text(180) == "straight up"


def test_rider_without_extras_is_unchanged(club):
    doc = showbook.generate(presets=["rider"], show_name="S", date="2026-10-06")
    assert "detail" not in doc["sections"]["rider"] and "extras" not in doc["sections"]["rider"]


def test_rider_detail(club):
    doc = showbook.generate(presets=["rider"], show_name="S", date="2026-10-06",
                            rider_extras=["patch", "tilt", "meshes", "bogus"])
    r = doc["sections"]["rider"]
    assert r["extras"] == ["patch", "tilt", "meshes"]
    fx = r["detail"]["fixtures"]
    assert len(fx) == r["total_fixtures"] == 6
    assert all("tilt_text" in f and f["channels"] for f in fx)
    assert fx == sorted(fx, key=lambda f: (f["universe"], f["address"]))
    assert any(f["tilt"] for f in fx)                     # Quick Start tilts its fixtures
    names = [m["name"] for m in r["detail"]["meshes"]]
    assert names == ["Singer"]                            # the hidden one is not on the paper
    m = r["detail"]["meshes"][0]
    assert m["bottom"] == 0 and m["h"] == 1800 and m["w"] == 1000
    # still venue-safe: nothing about functions, buttons or bindings
    assert "functions" not in doc["sections"] and "vc_layout" not in doc["sections"]


def test_rider_meshes_optional(club):
    r = showbook.generate(presets=["rider"], rider_extras=["patch"])["sections"]["rider"]
    assert r["detail"]["meshes"] == []


def test_pdf_and_route(club):
    doc = showbook.generate(presets=["rider"], show_name="S", date="2026-10-06",
                            rider_extras=["patch", "tilt", "meshes"])
    pdf = showbook.export_pdf(doc, "A4 Landscape")
    assert pdf.startswith(b"%PDF") and b"Singer" in _text(pdf)
    plain = showbook.export_pdf(showbook.generate(presets=["rider"], show_name="S", date="2026-10-06"), "A4 Landscape")
    assert b"Singer" not in _text(plain) and len(_text(pdf)) > len(_text(plain))
    c = app.create_app().test_client()
    r = c.post("/api/showbook/preview", json={"presets": ["rider"], "rider_extras": ["tilt", "meshes", "x"]})
    assert r.status_code == 200
    assert r.get_json()["document"]["sections"]["rider"]["extras"] == ["tilt", "meshes"]
    r = c.post("/api/showbook/export/pdf", json={"presets": ["rider"], "rider_extras": ["patch"]})
    assert r.status_code == 200 and r.data.startswith(b"%PDF")
