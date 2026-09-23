"""VC Visual Editor structural edits: copy/move widgets, duplicate/new pages."""
import os

import pytest

from core import qxw_io, vc_ops
from core import workspace as ws

HERE = os.path.dirname(os.path.abspath(__file__))
N = "{http://www.qlcplus.org/Workspace}"

XML = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Workspace>
<Workspace xmlns="http://www.qlcplus.org/Workspace">
 <Engine><Function ID="1" Type="Scene" Name="Red"/><Function ID="2" Type="Chaser" Name="Set"/></Engine>
 <VirtualConsole>
  <Frame Caption="PAGE A" ID="100">
   <WindowState Visible="True" X="0" Y="0" Width="1650" Height="884"/>
   <AllowResize>False</AllowResize>
   <Button Caption="Red" ID="1"><WindowState Visible="True" X="10" Y="20" Width="100" Height="40"/>
    <Function ID="1"/><Action>Toggle</Action><Key>R</Key><Input ID="0" Universe="1" Channel="5"/></Button>
   <Frame Caption="Box" ID="2"><WindowState Visible="True" X="300" Y="50" Width="400" Height="300"/>
    <Button Caption="Inner" ID="3"><WindowState Visible="True" X="5" Y="30" Width="80" Height="40"/><Function ID="1"/></Button>
   </Frame>
   <CueList Caption="Setlist" ID="4"><WindowState Visible="True" X="10" Y="400" Width="500" Height="300"/>
    <Chaser>2</Chaser><Next><Key>Space</Key></Next></CueList>
  </Frame>
  <Frame Caption="PAGE B" ID="200">
   <WindowState Visible="True" X="0" Y="0" Width="1650" Height="884"/>
   <Frame Caption="Target" ID="201"><WindowState Visible="True" X="100" Y="100" Width="500" Height="400"/></Frame>
  </Frame>
  <Properties><Size Width="1920" Height="1080"/></Properties>
 </VirtualConsole>
</Workspace>'''


@pytest.fixture
def root():
    return qxw_io.loads_qxw(XML.encode())


def w(root, wid):
    return [e for e in root.iter() if e.get("ID") == wid and e.tag != N + "Function"]


def xy(el):
    s = el.find(N + "WindowState")
    return int(s.get("X")), int(s.get("Y"))


def test_list_pages(root):
    pages = vc_ops.list_pages(root)
    assert [p["caption"] for p in pages] == ["PAGE A", "PAGE B"]
    assert pages[0]["frames"] == [{"id": "2", "caption": "Box", "depth": 1}]


def test_copy_to_other_page_renumbers_and_strips_bindings(root):
    r = vc_ops.copy_widgets(root, ["1", "2"], "201")
    assert r["new_ids"] == ["202", "203"]              # max(201)+1, document order
    assert r["count"] == 3 and r["bindings_removed"] == 2
    tgt = w(root, "201")[0]
    copies = [c for c in tgt if c.tag in (N + "Button", N + "Frame")]
    assert [c.get("Caption") for c in copies] == ["Red", "Box"]
    assert copies[0].find(N + "Key") is None and copies[0].find(N + "Input") is None
    assert copies[0].find(N + "Function").get("ID") == "1"   # still wired
    assert copies[1].find(N + "Button").get("ID") == "204"    # inner renumbered
    assert xy(copies[0]) == (10, 20)                          # same coords on another page
    # originals untouched
    assert w(root, "1")[0].find(N + "Key").text == "R"


def test_copy_keep_bindings_and_same_parent_offset(root):
    r = vc_ops.copy_widgets(root, ["1"], "100", keep_bindings=True)
    dup = w(root, r["new_ids"][0])[0]
    assert dup.find(N + "Key").text == "R"
    assert xy(dup) == (30, 40)                                # +20,+20 next to original


def test_copy_explicit_position_keeps_group_layout(root):
    r = vc_ops.copy_widgets(root, ["1", "4"], "201", x=0, y=0)
    a, b = (w(root, i)[0] for i in r["new_ids"])
    assert xy(a) == (0, 0) and xy(b) == (0, 380)
    assert b.find(N + "Next") is None                         # empty <Next/> dropped


def test_selection_inside_selected_frame_not_duplicated(root):
    r = vc_ops.copy_widgets(root, ["2", "3"], "201")
    assert len(r["new_ids"]) == 1 and r["count"] == 2


def test_move_keeps_ids_and_bindings(root):
    r = vc_ops.move_widgets(root, ["1"], "201")
    assert r["moved_ids"] == ["1"]
    btn = w(root, "1")[0]
    assert btn in list(w(root, "201")[0]) and btn.find(N + "Key").text == "R"
    assert btn not in list(w(root, "100")[0])


def test_move_errors(root):
    with pytest.raises(vc_ops.VcOpError, match="into itself"):
        vc_ops.move_widgets(root, ["2"], "2")
    with pytest.raises(vc_ops.VcOpError, match="choose a frame"):
        vc_ops.move_widgets(root, ["1"], "3")
    with pytest.raises(vc_ops.VcOpError, match="whole page"):
        vc_ops.move_widgets(root, ["100"], "201")
    with pytest.raises(vc_ops.VcOpError, match="not found"):
        vc_ops.copy_widgets(root, ["999"], "201")


def test_duplicate_ids_refused(root):
    w(root, "3")[0].set("ID", "1")                            # two widgets with ID 1
    with pytest.raises(vc_ops.VcOpError, match="Fix duplicate IDs"):
        vc_ops.copy_widgets(root, ["1"], "201")


def test_fix_duplicate_ids_keeps_first_in_document_order(root):
    w(root, "3")[0].set("ID", "100")              # inner button reuses the page's ID
    assert vc_ops.duplicate_ids(root) == [{"id": "100", "captions": ["PAGE A", "Inner"]}]
    r = vc_ops.fix_duplicate_ids(root)
    assert r["renumbered"] == [{"old": "100", "new": "202", "caption": "Inner"}]
    assert vc_ops.duplicate_ids(root) == []
    assert w(root, "100")[0].get("Caption") == "PAGE A"
    vc_ops.copy_widgets(root, ["1"], "100")        # page is a valid target again


def test_copy_page_and_new_page(root):
    r = vc_ops.copy_page(root, "100", "PAGE A2")
    pages = vc_ops.list_pages(root)
    assert [p["caption"] for p in pages] == ["PAGE A", "PAGE B", "PAGE A2"]
    assert r["page_id"] == "202" and r["bindings_removed"] == 3
    vc = root.find(N + "VirtualConsole")
    assert [c.tag.replace(N, "") for c in vc][-1] == "Properties"   # pages before Properties
    r2 = vc_ops.new_page(root, "Empty")
    page = w(root, r2["page_id"])[0]
    assert page.find(N + "AllowResize").text == "False"      # settings copied from first page
    assert not [c for c in page if c.tag == N + "Button"]
    assert vc_ops.list_pages(root)[-1]["caption"] == "Empty"


def test_frame_promoted_to_page_gets_page_size(root):
    r = vc_ops.copy_page(root, "2")
    page = w(root, r["page_id"])[0]
    s = page.find(N + "WindowState")
    assert (s.get("Width"), s.get("Height"), s.get("X")) == ("1650", "884", "0")
    assert page.get("Caption") == "Box (copy)"


def test_workspace_level_op_reparses_and_exports(tmp_path):
    src = tmp_path / "Show_v1.qxw"
    src.write_text(XML, encoding="utf-8")
    ws.load_qxw(str(src))
    n0 = len(ws._state["vc_widgets"])
    ws.vc_structural_edit("copy_page", page_id="100", caption="PAGE A COPY")
    assert len(ws._state["vc_widgets"]) == n0 + 5            # page + 4 widgets
    assert [p["caption"] for p in ws.get_vc_tree()["pages"]][-1] == "PAGE A COPY"
    ws.vc_structural_edit("move", ids=["1"], target_id="201")
    assert "PAGE B" in ws._state["vc_widgets"][
        [x["widget_id"] for x in ws._state["vc_widgets"]].index("1")]["frame_path"]
    out = tmp_path / "Show_v2.qxw"
    ws.export_qxw(str(out))
    ids = [e.get("ID") for e in qxw_io.load_qxw(str(out)).getroot().iter()
           if e.tag.replace(N, "") in vc_ops.WIDGET_TYPES]
    assert len(ids) == len(set(ids))                          # no duplicate widget IDs
    ws._reset()


@pytest.mark.skipif(not os.path.exists(os.path.join(HERE, "corpus", "LiquidBar_v14.qxw")),
                    reason="corpus not present")
def test_real_show_copy_page():
    root = qxw_io.load_qxw(os.path.join(HERE, "corpus", "LiquidBar_v14.qxw")).getroot()
    before = len(vc_ops.list_pages(root))
    vc_ops.copy_page(root, vc_ops.list_pages(root)[1]["id"])
    ids = [e.get("ID") for e in root.iter() if e.tag.replace(N, "") in vc_ops.WIDGET_TYPES]
    assert len(vc_ops.list_pages(root)) == before + 1 and len(ids) == len(set(ids))
