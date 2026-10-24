"""3.10.0 VC Editor: resize by dragging handles.

The arithmetic is in static/js/vc_resize.js (pure functions); these tests run it with node.
Rules: the edges always land on the grid, a widget keeps a minimum size, stays inside its frame,
and a handle moves only the edges it stands on."""
import json
import os
import re
import shutil
import subprocess
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
O = {"x": 20, "y": 30, "w": 100, "h": 60}


def js(expr):
    code = textwrap.dedent("""
        const m = require(%r);
        process.stdout.write(JSON.stringify(%s));
    """) % (os.path.join(ROOT, "static", "js", "vc_resize.js"), expr)
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def rz(h, dx, dy, grid=5, bounds=None, o=O):
    return js("m.vceResizeRect(%s, %r, %s, %s, %s, %s)" % (json.dumps(o), h, dx, dy, grid, json.dumps(bounds)))


def test_the_east_handle_moves_only_the_right_edge():
    assert rz("e", 33, 99) == {"x": 20, "y": 30, "w": 135, "h": 60}


def test_the_west_handle_moves_the_left_edge_and_keeps_the_right_one():
    r = rz("w", -23, 0)
    assert r["x"] == 0 + 0 or r["x"] % 5 == 0
    assert r["x"] + r["w"] == 120 and r == {"x": 0, "y": 30, "w": 120, "h": 60}   # 20-23=-3 → 0 (not outside the frame)


def test_corners_move_two_edges():
    assert rz("se", 10, 10) == {"x": 20, "y": 30, "w": 110, "h": 70}
    assert rz("nw", -10, -10) == {"x": 10, "y": 20, "w": 110, "h": 70}
    assert rz("ne", 10, -10) == {"x": 20, "y": 20, "w": 110, "h": 70}
    assert rz("sw", -10, 10) == {"x": 10, "y": 30, "w": 110, "h": 70}


@pytest.mark.parametrize("grid", [1, 2, 5, 10, 25, 50])
@pytest.mark.parametrize("h", ["nw", "n", "ne", "e", "se", "s", "sw", "w"])
@pytest.mark.parametrize("dx,dy", [(7, 13), (-17, -9), (31, -4), (-3, 41)])
def test_the_dragged_edges_always_land_on_the_grid(h, grid, dx, dy):
    o = {"x": 40, "y": 50, "w": 200, "h": 100}                 # already on a 10 grid; 25 and 50 do not divide it
    r = rz(h, dx, dy, grid, {"w": 1000, "h": 800}, o)
    edges = {"w": r["x"], "e": r["x"] + r["w"], "n": r["y"], "s": r["y"] + r["h"]}
    for k in h:
        assert edges[k] % grid == 0, (h, grid, r)
    other = set("nsew") - set(h)                                 # edges the handle does not touch stay as they were
    orig = {"w": 40, "e": 240, "n": 50, "s": 150}
    for k in other:
        assert edges[k] == orig[k], (h, r)


def test_a_coarser_grid_gives_bigger_steps():
    assert rz("e", 12, 0, 5)["w"] == 110 and rz("e", 12, 0, 50)["w"] == 130 and rz("e", -8, 0, 50)["w"] == 80
    assert rz("e", 12, 0, 1)["w"] == 112


def test_a_widget_never_gets_smaller_than_the_minimum():
    assert rz("e", -500, 0)["w"] == 10 and rz("s", 0, -500)["h"] == 10
    assert rz("w", 500, 0) == {"x": 110, "y": 30, "w": 10, "h": 60}
    r = rz("e", -500, 0, 25)                                     # a big grid raises the minimum to one step
    assert r["w"] == 25


def test_a_widget_stays_inside_its_frame():
    b = {"w": 150, "h": 100}
    assert rz("e", 400, 0, 5, b)["w"] == 130                     # right edge 150
    assert rz("s", 0, 400, 5, b)["h"] == 70                      # bottom edge 100
    assert rz("nw", -400, -400, 5, b) == {"x": 0, "y": 0, "w": 120, "h": 90}
    small = {"w": 30, "h": 30}                                   # one that already reaches outside keeps its edge, is not squashed
    assert rz("e", 50, 0, 5, small)["w"] == 100 and rz("e", -20, 0, 5, small)["w"] == 80


def test_without_a_frame_there_is_no_upper_limit():
    assert rz("e", 5000, 0)["w"] == 5100


def test_handle_points_and_hit_testing():
    n = {"_absX": 100, "_absY": 200, "w": 80, "h": 40}
    pts = js("m.vceHandlePoints(%s)" % json.dumps(n))
    assert pts["nw"] == [100, 200] and pts["se"] == [180, 240] and pts["n"] == [140, 200] and pts["w"] == [100, 220]
    assert js("m.vceHandleAt(%s, 101, 201, 6)" % json.dumps(n)) == "nw"
    assert js("m.vceHandleAt(%s, 140, 198, 6)" % json.dumps(n)) == "n"
    assert js("m.vceHandleAt(%s, 140, 220, 6)" % json.dumps(n)) is None          # the middle of the widget is not a handle
    assert js("m.vceHandleCursor('ne')") == "nesw-resize" and js("m.vceHandleCursor('s')") == "ns-resize"


def test_the_editor_uses_it_and_pushes_one_history_step_per_drag():
    src = open(os.path.join(ROOT, "static", "js", "vc_editor.js"), encoding="utf-8").read()
    html = open(os.path.join(ROOT, "templates", "index.html"), encoding="utf-8").read()
    assert html.index("vc_resize.js") < html.index("vc_editor.js")                # loaded first
    move = src[src.index("if (_vceResize) {\n    const m = _vceResize;"):]
    move = move[:move.index("if (_vceMoveDrag) {")]
    assert move.count("_vcePush(") == 1 and "m.moved" in move                     # once, on the first move, not per pixel
    assert "vceResizeRect(" in move and "_vceChanges" in move
    assert "Math.min(g, 50)" in src                                              # the grid step is the box's, 1 to 50
    assert not re.search(r"_vceResize\s*=\s*\{[^}]*grid:\s*snap", src)           # resizing does not depend on the move checkbox


# ── after giopas's hand test (23 Oct): a duplicated ID must not change how far a widget may grow ──

def test_the_frame_size_comes_from_the_tree_not_from_an_id_map():
    """A page and a widget that share ID 0 made the page's size read from the widget (so a widget could
    not grow to the right). The bounds are the parent's size taken while the tree is flattened."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "static", "js", "vc_editor.js"), encoding="utf-8").read()
    assert "_pw: parentSize" in src and "bounds: n._pw != null" in src
    assert "_vceNodes[n._parentId]" not in src.split("function _vceOnMouseDown")[1].split("function _vceOnMouseUp")[0]


def test_one_grid_number_in_toolbar_and_panel():
    html = open(os.path.join(os.path.dirname(__file__), "..", "templates", "index.html"), encoding="utf-8").read()
    assert 'id="vce-grid-top"' in html and 'id="vce-snap-grid"' in html and "Mask ±" in html


def test_the_resize_message_is_not_wiped_by_hovering():
    src = open(os.path.join(os.path.dirname(__file__), "..", "static", "js", "vc_editor.js"), encoding="utf-8").read()
    assert "_vceKeepMsg = true;" in src and "if (_vceKeepMsg)" in src and "_vceKeepMsg = false;" in src
