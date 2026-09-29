"""VC Builder (WORKPLAN Phase 2.4)."""
import os
import shutil

import pytest

import app
from core import qxw_io, vc_builder as vb, vc_ops
from core.doctor import check, load_qxf_defs
from core.doctor.fixes import _unlink_function
from core.quick_start import nomenclature
from core.vc_ops import VcOpError

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
DEFS = load_qxf_defs([CORPUS])
FEST = os.path.join(CORPUS, "Festival_14fix.qxw")
QS6 = os.path.join(CORPUS, "QuickStart_6fix.qxw")


def _root(p=FEST):
    r = qxw_io.load_qxw(p).getroot()          # namespaced, as the app holds it
    vc_ops.fix_duplicate_ids(r)
    return r


def _pages(r):
    return vb._pages(vc_ops._vc(r))


def _w(r, wid):
    by_id, _ = vc_ops._index(vc_ops._vc(r))
    return by_id[str(wid)][0]


def _errors(r):
    s = qxw_io.strip_ns(qxw_io.loads_qxw(qxw_io.qxw_bytes(r)))
    return {(f.code, f.location, f.message) for f in check(s, DEFS).errors}


def test_create_every_kind_and_wire():
    r = _root()
    before = _errors(r)
    pid = vc_ops.new_page(r, "Build")["page_id"]
    page = next(p for p in _pages(r) if p.get("ID") == pid)
    ids = []
    for kind in vb.KINDS:
        d = vb.create_widget(r, page.get("ID"), kind, f"new {kind}")
        ids.append(d["new_ids"][0])
    assert len(set(ids)) == len(ids)
    rects = [vb._rect(_w(r, i)) for i in ids]
    for i, a in enumerate(rects):                                   # no overlaps among new ones
        for b in rects[i + 1:]:
            assert not vb._overlaps(a, b, 0)
    b = vb.create_widget(r, page.get("ID"), "Button", "Look", func_id="100")
    assert "Scene 100" in b["wired"] and _w(r, b["new_ids"][0]).find(vc_ops._NS + "Function").get("ID") == "100"
    cl = ids[vb.KINDS.index("CueList")]
    with pytest.raises(VcOpError):
        vb.wire(r, cl, "100")                                       # a scene on a CueList
    assert "Chaser 0" in vb.wire(r, cl, "0")["wired"]
    assert _errors(r) <= before                                     # nothing new for the Doctor
    with pytest.raises(VcOpError):
        vb.create_widget(r, page.get("ID"), "Knob")
    with pytest.raises(VcOpError):
        vb.wire(r, ids[0], "99999")


def test_slider_playback_wiring_and_unlink():
    r = qxw_io.strip_ns(_root())
    page = _pages(r)[1]
    sid = vb.create_widget(r, page.get("ID"), "Slider", "Fader")["new_ids"][0]
    vb.wire(r, sid, "100")
    s = _w(r, sid)
    assert s.findtext("SliderMode") == "Playback" and s.find("Playback").findtext("Function") == "100"
    from core.doctor.checks import _Workspace
    assert _Workspace.widget_function_refs(s) == ["100"]
    assert any("Fader" in x for x in _unlink_function(r, "100"))
    assert s.find("Playback").findtext("Function") == vb.NONE_ID
    vb.wire(r, sid, "")
    assert s.findtext("SliderMode") == "Submaster" and s.find("Playback") is None


def test_delete_and_duplicate():
    r = _root()
    page = _pages(r)[0]
    frame = next(c for c in page if vc_ops._local(c.tag) == "Frame")
    n_inside = sum(1 for w in frame.iter() if vc_ops._is_widget(w))
    assert vb.delete_widgets(r, [frame.get("ID")])["deleted"] == n_inside
    with pytest.raises(VcOpError):
        vb.delete_widgets(r, [page.get("ID")])
    btn = next(c for c in page if vc_ops._local(c.tag) == "Button")
    x, y, _, _ = vb._rect(btn)
    d = vb.duplicate_widgets(r, [btn.get("ID")])
    dup = _w(r, d["new_ids"][0])
    assert vb._rect(dup)[:2] == (x + 20, y + 20) and dup.get("Caption") == btn.get("Caption")
    assert not list(dup.iter(vc_ops._NS + "Input")) and not list(dup.iter(vc_ops._NS + "Key"))


def test_pages():
    r = _root()
    caps = lambda: [p.get("Caption") for p in _pages(r)]  # noqa: E731
    assert caps() == ["MASTER SHOW", "Band A", "Band B", "Band C"]
    pid = _pages(r)[2].get("ID")
    vb.move_page(r, pid, 0)
    assert caps() == ["Band B", "MASTER SHOW", "Band A", "Band C"]
    vb.move_page(r, pid, 99)
    assert caps()[-1] == "Band B"
    vb.rename_page(r, pid, "Encore")
    assert caps()[-1] == "Encore"
    with pytest.raises(VcOpError):
        vb.rename_page(r, pid, " ")
    for p in _pages(r)[1:]:
        vb.delete_page(r, p.get("ID"))
    with pytest.raises(VcOpError):
        vb.delete_page(r, _pages(r)[0].get("ID"))


def test_label_panel_columns():
    r = _root()
    prof = nomenclature.load_profile("prefix")
    lines = vb.legend_lines(prof)
    assert lines[0].startswith("A — ")
    d = vb.label_panel(r, _pages(r)[1].get("ID"), lines, columns=2)
    frame = _w(r, d["new_ids"][0])
    labels = [c for c in frame if vc_ops._local(c.tag) == "Label"]
    assert [lab.get("Caption") for lab in labels] == lines
    rows = (len(lines) + 1) // 2
    assert vb._rect(labels[0])[0] == vb._rect(labels[rows - 1])[0]      # column-major
    assert vb._rect(labels[rows])[0] > vb._rect(labels[0])[0]
    fw, fh = vb._rect(frame)[2:]
    assert all(vb._rect(lab)[0] + vb._rect(lab)[2] <= fw and vb._rect(lab)[1] + vb._rect(lab)[3] <= fh for lab in labels)


def test_auto_arrange_by_nomenclature():
    r = _root()
    eng = vb._engine(r)
    names = {"100": "FD · Wave", "101": "AS · Red", "102": "AD · Fade", "105": "AS · Blue", "104": "PANIC"}
    for f in eng:
        if f.get("ID") in names:
            f.set("Name", names[f.get("ID")])
    page = _pages(r)[1]
    fr = vb.create_widget(r, page.get("ID"), "Frame", "Mix", w=900, h=400)["new_ids"][0]
    for fid in ["100", "104", "101", "102", "105"]:
        vb.create_widget(r, fr, "Button", fid, func_id=fid)
    d = vb.auto_arrange(r, fr, nomenclature.load_profile("prefix"))
    assert d == {"arranged": 5, "groups": 3}                     # A · F · no prefix
    btns = sorted([c for c in _w(r, fr) if vc_ops._local(c.tag) == "Button"],
                  key=lambda b: (vb._rect(b)[1], vb._rect(b)[0]))
    assert [b.get("Caption") for b in btns] == ["105", "101", "102", "100", "104"]   # AS Blue, AS Red, AD | FD | (no prefix)
    ys = [vb._rect(b)[1] for b in btns]
    assert ys[0] == ys[1] == ys[2] < ys[3] < ys[4]


def test_screen_profiles():
    r = _root()
    d = vb.apply_screen(r, "macbook", scale=True)
    assert d["pages"] == 4 and d["size"] == "1650×884" and d["outside"] == 0
    assert all(vb._rect(p)[2:] == (1650, 884) for p in _pages(r))
    r2 = _root()
    d2 = vb.apply_screen(r2, "ipad", [_pages(r2)[0].get("ID")])
    assert d2["pages"] == 1 and d2["outside"] > 0                    # not scaled: some widgets fall outside
    with pytest.raises(VcOpError):
        vb.apply_screen(r, "cinema")


def test_templates_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_VC_TEMPLATES", str(tmp_path))
    r = _root()
    page = _pages(r)[1]
    s = vb.save_template(r, page.get("ID"), "Band page")
    assert s["widgets"] > 5 and s["functions"] > 0
    assert [t["name"] for t in vb.list_templates()] == ["Band page"]
    # same show: every function found, widget IDs new, no bindings
    r2 = _root()
    n_before = len(_pages(r2))
    a = vb.apply_template(r2, "Band page", "Copy")
    assert a["missing"] == [] and a["matched"] == s["functions"] and len(_pages(r2)) == n_before + 1
    new = _pages(r2)[-1]
    assert new.get("Caption") == "Copy" and not list(new.iter(vc_ops._NS + "Input"))
    assert not vc_ops.duplicate_ids(r2)
    # another show: functions missing → listed, unwired
    r3 = qxw_io.load_qxw(QS6).getroot()
    a3 = vb.apply_template(r3, "Band page")
    assert a3["missing"] and a3["matched"] == 0
    refs = [e.get("ID") for e in _pages(r3)[-1].iter(vc_ops._NS + "Function")]
    assert set(refs) <= {vb.NONE_ID}
    assert vb.delete_template("Band page") and not vb.list_templates()
    with pytest.raises(VcOpError):
        vb.apply_template(r3, "Band page")


def test_setlist_cuelist():
    r = _root()
    d = vb.setlist_cuelist(r, "0", page_id=_pages(r)[1].get("ID"))
    cl = _w(r, d["new_ids"][0])
    assert vc_ops._local(cl.tag) == "CueList" and cl.findtext(vc_ops._NS + "Chaser") == "0"
    old = next(w for w in _pages(r)[1].iter(vc_ops._NS + "CueList") if w is not cl)
    d2 = vb.setlist_cuelist(r, "0", cuelist_id=old.get("ID"))
    assert "Chaser 0" in d2["wired"] and d2["new_ids"] == []
    with pytest.raises(VcOpError):
        vb.setlist_cuelist(r, "100")


def test_api(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_VC_TEMPLATES", str(tmp_path / "tpl"))
    p = tmp_path / "Fest.qxw"
    shutil.copy(FEST, p)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    assert c.post("/api/vc/op", json={"op": "fix_ids"}).status_code == 200
    info = c.get("/api/vc/builder-info?profile=prefix").get_json()
    assert info["kinds"] == list(vb.KINDS) and info["legend"] and info["chasers"]
    pages = c.get("/api/vc/pages").get_json()["pages"]
    r = c.post("/api/vc/op", json={"op": "create", "parent_id": pages[1]["id"], "kind": "Button",
                                   "caption": "API", "func_id": "100"}).get_json()
    assert r["ok"] and r["new_ids"]
    tree = c.get("/api/vc/tree").get_json()
    node = [n for n in tree["pages"][1]["children"] if n["id"] == r["new_ids"][0]][0]
    assert node["func_id"] == "100" and node["func_name"]
    assert c.post("/api/vc/op", json={"op": "delete", "ids": r["new_ids"]}).get_json()["deleted"] == 1
    assert c.post("/api/vc/undo").get_json()["ok"]
    assert c.post("/api/vc/op", json={"op": "wire", "widget_id": r["new_ids"][0], "func_id": "99999"}).status_code == 400
    t = c.post("/api/vc/template", json={"page_id": pages[1]["id"], "name": "T1"}).get_json()
    assert t["ok"] and t["templates"][0]["name"] == "T1"
    assert c.post("/api/vc/op", json={"op": "apply_template", "name": "T1"}).get_json()["ok"]
    assert c.post("/api/vc/template", json={"action": "delete", "name": "T1"}).status_code == 200
    out = tmp_path / "Fest_v2.qxw"
    assert c.post("/api/vc/export-qxw", json={"path": str(out)}).get_json()["ok"]
    assert out.is_file() and p.read_bytes() == open(FEST, "rb").read()
