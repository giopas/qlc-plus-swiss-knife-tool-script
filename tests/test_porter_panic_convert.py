"""v2.4.0 — the Porter turns a plain-scene PANIC RESET of the target into the script form."""
import xml.etree.ElementTree as ET
from core import porter

XML = """<Workspace><Engine>
<Function ID="0" Type="Scene" Name="Look"><Speed FadeIn="0" FadeOut="0" Duration="0"/></Function>
<Function ID="1" Type="Scene" Name="PANIC RESET"><Speed FadeIn="0" FadeOut="0" Duration="0"/></Function>
</Engine><VirtualConsole><Frame><Button Caption="R"><Function ID="1"/></Button></Frame></VirtualConsole></Workspace>"""


def test_plain_scene_becomes_script_and_button_follows():
    root = ET.fromstring(XML)
    out = porter._convert_panic_scene(root)
    assert out and "stops every function" in out[0]
    eng = root.find("Engine")
    script = next(f for f in eng.findall("Function") if f.get("Type") == "Script")
    cmds = [c.text for c in script.findall("Command")]
    assert "stopfunction%3A0" in cmds and "startfunction%3A1" in cmds
    btn = root.find(".//Button/Function")
    assert btn.get("ID") == script.get("ID")
    assert porter._convert_panic_scene(root) == []          # already a script


def test_script_target_is_left_alone():
    root = ET.fromstring(XML)
    porter._convert_panic_scene(root)
    n = len(root.find("Engine").findall("Function"))
    porter._convert_panic_scene(root)
    assert len(root.find("Engine").findall("Function")) == n
