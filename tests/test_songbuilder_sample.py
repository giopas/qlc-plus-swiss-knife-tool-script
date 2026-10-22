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
