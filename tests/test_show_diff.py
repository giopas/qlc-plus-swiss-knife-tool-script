"""2.8 — what an in-place step changed (core.show_diff, the show report)."""
import copy
import os
import xml.etree.ElementTree as ET

from core import show_diff, qxw_io

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


def _pub():
    return qxw_io.strip_ns(qxw_io.loads_qxw(open(os.path.join(CORPUS, "Pub_6fix.qxw"), "rb").read()))


def test_nothing_changed():
    r = _pub()
    assert show_diff.summarise(r, copy.deepcopy(r)) == []


def test_functions_groups_pages_widgets():
    a = _pub()
    b = copy.deepcopy(a)
    eng = b.find("Engine")
    fns = eng.findall("Function")
    fns[0].set("Name", "Renamed Look")
    eng.remove(fns[1])
    ET.SubElement(eng, "Function", {"ID": "77777", "Type": "Scene", "Name": "Brand New"})
    g = eng.find("FixtureGroup")
    g.find("Name").text = "Other Name"
    vc = b.find("VirtualConsole")
    page = next(p for p in vc.iter("Frame") if p.get("Caption"))
    btn = next(page.iter("Button"))
    btn.set("Caption", "New caption")
    lines = "\n".join(show_diff.summarise(a, b))
    assert "Functions added (1): 'Brand New'" in lines
    assert "Functions removed (1)" in lines and "Functions renamed (1)" in lines and "→ 'Renamed Look'" in lines
    assert "Fixture groups renamed (1)" in lines
    assert "Widgets changed (1): 'New caption on" in lines


def test_page_order():
    a = _pub()
    b = copy.deepcopy(a)
    vc = b.find("VirtualConsole")
    holder = next(f for f in [vc, *vc.iter("Frame")]
                  if len([c for c in f if c.tag in ("Frame", "SoloFrame") and c.get("Caption")]) >= 2)
    pages = [c for c in holder if c.tag in ("Frame", "SoloFrame") and c.get("Caption")]
    holder.remove(pages[-1])
    holder.insert(list(holder).index(pages[0]), pages[-1])
    lines = show_diff.summarise(a, b)
    assert any(l.startswith("Virtual Console page order now: '" + pages[-1].get("Caption").strip()) for l in lines)
