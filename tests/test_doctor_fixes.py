"""Workspace Doctor auto-fixes (WORKPLAN Phase 2.1)."""
import os
import re
import xml.etree.ElementTree as ET

from core import qxw_io
from core.doctor import check, load_qxf_defs
from core.doctor import fixes
from core.doctor.__main__ import main as cli_main
from tests.test_doctor import (CORPUS, DEFS, FULL, PROGRAM, STROBE, button, chaser,
                               scene, ws)

ALL_DEFS = load_qxf_defs([CORPUS, os.path.join(os.path.dirname(CORPUS), "fixtures")])


def fn(root, fid):
    return next(f for f in root.find("Engine").findall("Function") if f.get("ID") == fid)


def fids(root):
    return [f.get("ID") for f in root.find("Engine").findall("Function")]


def test_d003_dangling_removed():
    root = ws(chaser("5", ["1", "404", "2"]) + scene("1") + scene("2")
              + scene("6", fixture="9"), button(3, "404"))
    r = fixes.fix(root, DEFS, codes={"D003"})
    assert not r.after.by_code("D003")
    steps = [s.text for s in fn(r.root, "5").findall("Step")]
    assert steps == ["1", "2"]
    assert [s.get("Number") for s in fn(r.root, "5").findall("Step")] == ["0", "1"]
    assert fn(r.root, "6").findall("FixtureVal") == []
    btn = next(b for b in r.root.iter("Button") if b.get("ID") == "3")
    assert btn.find("Function").get("ID") == fixes.NONE_ID


def test_cuelist_without_chaser_not_fixable():
    root = ws(scene("1"), button(2, "1") + '<CueList Caption="S" ID="4"><Chaser>4294967295</Chaser></CueList>')
    r = fixes.fix(root, DEFS, codes={"D003"})
    assert r.actions == [] and r.skipped and "no automatic fix" in r.skipped[0]["reason"]


def test_d004_remove_empty_with_cascade():
    f = (scene("1") + '<Function ID="2" Type="Scene" Name="Empty"><FixtureVal ID="0"/></Function>'
         + chaser("3", ["1", "2", "1"]))
    r = fixes.fix(ws(f, button(9, "3") + button(12, "2")), DEFS, codes={"D004"})
    assert "2" not in fids(r.root)
    assert [s.text for s in fn(r.root, "3").findall("Step")] == ["1", "1"]
    btn = next(b for b in r.root.iter("Button") if b.get("ID") == "12")
    assert btn.find("Function").get("ID") == fixes.NONE_ID
    assert not r.after.by_code("D003")


def test_d005_completed_at_neutral():
    r = fixes.fix(ws(scene("1", "0,255,1,255"), button(2, "1")), DEFS, codes={"D005"})
    v = fn(r.root, "1").find("FixtureVal").text
    assert v == "0,255,1,255,2,0,3,0,4,0,5,0,6,0"
    assert not r.after.by_code("D005")


def test_d006_to_neutral():
    r = fixes.fix(ws(scene("1", STROBE) + scene("2", PROGRAM), button(3, "1") + button(4, "2")),
                  DEFS, codes={"D006"})
    assert fn(r.root, "1").find("FixtureVal").text == FULL.replace("0,255,1,0", "0,255,1,255")
    assert fn(r.root, "2").find("FixtureVal").text.endswith("5,0,6,0")
    assert not r.after.by_code("D006")


def test_d007_scene_copied_for_chaser():
    r = fixes.fix(ws(scene("1") + scene("2") + chaser("3", ["1", "2"]),
                     button(4, "1") + button(5, "3")), DEFS, codes={"D007"})
    steps = [s.text for s in fn(r.root, "3").findall("Step")]
    new = steps[0]
    assert new not in ("1", "2") and fn(r.root, new).get("Name") == "Scene 1 (chaser)"
    assert not r.after.by_code("D007")


def test_d008_creates_panic_reset():
    root = qxw_io.strip_ns(ws(scene("1"), button(2, "1")))
    eng = root.find("Engine")
    eng.remove(fn(root, "900"))
    frame = root.find("VirtualConsole/Frame")
    frame.remove(next(b for b in frame.findall("Button") if b.get("ID") == "900"))
    r = fixes.fix(root, DEFS, codes={"D008"})
    names = {f.get("Name"): f for f in r.root.find("Engine").findall("Function")}
    script, reset = names["PANIC RESET"], names["Reset: neutral state"]
    cmds = [c.text for c in script.findall("Command")]
    assert cmds[0] == "stoponexit%3Afalse" and "stopfunction%3A1" in cmds
    assert f"startfunction%3A{reset.get('ID')}" in cmds and cmds[-1] == f"stopfunction%3A{script.get('ID')}"
    assert reset.find("FixtureVal").text == "0,0,1,0,2,0,3,0,4,0,5,0,6,0"
    btn = [b for b in r.root.iter("Button") if b.get("Caption") == "PANIC RESET"]
    assert btn and btn[0].find("Function").get("ID") == script.get("ID")
    assert not r.after.by_code("D008") and not r.after.errors


def test_d017_panic_scene_wrapped_in_script():
    path = os.path.join(CORPUS, "Pub_6fix.qxw")
    r = fixes.fix(qxw_io.load_qxw(path).getroot(), DEFS, codes={"D017"})
    assert not r.after.warnings and not r.after.errors
    scripts = [f for f in r.root.find("Engine").findall("Function") if f.get("Type") == "Script"]
    [s] = scripts
    assert s.get("Name") == "🚨 PANIC RESET (kill auto modes)"
    assert fn(r.root, "3000").get("Name").endswith("(state)")
    runs = {b.find("Function").get("ID") for b in r.root.iter("Button")
            if "PANIC RESET" in (b.get("Caption") or "")}
    assert runs == {s.get("ID")}


def test_d002_function_renumbered():
    r = fixes.fix(ws(scene("1") + scene("1", name="Other"), button(2, "1")), DEFS, codes={"D002"})
    assert sorted(fids(r.root), key=int) == ["1", "900", "901"] or len(set(fids(r.root))) == len(fids(r.root))
    assert not r.after.by_code("D002")


def test_festival_default_fix_and_determinism():
    root = qxw_io.load_qxw(os.path.join(CORPUS, "Festival_14fix.qxw")).getroot()
    before = qxw_io.qxw_bytes(root)
    a = fixes.fix(root, ALL_DEFS, codes=fixes.DEFAULT_CODES)
    b = fixes.fix(root, ALL_DEFS, codes=fixes.DEFAULT_CODES)
    assert qxw_io.qxw_bytes(root) == before                    # input untouched
    assert qxw_io.qxw_bytes(a.root) == qxw_io.qxw_bytes(b.root)
    assert not a.after.errors
    assert set(a.after.counts()) & {"D002", "D005", "D017"} == set()
    assert "D016" in a.after.counts()                          # removals not by default


def test_keys_pick_single_findings():
    root = ws(scene("1", "0,255") + scene("2", "0,255"), button(3, "1") + button(4, "2"))
    rep = check(root, DEFS)
    first = [f for f in rep.by_code("D005")][0]
    r = fixes.fix(root, DEFS, keys=[fixes.finding_key(first)])
    assert len(r.after.by_code("D005")) == 1


def test_fix_file_never_overwrites(tmp_path):
    src = tmp_path / "Show_v7.qxw"
    src.write_bytes(open(os.path.join(CORPUS, "Pub_6fix.qxw"), "rb").read())
    before = src.read_bytes()
    out = fixes.fix_file(str(src), DEFS)
    assert out["output"].endswith("Show_v8.qxw") and src.read_bytes() == before
    assert os.path.isfile(out["report_path"]) and out["report_path"].endswith("Show_v8_fix_report.txt")
    text = open(out["report_path"], encoding="utf-8").read()
    assert "Before:  0 error(s), 1 warning(s)" in text and "After:   0 error(s), 0 warning(s)" in text
    head = open(out["output"], "rb").read(200)
    assert b"<!DOCTYPE Workspace>" in head


def test_cli_fix(tmp_path, capsys):
    src = tmp_path / "Fest.qxw"
    src.write_bytes(open(os.path.join(CORPUS, "Festival_14fix.qxw"), "rb").read())
    assert cli_main([str(src), "--fix", "--min-severity", "error"]) == 0   # the D002 error fixed
    out = capsys.readouterr().out
    assert "Fest_v2.qxw" in out and (tmp_path / "Fest_v2_fix_report.txt").exists()


# ── D010 / D011 / D013 / D014 (checks + fixes) ───────────────────────────────

def _two_pages(first_has_cuelist=False):
    root = qxw_io.strip_ns(ws(scene("1") + chaser("5", ["1", "1"]), button(2, "1")))
    vc = root.find("VirtualConsole")
    p1 = vc.find("Frame")
    ET.SubElement(p1, "WindowState", {"X": "0", "Y": "0", "Width": "800", "Height": "600"})
    p2 = ET.SubElement(vc, "Frame", {"Caption": "Setlist", "ID": "50"})
    ET.SubElement(p2, "WindowState", {"X": "0", "Y": "0", "Width": "800", "Height": "600"})
    cl = ET.SubElement(p1 if first_has_cuelist else p2, "CueList", {"Caption": "Songs", "ID": "51"})
    ET.SubElement(cl, "Chaser").text = "5"
    return root


def test_d010_setlist_page_moved_first():
    root = _two_pages()
    [f] = check(root, DEFS).by_code("D010")
    assert f.severity == "info" and "page 2" in f.message
    r = fixes.fix(root, DEFS, codes={"D010"})
    assert r.root.find("VirtualConsole").find("Frame").get("Caption") == "Setlist"
    assert not r.after.by_code("D010")
    assert not check(_two_pages(first_has_cuelist=True), DEFS).by_code("D010")


def test_d011_overflow_moved_inside():
    root = _two_pages()
    btn = next(b for b in root.iter("Button") if b.get("ID") == "2")
    ET.SubElement(btn, "WindowState", {"X": "780", "Y": "10", "Width": "100", "Height": "50"})
    [f] = check(root, DEFS).by_code("D011")
    assert "780,10 size 100×50" in f.message and "page (800×600)" in f.message
    r = fixes.fix(root, DEFS, codes={"D011"})
    ws_ = next(b for b in r.root.iter("Button") if b.get("ID") == "2").find("WindowState")
    assert (ws_.get("X"), ws_.get("Y")) == ("700", "10")
    assert not r.after.by_code("D011")


def test_d013_zero_length_steps():
    body = ('<Function ID="7" Type="Chaser" Name="Z"><Speed FadeIn="0" FadeOut="0" Duration="0"/>'
            '<SpeedModes FadeIn="Default" FadeOut="Default" Duration="Common"/>'
            '<Step Number="0">1</Step><Step Number="1">1</Step></Function>')
    rep = check(ws(scene("1") + body, button(2, "1") + button(3, "7")), DEFS)
    [f] = rep.by_code("D013")
    assert "all step(s) last 0 ms" in f.message and not fixes.fixable(f)


def test_d014_cuelist_empty_chaser():
    root = _two_pages()
    cl = next(root.iter("CueList"))
    cl.find("Chaser").text = "8"
    root.find("Engine").append(ET.fromstring('<Function ID="8" Type="Chaser" Name="Setlist"/>'))
    [f] = check(root, DEFS).by_code("D014")
    assert "chaser 8 'Setlist'" in f.message
