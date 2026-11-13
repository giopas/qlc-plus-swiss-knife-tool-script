"""
Find a song's tempo and its first beat (3.20.0, Song Builder).

The Song Builder's click and its bars need two numbers from the music: the BPM and where
bar 1 starts.  This module listens to the sound file and proposes both.  It is a proposal:
the page fills the two boxes and the user checks them by ear with the click track.

How (the usual way of beat trackers, kept small):
  1. the sound is read (``soundfile``: .wav, .mp3, .ogg, .flac, .aiff), mixed to mono and
     taken down to about 11 kHz;
  2. an *onset curve*: how much louder each frequency band gets from one 12 ms frame to
     the next (spectral flux); drums and new notes make peaks;
  3. the tempo: the curve's autocorrelation, weighted towards 120 BPM (a song is more often
     near 120 than near 60 or 240), gives a rough BPM; a comb of beats is then slid over the
     curve at BPMs around it and at every phase, and the comb that lands on the most onsets
     gives the exact BPM and where the beats fall; a BPM very close to a whole number is
     taken as that whole number when it fits as well (most songs recorded to a click are);
  4. bar 1: of the 2 to 16 places a bar can start, the one whose beats carry the most low
     sound (the kick drum) is taken, and the first of those beats once the music has
     started is the first beat.

Limits, said plainly to the user: a song that speeds up or slows down has no single BPM;
half or double the tempo can come out (both are offered); the first beat may be one beat or
one bar off on songs without drums.  .m4a / AAC cannot be read (no decoder in soundfile).

Needs ``numpy`` and ``soundfile`` (pip install numpy soundfile).  They are optional:
without them :func:`available` says what to install and the rest of Swiss Knife works as
before.  Nothing is written; the file is only read, and at most :data:`MAX_SECONDS` of it.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

MAX_SECONDS = 360            # the first six minutes are plenty for a tempo
MAX_BYTES = 500 * 1024 * 1024
TARGET_SR = 11025
N_FFT = 1024
HOP = 128
BPM_LO, BPM_HI = 40.0, 240.0
LAG_MS = 27                  # measured on test songs: the onset curve peaks this much before the hit
READABLE = (".wav", ".mp3", ".ogg", ".oga", ".flac", ".aif", ".aiff")
INSTALL = "pip install numpy soundfile"


def available() -> Optional[str]:
    """None when tempo finding works here, else what to do, in plain words."""
    missing = []
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    try:
        import soundfile  # noqa: F401
    except (ImportError, OSError):            # OSError: the library inside soundfile is missing
        missing.append("soundfile")
    if not missing:
        return None
    return ("Finding the tempo needs " + " and ".join(missing) + ", which are not installed here: run "
            f"'{INSTALL}' and start Swiss Knife again, or type the BPM yourself.")


def _load(path: str):
    """(mono samples at about TARGET_SR as float32, sample rate)."""
    import numpy as np
    import soundfile as sf
    with sf.SoundFile(path) as f:
        sr = f.samplerate
        n = min(f.frames if f.frames > 0 else sr * MAX_SECONDS, sr * MAX_SECONDS)
        x = f.read(frames=n, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    k = max(1, int(sr // TARGET_SR))
    if k > 1:                                  # average k samples: a plain low-pass and decimation
        x = x[: len(x) - len(x) % k].reshape(-1, k).mean(axis=1)
    return x.astype("float32"), sr / k


def _onsets(x, sr: float):
    """(onset curve of the whole sound, onset curve of the low band, the notes' spectrum per frame,
    rms per frame, frames per second)."""
    import numpy as np
    x = np.pad(x, (N_FFT // 2, N_FFT // 2))            # frame t is centred on sample t * HOP
    n = 1 + (len(x) - N_FFT) // HOP
    if n < 8:
        raise ValueError("The sound is too short to find a tempo.")
    win = np.hanning(N_FFT).astype("float32")
    s = np.empty((n, N_FFT // 2 + 1), dtype="float32")
    rms = np.empty(n, dtype="float32")
    for a in range(0, n, 4096):                         # in pieces, so a long song stays light on memory
        b = min(n, a + 4096)
        idx = np.arange(N_FFT)[None, :] + HOP * np.arange(a, b)[:, None]
        frames = x[idx] * win
        s[a:b] = np.log1p(100.0 * np.abs(np.fft.rfft(frames, axis=1)))
        rms[a:b] = np.sqrt((frames ** 2).mean(axis=1))
    d = np.maximum(0.0, np.diff(s, axis=0, prepend=s[:1]))
    low_bins = max(2, int(150 * N_FFT / sr))
    fps = sr / HOP

    def clean(env):
        w = max(1, int(fps * 0.4))
        env = env - np.convolve(env, np.ones(w) / w, mode="same")     # take away the slow swell
        env = np.maximum(env, 0.0)
        m = env.max()
        return env / m if m > 0 else env

    mid_hi = max(low_bins + 2, int(2000 * N_FFT / sr))
    # the kick (low band) helps find bar 1; the notes (the band up to 2 kHz, read beat by
    # beat) say where the harmony changes, which is mostly on bar 1
    return clean(d.sum(axis=1)), clean(d[:, :low_bins].sum(axis=1)), s[:, low_bins:mid_hi], rms, fps


def _rough_bpm(env, fps: float) -> float:
    """The autocorrelation's best lag, weighted towards 120 BPM."""
    import numpy as np
    e = env - env.mean()
    n = 1 << int(np.ceil(np.log2(2 * len(e))))
    ac = np.fft.irfft(np.abs(np.fft.rfft(e, n)) ** 2)[: len(e)]
    lags = np.arange(int(fps * 60 / BPM_HI), int(fps * 60 / BPM_LO) + 1)
    lags = lags[(lags > 0) & (lags < len(ac))]
    bpms = 60 * fps / lags
    prior = np.exp(-0.5 * (np.log2(bpms / 120.0) / 0.9) ** 2)
    score = ac[lags] * prior
    return float(bpms[int(np.argmax(score))])


def _comb(env, fps: float, bpm: float, step: float = 0.5):
    """(best mean onset strength on a comb of beats at *bpm*, its phase in frames, all scores)."""
    import numpy as np
    period = fps * 60.0 / bpm
    phases = np.arange(0.0, period, step)
    k = np.arange(int((len(env) - 1) / period) + 1)
    pos = phases[:, None] + period * k[None, :]
    ok = pos <= len(env) - 1
    vals = np.interp(np.where(ok, pos, 0.0), np.arange(len(env)), env) * ok
    scores = vals.sum(axis=1) / np.maximum(ok.sum(axis=1), 1)
    i = int(np.argmax(scores))
    return float(scores[i]), float(phases[i]), scores


def _harmony_change(notes, beats):
    """For each beat, how different its notes are from the beat before (0 the same, up to 1)."""
    import numpy as np
    edges = np.clip(np.round(beats).astype(int), 0, len(notes))
    out = np.zeros(len(beats))
    prev = None
    for i in range(len(beats)):
        a, b = edges[i], edges[i + 1] if i + 1 < len(beats) else min(len(notes), edges[i] + (edges[i] - edges[i - 1] if i else 1))
        if b <= a:
            prev = None
            continue
        v = notes[a:b].mean(axis=0)
        v = v - v.mean()
        n = float(np.linalg.norm(v))
        if prev is not None and n > 0:
            out[i] = 1.0 - float(np.dot(v, prev)) / n
        prev = v / n if n > 0 else None
    m = out.max()
    return out / m if m > 0 else out


def detect(path: str, beats_per_bar: int = 4) -> Dict[str, object]:
    """Listen to *path* and propose its tempo and first beat.

    Returns ``{bpm, first_beat_ms, sure, half, double, seconds_read}``; ``sure`` is False when
    the beats are weak or uneven (check by ear, or type the BPM).  ValueError in plain words
    when the file cannot be read or holds no beat."""
    why = available()
    if why:
        raise ValueError(why)
    import numpy as np
    if not os.path.isfile(path):
        raise ValueError("The music file is not found on this computer.")
    ext = os.path.splitext(path)[1].lower()
    if ext not in READABLE:
        raise ValueError(f"A {ext or 'file without extension'} cannot be read to find the tempo: use a .wav, .mp3, "
                         ".ogg or .flac copy of the song, or type the BPM yourself.")
    if os.path.getsize(path) > MAX_BYTES:
        raise ValueError("The music file is too large to find the tempo (over 500 MB).")
    if not 1 <= int(beats_per_bar) <= 16:
        raise ValueError("A bar has 1 to 16 beats.")
    try:
        x, sr = _load(path)
    except Exception as e:  # noqa: BLE001  (soundfile raises its own error types)
        raise ValueError(f"The music file could not be read: {str(e)[:160]}")
    if len(x) < sr * 4:
        raise ValueError("The music is shorter than four seconds: too short to find a tempo.")
    env, low, notes, rms, fps = _onsets(x, sr)
    if env.max() <= 0:
        raise ValueError("No beat was found: the sound is silent or has no clear onsets.")
    smooth = np.convolve(env, np.array([0.25, 0.5, 1.0, 0.5, 0.25]) / 2.5, mode="same")   # a little give for a human player
    rough = _rough_bpm(env, fps)

    best = (-1.0, rough, 0.0, None)
    for b in np.arange(rough * 0.96, rough * 1.04, 0.02):
        sc, ph, all_sc = _comb(smooth, fps, float(b))
        if sc > best[0]:
            best = (sc, float(b), ph, all_sc)
    score, bpm, phase, all_scores = best
    whole = round(bpm)
    if abs(bpm - whole) < 0.3:                 # a song recorded to a click is usually at a whole BPM
        sc, ph, all_sc = _comb(smooth, fps, float(whole))
        if sc >= 0.98 * score:
            score, bpm, phase, all_scores = sc, float(whole), ph, all_sc
    sure = bool(score > 2.2 * float(np.median(all_scores)) and score > 0.08)

    # the beats, then which of them start a bar: the one whose beats carry most of the kick
    period = fps * 60.0 / bpm
    lag = LAG_MS * fps / 1000.0                  # an onset peaks a little before the hit (the window looks ahead)
    if phase + lag - period > -0.15 * period:    # a beat right at 0:00 (or a hair before)
        phase -= period
    beats = phase + period * np.arange(int((len(env) - 1 - phase) / period) + 1)
    bpb = int(beats_per_bar)
    lows = np.interp(beats, np.arange(len(low)), np.convolve(low, np.ones(3) / 3, mode="same"))
    loud = np.interp(beats, np.arange(len(env)), smooth)
    loud = loud / loud.max() if loud.max() > 0 else loud
    change = _harmony_change(notes, beats)
    weight = []
    for j in range(bpb):                         # harmony changes, kick drum and accents mark bar 1
        ch, lo, ac = change[j::bpb], lows[j::bpb], loud[j::bpb]
        weight.append(float(ch.mean() + 0.5 * lo.mean() + 0.5 * ac.mean()) if len(ch) else 0.0)
    bar_phase = int(np.argmax(weight))
    sounding = np.nonzero(rms > 0.1 * rms.max())[0]
    start = float(sounding[0]) if len(sounding) else 0.0
    downbeats = beats[bar_phase::bpb]
    later = downbeats[downbeats >= start - 0.25 * period]
    first = float(later[0] if len(later) else downbeats[0])
    first_ms = max(0, int(round((first + lag) * HOP * 1000.0 / sr)))

    def nice(v: float) -> float:
        return float(round(v)) if abs(v - round(v)) < 1e-6 else round(v, 2)

    out = {"bpm": nice(bpm), "first_beat_ms": first_ms, "sure": sure,
           "seconds_read": round(len(x) / sr, 1)}
    out["half"] = nice(bpm / 2) if bpm / 2 >= 20 else None
    out["double"] = nice(bpm * 2) if bpm * 2 <= 400 else None
    return out


def first_beat_text(ms: int) -> str:
    """1234 → '0:01.234', as the first-beat box shows it."""
    s, ms = divmod(int(ms), 1000)
    return f"{s // 60}:{s % 60:02d}.{ms:03d}"


__all__: List[str] = ["available", "detect", "first_beat_text", "INSTALL", "READABLE"]
