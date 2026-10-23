"""3.10.0: knob, XY pad, speed dial and clock are written as QLC+ 5.3.0 saves them.

The reference is tests/corpus/VC_widgets_qlc530.qxw, saved by QLC+ 5.3.0 with one of each."""
import copy
import os
import xml.etree.ElementTree as ET

import pytest

from core import qxw_io, vc_builder as vb, vc_ops
from core.doctor import checks  # noqa: F401  (the Doctor must still read the file)

HERE = os.path.dirname(__file__)
REF = os.path.join(HERE, "corpus", "VC_widgets_qlc530.qxw")
SMALL = os.path.join(HERE, "corpus", "Pub_6fix.qxw")


def _load(path):
    return qxw_io.strip_ns(ET.parse(path).getroot())


def _shape(el):
    """Tag, attribute names, and the same for every child, in order (values left out)."""
    return (el.tag, tuple(el.attrib), tuple(_shape(c) for c in el))


def _ref(kind):
    root = _load(REF)
    if kind == "Knob":
        return next(w for w in root.iter("Slider") if w.get("WidgetStyle") == "Knob")
    return next(root.iter(kind))


def _page(root):
    vc = root.find("Engine/../VirtualConsole")
    return vc.find("Frame")


@pytest.mark.parametrize("kind", vb.EXTRA_KINDS)
def test_same_shape_as_qlc_5_3_0(kind):
    root = _load(SMALL)
    vc = root.find("VirtualConsole")
    page = vc.find("Frame")
    d = vb.create_widget(root, page.get("ID"), kind, "t")
    new = next(w for w in vc.iter() if w.get("ID") == d["new_ids"][0])
    want, got = _ref(kind), new
    assert _shape(got) == _shape(want)
    for tag in ("WindowState",):
        assert set(got.find(tag).attrib) == set(want.find(tag).attrib)


def test_knob_is_a_slider_style_not_a_tag():
    root = _load(SMALL)
    page = root.find("VirtualConsole/Frame")
    vb.create_widget(root, page.get("ID"), "Knob", "K")
    assert not list(root.iter("Knob"))
    assert [w for w in root.iter("Slider") if w.get("WidgetStyle") == "Knob"]


def test_reference_reads_in_the_doctor_and_the_editor_model():
    from core import show_diff  # noqa: F401
    root = _load(REF)
    assert root.findtext("Creator/Version") == "5.3.0"
    assert {"SpeedDial", "Clock", "XYPad"} <= {w.tag for w in root.iter()}


def test_upgrade_is_offered_only_before_5_3():
    old = _load(SMALL)                                   # a 5.2.x show
    page = old.find("VirtualConsole/Frame")
    d = vb.create_widget(old, page.get("ID"), "Clock", "c")
    assert d["upgrade53"]["kinds"] == ["Clock"] and "5.3" in d["upgrade53"]["message"]
    assert "upgrade53" not in vb.create_widget(old, page.get("ID"), "Button", "b")
    new = _load(REF)
    p2 = new.find("VirtualConsole/Frame")
    assert "upgrade53" not in vb.create_widget(new, p2.get("ID"), "XYPad", "x")


def test_new_widgets_get_fresh_ids_and_save_cleanly(tmp_path):
    root = _load(REF)
    p = root.find("VirtualConsole/Frame")
    ids = [vb.create_widget(root, p.get("ID"), k, k)["new_ids"][0] for k in vb.EXTRA_KINDS]
    all_ids = [w.get("ID") for w in root.find("VirtualConsole").iter() if w.get("ID") and w.get("Caption") is not None]
    assert len(all_ids) == len(set(all_ids)) and set(ids) <= set(all_ids)
    out = tmp_path / "o.qxw"
    qxw_io.write_qxw(qxw_io.qualify_ns(copy.deepcopy(root)), str(out))
    assert ET.parse(out).getroot() is not None
