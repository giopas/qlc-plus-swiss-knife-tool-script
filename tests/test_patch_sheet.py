"""Patch sheet (Show Paperwork): DIP switches, the A4 page, the thermal
ticket (PDF / text), CSV, and the logo (core/patch_sheet.py, core/pdf_image.py)."""
import base64
import io
import os
import shutil
import struct
import zipfile
import zlib

import pytest

import app
from core import patch_sheet, pdf_image

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


def _png(w, h, ctype, depth=8, pixels=None, plte=None, trns=None):
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = (w * chans * depth + 7) // 8
    raw = b"".join(b"\x00" + (pixels or bytes(stride))[:stride] for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, depth, ctype, 0, 0, 0))
    if plte:
        out += chunk(b"PLTE", plte)
    if trns:
        out += chunk(b"tRNS", trns)
    return out + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")):
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    assert client.post("/api/load", json={"path": str(tmp_path / "Festival_14fix.qxw")}).status_code == 200
    return client


def test_dip_switches():
    assert patch_sheet.dip_on(1) == [1]
    assert patch_sheet.dip_on(8) == [4]
    assert patch_sheet.dip_on(15) == [1, 2, 3, 4]
    assert patch_sheet.dip_on(256, 9) == [9]
    assert patch_sheet.dip_on(512) == [10]
    assert patch_sheet.dip_on(512, 9) == []           # does not fit on 9 switches


def test_sheet_by_universe_and_address(c):
    d = c.post("/api/showbook/preview", json={"presets": ["patch"]}).get_json()["document"]
    assert list(d["sections"]) == ["patch_sheet"]            # venue-safe: nothing else
    ps = d["sections"]["patch_sheet"]
    u = ps["universes"][0]
    addrs = [f["address"] for f in u["fixtures"]]
    assert addrs == sorted(addrs) and ps["total"] == 14
    first = u["fixtures"][0]
    assert first["address"] == 1 and first["end"] == 7 and first["dip"] == [1] and first["channels"] == 7
    assert u["used"] == [1, 154]


def test_pdf_with_logo_and_event(c):
    logo = _png(4, 2, 6, pixels=bytes([255, 0, 0, 128] * 4))
    body = {"presets": ["patch"], "event": "Pub night", "paper": "A4 Portrait",
            "logo": "data:image/png;base64," + base64.b64encode(logo).decode()}
    r = c.post("/api/showbook/export/pdf", json=body)
    assert r.status_code == 200 and r.data.startswith(b"%PDF")
    assert b"/XObject << /Logo" in r.data and b"/SMask" in r.data
    assert r.headers["X-Suggested-Filename"].endswith("_PatchSheet.pdf")


def test_bad_logo_is_refused_cleanly(c):
    r = c.post("/api/showbook/export/pdf", json={"presets": ["patch"], "logo": "data:image/gif;base64,R0lGODlh"})
    assert r.status_code == 400 and "PNG or JPEG" in r.get_json()["error"]


@pytest.mark.parametrize("width,cols", [("58", 32), ("80", 48)])
def test_ticket_text(c, width, cols):
    r = c.post("/api/showbook/export/receipt", json={"width": width, "format": "txt", "event": "Pub night",
                                                      "date": "2026-10-10"})
    assert r.status_code == 200
    text = r.data.decode("utf-8")
    lines = text.splitlines()
    assert max(len(x) for x in lines) <= cols and lines[0] == "Pub night"
    assert "001-007  PA Left (High Side)" in text and "DIP [#.........] ON 1" in text
    assert text.isascii()


def test_ticket_pdf_is_narrow(c):
    r = c.post("/api/showbook/export/receipt", json={"width": "58"})
    assert r.status_code == 200 and b"/MediaBox [0 0 164.40" in r.data
    assert r.headers["X-Suggested-Filename"].endswith("_Patch_58mm.pdf")


def test_csv_has_the_issue_2086_columns(c):
    r = c.post("/api/showbook/export/csv", json={"presets": ["patch"]})
    z = zipfile.ZipFile(io.BytesIO(r.data))
    head = z.read("patch_sheet.csv").decode("utf-8").splitlines()[0]
    assert head.startswith("universe,address,manufacturer,model,mode,name")


@pytest.mark.parametrize("ctype,depth,kw,cs,alpha", [
    (0, 8, {}, "/DeviceGray", False),
    (0, 1, {}, "/DeviceGray", False),
    (2, 8, {}, "/DeviceRGB", False),
    (2, 16, {}, "/DeviceRGB", False),
    (3, 8, {"plte": b"\xff\x00\x00\x00\xff\x00", "trns": b"\x00"}, "/DeviceRGB", True),
    (4, 8, {}, "/DeviceGray", True),
    (6, 8, {}, "/DeviceRGB", True),
])
def test_png_kinds(ctype, depth, kw, cs, alpha):
    im = pdf_image.load(_png(3, 2, ctype, depth, **kw))
    assert (im.width, im.height, im.colorspace) == (3, 2, cs)
    assert (im.smask is not None) == alpha
    chans = 1 if cs == "/DeviceGray" else 3
    assert len(zlib.decompress(im.data)) == 3 * 2 * chans


def test_png_filters_are_undone():
    # one RGB row with the Sub filter: 10,20,30 then +1,+1,+1 → 11,21,31
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    raw = b"\x01" + bytes([10, 20, 30, 1, 1, 1])
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    assert zlib.decompress(pdf_image.load(data).data) == bytes([10, 20, 30, 11, 21, 31])


def test_jpeg_header():
    sof = b"\xff\xc0\x00\x11\x08\x00\x20\x00\x40\x03" + b"\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    im = pdf_image.load(b"\xff\xd8" + sof + b"\xff\xd9")
    assert (im.width, im.height, im.colorspace, im.filter) == (64, 32, "/DeviceRGB", "/DCTDecode")


def test_not_an_image():
    with pytest.raises(pdf_image.ImageError):
        pdf_image.load(b"GIF89a....")


def test_floorshow_sheet(tmp_path):
    shutil.copy(os.path.join(CORPUS, "FloorShow_8fix.qxw"), tmp_path / "F.qxw")
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(tmp_path / "F.qxw")}).status_code == 200
    ps = c.post("/api/showbook/preview", json={"presets": ["patch"]}).get_json()["document"]["sections"]["patch_sheet"]
    names = [f["name"] for u in ps["universes"] for f in u["fixtures"]]
    assert ps["total"] == 8 and "CL: Ceiling Left" in names
    for u in ps["universes"]:
        for f in u["fixtures"]:
            assert sum(1 << (n - 1) for n in f["dip"]) == f["address"]
