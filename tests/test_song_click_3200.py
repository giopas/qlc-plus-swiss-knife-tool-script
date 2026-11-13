"""Song Builder 3.20.0: music and click together, the click on its own output, the first
beat of the music, and the tempo found by listening (core/tempo_detect.py)."""
import hashlib
import io
import os
import struct
import wave
import xml.etree.ElementTree as ET

import pytest

from core import click_track, media, qxw_io, song_builder as sb, workspace
from core.doctor import checks
from tests.test_doctor import scene, ws
from tests.test_shows_398 import audio
from tests.test_song_builder import NS, engine_of, items, spec


def _silence(path, seconds):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000)
        f.writeframes(struct.pack("<h", 0) * 8000 * seconds)
    return str(path)


def _show(eng, out):
    return next(f for f in eng if f.get("ID") == out["show_id"])


def _track(show, name):
    return [t for t in show.findall(f"{{{NS}}}Track") if t.get("Name") == name]


# ── the first beat ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,ms", [("", 0), ("0", 0), ("0:00", 0), ("0.0", 0), ("1.25", 1250),
                                     ("0:01.25", 1250), ("0:01.250", 1250), ("1250ms", 1250), ("2s", 2000)])
def test_first_beat_is_read_as_a_time(text, ms):
    assert sb.parse_first_beat(text) == ms


@pytest.mark.parametrize("text", ["soon", "bar 2", "11:00"])
def test_a_bad_first_beat_says_why(text):
    with pytest.raises(ValueError, match="first beat"):
        sb.parse_first_beat(text)


def test_the_first_part_covers_the_lead_in_and_bars_count_from_the_first_beat():
    eng = engine_of(scene("5") + scene("6"))
    p = sb.plan(eng, spec(first_beat="0:01.5", parts=[
        {"name": "Intro", "function_id": "5", "length": "2 bars"},          # 4 s at 120 BPM
        {"name": "Verse", "function_id": "6", "length": "until bar 5"},     # bars 3 and 4: 4 s
        {"name": "Out", "function_id": "5", "length": "until 0:12"}]))      # a time counts from 0:00
    rows = p["parts"]
    assert p["lead_ms"] == 1500 and rows[0]["lead_ms"] == 1500
    assert (rows[0]["start_ms"], rows[0]["end_ms"]) == (0, 5500)
    assert (rows[1]["start_ms"], rows[1]["end_ms"]) == (5500, 9500)
    assert (rows[2]["start_ms"], rows[2]["end_ms"]) == (9500, 12000)


def test_without_a_first_beat_nothing_changes():
    eng = engine_of(scene("5") + scene("6"))
    p = sb.plan(eng, spec())
    assert p["lead_ms"] == 0 and "lead_ms" not in p["parts"][0]
    assert [r["start_ms"] for r in p["parts"]] == [0, 4000]


def test_to_the_end_already_counts_from_0_00(tmp_path):
    w = _silence(tmp_path / "song.wav", 10)
    eng = engine_of(scene("5"))
    p = sb.plan(eng, spec(first_beat="1", music={"path": w},
                          parts=[{"name": "All", "function_id": "5", "length": "to the end"}]))
    assert p["parts"][0]["end_ms"] == 10000 and p["free_ms"] == 0


def test_a_first_beat_after_the_music_is_refused(tmp_path):
    w = _silence(tmp_path / "song.wav", 5)
    eng = engine_of(scene("5") + scene("6"))
    with pytest.raises(ValueError, match="first beat"):
        sb.plan(eng, spec(first_beat="0:06", music={"path": w}))
    assert any("first beat" in x for x in sb.plan(eng, spec(first_beat="0:06", music={"path": w}),
                                                  lenient=True)["warnings"])


def test_the_built_show_starts_at_0_and_the_first_item_holds_the_lead_in():
    eng = engine_of(scene("5") + scene("6"))
    out = sb.build(eng, spec(first_beat="0.5", parts=[
        {"name": "Intro", "function_id": "5", "length": "1 bar", "repeat": 2},
        {"name": "Verse", "function_id": "6", "length": "1 bar"}]), 100)
    got = [(n, s, d) for n, _f, s, d in items(_show(eng, out))]
    assert got == [("Intro", 0, 2500), ("Intro", 2500, 2000), ("Verse", 4500, 2000)]
    assert sb.spec_of(_show(eng, out))["first_beat"] == "0.5"


# ── music and click together ─────────────────────────────────────────────────

def test_music_and_click_each_get_a_track_and_the_click_its_output(tmp_path):
    music = _silence(tmp_path / "song.wav", 12)
    click = _silence(tmp_path / "Galvanize click 120 BPM.wav", 12)
    eng = engine_of(scene("5") + scene("6"))
    out = sb.build(eng, spec(music={"path": music}, click={"path": click, "device": "Scarlett 2i2 USB"}), 100)
    show = _show(eng, out)
    assert _track(show, "Music") and _track(show, "Click")
    a = next(f for f in eng if f.get("ID") == out["click_id"])
    src = a.find(f"{{{NS}}}Source")
    assert src.text == click and src.get("Device") == "Scarlett 2i2 USB"
    assert a.get(sb.PART_ATTR) == "click"
    m = next(f for f in eng if f.get("ID") == out["audio_id"])
    assert m.find(f"{{{NS}}}Source").get("Device") is None                   # the music stays on the main output
    kept = sb.spec_of(show)
    assert kept["click"] == {"path": click, "name": "", "device": "Scarlett 2i2 USB"}


def test_the_device_is_written_as_qlc_writes_it(tmp_path):
    click = _silence(tmp_path / "c.wav", 3)
    eng = engine_of(scene("5") + scene("6"))
    out = sb.build(eng, spec(click={"path": click, "device": "In-ears"}), 100)
    xml = ET.tostring(next(f for f in eng if f.get("ID") == out["click_id"]), encoding="unicode")
    assert 'Device="In-ears"' in xml and xml.index("Device=") < xml.index(click)


def test_a_new_output_moves_the_click_it_made_and_makes_no_second_one(tmp_path):
    click = _silence(tmp_path / "c.wav", 12)
    eng = engine_of(scene("5") + scene("6"))
    first = sb.build(eng, spec(click={"path": click, "device": "A"}), 100)
    again = sb.build(eng, spec(click={"path": click, "device": "B"}, show_id=first["show_id"]), first["next_id"])
    audios = [f for f in eng if f.get("Type") == "Audio"]
    assert len(audios) == 1 and again["click_id"] == ""
    assert audios[0].find(f"{{{NS}}}Source").get("Device") == "B"
    sb.build(eng, spec(click={"path": click}, show_id=first["show_id"]), again["next_id"])
    assert audios[0].find(f"{{{NS}}}Source").get("Device") is None           # empty: back to the main output


def test_someone_elses_sound_of_the_same_file_is_not_moved(tmp_path):
    click = _silence(tmp_path / "c.wav", 12)
    eng = engine_of(scene("5") + scene("6") + audio("9", click, "Mine"))
    out = sb.build(eng, spec(click={"path": click, "device": "In-ears"}), 100)
    mine = next(f for f in eng if f.get("ID") == "9")
    assert mine.find(f"{{{NS}}}Source").get("Device") is None and out["click_id"] not in ("", "9")


def test_a_short_click_and_a_missing_click_are_said(tmp_path):
    click = _silence(tmp_path / "c.wav", 5)
    eng = engine_of(scene("5") + scene("6"))
    w = sb.plan(eng, spec(click={"path": click}))["warnings"]
    assert any("click track stops" in x and "make it again" in x for x in w)
    w = sb.plan(eng, spec(click={"path": str(tmp_path / "gone.wav")}))["warnings"]
    assert any("click file is not found" in x for x in w)


def test_a_table_without_click_or_first_beat_is_stored_as_before():
    eng = engine_of(scene("5") + scene("6"))
    out = sb.build(eng, spec(), 100)
    kept = sb.spec_of(_show(eng, out))
    assert "click" not in kept and "first_beat" not in kept and "lead_ms" not in kept


def test_a_bad_device_name_is_refused():
    eng = engine_of(scene("5") + scene("6"))
    with pytest.raises(ValueError, match="sound device"):
        sb.plan(eng, spec(click={"path": "c.wav", "device": "x\ny"}))


# ── the click starts on the first beat ───────────────────────────────────────

def test_the_click_starts_on_the_first_beat_and_counts_the_lead_in_back():
    rate = click_track.RATE
    marks = click_track.clicks(120, 4, rate * 4, first_beat_ms=1250)
    times = [round(f * 1000 / rate) for f, _a in marks]
    assert times[:4] == [250, 750, 1250, 1750]
    accents = [a for _f, a in marks]
    assert accents[:4] == [False, False, True, False]                   # beats 3 and 4 of a pick-up bar, then bar 1
    assert click_track.clicks(120, 4, rate * 4) == click_track.clicks(120, 4, rate * 4, first_beat_ms=0)


def test_a_click_file_with_a_lead_in_keeps_its_length(tmp_path):
    out = click_track.write(str(tmp_path), "Song", 120, 4, 6000, "wood", first_beat_ms=900)
    with wave.open(out["path"]) as w:
        assert w.getnframes() == round(6000 * click_track.RATE / 1000)
        data = w.readframes(w.getnframes())
    first = next(i for i in range(0, len(data), 2) if data[i:i + 2] != b"\x00\x00") // 2
    assert abs(first - round(400 * click_track.RATE / 1000)) <= 1         # 900 - 500: one beat back


def test_without_a_first_beat_the_bytes_are_the_same_as_before():
    a, b = io.BytesIO(), io.BytesIO()
    click_track.write_frames(a, 120, 4, 8000, "beep")
    click_track.write_frames(b, 120, 4, 8000, "beep", None, 0)
    assert hashlib.sha256(a.getvalue()).digest() == hashlib.sha256(b.getvalue()).digest()


def test_the_song_builder_click_starts_on_the_tables_first_beat(tmp_path):
    p = tmp_path / "s.qxw"
    p.write_bytes(qxw_io.qxw_bytes(ws(scene("5") + scene("6"))))
    workspace.load_qxw(str(p))
    out = workspace.song_click(spec(first_beat="0:00.5"))
    with wave.open(out["path"]) as w:
        data = w.readframes(w.getnframes())
    first = next(i for i in range(0, len(data), 2) if data[i:i + 2] != b"\x00\x00") // 2
    assert first <= 1                                                    # 0.5 s back at 120 BPM: a click at 0:00 (a sine starts at 0)
    marks = click_track.clicks(120, 4, round(out["length_ms"] * click_track.RATE / 1000), first_beat_ms=500)
    assert marks[1] == (round(0.5 * click_track.RATE), True)


# ── the Doctor ───────────────────────────────────────────────────────────────

def test_doctor_notes_a_sound_on_an_output_of_its_own():
    a = audio("9", "c.wav").replace("<Source>", '<Source Device="In-ears">')
    rep = checks.check(ws(scene("5") + a))
    got = rep.by_code("I010")
    assert len(got) == 1 and got[0].severity == "info" and "In-ears" in got[0].message
    assert not checks.check(ws(scene("5") + audio("9", "c.wav"))).by_code("I010")


# ── the routes ───────────────────────────────────────────────────────────────

def test_devices_route_lists_the_outputs_already_used(tmp_path):
    import app as app_mod
    client = app_mod.create_app().test_client()
    a = audio("9", "c.wav").replace("<Source>", '<Source Device="In-ears">')
    b = audio("10", "d.wav").replace("<Source>", '<Source Device="booth">')
    p = tmp_path / "s.qxw"
    p.write_bytes(qxw_io.qxw_bytes(ws(scene("5") + a + b + audio("11", "e.wav"))))
    workspace.load_qxw(str(p))
    assert client.get("/api/songbuilder/devices").get_json() == ["booth", "In-ears"]


def test_build_route_keeps_music_click_and_first_beat(tmp_path):
    import app as app_mod
    client = app_mod.create_app().test_client()
    p = tmp_path / "s.qxw"
    p.write_bytes(qxw_io.qxw_bytes(ws(scene("5") + scene("6"))))
    music = _silence(tmp_path / "song.wav", 14)
    workspace.load_qxw(str(p))
    click = client.post("/api/songbuilder/click", json=spec(first_beat="0:01", music={"path": "song.wav"})).get_json()
    r = client.post("/api/songbuilder/build", json=spec(first_beat="0:01", music={"path": "song.wav"},
                                                         click={"path": click["path"], "device": "In-ears"}))
    assert r.status_code == 200, r.get_json()
    got = client.get("/api/songbuilder/open?id=" + r.get_json()["show_id"]).get_json()
    assert got["first_beat"] == "0:01" and got["click"]["device"] == "In-ears"
    assert got["music"]["path"] == "song.wav" and os.path.isfile(music)
