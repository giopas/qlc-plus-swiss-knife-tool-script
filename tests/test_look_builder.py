"""Look and Chaser Builder (WORKPLAN Phase 2.3)."""
import os
import shutil

import pytest

import app
from core import look_builder as lb, qxw_io, vc_ops
from core.doctor import check, load_qxf_defs
from core.quick_start import nomenclature

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
DEFS = load_qxf_defs([CORPUS])
FEST = os.path.join(CORPUS, "Festival_14fix.qxw")
QS6 = os.path.join(CORPUS, "QuickStart_6fix.qxw")


def _root(p=FEST):
    return qxw_io.load_qxw(p).getroot()


def _fns(root, t=None):
    return [f for f in root.find("Engine").findall("Function") if t is None or f.get("Type") == t]


# ── data ─────────────────────────────────────────────────────────────────────

def test_palettes_and_colours():
    p = lb.palettes()
    assert {"warm", "cold", "scenic"} <= set(p)
    assert lb.colour("amber") == {"name": "Amber", "hex": "#FFB000", "white": 0.0}
    assert lb.colour("#ff8800")["hex"] == "#FF8800"
    assert lb.colour({"name": "Mine", "hex": "10ff20"}) == {"name": "Mine", "hex": "#10FF20", "white": 0.0}
    assert lb.colour("Cold White")["white"] == 1.0
    with pytest.raises(ValueError):
        lb.colour("no such colour")
    with pytest.raises(ValueError):
        lb.colour({"name": "x", "hex": "#12"})


def test_step_time():
    assert lb.step_time(bpm=120, note="1/4") == 500
    assert lb.step_time(bpm=120, note="1/8") == 250
    assert lb.step_time(bpm=128, note="1/16") == 117
    assert lb.step_time(bpm=60, note="1/1") == 4000
    assert lb.step_time(step_ms=280) == 280
    for bad in (dict(step_ms=5), dict(bpm=10), dict(bpm=120, note="1/3")):
        with pytest.raises(ValueError):
            lb.step_time(**bad)


def test_patterns():
    P = lb.pattern_states
    on = lambda st: [[i for i, x in enumerate(s) if x] for s in st]  # noqa: E731
    assert on(P("all", 4)) == [[0, 1, 2, 3], []]
    assert on(P("all", 4, n_colours=3)) == [[0, 1, 2, 3]] * 3
    assert on(P("alternate", 5)) == [[0, 1, 2], [3, 4]]
    assert on(P("alternate", 4, split="odd_even")) == [[0, 2], [1, 3]]
    assert on(P("chase", 4)) == [[0], [1], [2], [3]]
    assert on(P("pingpong", 4)) == [[0], [1], [2], [3], [2], [1]]
    assert on(P("pingpong", 1)) == [[0]]
    assert on(P("buildup", 3)) == [[0], [0, 1], [0, 1, 2]]
    assert on(P("chase", 3, steps=5)) == [[0], [1], [2], [0], [1]]
    r1 = P("random", 6, 12, seed=7, on_count=2)
    assert r1 == P("random", 6, 12, seed=7, on_count=2)          # seeded = deterministic
    assert r1 != P("random", 6, 12, seed=8, on_count=2)
    assert len(r1) == 12 and all(sum(s) == 2 for s in r1)
    assert all(a != b for a, b in zip(r1, r1[1:]))                  # no step repeats the previous
    with pytest.raises(ValueError):
        P("sideways", 3)


def test_chaser_spec_validation():
    s = lb.chaser_spec({"pattern": "chase", "bpm": 120, "note": "1/8", "fade": "fade", "fade_pct": 50,
                        "colours": ["Red", "Blue"]})
    assert s["step_ms"] == 250 and s["fade_ms"] == 125 and [c["name"] for c in s["colours"]] == ["Red", "Blue"]
    assert lb.chaser_spec({"step_ms": 300})["fade_ms"] == 0          # cut by default
    for bad in ({"pattern": "x", "step_ms": 300}, {"step_ms": 300, "fade": "fade", "fade_pct": 120},
                {"step_ms": 300, "steps": 999}):
        with pytest.raises(ValueError):
            lb.chaser_spec(bad)


# ── groups, values, preview ─────────────────────────────────────────────────

def test_groups():
    g = lb.groups(_root(), DEFS)
    assert g[0]["id"] == "all" and len(g[0]["fixtures"]) == 14 and g[0]["supported"] == 14
    ceiling = next(x for x in g if x["name"] == "Ceiling")
    assert ceiling["fixtures"] == ["0", "1", "2", "3", "4", "5"]      # head order X 0..5
    # without definitions nothing can be built
    assert lb.groups(_root(), {})[0]["supported"] == 0


def test_every_channel_declared_and_colour_right():
    root = _root()
    res = lb.build(root, DEFS, {"looks": [{"group": "all", "colours": ["Red", "Amber", "Cold White"]}]})
    looks = [f for f in _fns(res["root"], "Scene") if f.get("Path") == "Look Builder/Looks"]
    assert [f.get("Name") for f in looks] == ["Red", "Amber", "Cold White"]
    chans = {(f.findtext("ID") or "").strip(): int(f.findtext("Channels"))
             for f in res["root"].find("Engine").findall("Fixture")}
    info = lb._fixture_info(res["root"], DEFS)
    for sc, want in zip(looks, ("#FF0000", "#FFB000", "#FFFFFF")):
        vals = sc.findall("FixtureVal")
        assert len(vals) == 14
        for v in vals:
            pairs = [int(x) for x in v.text.split(",")]
            chs = pairs[0::2]
            assert chs == list(range(chans[v.get("ID")]))           # every channel, in order
            got = lb.simulate(info[v.get("ID")], dict(zip(chs, pairs[1::2])))
            assert got == want, (sc.get("Name"), v.get("ID"), got)


def test_preview_chaser_chase():
    pv = lb.preview_chaser(_root(), DEFS, {"group": "0", "pattern": "chase", "colours": ["Red"], "step_ms": 280})
    assert pv["steps"] == 6 and pv["step_ms"] == 280 and pv["fade_ms"] == 0
    for i, row in enumerate(pv["fixtures"]):
        assert row["cells"] == ["#FF0000" if k == i else "#000000" for k in range(6)]


def test_preview_background_and_colour_per_fixture():
    pv = lb.preview_chaser(_root(), DEFS, {"group": "0", "pattern": "chase", "colours": ["Red", "Green"],
                                           "colour_mode": "fixture", "step_ms": 300,
                                           "background": {"colour": "Blue", "level": 1.0}})
    rows = pv["fixtures"]
    assert rows[0]["cells"][0] == "#FF0000" and rows[1]["cells"][1] == "#00FF00"
    assert rows[0]["cells"][1] == "#0000FF"                          # background when off


def test_preview_look():
    pv = lb.preview_look(_root(), DEFS, "0", ["Blue"], 0.5)
    assert len(pv["fixtures"]) == 6 and pv["looks"][0]["cells"] == ["#000080"] * 6


# ── build ────────────────────────────────────────────────────────────────────

PLAN = {"looks": [{"group": "all", "colours": ["Amber", "Blue"]}],
        "chasers": [{"group": "0", "pattern": "pingpong", "colours": ["Red"], "bpm": 120, "note": "1/8",
                     "fade": "fade", "fade_pct": 50, "name": "Sweep"}],
        "vc_page": "Looks"}


def test_build_chaser_xml_and_ids():
    root = _root()
    before = qxw_io.qxw_bytes(root)
    max_id = max(int(f.get("ID")) for f in _fns(lb._stripped(root)))
    res = lb.build(root, DEFS, PLAN)
    assert qxw_io.qxw_bytes(root) == before                          # input untouched
    new = [f for f in _fns(res["root"]) if int(f.get("ID")) > max_id]
    assert [int(f.get("ID")) for f in new] == list(range(max_id + 1, max_id + 1 + len(new)))
    ch = next(f for f in new if f.get("Type") == "Chaser")
    assert ch.get("Name") == "Ceiling · Sweep" and ch.get("Path") == "Look Builder/Chasers/Ceiling · Sweep"
    sp = ch.find("Speed")
    assert (sp.get("Duration"), sp.get("FadeIn"), sp.get("FadeOut")) == ("250", "125", "125")
    assert ch.find("SpeedModes").get("Duration") == "Common"
    steps = [s.text for s in ch.findall("Step")]
    assert len(steps) == 10 and len(set(steps)) == 6                 # ping-pong reuses scenes
    assert steps[:6] == sorted(set(steps), key=steps.index)
    assert res["created"] == {"looks": 2, "chasers": 1, "step_scenes": 6, "buttons": 3}


def test_build_deterministic_and_doctor_clean():
    a = lb.run(_root(), DEFS, PLAN)
    b = lb.run(_root(), DEFS, PLAN)
    assert qxw_io.qxw_bytes(a["root"]) == qxw_io.qxw_bytes(b["root"])
    assert a["doctor"]["new_errors"] == [] and a["doctor"]["new_warnings"] == []
    assert not a["blocked"]


def test_vc_page_buttons():
    res = lb.build(_root(), DEFS, PLAN)
    vc = res["root"].find("VirtualConsole")
    page = [p for p in vc if p.tag in ("Frame", "SoloFrame")][-1]
    assert page.get("Caption") == "Looks"
    assert not list(page.iter("Input")) and not list(page.iter("Key"))   # no copied page bindings
    frames = page.findall("SoloFrame")
    assert [f.get("Caption") for f in frames] == ["Looks · All fixtures", "Chasers"]
    btns = [b for f in frames for b in f.findall("Button")]
    names = {f.get("ID"): f.get("Name") for f in _fns(res["root"])}
    assert [names[b.find("Function").get("ID")] for b in btns] == ["Amber", "Blue", "Ceiling · Sweep"]
    assert btns[0].findtext("Appearance/BackgroundColor") == str(0xFFFFB000)


def test_no_vc_page_means_d016_warnings_only():
    res = lb.run(_root(), DEFS, {**PLAN, "vc_page": None})
    assert res["created"]["buttons"] == 0 and not res["blocked"]
    assert res["doctor"]["new_errors"] == []
    assert all(w.startswith("D016") for w in res["doctor"]["new_warnings"])


def test_names_unique_and_nomenclature():
    res = lb.build(_root(QS6), DEFS, {"looks": [{"group": "all", "colours": ["Amber", "Amber"]}]})
    names = [f.get("Name") for f in _fns(res["root"], "Scene")][-2:]
    assert names == ["Amber", "Amber (2)"]
    nom = nomenclature.load_profile("prefix")
    res = lb.build(_root(), DEFS, {"looks": [{"group": "all", "colours": ["Amber"]}],
                                   "chasers": [{"group": "0", "pattern": "chase", "colours": ["Red"],
                                                "step_ms": 300, "name": "Run"}]}, nom)
    got = [f.get("Name") for f in _fns(res["root"]) if f.get("Type") in ("Scene", "Chaser")
           and f.get("Path", "").startswith("Look Builder") and "step" not in f.get("Name")]
    assert got == ["AS · Amber", "CD · Run"]


def test_panic_reset_script_stops_new_functions():
    root = _root(QS6)
    res = lb.build(root, DEFS, PLAN)
    panic = next(f for f in _fns(res["root"], "Script") if "PANIC" in f.get("Name"))
    cmds = [c.text for c in panic.findall("Command")]
    top = [f["id"] for f in res["functions"]]
    first_start = next(i for i, c in enumerate(cmds) if c.startswith("startfunction"))
    for fid in top:
        assert cmds.index(f"stopfunction%3A{fid}") < first_start
    assert any("PANIC RESET" in x for x in res["log"])


def test_unsupported_fixtures_skipped():
    res = lb.build(_root(), {}, {"looks": [{"group": "all", "colours": ["Red"]}]})
    assert res["created"]["looks"] == 0 and any("no fixture with a definition" in n for n in res["notes"])
    with pytest.raises(ValueError):
        lb.build(_root(), DEFS, {"looks": [{"group": "99", "colours": ["Red"]}]})


def test_build_file_never_overwrites(tmp_path):
    p = tmp_path / "Fest.qxw"
    shutil.copy(FEST, p)
    before = p.read_bytes()
    res = lb.build_file(str(p), DEFS, PLAN)
    assert p.read_bytes() == before
    assert res["output"].endswith("Fest_v2.qxw") and os.path.isfile(res["report_path"])
    assert res["report_path"].endswith("Fest_v2_looks_report.txt")
    txt = open(res["report_path"], encoding="utf-8").read()
    assert "chaser" in txt and "WORKSPACE DOCTOR" in txt
    assert check(qxw_io.load_qxw(res["output"]).getroot(), DEFS).errors == \
        check(_root(), DEFS).errors


def test_new_page_strips_template_bindings():
    root = qxw_io.strip_ns(_root())
    pid = vc_ops.new_page(root, "X")["page_id"]
    page = next(p for p in root.find("VirtualConsole") if p.get("ID") == pid)
    assert not list(page.iter("Input")) and page.find("Enable") is None


# ── presets ──────────────────────────────────────────────────────────────────

def test_presets(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    built = lb.presets()
    assert built and all(p["builtin"] for p in built)
    for p in built:
        lb.chaser_spec(p)                                             # every built-in is valid
    drive = next(p for p in built if p["name"].startswith("Drive"))
    assert (drive["steps"], drive["step_ms"], drive["fade"]) == (8, 280, "cut")
    lb.save_preset({"name": "My Song", "pattern": "buildup", "bpm": 100, "note": "1/4", "colours": ["Red"],
                    "group": "ignored"})
    mine = [p for p in lb.presets() if not p["builtin"]]
    assert [p["name"] for p in mine] == ["My Song"] and "group" not in mine[0]
    lb.save_preset({"name": "my song", "pattern": "chase", "step_ms": 200})      # replace by name
    assert [p["pattern"] for p in lb.presets() if not p["builtin"]] == ["chase"]
    with pytest.raises(ValueError):
        lb.save_preset({"name": drive["name"], "step_ms": 200})
    with pytest.raises(ValueError):
        lb.save_preset({"name": "bad", "step_ms": 1})
    assert lb.delete_preset("MY SONG") and not lb.delete_preset("MY SONG")


# ── API ──────────────────────────────────────────────────────────────────────

def test_api(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    p = tmp_path / "Fest.qxw"
    shutil.copy(FEST, p)
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    c = app.create_app().test_client()
    assert c.get("/api/looks/options").status_code in (200, 400)
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    o = c.get("/api/looks/options").get_json()
    assert o["groups"][0]["supported"] == 14 and "warm" in o["palettes"] and len(o["patterns"]) == 6
    pv = c.post("/api/looks/preview-chaser", json={"group": "0", "pattern": "chase", "colours": ["Red"],
                                                   "bpm": 120, "note": "1/4"}).get_json()
    assert pv["steps"] == 6 and pv["step_ms"] == 500
    assert c.post("/api/looks/preview-chaser", json={"pattern": "x", "step_ms": 100}).status_code == 400
    ck = c.post("/api/looks/check", json={**PLAN, "nomenclature": "plain"}).get_json()
    assert ck["created"]["chasers"] == 1 and not ck["blocked"]
    assert c.post("/api/looks/check", json={}).status_code == 400
    r = c.post("/api/looks/build", json=PLAN)
    assert r.status_code == 200 and r.headers["X-Suggested-Filename"] == "Fest_v2.qxw"
    root = qxw_io.loads_qxw(r.data)
    assert any(f.get("Name") == "Ceiling · Sweep" for f in root.iter() if f.tag.endswith("Function"))
    out = tmp_path / "Fest_v2.qxw"
    out.write_bytes(r.data)
    sr = c.post("/api/looks/save-report", json={"qxw_path": str(out)}).get_json()
    assert sr["name"] == "Fest_v2_looks_report.txt"
    assert c.post("/api/looks/presets", json={"name": "Mine", "step_ms": 300}).status_code == 200
    assert c.post("/api/looks/presets/delete", json={"name": "Mine"}).status_code == 200
    assert c.post("/api/looks/presets/delete", json={"name": "Mine"}).status_code == 404
