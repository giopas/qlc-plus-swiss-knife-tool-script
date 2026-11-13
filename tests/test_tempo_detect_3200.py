"""Finding a song's tempo and first beat by listening (3.20.0, core/tempo_detect.py).
Skipped where numpy or soundfile are not installed; the rest of the Song Builder is tested
in test_song_click_3200.py without them."""
import pytest

np = pytest.importorskip("numpy", reason="finding the tempo needs numpy")
sf = pytest.importorskip("soundfile", reason="finding the tempo needs soundfile")

from core import click_track, media, qxw_io, song_builder as sb, tempo_detect, workspace  # noqa: E402
from tests.test_doctor import scene, ws  # noqa: E402
from tests.test_shows_398 import audio  # noqa: E402
from tests.test_song_click_3200 import _silence  # noqa: E402


# ── finding the tempo ────────────────────────────────────────────────────────



def _band(path, bpm, first, seconds=40, sr=22050, bpb=4, seed=3):
    """A small band: kick on 1 and 3, snare on 2 and 4, hats on eighths, a chord each bar,
    two pick-up notes before bar 1."""
    rng = np.random.default_rng(seed)
    x = np.zeros(int(seconds * sr), np.float32)
    beat = 60.0 / bpm
    tt = np.arange(int(0.25 * sr)) / sr

    def add(t, sig):
        i = int(round(t * sr))
        if 0 <= i < len(x):
            m = min(len(sig), len(x) - i)
            x[i:i + m] += sig[:m]
    kick = np.sin(2 * np.pi * (55 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 12)
    snare = rng.standard_normal(len(tt)) * np.exp(-tt * 25) * 0.5
    hat = rng.standard_normal(int(0.04 * sr)) * np.exp(-np.arange(int(0.04 * sr)) / sr * 120) * 0.2
    for j in (1, 2):
        add(first - j * beat, 0.3 * np.sin(2 * np.pi * 440 * tt) * np.exp(-tt * 6))
    k = 0
    while first + k * beat < seconds:
        t = first + k * beat
        add(t, kick if k % bpb in (0, 2) else snare)
        add(t, hat)
        add(t + beat / 2, hat)
        if k % bpb == 0:
            f = [220, 247, 262, 196][(k // bpb) % 4]
            tc = np.arange(int(beat * bpb * sr)) / sr
            add(t, 0.15 * (np.sin(2 * np.pi * f * tc) + np.sin(2 * np.pi * f * 1.5 * tc)) * np.exp(-tc * 0.8))
        k += 1
    sf.write(str(path), x / (np.abs(x).max() * 1.1), sr)
    return str(path)


@pytest.mark.parametrize("bpm,first", [(120, 1.0), (128, 0.48), (97.5, 2.3), (85, 1.7), (140, 0.0)])
def test_tempo_and_first_beat_of_a_band(tmp_path, bpm, first):
    r = tempo_detect.detect(_band(tmp_path / "band.wav", bpm, first))
    assert abs(r["bpm"] - bpm) < 0.1 and r["sure"]
    assert abs(r["first_beat_ms"] - first * 1000) <= 30
    assert r["half"] == pytest.approx(r["bpm"] / 2, abs=0.01) and r["double"] == pytest.approx(r["bpm"] * 2, abs=0.01)


def test_a_whole_bpm_is_given_as_a_whole_number(tmp_path):
    assert tempo_detect.detect(_band(tmp_path / "b.wav", 110, 0.25))["bpm"] == 110


def test_three_four(tmp_path):
    r = tempo_detect.detect(_band(tmp_path / "w.wav", 90, 1.2, bpb=3), 3)
    assert r["bpm"] == 90 and abs(r["first_beat_ms"] - 1200) <= 30


def test_its_own_click_track_is_heard_back(tmp_path):
    out = click_track.write(str(tmp_path), "Song", 100, 4, 20000, "tick", first_beat_ms=700)
    r = tempo_detect.detect(out["path"])
    assert r["bpm"] == 100 and abs(r["first_beat_ms"] - 700) <= 30


def test_mp3_flac_and_ogg_are_read(tmp_path):
    src = _band(tmp_path / "b.wav", 123, 1.111, seconds=25)
    data, sr = sf.read(src)
    for ext, fmt in (("flac", "FLAC"), ("ogg", "OGG"), ("mp3", "MP3")):
        if fmt not in sf.available_formats():
            continue
        p = str(tmp_path / f"b.{ext}")
        sf.write(p, data, sr, format=fmt)
        r = tempo_detect.detect(p)
        assert r["bpm"] == 123, ext


def test_what_cannot_be_read_says_so(tmp_path):
    (tmp_path / "a.m4a").write_bytes(b"x")
    with pytest.raises(ValueError, match="m4a"):
        tempo_detect.detect(str(tmp_path / "a.m4a"))
    with pytest.raises(ValueError, match="not found"):
        tempo_detect.detect(str(tmp_path / "gone.wav"))
    (tmp_path / "bad.wav").write_bytes(b"RIFF0000garbage")
    with pytest.raises(ValueError, match="could not be read"):
        tempo_detect.detect(str(tmp_path / "bad.wav"))
    with pytest.raises(ValueError, match="silent|no clear"):
        tempo_detect.detect(_silence(tmp_path / "quiet.wav", 6))
    with pytest.raises(ValueError, match="shorter than four seconds"):
        tempo_detect.detect(_silence(tmp_path / "short.wav", 2))


def test_without_the_add_ons_it_says_what_to_install(monkeypatch):
    import builtins
    real = builtins.__import__

    def no_soundfile(name, *a, **k):
        if name == "soundfile":
            raise ImportError(name)
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_soundfile)
    why = tempo_detect.available()
    assert "soundfile" in why and "pip install numpy soundfile" in why and "numpy and" not in why
    with pytest.raises(ValueError, match="pip install"):
        tempo_detect.detect("x.wav")


def test_tempo_route(tmp_path):
    import app as app_mod
    client = app_mod.create_app().test_client()
    p = tmp_path / "s.qxw"
    p.write_bytes(qxw_io.qxw_bytes(ws(scene("5") + audio("9", "band.wav", "Band"))))
    _band(tmp_path / "band.wav", 128, 0.48, seconds=20)
    workspace.load_qxw(str(p))
    for music in ({"path": "band.wav"}, {"function_id": "9"}):
        r = client.post("/api/songbuilder/tempo", json={"music": music, "beats_per_bar": 4})
        assert r.status_code == 200, r.get_json()
        got = r.get_json()
        assert got["bpm"] == 128 and got["first_beat"].startswith("0:00.4")
        assert sb.parse_first_beat(got["first_beat"]) == got["first_beat_ms"]
    r = client.post("/api/songbuilder/tempo", json={"music": {}})
    assert r.status_code == 400 and "Choose the music" in r.get_json()["error"]
    assert media.audio_length_ms(str(tmp_path / "band.wav")) == 20000
