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
    bad = client.post("/api/songbuilder/preview", json=spec(name=""))
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
