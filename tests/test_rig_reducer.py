"""Rig Reducer (WORKPLAN Phase 2.2)."""
import os
import shutil
import xml.etree.ElementTree as ET

import app
from core import qxw_io, rig_reducer as rr
from core.doctor import check, load_qxf_defs
from tests.test_doctor import FULL, button, chaser, scene, ws, PAR

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
DEFS = load_qxf_defs([CORPUS])
FEST = os.path.join(CORPUS, "Festival_14fix.qxw")


def _fest():
    return qxw_io.load_qxw(FEST).getroot()


def _key(f):
    return (f.code, f.location, f.message)


def test_fixtures_listed_one_based():
    fx = rr.fixtures(_fest())
    assert len(fx) == 14 and fx[0]["name"] == "Ceiling 1"
    assert all(f["universe"] >= 1 and f["address"] >= 1 for f in fx)


def test_festival_keep_the_pars():
    root = _fest()
    before_bytes = qxw_io.qxw_bytes(root)
    keep = [f["id"] for f in rr.fixtures(root) if "Slim Spot" not in f["model"]]
    res = rr.reduce(root, keep)
    assert qxw_io.qxw_bytes(root) == before_bytes                      # input untouched
    assert res["removed"]["fixtures"] == 6 and res["removed"]["functions"] == 11
    r = res["root"]
    ids = {(f.findtext("ID") or "").strip() for f in r.find("Engine").findall("Fixture")}
    assert ids == set(keep)
    vals = {v.get("ID") for v in r.iter("FixtureVal")}
    assert vals <= set(keep)
    assert {i.get("ID") for i in r.iter("FxItem")} <= set(keep)
    heads = {h.get("Fixture") for h in r.iter("Head")}
    assert heads <= set(keep)
    # nothing new for the Doctor (only fewer findings)
    before = {_key(f) for f in check(_fest(), DEFS).findings}
    new = [f for f in check(r, DEFS).findings if _key(f) not in before]
    assert new == []
    # pre-existing empty chasers are not "removed because empty"
    names = {f.get("Name") for f in r.find("Engine").findall("Function")}
    assert "Setlist: Band A" in names and "Rock Loop Ceiling" not in names
    assert qxw_io.qxw_bytes(rr.reduce(root, keep)["root"]) == qxw_io.qxw_bytes(r)


def _two_fixture_ws():
    fixtures = PAR.format(id=0, addr=0) + PAR.format(id=1, addr=7)
    efx = ('<Function ID="20" Type="EFX" Name="Circle"><Fixture><ID>1</ID><Head>0</Head>'
           '<Mode>0</Mode></Fixture></Function>')
    grp = ('<FixtureGroup ID="3"><Name>G</Name><Size X="1" Y="1"/>'
           '<Head X="0" Y="0" Fixture="1">0</Head></FixtureGroup>')
    mtx = '<Function ID="21" Type="RGBMatrix" Name="M"><FixtureGroup>3</FixtureGroup></Function>'
    both = (f'<Function ID="15" Type="Scene" Name="Bound"><FixtureVal ID="0">{FULL}</FixtureVal>'
            f'<FixtureVal ID="1">{FULL}</FixtureVal></Function>')
    seq = ('<Function ID="22" Type="Sequence" Name="Seq" BoundScene="15">'
           f'<Step Number="0" Values="14">0:{FULL}:1:{FULL}</Step></Function>')
    seq2 = ('<Function ID="23" Type="Sequence" Name="Seq only 1" BoundScene="11">'
            f'<Step Number="0" Values="7">1:{FULL}</Step></Function>')
    funcs = (scene("10", fixture="0") + scene("11", fixture="1") + both
             + chaser("12", ["11"]) + chaser("13", []) + efx + mtx + seq + seq2)
    slider = ('<Slider Caption="Dim" ID="30"><Level LowLimit="0" HighLimit="255" Value="0">'
              '<Channel Fixture="1">0</Channel></Level></Slider>')
    cl = '<CueList Caption="Songs" ID="31"><Chaser>12</Chaser></CueList>'
    vc = button(40, "10") + button(41, "11") + button(42, "20") + slider + cl
    root = ws(funcs, vc, fixtures=fixtures + grp)
    return root


def test_cascade_on_small_workspace():
    res = rr.reduce(_two_fixture_ws(), ["0"])
    r = res["root"]
    fids = {f.get("ID") for f in r.find("Engine").findall("Function")}
    # scene 11 (only fixture 1) → gone, chaser 12 lost its step → gone,
    # EFX 20 and matrix 21 → gone; empty-before chaser 13 stays
    assert {"11", "12", "20", "21", "23"} & fids == set() and {"10", "13", "15", "22"} <= fids
    seq = next(f for f in r.find("Engine").findall("Function") if f.get("ID") == "22")
    st = seq.find("Step")
    assert st.text == f"0:{FULL}" and st.get("Values") == "7"
    assert r.find("Engine").find("FixtureGroup") is None
    wids = {w.get("ID") for w in r.find("VirtualConsole").iter() if w.get("ID")}
    assert {"41", "42", "30", "31"} & wids == set() and "40" in wids
    assert not check(r, DEFS).errors


def test_repatch_one_based_and_overlap_reported():
    res = rr.run(_two_fixture_ws(), ["0", "1"],
                 {"1": {"name": "Front", "universe": 1, "address": 3}}, DEFS)
    fx = {f.findtext("ID"): f for f in res["root"].find("Engine").findall("Fixture")}
    assert fx["1"].findtext("Name") == "Front" and fx["1"].findtext("Address") == "2"
    assert any(w.startswith("D009") for w in res["doctor"]["new_warnings"])
    assert not res["blocked"]


def test_reduce_file_never_overwrites(tmp_path):
    src = tmp_path / "Show_v3.qxw"
    shutil.copy(FEST, src)
    before = src.read_bytes()
    keep = [f["id"] for f in rr.fixtures(qxw_io.load_qxw(str(src)).getroot())][6:]
    out = rr.reduce_file(str(src), keep, qxf_defs=DEFS)
    assert out["output"].endswith("Show_v4.qxw") and src.read_bytes() == before
    text = open(out["report_path"], encoding="utf-8").read()
    assert out["report_path"].endswith("Show_v4_reduce_report.txt")
    assert "Removed: 6 fixture(s)" in text and "── DOCTOR ──" in text


def test_api(tmp_path):
    p = tmp_path / "Fest.qxw"
    shutil.copy(FEST, p)
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    fx = c.get("/api/reducer/fixtures").get_json()["fixtures"]
    keep = [f["id"] for f in fx if "Slim Spot" not in f["model"]]
    pv = c.post("/api/reducer/preview", json={"keep": keep}).get_json()
    assert pv["removed"]["fixtures"] == 6 and not pv["blocked"]
    r = c.post("/api/reducer/reduce", json={"keep": keep, "repatch": {"6": {"name": "Drums"}}})
    assert r.status_code == 200 and r.headers["X-Suggested-Filename"] == "Fest_v2.qxw"
    root = qxw_io.loads_qxw(r.data)
    assert len(rr.fixtures(root)) == 8
    assert any(f["name"] == "Drums" for f in rr.fixtures(root))
    assert c.post("/api/reducer/reduce", json={"keep": []}).status_code == 400


def test_rename_is_not_a_new_finding():
    root = _fest()
    keep = [f["id"] for f in rr.fixtures(root) if "Slim Spot" not in f["model"]]
    res = rr.run(root, keep, {"13": {"name": "Front Fill"}}, DEFS)
    assert res["doctor"]["new_warnings"] == [] and res["doctor"]["new_errors"] == []


def test_apply_title_tells_renamed_from_repatched(tmp_path):
    """Pub-test run: renaming 6 fixtures was reported as '6 re-patched'."""
    import shutil
    import app
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus", "Pub_6fix.qxw")
    p = tmp_path / "Pub.qxw"
    shutil.copy(src, p)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    r = c.post("/api/reducer/apply", json={"keep": ["6", "7", "8", "9", "11"],
                                            "repatch": {"6": {"name": "Drums"}, "7": {"address": 200}}})
    assert r.status_code == 200, r.get_json()
    steps = c.get("/api/show/history").get_json()["steps"]
    assert steps[-1]["title"] == "kept 5 fixtures, renamed 1, re-patched 1"
