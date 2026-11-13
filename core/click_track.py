"""
Click track (3.10.0): a plain sound file with a click on every beat.

The Song Builder (3.9.8) takes one music track.  A band that plays to a click, or a song
that has no recording yet, can have the tool make that track: a mono 16-bit ``.wav`` with a
click on every beat and a different, louder one on the first beat of each bar, at the song's
BPM and for its length, in one of three sounds (beep, wood block, tick).  Only the standard library is used (``wave``, ``array``).

Rules (WORKPLAN principles 1 and 3):
  * the file is written next to the saved show, and **never over another file**: when the
    name is taken, ``name 2.wav``, ``name 3.wav`` … is used (the file is opened with ``x``);
  * the same input gives the same bytes: no clock, no random numbers;
  * the page never sends a path, only a name, which is reduced to a plain file name.
"""

from __future__ import annotations

import array
import math
import os
import re
import wave
from typing import Dict, List, Optional, Sequence, Tuple

from core import setlist_tempo

RATE = 22050                   # Hz: a click is short, so this is plenty and keeps the file small
MAX_MS = 20 * 60 * 1000        # twenty minutes (about 53 MB); a longer song is a mistake here
CLICK_MS = 25                  # how long one click rings
HIGH_HZ, LOW_HZ = 1600, 1000   # first beat of the bar, other beats
HIGH_AMP, LOW_AMP = 0.9, 0.6

# The sounds to choose from.  Every one makes the first beat of the bar clearly different
# (higher or fuller, and louder).  "beep" is the sound of the first 3.10.0 click tracks.
SOUNDS = ("beep", "wood", "tick")
DEFAULT_SOUND = "beep"

_BAD = re.compile(r"[^\w .,()+-]", re.UNICODE)


def _click(freq: int, amp: float) -> array.array:
    """One click: a sine with a fast decay (the same samples every time)."""
    n = RATE * CLICK_MS // 1000
    return array.array("h", (round(32767 * amp * math.sin(2 * math.pi * freq * i / RATE) * math.exp(-6.0 * i / n))
                             for i in range(n)))


def _wood(accent: bool) -> array.array:
    """A wood-block: two partials that die quickly; the first beat is higher and louder."""
    f, amp = (1500, 0.95) if accent else (900, 0.65)
    n = RATE * 30 // 1000
    return array.array("h", (round(32767 * amp * (0.75 * math.sin(2 * math.pi * f * i / RATE)
                                                  + 0.25 * math.sin(2 * math.pi * f * 2.43 * i / RATE))
                                   * math.exp(-9.0 * i / n)) for i in range(n)))


def _tick(accent: bool) -> array.array:
    """A soft tick: a short burst of noise (a fixed sequence, so the same bytes every time).
    The first beat is longer, louder and has a low body under the tick."""
    n = RATE * (40 if accent else 12) // 1000
    amp = 0.9 if accent else 0.5
    seed, out = 12345, []
    for i in range(n):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        noise = (seed / 0x3FFFFFFF) - 1.0
        body = 0.6 * math.sin(2 * math.pi * 220 * i / RATE) if accent else 0.0
        out.append(round(32767 * amp * (0.7 * noise + body) / 1.3 * math.exp(-7.0 * i / n)))
    return array.array("h", out)


def sounds(sound: str):
    """(first beat, other beats) samples for a sound name."""
    if sound == "wood":
        return _wood(True), _wood(False)
    if sound == "tick":
        return _tick(True), _tick(False)
    return _click(HIGH_HZ, HIGH_AMP), _click(LOW_HZ, LOW_AMP)


def check_sound(sound) -> str:
    """The sound name, or ValueError in plain words."""
    sound = (str(sound).strip().lower() if sound not in (None, "") else DEFAULT_SOUND)
    if sound not in SOUNDS:
        raise ValueError("The click sound is beep, wood or tick.")
    return sound


def beat_frames(n: int, bpm: float) -> int:
    """The sample where beat *n* (from 0) starts."""
    return round(n * 60 * RATE / bpm)


def check(bpm, beats_per_bar, length_ms):
    """(bpm, beats_per_bar, length_ms) as numbers, or ValueError in plain words."""
    try:
        bpm = float(bpm)
    except (TypeError, ValueError):
        raise ValueError("A click track needs the song's BPM.")
    if not setlist_tempo.BPM_MIN <= bpm <= setlist_tempo.BPM_MAX:
        raise ValueError("The BPM must be from 20 to 400.")
    try:
        bpb = 4 if beats_per_bar in (None, "") else int(beats_per_bar)
    except (TypeError, ValueError):
        raise ValueError("The beats per bar must be a whole number.")
    if not 1 <= bpb <= 16:
        raise ValueError("A bar has 1 to 16 beats.")
    try:
        length_ms = int(length_ms)
    except (TypeError, ValueError):
        raise ValueError("A click track needs a length: give the parts a length first.")
    if length_ms <= 0:
        raise ValueError("A click track needs a length: give the parts a length first.")
    if length_ms > MAX_MS:
        raise ValueError("A click track is at most 20 minutes long.")
    return bpm, bpb, length_ms


def clicks(bpm: float, beats_per_bar: int, total: int,
           tempo: Optional[Sequence[Tuple[int, float]]] = None, first_beat_ms: int = 0) -> List[Tuple[int, bool]]:
    """``(frame, first beat of the bar)`` of every click.  *tempo* is the Song Builder's tempo
    map (3.13.0): ``(start_ms, bpm)`` where a part changes the tempo.  Each change starts on a
    first beat of the bar, as a tempo change does in a song; without one, one BPM throughout.
    *first_beat_ms* (3.20.0) is where bar 1 starts in the music: the clicks before it count
    back from there at the first tempo, so the lead-in has a click too (a pick-up bar)."""
    offset = round(max(0, first_beat_ms) * RATE / 1000)
    points = [(offset, float(bpm))]
    for ms, b in sorted(tempo or []):
        if round(ms * RATE / 1000) <= offset:
            points[0] = (offset, float(b))
        elif float(b) != points[-1][1]:
            points.append((round(ms * RATE / 1000), float(b)))
    out: List[Tuple[int, bool]] = []
    k = 1                                        # the lead-in, counted back from the first beat
    while offset and offset - beat_frames(k, points[0][1]) >= 0:
        out.append((offset - beat_frames(k, points[0][1]), k % beats_per_bar == 0))
        k += 1
    out.reverse()
    for i, (start, b) in enumerate(points):
        stop = points[i + 1][0] if i + 1 < len(points) else total
        n = 0
        while True:
            at = start + beat_frames(n, b)
            if at >= min(stop, total):
                break
            out.append((at, n % beats_per_bar == 0))
            n += 1
    return out


def write_frames(fh, bpm: float, beats_per_bar: int, length_ms: int, sound: str = DEFAULT_SOUND,
                 tempo: Optional[Sequence[Tuple[int, float]]] = None, first_beat_ms: int = 0) -> int:
    """Write the click track as a WAV to the open binary file *fh*; returns the frames written."""
    total = round(length_ms * RATE / 1000)
    high, low = sounds(check_sound(sound))
    marks = clicks(bpm, beats_per_bar, total, tempo, first_beat_ms)
    with wave.open(fh, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        if marks and marks[0][0] > 0:            # silence before the first click
            w.writeframes(bytes(2 * marks[0][0]))
        for k, (start, accent) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else total
            ring = (high if accent else low)[: end - start]
            seg = array.array("h", ring)
            seg.extend(array.array("h", bytes(2 * (end - start - len(ring)))))
            if _bigendian():
                seg.byteswap()
            w.writeframes(seg.tobytes())
    return total


def _bigendian() -> bool:
    import sys
    return sys.byteorder == "big"


def plain_name(name: str, bpm: float, tempos: Sequence[float] = ()) -> str:
    """A safe file name (no folder, no dot at the start) for a click track of *name*;
    with tempo changes, every tempo in order: ``Song click 120-90-120 BPM``."""
    base = _BAD.sub("", os.path.basename(str(name or "").replace("\\", "/"))).strip(" .")[:80]
    if base.lower().endswith(" click"):
        base = base[:-6]
    seq = [round(bpm)]
    for b in tempos:
        if round(b) != seq[-1]:
            seq.append(round(b))
    return f"{base or 'Song'} click {'-'.join(str(x) for x in seq[:6])} BPM"


def write(folder: str, name: str, bpm, beats_per_bar, length_ms, sound=None,
          tempo: Optional[Sequence[Tuple[int, float]]] = None, first_beat_ms: int = 0) -> Dict[str, object]:
    """Make the file in *folder* under a free name.  Returns {path, name, length_ms, bpm, beats_per_bar, sound}.
    *tempo*: where the tempo changes, ``(start_ms, bpm)`` (3.13.0); *first_beat_ms*: where
    bar 1 starts (3.20.0)."""
    bpm, bpb, length_ms = check(bpm, beats_per_bar, length_ms)
    tempo = [(int(ms), check(b, bpb, length_ms)[0]) for ms, b in (tempo or [])]
    sound = check_sound(sound)
    if not folder or not os.path.isdir(folder):
        raise ValueError("Open a show that is saved on this computer first: the click track is saved next to it.")
    stem = plain_name(name, bpm, [b for _ms, b in sorted(tempo)])
    n = 1
    while True:
        fname = f"{stem}.wav" if n == 1 else f"{stem} {n}.wav"
        path = os.path.join(folder, fname)
        try:
            with open(path, "xb") as fh:            # "x": never over an existing file
                frames = write_frames(fh, bpm, bpb, length_ms, sound, tempo, int(first_beat_ms or 0))
            break
        except FileExistsError:
            n += 1
            if n > 999:
                raise ValueError("Too many click tracks with that name in the folder.")
    return {"path": path, "name": fname, "length_ms": round(frames * 1000 / RATE), "bpm": bpm, "beats_per_bar": bpb, "sound": sound}
