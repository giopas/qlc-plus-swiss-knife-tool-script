"""Ready for QLC+ 5.3.1 (3.13.0).

QLC+ 5.3.1 saves Virtual Console pages without an ID and gives cross-universe
fixtures a mode (Pixel or Fill).  The addressing is checked against the QLC+
code (``Fixture::channelAddress`` at tag QLC+_5.3.1); the page tools are run
on a show whose pages have no ID, as 5.3.1 writes it.
"""
import os
import re
import xml.etree.ElementTree as ET

import pytest

from core import qlc531, qxw_io, upgrade53 as U, vc_ops
from core.doctor import check
from core.doctor import fixes as F

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")

# ── pages without ID ─────────────────────────────────────────────────────────

VC_531 = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Workspace>
<Workspace xmlns="http://www.qlcplus.org/Workspace" CurrentWindow="VirtualConsole">
 <Creator><Name>Q Light Controller Plus</Name><Version>5.3.1</Version></Creator>
 <Engine><Function ID="1" Type="Scene" Name="Red"/><Function ID="2" Type="Chaser" Name="Set"/></Engine>
 <VirtualConsole>
  <Frame Caption="Main">
   <WindowState Visible="True" X="0" Y="0" Width="1650" Height="884"/>
   <Button Caption="Red" ID="1"><WindowState Visible="True" X="10" Y="20" Width="100" Height="40"/><Function ID="1"/></Button>
   <Frame Caption="Box" ID="7"><WindowState Visible="True" X="300" Y="50" Width="400" Height="300"/></Frame>
  </Frame>
  <Frame Caption="Setlist">
   <WindowState Visible="True" X="0" Y="0" Width="1650" Height="884"/>
   <CueList Caption="Songs" ID="3"><WindowState Visible="True" X="10" Y="10" Width="500" Height="300"/><Chaser>2</Chaser></CueList>
  </Frame>
 </VirtualConsole>
</Workspace>'''


def _pages(root):
    return qlc531.pages(root)


def test_pages_saved_by_531_get_an_id_when_read():
    root = qxw_io.loads_qxw(VC_531.encode())
    assert [p.get("ID") for p in _pages(root)] == ["8", "9"]       # above every ID, in page order
    again = qxw_io.loads_qxw(VC_531.encode())
    assert [p.get("ID") for p in _pages(again)] == ["8", "9"]       # the same file, the same IDs


def test_a_page_id_in_the_file_is_kept(tmp_path):
    text = VC_531.replace('<Frame Caption="Main">', '<Frame Caption="Main" ID="40">')
    root = qxw_io.loads_qxw(text.encode())
    assert [p.get("ID") for p in _pages(root)] == ["40", "41"]
    p = tmp_path / "s.qxw"
    p.write_text(VC_531)
    assert [x.get("ID") for x in _pages(qxw_io.load_qxw(str(p)).getroot())] == ["8", "9"]


def test_no_id_references_are_not_counted():
    # a button with no function carries <Function ID="4294967295"/> (QLC+'s "no ID")
    text = VC_531.replace('<Function ID="1"/></Button>', '<Function ID="4294967295"/></Button>')
    root = qxw_io.loads_qxw(text.encode())
    assert [p.get("ID") for p in _pages(root)] == ["8", "9"]
    assert int(vc_ops.new_page(root, "x")["page_id"]) < 4294967295


def test_only_workspaces_are_touched():
    el = ET.fromstring('<FixtureDefinition><VirtualConsole><Frame/></VirtualConsole></FixtureDefinition>')
    assert qlc531.give_pages_ids(el) == 0
    assert el.find("VirtualConsole/Frame").get("ID") is None


def test_page_tools_work_on_a_531_show():
    root = qxw_io.loads_qxw(VC_531.encode())
    pages = vc_ops.list_pages(root)
    assert all(p.get("id") or p.get("ID") for p in pages)
    dup = vc_ops.copy_page(root, "8", "Main 2")
    new = vc_ops.new_page(root, "Empty")
    ids = [w.get("ID") for w in root.iter() if w.get("ID") is not None and w.tag.endswith(("Frame", "Button", "CueList"))]
    assert len(ids) == len(set(ids)), ids
    assert dup["page_id"] and new["page_id"] and dup["page_id"] != new["page_id"]


def test_doctor_on_a_531_show_finds_no_duplicate_ids_and_moves_the_setlist_page():
    root = qxw_io.loads_qxw(VC_531.encode())
    rep = check(root)
    assert not [f for f in rep.findings if f.code == "D002"]
    d010 = [f for f in rep.findings if f.code == "D010"]
    assert d010
    res = F.fix(root, codes={"D010"})
    assert res.actions
    first = qlc531.pages(res.root)[0]
    assert first.get("Caption") == "Setlist"


def test_every_corpus_show_without_page_ids_reads_the_same_pages():
    for name in ("VC_widgets_qlc530.qxw", "QuickStart_club_qlc530.qxw", "Festival_14fix.qxw"):
        raw = open(os.path.join(CORPUS, name), encoding="utf-8").read()
        root = qxw_io.loads_qxw(raw.encode())
        pages = qlc531.pages(root)
        stripped = raw
        for p in pages:
            stripped = re.sub(r'(<Frame[^>]*Caption="%s")([^>]*?) ID="%s"' % (re.escape(p.get("Caption", "")), p.get("ID")),
                              r"\1\2", stripped, count=1)
        again = qxw_io.loads_qxw(stripped.encode())
        assert [p.get("Caption") for p in qlc531.pages(again)] == [p.get("Caption") for p in pages]
        assert all(p.get("ID") for p in qlc531.pages(again))
        assert not [f for f in check(again).findings if f.code == "D002"]


# ── cross-universe addressing (Fixture::channelAddress, QLC+ 5.3.1) ──────────

HEADS_3x4 = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]       # 4 pixels of RGB


def test_fill_runs_straight_on():
    a = qlc531.addresses(0, 508, 12, qlc531.FILL, HEADS_3x4)
    assert a[:4] == [(0, 508), (0, 509), (0, 510), (0, 511)]
    assert a[4:] == [(1, c) for c in range(8)]


def test_pixel_keeps_whole_heads():
    a = qlc531.addresses(0, 508, 12, qlc531.PIXEL, HEADS_3x4)
    # one pixel fits (508-510), the second would straddle: it starts universe 2
    assert a[:3] == [(0, 508), (0, 509), (0, 510)]
    assert a[3:] == [(1, c) for c in range(9)]


def test_pixel_without_heads_is_fill():
    assert qlc531.addresses(0, 508, 12, qlc531.PIXEL, None) == qlc531.addresses(0, 508, 12, qlc531.FILL)


def test_pixel_size_follows_qlc():
    assert qlc531.pixel_size(12, HEADS_3x4) == 3
    assert qlc531.pixel_size(13, HEADS_3x4) == 1           # heads don't cover the channels
    assert qlc531.pixel_size(12, []) == 1


def test_pixel_over_several_universes():
    a = qlc531.addresses(2, 0, 3 * 400, qlc531.PIXEL, [[0, 1, 2]] * 400)
    assert a[3 * 170 - 1] == (2, 509)                      # 170 pixels in the first universe
    assert a[3 * 170] == (3, 0)
    assert a[3 * 340] == (4, 0)


def test_legacy_flag_is_pixel_in_531_and_straight_on_before():
    assert qlc531.addresses(0, 508, 12, qlc531.LEGACY, HEADS_3x4) == \
        qlc531.addresses(0, 508, 12, qlc531.PIXEL, HEADS_3x4)
    assert qlc531.addresses(0, 508, 12, qlc531.LEGACY, HEADS_3x4, (5, 3, 0)) == \
        qlc531.addresses(0, 508, 12, qlc531.FILL, HEADS_3x4)


def test_a_fixture_that_does_not_fit_moves_to_address_1():
    assert qlc531.addresses(0, 508, 12, qlc531.NONE) == [(0, c) for c in range(12)]
    assert qlc531.does_not_fit(508, 12) and not qlc531.does_not_fit(500, 12)


def test_cross_mode_read_and_written_where_qlc_writes_it():
    fx = ET.fromstring("<Fixture><Name>Bar</Name><Universe>0</Universe><Address>508</Address></Fixture>")
    assert qlc531.cross_mode(fx) == qlc531.NONE
    qlc531.set_cross_mode(fx, qlc531.FILL)
    assert [c.tag for c in fx] == ["Name", "Universe", "CrossUniverse", "Address"]
    assert fx.findtext("CrossUniverse") == "Fill" and qlc531.cross_mode(fx) == qlc531.FILL
    fx.find("CrossUniverse").text = "True"
    assert qlc531.cross_mode(fx) == qlc531.LEGACY
    qlc531.set_cross_mode(fx, qlc531.NONE)
    assert fx.find("CrossUniverse") is None


# ── Doctor and Upgrade ───────────────────────────────────────────────────────

DEFS = [{"manufacturer": "Test", "model": "Bar", "mode_channels": {"12ch": [f"c{i}" for i in range(12)]},
         "mode_heads": {"12ch": HEADS_3x4}},
        {"manufacturer": "Test", "model": "Par", "mode_channels": {"3ch": ["R", "G", "B"]}}]


def _rig(*fixtures):
    fx = "".join(
        f'<Fixture><Manufacturer>Test</Manufacturer><Model>{m}</Model><Mode>{mode}</Mode>'
        f'<ID>{i}</ID><Name>{m} {i}</Name><Universe>{u}</Universe>{cross}'
        f'<Address>{a}</Address><Channels>{n}</Channels></Fixture>'
        for i, (m, mode, u, a, n, cross) in enumerate(fixtures))
    return qxw_io.loads_qxw(
        f'<?xml version="1.0"?><Workspace xmlns="http://www.qlcplus.org/Workspace">'
        f'<Creator><Name>Q Light Controller Plus</Name><Version>5.3.0</Version></Creator>'
        f'<Engine>{fx}</Engine></Workspace>'.encode())


BAR_TRUE = ("Bar", "12ch", 0, 508, 12, "<CrossUniverse>True</CrossUniverse>")
BAR_FILL = ("Bar", "12ch", 0, 508, 12, "<CrossUniverse>Fill</CrossUniverse>")


def _codes(root, code):
    return [f for f in check(root, DEFS).findings if f.code == code]


def test_d009_checks_the_next_universe():
    root = _rig(BAR_FILL, ("Par", "3ch", 1, 2, 3, ""))       # bar reaches U2.1-8, par sits on U2.3-5
    d = _codes(root, "D009")
    assert len(d) == 1 and "U2.3" in d[0].message
    clear = _rig(BAR_FILL, ("Par", "3ch", 1, 8, 3, ""))
    assert not _codes(clear, "D009")


def test_d026_a_fixture_that_does_not_fit():
    root = _rig(("Bar", "12ch", 0, 508, 12, ""))
    d = _codes(root, "D026")
    assert len(d) == 1 and "address 1" in d[0].message
    assert not _codes(root, "D009")


def test_d027_legacy_flag_and_its_fix():
    root = _rig(BAR_TRUE)
    d = _codes(root, "D027")
    assert len(d) == 1 and "U1.512" in d[0].message and "U2.1" in d[0].message
    res = F.fix(root, DEFS, codes={"D027"})
    assert res.actions and not [f for f in res.after.findings if f.code == "D027"]
    assert res.root.find("Engine/Fixture/CrossUniverse").text == "Fill"
    assert "D027" in F.DEFAULT_CODES


def test_d027_quiet_when_both_versions_agree():
    assert not _codes(_rig(("Bar", "12ch", 0, 500, 12, "<CrossUniverse>True</CrossUniverse>")), "D027")
    assert not _codes(_rig(("Bar", "12ch", 0, 506, 12, "<CrossUniverse>True</CrossUniverse>")), "D027")


def test_upgrade_step_writes_fill_and_is_ticked_by_default():
    root = _rig(BAR_TRUE)
    a = U.analyse(root, DEFS)
    step = next(s for s in a["steps"] if s["id"] == "crossuniverse")
    assert step["count"] == 1 and "crossuniverse" in a["defaults"]
    assert a["latest"] == "5.3.1" and a["newer"] is False
    new, acts = U.upgrade(root, DEFS, ["crossuniverse"])
    assert [x["step"] for x in acts] == ["crossuniverse"]
    assert new.find("Engine/Fixture/CrossUniverse").text == "Fill"
    _new2, acts2 = U.upgrade(new, DEFS, ["crossuniverse"])
    assert acts2 == []                                         # idempotent
    _n, acts522 = U.upgrade(root, DEFS, ["crossuniverse"], "5.2.2")
    assert acts522                                             # Fill is read by every QLC+ 5


def test_upgrade_targets():
    assert U.target_of("5.3.1") == U.target_of("5.3.0") == U.target_of("5.3") == "5.3"
    assert U.target_of("5.2.2") == "5.2.2"
    assert U.newer_than_known("5.3.2") and U.newer_than_known("5.4.0")
    assert not U.newer_than_known("5.3.1") and not U.newer_than_known("5.2.2")
    root = _rig(BAR_FILL)
    root.find("{http://www.qlcplus.org/Workspace}Creator/{http://www.qlcplus.org/Workspace}Version").text = "5.4.0"
    assert U.analyse(root, DEFS)["newer"] is True
