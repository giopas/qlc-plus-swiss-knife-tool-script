"""3.10.0 Song Builder: the click track."""
import array
import os
import shutil
import wave

import pytest

import app as app_mod
from core import click_track as ct, media, workspace

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")


def read(path):
    with wave.open(path, "rb") as w:
        data = array.array("h", w.readframes(w.getnframes()))
        return w.getframerate(), w.getnchannels(), w.getsampwidth(), data


def test_a_click_on_every_beat_and_a_higher_louder_one_on_the_bar(tmp_path):
    out = ct.write(str(tmp_path), "Song", 120, 4, 4000)                # 8 beats, 2 bars
    rate, ch, width, data = read(out["path"])
    assert (rate, ch, width) == (ct.RATE, 1, 2) and len(data) == round(4 * ct.RATE)
    beat = ct.RATE // 2                                                # 120 BPM → 0.5 s
    for n in range(8):
        seg = data[n * beat: n * beat + ct.RATE * ct.CLICK_MS // 1000]
        assert max(abs(x) for x in seg) > 5000, n                      # a click is there
        assert max(abs(x) for x in data[n * beat + beat // 2: (n + 1) * beat]) == 0, n   # silence between
    loud = [max(abs(x) for x in data[n * beat: n * beat + 400]) for n in range(8)]
    assert loud[0] > loud[1] and loud[4] > loud[5] and loud[1] == loud[2] == loud[3]
    assert media.audio_length_ms(out["path"]) == 4000 and out["length_ms"] == 4000


def test_the_same_input_gives_the_same_bytes(tmp_path):
    a = ct.write(str(tmp_path), "A", 97.5, 3, 5000)["path"]
    b = ct.write(str(tmp_path), "B", 97.5, 3, 5000)["path"]
    assert open(a, "rb").read() == open(b, "rb").read()


def test_a_file_is_never_replaced(tmp_path):
    first = ct.write(str(tmp_path), "Song", 100, 4, 2000)
    (tmp_path / first["name"]).write_bytes(b"mine")
    second = ct.write(str(tmp_path), "Song", 100, 4, 2000)
    assert second["name"] != first["name"] and second["name"].endswith(" 2.wav")
    assert (tmp_path / first["name"]).read_bytes() == b"mine"


@pytest.mark.parametrize("name", ["../../evil", "..\\..\\evil", "/etc/passwd", ".hidden", "a/b/c", "x\x00y", ""])
def test_a_name_cannot_leave_the_folder(tmp_path, name):
    out = ct.write(str(tmp_path), name, 100, 4, 1000)
    assert os.path.dirname(out["path"]) == str(tmp_path) and out["name"].endswith(".wav")
    assert not out["name"].startswith(".") and "/" not in out["name"] and "\\" not in out["name"]
    assert os.listdir(tmp_path) == [out["name"]]


@pytest.mark.parametrize("args,word", [((0, 4, 1000), "BPM"), ((10, 4, 1000), "BPM"), ((500, 4, 1000), "BPM"),
                                       ((120, 0, 1000), "bar"), ((120, 17, 1000), "bar"),
                                       ((120, 4, 0), "length"), ((120, 4, "x"), "length"),
                                       ((120, 4, ct.MAX_MS + 1), "20 minutes")])
def test_bad_numbers_are_refused_in_plain_words(tmp_path, args, word):
    with pytest.raises(ValueError, match=word):
        ct.write(str(tmp_path), "S", *args)
    assert os.listdir(tmp_path) == []


def test_no_folder_no_file():
    with pytest.raises(ValueError, match="saved on this computer"):
        ct.write("/nonexistent/folder", "S", 120, 4, 1000)


def test_route_makes_the_file_next_to_the_show(tmp_path):
    show = tmp_path / "Pub_6fix.qxw"
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), show)
    c = app_mod.create_app().test_client()
    assert c.post("/api/load", json={"path": str(show)}).status_code == 200
    scenes = [f for f in c.get("/api/functions").get_json() if f["type"] == "Scene"][:2]
    table = {"name": "Galvanize", "bpm": 120, "beats_per_bar": 4, "unit": "bars",
             "parts": [{"name": "A", "function_id": scenes[0]["id"], "length": "4"},
                       {"name": "B", "function_id": scenes[1]["id"], "length": "4"}]}
    r = c.post("/api/songbuilder/click", json={**table, "path": "/tmp/evil.wav"})      # a path from the page is ignored
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["path"] == str(tmp_path / "Galvanize click 120 BPM.wav") and d["length_ms"] == 16000
    assert read(d["path"])[0] == ct.RATE
    # it can be chosen as the music: the length is read and the parts end with it
    plan = c.post("/api/songbuilder/preview", json={**table, "music": {"path": d["path"]}}).get_json()
    assert plan["music_ms"] == 16000 and plan["length_ms"] == 16000 and plan["warnings"] == []
    # without a BPM or any length, a plain refusal and no file
    n = len(os.listdir(tmp_path))
    assert c.post("/api/songbuilder/click", json={**table, "bpm": ""}).status_code == 400
    assert c.post("/api/songbuilder/click", json={"name": "x", "bpm": 120, "parts": []}).status_code == 400
    assert len(os.listdir(tmp_path)) == n


def test_the_show_is_not_changed_by_a_click_track(tmp_path):
    show = tmp_path / "Pub_6fix.qxw"
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), show)
    c = app_mod.create_app().test_client()
    c.post("/api/load", json={"path": str(show)})
    before = workspace.get_state()["func_count"]
    fid = [f for f in c.get("/api/functions").get_json() if f["type"] == "Scene"][0]["id"]
    assert c.post("/api/songbuilder/click", json={"name": "S", "bpm": 90, "unit": "seconds",
                                                  "parts": [{"name": "A", "function_id": fid, "length": "5"}]}).status_code == 200
    assert workspace.get_state()["func_count"] == before
    assert c.get("/api/show/history").get_json()["steps"] == []


# ── 3.10.0: a choice of sound ────────────────────────────────────────────────

import io
import wave as _wave

from core import click_track as _ct


def _pcm(sound, bpm=120, bpb=4, ms=4000):
    b = io.BytesIO()
    _ct.write_frames(b, bpm, bpb, ms, sound)
    b.seek(0)
    with _wave.open(b) as w:
        import array as _a
        a = _a.array("h")
        a.frombytes(w.readframes(w.getnframes()))
        return a


def test_every_sound_is_a_valid_wave_of_the_right_length():
    for s in _ct.SOUNDS:
        a = _pcm(s)
        assert len(a) == round(4000 * _ct.RATE / 1000) and max(map(abs, a)) > 5000


def test_first_beat_of_the_bar_is_louder_in_every_sound():
    for s in _ct.SOUNDS:
        a = _pcm(s)
        beat = _ct.beat_frames(1, 120)
        first = max(abs(x) for x in a[:beat])
        second = max(abs(x) for x in a[beat:2 * beat])
        fifth = max(abs(x) for x in a[_ct.beat_frames(4, 120):_ct.beat_frames(5, 120)])
        assert first > second * 1.2, s
        assert abs(first - fifth) <= 1, s            # the next bar starts the same way


def test_the_sounds_differ_and_beep_is_unchanged():
    outs = {s: _pcm(s).tobytes() for s in _ct.SOUNDS}
    assert len(set(outs.values())) == 3
    a, b = io.BytesIO(), io.BytesIO()
    _ct.write_frames(a, 120, 4, 4000)                # no sound given = beep
    _ct.write_frames(b, 120, 4, 4000, "beep")
    assert a.getvalue() == b.getvalue()


def test_same_input_same_bytes_and_bad_sound_refused(tmp_path):
    for s in _ct.SOUNDS:
        assert _pcm(s).tobytes() == _pcm(s).tobytes()
    with pytest.raises(ValueError):
        _ct.check_sound("gong")
    r = _ct.write(str(tmp_path), "Song", 120, 4, 2000, "wood")
    assert r["sound"] == "wood" and (tmp_path / r["name"]).exists()
    assert _ct.write(str(tmp_path), "Song", 120, 4, 2000, "wood")["name"] != r["name"]   # never over a file
