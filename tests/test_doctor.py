"""Workspace Doctor — read-only checks (WORKPLAN Phase 1.0)."""
import json
import os
import subprocess
import sys

import pytest

from core import qxw_io
from core.doctor import ERROR, INFO, check, check_file, load_qxf_defs
from core.doctor.__main__ import main as cli_main

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CORPUS = os.path.join(HERE, "corpus")
BASELINE = json.load(open(os.path.join(CORPUS, "expected_baseline.json"), encoding="utf-8"))
DEFS = load_qxf_defs([CORPUS])

PAR = ("<Fixture><Manufacturer>Generic</Manufacturer><Model>7-Ch RGB LED PAR</Model>"
       "<Mode>7 Channel</Mode><ID>{id}</ID><Name>PAR {id}</Name><Universe>0</Universe>"
       "<Address>{addr}</Address><Channels>7</Channels></Fixture>")
FULL = "0,255,1,0,2,0,3,0,4,0,5,0,6,0"          # all 7 channels, strobe/mode 0
PANIC = ('<Function ID="900" Type="Scene" Name="PANIC RESET">'
         '<FixtureVal ID="0">' + FULL + '</FixtureVal></Function>')
PANIC_BTN = '<Button Caption="PANIC" ID="900"><Function ID="900"/></Button>'


def ws(functions="", vc="", fixtures=None, iomap=""):
    """Build a namespaced workspace root from fragments."""
    fixtures = fixtures if fixtures is not None else PAR.format(id=0, addr=0)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n'
           '<Workspace xmlns="http://www.qlcplus.org/Workspace">'
           '<Creator><Name>Q Light Controller Plus</Name><Version>5.2.2</Version></Creator>'
           f'<Engine>{iomap}{fixtures}{PANIC}{functions}</Engine>'
           f'<VirtualConsole><Frame Caption="Page 1" ID="1">{PANIC_BTN}{vc}</Frame></VirtualConsole>'
           '</Workspace>')
    return qxw_io.loads_qxw(xml.encode("utf-8"))


def scene(fid, values=FULL, name=None, fixture="0"):
    return (f'<Function ID="{fid}" Type="Scene" Name="{name or "Scene " + fid}">'
            f'<FixtureVal ID="{fixture}">{values}</FixtureVal></Function>')


def chaser(fid, steps, name=None, ftype="Chaser"):
    body = "".join(f'<Step Number="{i}">{s}</Step>' for i, s in enumerate(steps))
    return f'<Function ID="{fid}" Type="{ftype}" Name="{name or ftype + " " + fid}">{body}</Function>'


def button(wid, fid, caption=None, action="Toggle"):
    return (f'<Button Caption="{caption or "B" + str(wid)}" ID="{wid}">'
            f'<Function ID="{fid}"/><Action>{action}</Action></Button>')


def codes(rep):
    return rep.counts()


# ── clean baseline ───────────────────────────────────────────────────────────

def test_minimal_clean_workspace():
    rep = check(ws(scene("1"), button(2, "1")), DEFS)
    assert rep.ok
    assert [f.code for f in rep.findings if f.severity != INFO] == []


def test_check_does_not_mutate_input():
    root = ws(scene("1"), button(2, "1"))
    before = qxw_io.qxw_bytes(root)
    check(root, DEFS)
    assert qxw_io.qxw_bytes(root) == before


def test_accepts_stripped_tree():
    root = qxw_io.strip_ns(ws(chaser("5", ["404"])))
    assert "D003" in codes(check(root))


# ── D001 ──────────────────────────────────────────────────────────────────────

def test_d001_missing_doctype(tmp_path):
    p = tmp_path / "x.qxw"
    p.write_bytes(qxw_io.qxw_bytes(ws()).replace(b"<!DOCTYPE Workspace>\n", b""))
    rep = check_file(str(p))
    assert rep.by_code("D001") and not rep.ok


def test_d001_not_well_formed(tmp_path):
    p = tmp_path / "x.qxw"
    p.write_bytes(qxw_io.qxw_bytes(ws())[:-20] + b"</Frame></Workspace>")
    rep = check_file(str(p))
    assert [f.code for f in rep.findings] == ["D001"]
    assert "well-formed" in rep.findings[0].message


def test_d001_wrong_root(tmp_path):
    p = tmp_path / "x.qxw"
    p.write_bytes(b'<?xml version="1.0"?>\n<!DOCTYPE Workspace>\n<FixtureDefinition/>')
    assert "not <Workspace>" in check_file(str(p)).by_code("D001")[0].message


# ── D002 / D003 ──────────────────────────────────────────────────────────────

def test_d002_duplicate_function_and_widget_ids():
    rep = check(ws(scene("1") + scene("1"), button(7, "1") + button(7, "1")), DEFS)
    d = rep.by_code("D002")
    assert {f.ref.get("function") or f.ref.get("widget") for f in d} == {"1", "7"}
    assert all(f.severity == ERROR for f in d)


def test_d003_dangling_references():
    vc = button(3, "404") + '<CueList Caption="Setlist" ID="4"><Chaser>4294967295</Chaser></CueList>'
    rep = check(ws(chaser("5", ["1", "404", "2"]) + scene("1") + scene("2")
                   + scene("6", fixture="9"), vc), DEFS)
    msgs = sorted(f.message for f in rep.by_code("D003"))
    assert msgs == ["CueList has no chaser attached", "step → missing function 404",
                    "values for missing fixture 9", "→ missing function 404"]


def test_d003_cuelist_must_point_to_chaser():
    vc = '<CueList Caption="Setlist" ID="4"><Chaser>1</Chaser></CueList>'
    rep = check(ws(scene("1"), vc), DEFS)
    assert "not a Chaser" in rep.by_code("D003")[0].message


# ── D004 ──────────────────────────────────────────────────────────────────────

def test_d004_empty_and_degenerate():
    f = (scene("1") + '<Function ID="2" Type="Scene" Name="Empty"><FixtureVal ID="0"/></Function>'
         + chaser("3", ["1"]) + chaser("4", ["1", "1"]) + chaser("5", [], ftype="Collection"))
    rep = check(ws(f, button(9, "3") + button(10, "4") + button(11, "5") + button(12, "2")), DEFS)
    got = {f.ref["function"]: f.message for f in rep.by_code("D004")}
    assert got == {"2": "empty scene (no channel values)",
                   "3": "degenerate chaser (1 step)", "5": "empty collection"}


# ── D005 ──────────────────────────────────────────────────────────────────────

def test_d005_incomplete_channels_named_from_qxf():
    rep = check(ws(scene("1", "0,255,1,255,2,0,3,0,4,0,5,0"), button(2, "1")), DEFS)
    [f] = rep.by_code("D005")
    assert "declares 6/7" in f.message and "7 Mode Speed" in f.message
    assert f.ref["missing"] == [6]


def test_d005_works_without_definitions():
    rep = check(ws(scene("1", "0,255"), button(2, "1")))
    assert "declares 1/7" in rep.by_code("D005")[0].message


# ── D006 ──────────────────────────────────────────────────────────────────────

STROBE = "0,255,1,255,2,0,3,0,4,220,5,0,6,0"     # ch5 Strobe = 220
PROGRAM = "0,255,1,0,2,0,3,0,4,0,5,120,6,0"      # ch6 Mode = 120 (auto program)
NO_FLASH = "0,255,1,0,2,0,3,0,4,5,5,5,6,0"       # strobe 5 = "No flash", mode 5 = DMX mode


def test_d006_flags_plain_scene():
    rep = check(ws(scene("1", STROBE, "Red wash") + scene("2", PROGRAM, "Blue"),
                   button(3, "1") + button(4, "2")), DEFS)
    msgs = [f.message for f in rep.by_code("D006")]
    assert len(msgs) == 2
    assert "Strobe = 220 (Stroboscopic slow to fast)" in msgs[0]
    assert "Mode = 120" in msgs[1]


def test_d006_neutral_capability_values_are_safe():
    rep = check(ws(scene("1", NO_FLASH, "Red"), button(2, "1")), DEFS)
    assert not rep.by_code("D006")


@pytest.mark.parametrize("name", ["Red Strobe", "FLASH hit", "C* · Red", "Punk blast",
                                  "Audio React", "Chaos Macro", "FX 3"])
def test_d006_own_name_marks_fx(name):
    assert not check(ws(scene("1", STROBE, name), button(2, "1")), DEFS).by_code("D006")


def test_d006_parent_name_marks_fx():
    """Lesson 1: [401] Scene - Unassigned inside ⚡ STROBE/RED FLASH ⚡ is FX."""
    f = (scene("401", STROBE, "[401] Scene - Unassigned")
         + chaser("1028", ["401"], "[1028] Collection - Unassigned", "Collection")
         + chaser("506", ["1028"], "⚡ STROBE/RED FLASH ⚡", "Collection"))
    assert not check(ws(f, button(3, "506")), DEFS).by_code("D006")


def test_d006_allow_list():
    root = ws(scene("1", STROBE, "Red wash"), button(2, "1"))
    assert check(root, DEFS).by_code("D006")
    assert not check(root, DEFS, allow_fx=["1"]).by_code("D006")


def test_d006_skipped_without_definition_but_reported():
    rep = check(ws(scene("1", STROBE), button(2, "1")))
    assert not rep.by_code("D006") and rep.by_code("I003")


# ── D007 / D008 / D009 / D012 ────────────────────────────────────────────────

def test_d007_scene_on_button_and_in_chaser():
    rep = check(ws(scene("1") + scene("2") + chaser("3", ["1", "2"]),
                   button(4, "1") + button(5, "3")), DEFS)
    [f] = rep.by_code("D007")
    assert f.ref["function"] == "1" and "chaser 3" in f.message


def test_d008_panic_missing_or_not_on_button():
    root = qxw_io.strip_ns(ws(scene("1"), button(2, "1")))
    frame = root.find("VirtualConsole/Frame")
    frame.remove(frame.find("Button"))                   # PANIC button gone
    assert "not on a VC button" in check(root, DEFS).by_code("D008")[0].message
    engine = root.find("Engine")
    engine.remove([f for f in engine.findall("Function") if f.get("ID") == "900"][0])
    assert check(root, DEFS).by_code("D008")[0].message == "no PANIC RESET function"


def test_d009_address_overlap():
    fx = PAR.format(id=0, addr=0) + PAR.format(id=1, addr=5)
    [f] = check(ws(fixtures=fx), DEFS).by_code("D009")
    assert f.ref == {"fixture": "1", "other": "0"} and "U1.6" in f.message


def test_d012_inputs_without_device():
    iomap = ('<InputOutputMap><Universe Name="U2" ID="1">'
             '<Input Plugin="MIDI" Name="None" UID="None" Line="0"/></Universe></InputOutputMap>')
    vc = ('<Button Caption="X" ID="5"><Function ID="1"/><Input ID="0" Universe="1" Channel="4"/></Button>')
    rep = check(ws(scene("1"), vc, iomap=iomap), DEFS)
    assert rep.by_code("D012")[0].ref == {"universe": "1", "bindings": 1}
    patched = iomap.replace('Name="None" UID="None"', 'Name="nanoKONTROL" UID="x"')
    assert not check(ws(scene("1"), vc, iomap=patched), DEFS).by_code("D012")


# ── D015 / D016 / I001 / I002 ────────────────────────────────────────────────

def test_d015_d016_i001_i002():
    f = scene("1", name="[1] Scene - Unassigned") + scene("2")
    vc = (button(3, "1") + '<Button Caption="legend" ID="4"><Function ID="4294967295"/>'
          '<Action>Toggle</Action></Button><Button Caption="STOP" ID="5">'
          '<Function ID="4294967295"/><Action>StopAll</Action></Button>')
    rep = check(ws(f, vc), DEFS)
    assert [x.ref["function"] for x in rep.by_code("D015")] == ["1"]
    assert [x.ref["function"] for x in rep.by_code("D016")] == ["2"]
    assert [x.ref["widget"] for x in rep.by_code("I001")] == ["4"]
    assert rep.by_code("I002")[0].ref == {"pages": ["Page 1"]}


# ── real corpus ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(BASELINE))
def test_corpus_matches_baseline(name):
    exp = BASELINE[name]["doctor"]
    rep = check_file(os.path.join(CORPUS, name), DEFS)
    assert rep.counts() == exp["counts"]
    assert rep.severity_counts() == exp["summary"]


def test_liquidbar_is_clean_reference():
    rep = check_file(os.path.join(CORPUS, "LiquidBar_v14.qxw"), DEFS)
    assert rep.ok and not rep.warnings


def test_corpus_false_positives_gone():
    """expected_baseline 'D006 … 4' in LiquidBar were all false positives."""
    for name in BASELINE:
        rep = check_file(os.path.join(CORPUS, name), DEFS)
        assert not rep.by_code("D006")
        assert "401" not in {f.ref.get("function") for f in rep.by_code("D006")}


def test_report_is_deterministic():
    path = os.path.join(CORPUS, "SangAKlang_v41.qxw")
    assert check_file(path, DEFS).to_json() == check_file(path, load_qxf_defs([CORPUS])).to_json()


# ── CLI ───────────────────────────────────────────────────────────────────────

def test_cli_exit_codes(capsys):
    assert cli_main([os.path.join(CORPUS, "LiquidBar_v14.qxw")]) == 0
    assert cli_main([os.path.join(CORPUS, "SangAKlang_v41.qxw")]) == 1
    assert cli_main([os.path.join(CORPUS, "missing.qxw")]) == 2
    capsys.readouterr()


def test_cli_json(capsys):
    cli_main([os.path.join(CORPUS, "LiquidBar_v14.qxw"), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True and data["stats"]["fixtures"] == 6


def test_cli_as_module():
    r = subprocess.run([sys.executable, "-m", "core.doctor",
                        os.path.join(CORPUS, "SangAKlang_v41.qxw"), "--min-severity", "error"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 1 and "[ERROR] D002" in r.stdout and "D005" not in r.stdout
