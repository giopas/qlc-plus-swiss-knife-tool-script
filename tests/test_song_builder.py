"""Song Builder (3.9.8): a table of parts becomes one Show."""
import struct
import wave
import xml.etree.ElementTree as ET

import pytest

from core import media, song_builder as sb, workspace
from core import qxw_io
from tests.test_doctor import scene, ws
from tests.test_shows_398 import audio

NS = "http://www.qlcplus.org/Workspace"


def chaser_fn(fid, name="Pulse", run="SingleShot", steps=("5", "6"), hold=500):
    st = "".join(f'<Step Number="{i}" FadeIn="0" Hold="{hold}" FadeOut="0">{s}</Step>' for i, s in enumerate(steps))
    return (f'<Function ID="{fid}" Type="Chaser" Name="{name}"><Speed FadeIn="0" FadeOut="0" Duration="{hold}"/>'
            f'<Direction>Forward</Direction><RunOrder>{run}</RunOrder>'
            f'<SpeedModes FadeIn="PerStep" FadeOut="PerStep" Duration="Common"/>{st}</Function>')


def engine_of(functions):
    return qxw_io.qxw_bytes and ws(functions).find(f"{{{NS}}}Engine")


def spec(**kw):
    d = {"name": "Galvanize", "bpm": 120, "beats_per_bar": 4,
         "parts": [{"name": "Intro", "function_id": "5", "length": "2 bars", "repeat": 1},
                   {"name": "Verse", "function_id": "6", "length": "4s", "repeat": 2}],
         "music": {}}
    d.update(kw)
    return d


def items(show):
    return [(t.get("Name"), i["function"], i["start"], i["duration"]) for t in show.findall(f"{{{NS}}}Track")
            for i in media.show_items(ET.fromstring(ET.tostring(show)))
            if i["track"] == t.get("Name")]


def test_lengths():
    assert sb.parse_length("2 bars", 120, 4) == 4000
    assert sb.parse_length("16 beats", 120) == 8000
    assert sb.parse_length("5s") == 5000 and sb.parse_length("0:05") == 5000 and sb.parse_length("1500ms") == 1500
    assert sb.parse_length("12") == 12000
    with pytest.raises(ValueError, match="BPM"):
        sb.parse_length("2 bars", 0)
    with pytest.raises(ValueError):
        sb.parse_length("soon")
    assert sb.parse_fade("") == 0 and sb.parse_fade("2") == 2000 and sb.parse_fade("500ms") == 500


def test_a_table_becomes_one_show_with_parts_back_to_back():
    eng = engine_of(scene("5") + scene("6"))
    out = sb.build(eng, spec(), 100)
    show = next(f for f in eng if f.get("ID") == out["show_id"])
    assert show.get("Type") == "Show" and show.get("Name") == "Galvanize"
    assert out["length_ms"] == 4000 + 8000
    tr = {t.get("Name"): [(i.get("ID"), i.get("StartTime"), i.get("Duration")) for i in t] for t in show.findall(f"{{{NS}}}Track")}
    assert tr["Intro"] == [("5", "0", "4000")]
    assert tr["Verse"] == [("6", "4000", "4000"), ("6", "8000", "4000")]
    assert out["copies"] == []                       # no fades, no copies: the originals are used
    assert media.show_length_ms(show) == 12000


def test_fades_make_a_copy_of_the_scene_with_the_fade():
    eng = engine_of(scene("5") + scene("6"))
    t = spec()
    t["parts"][0].update(fade_in="2s", fade_out="500ms")
    out = sb.build(eng, t, 100)
    assert len(out["copies"]) == 1
    cp = next(f for f in eng if f.get("ID") == out["copies"][0])
    sp = cp.find(f"{{{NS}}}Speed")
    assert (sp.get("FadeIn"), sp.get("FadeOut")) == ("2000", "500")
    # the original scene is untouched
    orig = next(f for f in eng if f.get("ID") == "5")
    assert orig.find(f"{{{NS}}}Speed") is None or orig.find(f"{{{NS}}}Speed").get("FadeIn") in (None, "0")


def test_a_chaser_copy_loops_and_follows_the_tempo():
    eng = engine_of(scene("5") + scene("6") + chaser_fn("7"))
    t = spec(parts=[{"name": "Chorus", "function_id": "7", "length": "4 bars", "repeat": 1, "beats": "1"}])
    out = sb.build(eng, t, 100)
    cp = next(f for f in eng if f.get("ID") == out["copies"][0])
    assert cp.find(f"{{{NS}}}RunOrder").text == "Loop"
    assert {s.get("Hold") for s in cp.findall(f"{{{NS}}}Step")} == {"500"}     # 1 beat at 120 BPM
    orig = next(f for f in eng if f.get("ID") == "7")
    assert orig.find(f"{{{NS}}}RunOrder").text == "SingleShot"


def test_a_second_build_replaces_the_first():
    eng = engine_of(scene("5") + scene("6"))
    t = spec()
    t["parts"][0].update(fade_in="1s")
    first = sb.build(eng, t, 100)
    show = next(f for f in eng if f.get("ID") == first["show_id"])
    again = spec(show_id=first["show_id"])
    again["parts"][1]["repeat"] = 3
    second = sb.build(eng, again, first["next_id"])
    assert second["show_id"] == first["show_id"]
    assert not any(f.get("ID") in first["copies"] for f in eng)               # last build's copies are gone
    assert len([f for f in eng if f.get("Type") == "Show"]) == 1
    assert media.show_length_ms(show) == 4000 + 12000
    assert sb.spec_of(show)["parts"][1]["repeat"] == 3


def test_music_is_one_track_that_is_not_cut(tmp_path):
    w = tmp_path / "song.wav"
    with wave.open(str(w), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000)
        f.writeframes(struct.pack("<h", 0) * 8000 * 10)                       # 10 s
    eng = engine_of(scene("5") + scene("6"))
    out = sb.build(eng, spec(music={"path": str(w)}), 100)
    assert out["music_ms"] == 10000
    assert any("past the end of the music" in x for x in out["warnings"])      # parts run 12 s
    show = next(f for f in eng if f.get("ID") == out["show_id"])
    music = [t for t in show.findall(f"{{{NS}}}Track") if t.get("Name") == "Music"][0]
    assert music[0].get("StartTime") == "0" and music[0].get("Duration") == "10000"
    a = next(f for f in eng if f.get("ID") == out["audio_id"])
    assert a.get("Type") == "Audio" and a.find(f"{{{NS}}}Source").text == str(w)
    # building again does not make a second Audio function
    again = sb.build(eng, spec(music={"path": str(w)}, show_id=out["show_id"]), out["next_id"])
    assert again["audio_id"] == "" and len([f for f in eng if f.get("Type") == "Audio"]) == 1


def test_an_existing_audio_function_can_be_the_music():
    eng = engine_of(scene("5") + scene("6") + audio("9", "/x/a.mp3", "A").replace("60000", "20000"))
    out = sb.build(eng, spec(music={"function_id": "9"}), 100)
    assert out["music_ms"] == 20000 and out["audio_id"] == ""


def test_bad_tables_say_why():
    eng = engine_of(scene("5"))
    for bad, msg in [(spec(name=""), "name"), (spec(parts=[]), "at least one"),
                     (spec(parts=[{"name": "A", "function_id": "", "length": "1s"}]), "no look"),
                     (spec(parts=[{"name": "A", "function_id": "99", "length": "1s"}]), "not in the show"),
                     (spec(parts=[{"name": "A", "function_id": "5", "length": "x"}]), "not a length"),
                     (spec(parts=[{"name": "A", "function_id": "5", "length": "1s", "repeat": 0}]), "repeat")]:
        with pytest.raises(ValueError, match=msg):
            sb.plan(eng, bad)


def _mp3(frames, bitrate_index=9, xing=None):
    """MPEG-1 layer III, 44.1 kHz, stereo; index 9 = 128 kbps → 417-byte frames."""
    head = bytes([0xFF, 0xFB, bitrate_index << 4, 0x00])
    first = head + bytes(413)
    if xing is not None:
        body = bytearray(413)
        body[32:36] = b"Xing"
        body[36:40] = (1).to_bytes(4, "big")
        body[40:44] = xing.to_bytes(4, "big")
        first = head + bytes(body)
    return first + (head + bytes(413)) * (frames - 1)


def test_mp3_length_cbr_and_xing(tmp_path):
    p = tmp_path / "a.mp3"
    p.write_bytes(_mp3(100))
    assert abs(media.audio_length_ms(str(p)) - 2606) < 20                      # 41700 bytes at 128 kbps
    q = tmp_path / "b.mp3"
    q.write_bytes(_mp3(10, xing=1000))
    assert media.audio_length_ms(str(q)) == round(1000 * 1152 * 1000 / 44100)
    assert media.audio_length_ms(str(tmp_path / "nope.mp3")) is None
    assert media.audio_length_ms(str(tmp_path / "x.flac")) is None


def test_in_the_workspace_the_built_show_is_found_and_edited(tmp_path):
    root = ws(scene("5") + scene("6"))
    p = tmp_path / "s.qxw"
    p.write_bytes(qxw_io.qxw_bytes(root))
    workspace.load_qxw(str(p))
    out = workspace.song_build(spec())
    assert out["show_id"] in [f["id"] for f in workspace.get_functions()]
    got = workspace.song_open(out["show_id"])
    assert got["name"] == "Galvanize" and got["show_id"] == out["show_id"]
    again = workspace.song_build(dict(got, bpm=100))
    assert again["show_id"] == out["show_id"]
    assert [f for f in workspace.get_functions() if f["type"] == "Show"][0]["show_ms"] == media.show_length_ms(
        workspace._find_by_id(workspace._state["qxw_root"].find("q:Engine", workspace.NS), "Function", out["show_id"]))


# ── the routes ───────────────────────────────────────────────────────────────

def test_routes_preview_build_open(tmp_path):
    import app as app_mod
    client = app_mod.create_app().test_client()
    p = tmp_path / "s.qxw"
    p.write_bytes(qxw_io.qxw_bytes(ws(scene("5") + scene("6"))))
    workspace.load_qxw(str(p))
    r = client.post("/api/songbuilder/preview", json=spec())
    assert r.status_code == 200 and r.get_json()["length_ms"] == 12000
    half = client.post("/api/songbuilder/preview", json=spec(name=""))          # a live preview accepts a half-filled table
    assert half.status_code == 200
    bad = client.post("/api/songbuilder/build", json=spec(name=""))
    assert bad.status_code == 400 and "name" in bad.get_json()["error"]
    r = client.post("/api/songbuilder/build", json=spec())
    assert r.status_code == 200
    sid = r.get_json()["show_id"]
    assert client.get("/api/songbuilder/list").get_json() == [{"id": sid, "name": "Galvanize"}]
    assert client.get("/api/songbuilder/open?id=" + sid).get_json()["parts"][1]["repeat"] == 2
    assert client.get("/api/songbuilder/open?id=5").status_code == 400        # a scene, not a built song
    w = tmp_path / "a.wav"
    with wave.open(str(w), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000); f.writeframes(b"\0\0" * 8000)
    m = client.post("/api/songbuilder/music", json={"path": str(w)}).get_json()
    assert m == {"name": "a.wav", "found": True, "length_ms": 1000}
    assert client.post("/api/songbuilder/music", json={"path": "/etc/passwd"}).status_code == 400


# ── units, to the end, until, half-filled tables ─────────────────────────────

def test_the_song_counts_in_seconds_bars_or_beats():
    eng = engine_of(scene("5") + scene("6"))
    for unit, text, ms in [("seconds", "8", 8000), ("bars", "2", 4000), ("beats", "8", 4000)]:
        t = spec(unit=unit, parts=[{"name": "A", "function_id": "5", "length": text}])
        assert sb.plan(eng, t)["length_ms"] == ms, unit
    # an explicit unit still wins, as in 'sixteen beats' on a song that counts in bars
    assert sb.plan(eng, spec(unit="bars", parts=[{"name": "A", "function_id": "5", "length": "16 beats"}]))["length_ms"] == 8000
    with pytest.raises(ValueError, match="BPM"):
        sb.plan(eng, spec(unit="bars", bpm=0, parts=[{"name": "A", "function_id": "5", "length": "2"}]))
    with pytest.raises(ValueError, match="seconds, bars or beats"):
        sb.plan(eng, spec(unit="days"))


def test_to_the_end_fills_up_to_the_music(tmp_path):
    w = tmp_path / "m.wav"
    with wave.open(str(w), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000); f.writeframes(b"\0\0" * 8000 * 30)    # 30 s
    eng = engine_of(scene("5") + scene("6"))
    t = spec(music={"path": str(w)}, parts=[{"name": "A", "function_id": "5", "length": "10s"},
                                             {"name": "B", "function_id": "6", "length": "to the end"}])
    p = sb.plan(eng, t)
    assert [r["length_ms"] for r in p["parts"]] == [10000, 20000] and p["free_ms"] == 0 and p["warnings"] == []
    first = [{"name": "A", "function_id": "5", "length": "to the end"}, {"name": "B", "function_id": "6", "length": "5s"}]
    with pytest.raises(ValueError, match="only be the last"):
        sb.plan(eng, spec(music={"path": str(w)}, parts=first))
    with pytest.raises(ValueError, match="needs the length of the music"):
        sb.plan(eng, spec(parts=[{"name": "A", "function_id": "5", "length": "end"}]))
    with pytest.raises(ValueError, match="cannot be repeated"):
        sb.plan(eng, spec(music={"path": str(w)}, parts=[{"name": "A", "function_id": "5", "length": "end", "repeat": 2}]))


def test_until_counts_from_the_beginning_of_the_song():
    eng = engine_of(scene("5") + scene("6"))
    t = spec(parts=[{"name": "A", "function_id": "5", "length": "10s"},
                    {"name": "B", "function_id": "6", "length": "until 0:25"},
                    {"name": "C", "function_id": "5", "length": "until bar 17"}])            # bar 17 at 120 BPM = 32 s
    assert [r["length_ms"] for r in sb.plan(eng, t)["parts"]] == [10000, 15000, 7000]
    with pytest.raises(ValueError, match="not after the start"):
        sb.plan(eng, spec(parts=[{"name": "A", "function_id": "5", "length": "10s"},
                                 {"name": "B", "function_id": "6", "length": "until 5"}]))
    # in a song that counts in bars a bare number after 'until' is a bar NUMBER: bar 1 is the beginning
    t = spec(unit="bars", parts=[{"name": "A", "function_id": "5", "length": "until 3"}])
    assert sb.plan(eng, t)["length_ms"] == 4000          # bar 3 starts after two bars of 2 s


def test_a_half_filled_table_still_gives_a_preview():
    eng = engine_of(scene("5"))
    t = spec(name="", parts=[{"name": "A", "function_id": "5", "length": "10s"},
                             {"name": "B", "function_id": "", "length": "5s"},
                             {"name": "C", "function_id": "5", "length": "soon"}])
    p = sb.plan(eng, t, lenient=True)
    assert [r["length_ms"] for r in p["parts"]] == [10000, 5000, 0]       # no look keeps its length, so the bar can show it
    assert "no look" in p["parts"][1]["issue"] and "not a length" in p["parts"][2]["issue"]
    with pytest.raises(ValueError):
        sb.plan(eng, t)                                           # building stays strict


def test_free_time_is_what_the_music_has_left(tmp_path):
    w = tmp_path / "m.wav"
    with wave.open(str(w), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000); f.writeframes(b"\0\0" * 8000 * 30)
    eng = engine_of(scene("5"))
    p = sb.plan(eng, spec(music={"path": str(w)}, parts=[{"name": "A", "function_id": "5", "length": "10s"}]))
    assert p["free_ms"] == 20000


def test_limits():
    eng = engine_of(scene("5"))
    many = [{"name": "A", "function_id": "5", "length": "1s", "repeat": 64}] * 60               # 3840 items
    with pytest.raises(ValueError, match="more than"):
        sb.plan(eng, spec(parts=many))
    with pytest.raises(ValueError, match="at most"):
        sb.plan(eng, spec(parts=[{"name": "A", "function_id": "5", "length": "1s"}] * 301))
    with pytest.raises(ValueError, match="longer than a day"):
        sb.plan(eng, spec(parts=[{"name": "A", "function_id": "5", "length": "999999s"}]))
    with pytest.raises(ValueError, match="not a path"):
        sb.plan(eng, spec(music={"path": "/x/\n/a.mp3"}))
    bad = ET.fromstring('<Function xmlns="%s" ID="10" Type="Show" Name="x" SwissKnifeSong="[1,2]"/>' % workspace.NS['q'])
    assert sb.spec_of(bad) is None                                                              # a table must be an object


# ── security (3.9.8) ─────────────────────────────────────────────────────────

def test_song_builder_page_has_no_inline_handler_that_carries_a_name_or_id_from_the_show():
    import os
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static/js/songbuilder.js"), encoding="utf-8").read()
    assert "sbdPickChoose('" not in js                         # ids travel in data-id, read by one listener
    assert "innerHTML = d.error" not in js and "_sbdOut(d.error" not in js
    for line in js.splitlines():                               # every inline handler passes only the row number
        for call in __import__("re").findall(r'on\w+="([^"]*)"', line):
            assert "${_sbdEsc" not in call and "${f." not in call, call


def test_music_route_only_looks_at_sound_files(tmp_path):
    from app import create_app
    c = create_app().test_client()
    secret = tmp_path / "passwd.txt"; secret.write_text("x")
    r = c.post("/api/songbuilder/music", json={"path": str(secret)})
    assert r.status_code == 400 and "sound file" in r.get_json()["error"]
    assert c.post("/api/songbuilder/music", json={"path": ""}).status_code == 400


def test_a_huge_or_wrong_table_stored_on_a_show_is_ignored():
    big = '<Function xmlns="%s" ID="10" Type="Show" Name="x" SwissKnifeSong="%s"/>' % (workspace.NS["q"], "a" * 300_000)
    assert sb.spec_of(ET.fromstring(big)) is None
