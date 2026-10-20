"""Fit the Virtual Console to a screen (3.7.0): screen sizes as data, Fit / Stretch /
Page size only, fonts, the warning for widgets too small to tap."""
import copy
import json
import os

import pytest

from core import library as lib, qxw_io, vc_builder as vb, vc_screens, vc_ops
from core.vc_ops import VcOpError
from tests.test_vc_builder import FEST, QS6, _pages, _root


def _rects(page):
    return [vb._rect(w) for w in page.iter() if w is not page and vc_ops._is_widget(w)]


def _fonts(page):
    return [f.text for el in page.iter() for f in vb._fonts(el)]


@pytest.fixture(autouse=True)
def _own_screens(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_VC_SCREENS", str(tmp_path / "screens"))


# ── the sizes ────────────────────────────────────────────────────────────────

def test_the_four_old_sizes_keep_their_ids_and_pixels():
    s = {x["id"]: (x["w"], x["h"]) for x in vc_screens.list_screens()}
    assert s["macbook"] == (1650, 884) and s["fullhd"] == (1920, 1080)
    assert s["tablet"] == (1280, 800) and s["ipad"] == (1024, 768)


def test_new_sizes_are_there_and_landscape():
    s = {x["id"]: x for x in vc_screens.list_screens()}
    assert (s["touch7_800"]["w"], s["touch7_800"]["h"]) == (800, 480) and s["touch7_800"]["touch"]
    assert (s["touch7_1024"]["w"], s["touch7_1024"]["h"]) == (1024, 600)
    assert all(x["w"] >= x["h"] for x in s.values())
    assert not s["fullhd"]["touch"] and s["ipad"]["touch"]
    assert len({x["id"] for x in vc_screens.BUILTIN}) == len(vc_screens.BUILTIN)


def test_resolve_custom_and_portrait():
    assert vc_screens.resolve(None, 1000, 700)[:2] == (1000, 700)
    assert vc_screens.resolve("touch7_800", orientation="portrait")[:2] == (480, 800)
    assert vc_screens.resolve(None, 500, 1000)[:2] == (1000, 500)         # stored in landscape
    for bad in ((None, 100, 100), (None, "x", 800), (None, 800, 99999)):
        with pytest.raises(vc_screens.ScreenError):
            vc_screens.resolve(*bad)
    with pytest.raises(vc_screens.ScreenError):
        vc_screens.resolve("cinema")
    with pytest.raises(vc_screens.ScreenError):
        vc_screens.resolve("ipad", orientation="diagonal")


def test_your_own_sizes_are_listed_after_the_built_in_ones(tmp_path):
    d = tmp_path / "screens"
    d.mkdir()
    (d / "stage_pi.json").write_text(json.dumps({"label": "Stage Pi", "w": 1024, "h": 600, "touch": True}))
    (d / "fullhd.json").write_text(json.dumps({"label": "Hijack", "w": 900, "h": 500}))     # a built-in id is not taken
    (d / "broken.json").write_text("{nope")
    ids = [x["id"] for x in vc_screens.list_screens()]
    assert ids[-1] == "stage_pi" and ids.count("fullhd") == 1
    assert vc_screens.get("fullhd")["w"] == 1920


# ── the ways to fit ──────────────────────────────────────────────────────────

def test_fit_keeps_proportions():
    r = _root()
    before = [(vb._rect(w)) for w in _pages(r)[1].iter() if vc_ops._is_widget(w) and w is not _pages(r)[1]]
    d = vb.apply_screen(r, "touch7_800", mode="fit")
    p = _pages(r)[1]
    assert vb._rect(p) == (0, 0, 800, 480) and d["mode"] == "fit" and d["outside"] == 0
    f = d["factor"]
    assert 0 < f < 1
    after = [(vb._rect(w)) for w in p.iter() if vc_ops._is_widget(w) and w is not p]
    for (x, y, w, h), (x2, y2, w2, h2) in zip(before, after):
        assert abs(w2 - max(10, w * f)) <= 1 and abs(h2 - max(10, h * f)) <= 1     # one factor for both
        assert abs(x2 - x * f) <= 1 and abs(y2 - y * f) <= 1


def test_fit_never_leaves_anything_outside_even_when_content_is_bigger_than_its_page():
    r = _root()
    p = _pages(r)[0]
    vb._set_rect(p, 0, 0, 600, 400)                  # a page smaller than what it holds
    d = vb.apply_screen(r, "fullhd", [p.get("ID")], mode="fit")
    assert d["outside"] == 0


def test_stretch_scales_width_and_height_separately():
    r = _root()
    d = vb.apply_screen(r, "ipad", mode="stretch")
    assert d["mode"] == "stretch" and d["outside"] == 0
    assert all(vb._rect(p)[2:] == (1024, 768) for p in _pages(r))


def test_page_only_leaves_the_widgets_alone():
    r = _root()
    p = _pages(r)[0]
    before = _rects(p)
    d = vb.apply_screen(r, "touch7_800", [p.get("ID")], mode="page")
    assert vb._rect(p) == (0, 0, 800, 480) and _rects(p) == before and d["outside"] > 0


def test_portrait_swaps_the_sides():
    r = _root()
    d = vb.apply_screen(r, "ipad", mode="fit", orientation="portrait")
    assert d["size"] == "768×1024"
    assert all(vb._rect(p)[2:] == (768, 1024) for p in _pages(r))


def test_your_own_width_and_height():
    r = _root()
    d = vb.apply_screen(r, width=1000, height=600, mode="fit")
    assert d["size"] == "1000×600" and d["touch"] is False and d["small"] == []


def test_unknown_mode_and_unknown_screen_are_refused():
    r = _root()
    with pytest.raises(VcOpError):
        vb.apply_screen(r, "ipad", mode="zoom")
    with pytest.raises(VcOpError):
        vb.apply_screen(r, "cinema")
    with pytest.raises(VcOpError):
        vb.apply_screen(r, "ipad", orientation="diagonal")


def test_old_calls_do_what_they_did():
    """No `mode`: scale true stretches (text unchanged), false sets the page size only."""
    a, b = _root(), _root()
    fonts = _fonts(_pages(a)[0])
    d = vb.apply_screen(a, "macbook", scale=True)
    assert d["pages"] == 4 and d["size"] == "1650×884" and d["outside"] == 0 and d["mode"] == "stretch"
    assert _fonts(_pages(a)[0]) == fonts                                    # recorded sessions replay to the same file
    before = _rects(_pages(b)[0])
    vb.apply_screen(b, "ipad", [_pages(b)[0].get("ID")])
    assert _rects(_pages(b)[0]) == before


def test_old_recipe_replays_to_the_same_bytes():
    x, y = _root(), _root()
    vb.apply_screen(x, "tablet", scale=True)
    vb.OPS["screen"](y, profile_id="tablet", page_ids=[], scale=True)
    assert qxw_io.qxw_bytes(x) == qxw_io.qxw_bytes(y)


# ── fonts ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("spec,k,want", [
    ("Roboto,10,-1,5,700,0,0,0,0,0,0,0,0,0,0,1", 0.5, "Roboto,8,-1,5,700,0,0,0,0,0,0,0,0,0,0,1"),    # not below 8
    ("Roboto,14,-1,5,400,0,0,0,0,0,0,0,0,0,0,1", 1.5, "Roboto,21,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"),
    ("Roboto,18,-1,5,400,0,0,0,0,0,0,0,0,0,0,1", 3.0, "Roboto,28,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"),    # not above 28
    ("Roboto,6,-1,5,400,0,0,0,0,0,0,0,0,0,0,1", 0.5, "Roboto,6,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"),      # already small: kept
    ("Roboto,-1,16,5,400,0,0,0,0,0,0,0,0,0,0,1", 0.5, "Roboto,-1,8,5,400,0,0,0,0,0,0,0,0,0,0,1"),      # pixel size
    ("odd", 2.0, "odd"),
])
def test_scale_font(spec, k, want):
    assert vb._scale_font(spec, k) == want


def test_fit_scales_the_text_with_the_widgets():
    r = _root()
    before = _fonts(_pages(r)[1])
    vb.apply_screen(r, "uhd", mode="fit")                  # a big screen: text grows
    after = _fonts(_pages(r)[1])
    sizes = lambda fs: [int(f.split(",")[1]) for f in fs]
    assert len(before) == len(after) and sizes(after) > sizes(before) and max(sizes(after)) <= 28


# ── tap size ─────────────────────────────────────────────────────────────────

def test_small_buttons_are_named_on_a_touch_screen_only():
    r = _root()
    d = vb.apply_screen(copy.deepcopy(r), "touch7_800", mode="fit")
    assert d["touch"] and d["small_count"] > 0
    row = d["small"][0]
    assert min(row["w"], row["h"]) < vc_screens.TAP_MIN and {"id", "caption", "type", "page"} <= set(row)
    assert vb.apply_screen(copy.deepcopy(r), "fullhd", mode="fit")["small_count"] == 0       # a monitor: no warning
    big = vb.apply_screen(copy.deepcopy(r), width=800, height=480, mode="fit", touch=True)
    assert big["small_count"] > 0                                                           # your own touch size


def test_label_strip_buttons_are_not_counted():
    r = _root(QS6)
    p = _pages(r)[0]
    n_before = len(vb.too_small_to_tap(p, tap=10**6))
    labels = [w for w in p.iter() if vc_ops._local(w.tag) == "Button" and not vb._is_tappable(w)]
    assert n_before == sum(1 for w in p.iter() if w is not p and vb._is_tappable(w))
    assert all(w not in [x for x in p.iter() if vb._is_tappable(x)] for w in labels)


def test_preview_does_not_touch_the_show():
    r = _root()
    before = qxw_io.qxw_bytes(r)
    d = vb.preview_screen(r, profile_id="touch7_800", mode="fit")
    assert d["small_count"] > 0 and qxw_io.qxw_bytes(r) == before


# ── the Library ──────────────────────────────────────────────────────────────

def test_screen_sizes_are_shared_through_the_library(tmp_path):
    d = tmp_path / "screens"
    d.mkdir()
    (d / "stage_pi.json").write_text(json.dumps({"id": "stage_pi", "label": "Stage Pi", "w": 1024, "h": 600, "touch": True}))
    inv = [i for i in lib.inventory() if i["kind"] == "vc_screen"]
    assert [i["name"] for i in inv] == ["Stage Pi"] and "1024" in inv[0]["summary"]
    pack = lib.export_pack([{"kind": "vc_screen", "name": "Stage Pi"}], "Screens")
    (d / "stage_pi.json").unlink()
    res = lib.install(pack, default="skip")
    assert res["installed"] == 1
    s = vc_screens.get("Stage_Pi") or vc_screens.get("stage_pi")
    assert s and (s["w"], s["h"], s["touch"]) == (1024, 600, True)


@pytest.mark.parametrize("data", [{"w": 10, "h": 10}, {"w": "wide", "h": 600}, {"w": 99999, "h": 600}])
def test_library_refuses_bad_screens(data):
    pack = {"format": lib.FORMAT, "title": "x", "items": [{"kind": "vc_screen", "name": "Bad", "data": data}]}
    pv = lib.preview(pack)
    assert pv["items"][0]["status"] == "invalid"


def test_library_does_not_replace_a_built_in_size():
    pack = {"format": lib.FORMAT, "title": "x",
            "items": [{"kind": "vc_screen", "name": "Full HD 1920 × 1080", "data": {"w": 900, "h": 500}}]}
    assert lib.preview(pack)["items"][0]["status"] == "reserved"


# ── the screen, from the app and from Claude ────────────────────────────────

def _client(path=FEST):
    import app
    from core import show
    c = app.create_app().test_client()
    show._show.clear()
    assert c.post("/api/load", json={"path": path}).status_code == 200
    return c


def test_builder_info_lists_the_screens_and_the_tap_size():
    c = _client()
    info = c.get("/api/vc/builder-info").get_json()
    assert info["tap_min"] == vc_screens.TAP_MIN
    ids = [s["id"] for s in info["screens"]]
    assert {"macbook", "touch7_800", "ipad_10_9"} <= set(ids)
    assert all({"id", "label", "w", "h", "touch"} <= set(s) for s in info["screens"])


def test_screen_op_through_the_app_and_its_preview():
    c = _client()
    page = c.get("/api/vc/pages").get_json()["pages"][0]["id"]
    body = {"op": "screen", "profile_id": "touch7_800", "mode": "fit", "page_ids": [page]}
    pv = c.post("/api/vc/screen-preview", json=body).get_json()
    assert pv["ok"] and pv["size"] == "800×480" and pv["small_count"] > 0
    assert c.get("/api/show/status").get_json()["steps"] == 0                 # a preview is no step
    r = c.post("/api/vc/op", json=body).get_json()
    assert r["ok"] and r["size"] == "800×480" and r["mode"] == "fit"
    assert c.get("/api/show/status").get_json()["steps"] == 1
    bad = c.post("/api/vc/screen-preview", json={"op": "screen", "profile_id": "cinema"})
    assert bad.status_code == 400
    own = c.post("/api/vc/op", json={"op": "screen", "width": 1000, "height": 500, "orientation": "portrait",
                                     "mode": "page", "page_ids": [page]}).get_json()
    assert own["size"] == "500×1000"


def test_screen_step_is_recorded_in_the_recipe_and_replays(tmp_path):
    from core import recipe
    c = _client()
    c.post("/api/vc/op", json={"op": "screen", "profile_id": "tablet", "mode": "fit"})
    out = tmp_path / "Fit_v2.qxw"
    saved = c.post("/api/show/save", json={"path": str(out)}).get_json()
    rec = json.load(open(saved["recipe_path"], encoding="utf-8"))
    assert [c["body"] for c in rec["calls"]] == [{"mode": "fit", "op": "screen", "profile_id": "tablet"}]
    assert recipe.replay(rec, recipe_dir=str(tmp_path))["identical"]


def test_claude_edit_vc_screen_with_preview(tmp_path, monkeypatch):
    from tests.test_mcp import Client
    import shutil
    folder = tmp_path / "shows"
    folder.mkdir()
    shutil.copy(FEST, folder / "Festival_14fix.qxw")
    from core import show
    show._show.clear()
    c = Client([str(folder)])
    c.ok("open_show", path=str(folder / "Festival_14fix.qxw"))
    pv = c.ok("edit_vc", op="screen", profile_id="touch7_800", mode="fit", preview=True)
    assert pv["size"] == "800×480" and pv["small_count"] > 0
    assert c.ok("show_history")["steps"] == []
    r = c.ok("edit_vc", op="screen", profile_id="touch7_800", mode="fit", orientation="portrait")
    assert r["result"]["size"] == "480×800"
    err, _txt = c.tool("edit_vc", op="new_page", preview=True)
    assert err
    guide = c.ok("guide", topic="edit_vc:screen")
    assert "touch7_800" in json.dumps(guide) and "fit" in json.dumps(guide)
