"""The Song Builder demo in tests/corpus (made by tools/make_songbuilder_sample.py)."""
import os

import pytest

from core import media, workspace

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
DEMO = os.path.join(CORPUS, "SongBuilder_demo.qxw")


@pytest.fixture
def demo():
    workspace.load_qxw(DEMO)
    return workspace


def test_the_demo_is_a_5_3_show_with_its_music_next_to_it():
    assert "<Version>5.3.0</Version>" in open(DEMO, encoding="utf-8").read()
    assert os.path.isfile(os.path.join(CORPUS, "SongBuilder_demo.wav"))
    assert media.audio_length_ms(os.path.join(CORPUS, "SongBuilder_demo.wav")) == 32000


def test_two_songs_are_listed_and_open_again(demo):
    songs = {s["name"]: s["id"] for s in demo.song_list()}
    assert set(songs) == {"Demo Song", "Demo Instrumental"}
    t = demo.song_open(songs["Demo Song"])
    assert t["unit"] == "bars" and t["parts"][-1]["length"] == "to the end"
    assert t["music"]["path"] == "SongBuilder_demo.wav"


def test_the_song_ends_where_its_music_ends_and_the_other_has_no_music(demo):
    shows = {f["name"]: f for f in demo.get_functions() if f["type"] == "Show"}
    assert shows["Demo Song"]["show_ms"] == 32000          # 16 bars at 120 BPM = the 32 s of music
    assert shows["Demo Instrumental"]["show_ms"] == 19200  # 8 bars at 100 BPM


def test_the_doctor_finds_no_error_and_no_missing_file(demo):
    from core.doctor import check
    res = check(workspace._state["qxw_root"], base_dir=CORPUS)
    assert not [f for f in res.findings if f.severity == "error"]
    assert not [f for f in res.findings if f.code in ("D024", "D025")]


def test_relative_music_is_found_next_to_the_show_wherever_swiss_knife_runs(demo, tmp_path, monkeypatch):
    """3.13.0: 'SongBuilder_demo.wav' was looked up from where Swiss Knife was started,
    not from the show's folder, so 'to the end' had no length (seen on giopas's Mac)."""
    monkeypatch.chdir(tmp_path)                            # anywhere but the show's folder
    songs = {s["name"]: s["id"] for s in demo.song_list()}
    spec = demo.song_open(songs["Demo Song"])
    res = demo.song_plan(spec, lenient=True)
    assert res["music_ms"] == 32000
    assert not [w for w in res["warnings"] if "not found" in w]
    assert not [p for p in res["parts"] if p["issue"]]


def test_the_music_route_finds_a_relative_file_and_writes_a_picked_one_relative(demo, tmp_path, monkeypatch):
    import app
    monkeypatch.chdir(tmp_path)
    c = app.create_app().test_client()
    d = c.post("/api/songbuilder/music", json={"path": "SongBuilder_demo.wav"}).get_json()
    assert d["found"] and d["length_ms"] == 32000 and d["path"] == "SongBuilder_demo.wav"
    d = c.post("/api/songbuilder/music", json={"path": os.path.join(CORPUS, "SongBuilder_demo.wav")}).get_json()
    assert d["found"] and d["path"] == "SongBuilder_demo.wav"          # inside the show's folder
    outside = tmp_path / "elsewhere.wav"
    outside.write_bytes(open(os.path.join(CORPUS, "SongBuilder_demo.wav"), "rb").read())
    d = c.post("/api/songbuilder/music", json={"path": str(outside)}).get_json()
    assert d["found"] and d["path"] == str(outside)                  # outside: kept absolute
