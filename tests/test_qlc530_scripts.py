"""QLC+ 5.3.0 compatibility — Script commands in the ``Engine.*`` form.

QLC+ 5.3.0 rewrites ``stopfunction:6`` as ``Engine.stopFunction(6);`` when it
saves a workspace.  tests/corpus/QuickStart_club_qlc530.qxw is the
QuickStart_club corpus file saved by QLC+ 5.3.0 (author anonymised).  Every
tool must read both forms and edit a script in that script's own style.
"""
import os
import xml.etree.ElementTree as ET

from core import porter, script_cmds as sc
from core.doctor import check_file, load_qxf_defs

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
Q530 = os.path.join(CORPUS, "QuickStart_club_qlc530.qxw")
Q522 = os.path.join(CORPUS, "QuickStart_club.qxw")
DEFS = load_qxf_defs([CORPUS, os.path.join(HERE, "fixtures")])


def test_both_forms_are_parsed():
    assert sc.func_refs("stopfunction%3A7") == [("stop", "7")]
    assert sc.func_refs("startfunction:7") == [("start", "7")]
    assert sc.func_refs("Engine.stopFunction%2812%29%3B") == [("stop", "12")]
    assert sc.func_refs("Engine.startFunction(5);") == [("start", "5")]
    assert sc.func_refs("Engine.stopOnExit%28false%29%3B") == []
    assert sc.func_refs("Engine.waitTime%28%22100ms%22%29%3B") == []
    assert sc.func_refs("stoponexit%3Afalse") == []


def test_make_and_renumber_keep_the_style():
    assert sc.make("stop", 12) == "stopfunction%3A12"
    assert sc.make("stop", 12, engine=True) == "Engine.stopFunction%2812%29%3B"
    assert sc.make("start", 3, engine=True, encoded=False) == "Engine.startFunction(3);"
    assert sc.renumber("Engine.stopFunction%286%29%3B", {"6": "60"}) == "Engine.stopFunction%2860%29%3B"
    assert sc.renumber("stopfunction%3A6", {"6": "60"}) == "stopfunction%3A60"
    assert sc.renumber("stopfunction:6", {"6": "60"}) == "stopfunction:60"
    assert sc.renumber("stopfunction%3A6", {"9": "90"}) == "stopfunction%3A6"
    assert sc.renumber("Engine.stopOnExit%28false%29%3B", {"6": "60"}) == "Engine.stopOnExit%28false%29%3B"


def _codes(path):
    rep = check_file(path, qxf_defs=DEFS)
    return sorted({f.code for f in rep.findings})


def test_doctor_treats_both_saves_alike():
    """A 5.3.0 save of a clean file has no false 'unreferenced function' warnings."""
    assert _codes(Q530) == _codes(Q522)
    assert "D016" not in _codes(Q530)


def test_corpus_file_is_in_the_new_form():
    root = ET.parse(Q530).getroot()
    ns = "{http://www.qlcplus.org/Workspace}"
    script = next(f for f in root.iter(ns + "Function")
                  if f.get("Type") == "Script" and "PANIC" in f.get("Name", ""))
    cmds = [c.text for c in script.findall(ns + "Command")]
    assert all(c.startswith("Engine.") for c in cmds), cmds
    assert script.get("Version") == "2"


def _panic_root(style_engine):
    stop = (lambda i: sc.make("stop", i, engine=style_engine))
    return ET.fromstring(
        '<Workspace><Engine>'
        '<Function ID="0" Type="Scene" Name="A"/>'
        '<Function ID="1" Type="Scene" Name="Neutral"/>'
        '<Function ID="2" Type="Script" Name="PANIC RESET">'
        f'<Command>{stop(0)}</Command>'
        f'<Command>{sc.make("start", 1, engine=style_engine)}</Command>'
        '</Function>'
        '<Function ID="3" Type="Scene" Name="New look"/>'
        '</Engine></Workspace>')


def test_porter_extends_panic_in_the_scripts_own_style():
    for engine in (False, True):
        root = _panic_root(engine)
        changed = porter._extend_panic_reset(root.find("Engine"), ["3"])
        assert changed
        script = root.find(".//Function[@ID='2']")
        cmds = [c.text for c in script.findall("Command")]
        assert sc.make("stop", 3, engine=engine) in cmds
        # stop commands go before the start, the start is still last
        assert sc.is_start(cmds[-1])
        # idempotent
        assert porter._extend_panic_reset(root.find("Engine"), ["3"]) == []


def test_look_builder_extends_panic_in_the_scripts_own_style():
    from core import look_builder
    for engine in (False, True):
        root = _panic_root(engine)
        out = look_builder._panic_add_stops(root, ["3"])
        assert out
        cmds = [c.text for c in root.find(".//Function[@ID='2']").findall("Command")]
        assert sc.make("stop", 3, engine=engine) in cmds
        assert look_builder._panic_add_stops(root, ["3"]) == []


def test_porter_closure_follows_engine_commands():
    root = ET.fromstring(
        '<Function ID="2" Type="Script" Name="S">'
        '<Command>Engine.startFunction%281%29%3B</Command>'
        '<Command>Engine.stopFunction%280%29%3B</Command></Function>')
    ids = []
    for cmd in root.findall("Command"):
        ids.extend(sc.func_ids(cmd.text))
    assert ids == ["1", "0"]
