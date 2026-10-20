"""v3.8.0 — per-song tempo in the setlist (idea: the Show Tempo Sections of mjcmatrix's fork of QLC+)."""
import os
import shutil
import xml.etree.ElementTree as ET

import pytest

import app
from core import qxw_io, setlist_io as sio, setlist_tempo as tp, workspace

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


# ── the module ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("line,name,bpm", [
    ("Song name | 128BPM", "Song name", "128"),
    ("Song name|128 bpm", "Song name", "128"),
    ("Song name | 128", "Song name", "128"),
    ("Song name | 127,5 Bpm", "Song name", "127.5"),
    ("Song name - 90 BPM", "Song name", "90"),
    ("Song name (120bpm)", "Song name", "120"),
    ("99 Luftballons", "99 Luftballons", None),      # a number without the bar or the word is part of the title
    ("Route 66", "Route 66", None),
    ("Highway 61 Revisited", "Highway 61 Revisited", None),
])
def test_split_line(line, name, bpm):
    n, b, rejected = tp.split_line(line)
    assert (n, b, rejected) == (name, bpm, False)


def test_a_tempo_out_of_range_is_dropped_and_said():
    assert tp.split_line("Song | 999BPM") == ("Song", None, True)
    assert tp.split_line("Song | 10") == ("Song", None, True)
    assert tp.parse_value("500") is None and tp.parse_value("128") == 128.0 and tp.parse_value("abc") is None


def test_step_time():
    assert tp.step_ms(120) == 500
    assert tp.step_ms(128, 1) == 469
    assert tp.step_ms(60, 4) == 4000
    assert tp.step_ms(120, 0.5) == 250


def test_clean_fields():
    assert tp.clean_bpm("128 BPM") == "128" and tp.clean_bpm("") == "" and tp.clean_bpm("5") == ""
    assert tp.clean_beats("2") == "2" and tp.clean_beats("0") == "" and tp.clean_beats("x") == ""


def _chaser(steps, duration="2000", mode="Common", tempo=None, fade_in="500", fade_out="500"):
    fn = ET.Element("Function", {"ID": "9", "Type": "Chaser", "Name": "C"})
    if tempo:
        ET.SubElement(fn, "TempoType").text = tempo
    ET.SubElement(fn, "Speed", {"FadeIn": fade_in, "FadeOut": fade_out, "Duration": duration})
    ET.SubElement(fn, "SpeedModes", {"FadeIn": mode, "FadeOut": mode, "Duration": mode})
    for i, (fi, h, fo) in enumerate(steps):
        ET.SubElement(fn, "Step", {"Number": str(i), "FadeIn": str(fi), "Hold": str(h), "FadeOut": str(fo)}).text = str(100 + i)
    return fn


def test_fit_keeps_the_share_of_fade_and_the_total():
    fn = _chaser([(500, 1500, 500), (500, 1500, 500)])               # 2000 ms steps, a quarter fade
    assert tp.chaser_fit(fn, 120, 1)["status"] == "off"
    r = tp.fit_chaser(fn, 120, 1)                                       # 500 ms steps
    assert r["status"] == "fitted" and r["want_ms"] == 500
    for s in fn.findall("Step"):
        assert (s.get("FadeIn"), s.get("Hold"), s.get("FadeOut")) == ("125", "375", "125")
        assert int(s.get("FadeIn")) + int(s.get("Hold")) == 500
    spd = fn.find("Speed")
    assert spd.get("Duration") == "500" and spd.get("FadeIn") == "125"
    assert tp.chaser_fit(fn, 120, 1)["status"] == "ok"
    assert tp.fit_chaser(fn, 120, 1)["status"] == "ok"                 # nothing left to do


def test_cut_chaser_stays_a_cut():
    fn = _chaser([(0, 400, 0), (0, 400, 0), (0, 400, 0)], duration="400", fade_in="0", fade_out="0")
    tp.fit_chaser(fn, 90, 2)                                            # 1333 ms
    assert [(s.get("FadeIn"), s.get("Hold")) for s in fn.findall("Step")] == [("0", "1333")] * 3


def test_beats_per_step():
    fn = _chaser([(0, 500, 0)])
    assert tp.chaser_fit(fn, 120, 1)["status"] == "ok"
    assert tp.chaser_fit(fn, 120, 4)["status"] == "off" and tp.chaser_fit(fn, 120, 4)["want_ms"] == 2000


@pytest.mark.parametrize("fn,why", [
    (_chaser([(0, 500, 0)], tempo="Beats"), "follows the QLC+ tempo"),
    (_chaser([(0, 4294967294, 0)]), "steps wait for the pedal"),
    (_chaser([]), "no steps"),
    (ET.Element("Function", {"Type": "Scene"}), "not a chaser"),
])
def test_what_cannot_follow_a_tempo_is_left_alone(fn, why):
    before = ET.tostring(fn)
    r = tp.fit_chaser(fn, 128, 1)
    assert r["status"] == "na" and r["why"] == why
    assert ET.tostring(fn) == before


# ── the setlist text ────────────────────────────────────────────────────────

def test_import_reads_the_tempo_of_a_list():
    r = sio.parse("1. Intro | 90\n2. Smoke on the Water - 112 BPM\n3. 99 Luftballons\nRoute 66 | 300 bpm\nToo fast | 999\n")
    songs = r["sets"][0]["songs"]
    assert [(s["txt_name"], s.get("bpm")) for s in songs] == [
        ("Intro", "90"), ("Smoke on the Water", "112"), ("99 Luftballons", None), ("Route 66", "300"), ("Too fast", None)]
    assert any("2 song(s)" not in n and "tempo" in n.lower() for n in r["notes"])
    assert any("Too fast" in n for n in r["notes"])


def test_import_reads_a_bpm_column():
    r = sio.parse("Song;BPM;Hold\nOne;128;3:00\nTwo;;\nThree;127,5 BPM;\n", "x.csv")
    s = r["sets"][0]["songs"]
    assert [x.get("bpm") for x in s] == ["128", None, "127.5"]
    assert s[0]["hold"] == "180000"
    r = sio.parse("Song;Tempo\nOne;90\n")
    assert r["sets"][0]["songs"][0]["bpm"] == "90"


def test_lists_without_a_tempo_parse_as_before():
    r = sio.parse("Song A\nSong B\n")
    assert all("bpm" not in s for s in r["sets"][0]["songs"])


# ── in the show ─────────────────────────────────────────────────────────────

@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith((".qxf", ".qxw")):
            shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    client.tmp = tmp_path
    return client


def _ok(r):
    assert r.status_code < 300, r.get_data(as_text=True)[:400]
    return r.get_json()


def _funcs(c):
    return {f["name"]: f for f in c.get("/api/functions").get_json()}


def _root(c):
    return qxw_io.strip_ns(qxw_io.loads_qxw(c.get("/api/show/file").data))


def _fn(root, fid):
    return next(f for f in root.find("Engine").findall("Function") if f.get("ID") == fid)


def test_apply_times_the_copy_and_leaves_the_original(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    fn = _funcs(c)
    rock, candle = fn["Rock Loop"]["id"], fn["Candle Loop"]["id"]
    before = ET.tostring(_fn(_root(c), rock))
    rows = [{"txt_name": "Song A", "qxw_id": rock, "qxw_name": "Rock Loop", "bpm": "120"},
            {"txt_name": "Song B", "qxw_id": candle, "qxw_name": "Candle Loop", "bpm": "128", "beats": "2"},
            {"txt_name": "Song C", "qxw_id": rock, "qxw_name": "Rock Loop"}]               # no tempo
    _ok(c.post("/api/setlist/4001/details", json={"rows": rows}))
    chk = _ok(c.post("/api/setlist/tempo-check", json={"rows": rows}))["rows"]
    assert [(r["idx"], r["status"]) for r in chk] == [(0, "off"), (1, "off")]
    res = _ok(c.post("/api/setlist/4001/apply", json={"target_chaser_id": "1756"}))
    assert res["tempo"]["fitted"] == 2 and res["tempo"]["lines"]
    root = _root(c)
    assert ET.tostring(_fn(root, rock)) == before                                          # the original is untouched
    cue = {s.text: s for s in _fn(root, "1756").findall("Step")}
    a = _fn(root, next(i for i, st in cue.items() if _fn(root, i).get("Name") == "Song A"))
    b = _fn(root, next(i for i, st in cue.items() if _fn(root, i).get("Name") == "Song B"))
    d = _fn(root, next(i for i, st in cue.items() if _fn(root, i).get("Name") == "Song C"))
    ms = lambda f: {int(s.get("FadeIn")) + int(s.get("Hold")) for s in f.findall("Step")}
    assert ms(a) == {500} and ms(b) == {int(round(60000 / 128 * 2))}
    assert ms(d) == {1500}                                                                  # no BPM, as the original
    # the check now looks at the copy in the cue list
    chk = _ok(c.post("/api/setlist/tempo-check", json={"rows": rows}))["rows"]
    assert [r["status"] for r in chk] == ["ok", "ok"]
    # the build is a step of the show in progress
    hist = _ok(c.get("/api/show/history"))
    assert any("Tempo" in (st.get("detail") or "") for st in hist["steps"])


def test_apply_tempo_can_be_switched_off(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    rock = _funcs(c)["Rock Loop"]["id"]
    rows = [{"txt_name": "Song A", "qxw_id": rock, "qxw_name": "Rock Loop", "bpm": "120"}]
    _ok(c.post("/api/setlist/4001/details", json={"rows": rows}))
    res = _ok(c.post("/api/setlist/4001/apply", json={"target_chaser_id": "1756", "apply_tempo": False}))
    assert res["tempo"]["fitted"] == 0
    root = _root(c)
    cue = _fn(root, "1756").findall("Step")[0].text
    assert {int(s.get("FadeIn")) + int(s.get("Hold")) for s in _fn(root, cue).findall("Step")} == {1500}


def test_a_scene_with_a_tempo_is_reported_not_changed(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    scene = next(f for f in c.get("/api/functions").get_json() if f["type"] == "Scene")
    rows = [{"txt_name": "Song A", "qxw_id": scene["id"], "qxw_name": scene["name"], "bpm": "120"}]
    _ok(c.post("/api/setlist/4001/details", json={"rows": rows}))
    assert _ok(c.post("/api/setlist/tempo-check", json={"rows": rows}))["rows"][0]["status"] == "na"
    res = _ok(c.post("/api/setlist/4001/apply", json={"target_chaser_id": "1756"}))
    assert res["tempo"]["fitted"] == 0 and res["tempo"]["na"][0]["why"] == "not a chaser"


def test_a_row_without_a_tempo_has_no_tempo_keys(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    rows = [{"txt_name": "x", "qxw_id": "", "qxw_name": "", "in": "0", "hold": "1", "out": "0", "bpm": "", "beats": "3"}]
    _ok(c.post("/api/setlist/4001/details", json={"rows": rows}))
    got = c.get("/api/setlist/4001/details").get_json()[0]
    assert "bpm" not in got and "beats" not in got


def test_save_and_load_a_slot_file_keeps_the_tempo(c, tmp_path):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    rock = _funcs(c)["Rock Loop"]["id"]
    rows = [{"txt_name": "Song A", "qxw_id": rock, "qxw_name": "Rock Loop", "in": "0", "hold": "9", "out": "0", "bpm": "126", "beats": "2"},
            {"txt_name": "Song B", "qxw_id": rock, "qxw_name": "Rock Loop", "in": "0", "hold": "9", "out": "0"}]
    _ok(c.post("/api/setlist/4001/details", json={"rows": rows}))
    path = str(tmp_path / "slot.txt")
    _ok(c.post("/api/setlist/4001/save-file", json={"path": path}))
    lines = [l for l in open(path, encoding="utf-8").read().splitlines() if not l.startswith("#")]
    assert lines[0].endswith("|126|2") and lines[1].count("|") == 5          # a song without a tempo: the old six fields
    _ok(c.post("/api/setlist/4001/songs", json={"songs": []}))
    got = _ok(c.post("/api/setlist/4001/load-file", json={"path": path}))["rows"]
    assert (got[0]["bpm"], got[0]["beats"]) == ("126", "2") and "bpm" not in got[1]


def test_a_plain_name_and_tempo_line_loads(c, tmp_path):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    path = tmp_path / "plain.txt"
    path.write_text("Song one | 128BPM\nSong two\n", encoding="utf-8")
    got = _ok(c.post("/api/setlist/4001/load-file", json={"path": str(path)}))["rows"]
    assert (got[0]["txt_name"], got[0]["bpm"]) == ("Song one", "128") and got[1]["txt_name"] == "Song two"


def test_claude_tool_reads_the_tempo(c):
    from core import mcp_server
    assert "128BPM" in next(t for t in mcp_server.TOOLS if t["name"] == "setlist")["description"]
