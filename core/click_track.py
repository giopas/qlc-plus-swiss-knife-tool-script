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
from typing import Dict

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


def write_frames(fh, bpm: float, beats_per_bar: int, length_ms: int, sound: str = DEFAULT_SOUND) -> int:
    """Write the click track as a WAV to the open binary file *fh*; returns the frames written."""
    total = round(length_ms * RATE / 1000)
    high, low = sounds(check_sound(sound))
    with wave.open(fh, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        beat = 0
        while True:
            start = beat_frames(beat, bpm)
            if start >= total:
                break
            end = min(beat_frames(beat + 1, bpm), total)
            ring = (high if beat % beats_per_bar == 0 else low)[: end - start]
            seg = array.array("h", ring)
            seg.extend(array.array("h", bytes(2 * (end - start - len(ring)))))
            if _bigendian():
                seg.byteswap()
            w.writeframes(seg.tobytes())
            beat += 1
    return total


def _bigendian() -> bool:
    import sys
    return sys.byteorder == "big"


def plain_name(name: str, bpm: float) -> str:
    """A safe file name (no folder, no dot at the start) for a click track of *name*."""
    base = _BAD.sub("", os.path.basename(str(name or "").replace("\\", "/"))).strip(" .")[:80]
    if base.lower().endswith(" click"):
        base = base[:-6]
    return f"{base or 'Song'} click {round(bpm)} BPM"


def write(folder: str, name: str, bpm, beats_per_bar, length_ms, sound=None) -> Dict[str, object]:
    """Make the file in *folder* under a free name.  Returns {path, name, length_ms, bpm, beats_per_bar, sound}."""
    bpm, bpb, length_ms = check(bpm, beats_per_bar, length_ms)
    sound = check_sound(sound)
    if not folder or not os.path.isdir(folder):
        raise ValueError("Open a show that is saved on this computer first: the click track is saved next to it.")
    stem = plain_name(name, bpm)
    n = 1
    while True:
        fname = f"{stem}.wav" if n == 1 else f"{stem} {n}.wav"
        path = os.path.join(folder, fname)
        try:
            with open(path, "xb") as fh:            # "x": never over an existing file
                frames = write_frames(fh, bpm, bpb, length_ms, sound)
            break
        except FileExistsError:
            n += 1
            if n > 999:
                raise ValueError("Too many click tracks with that name in the folder.")
    return {"path": path, "name": fname, "length_ms": round(frames * 1000 / RATE), "bpm": bpm, "beats_per_bar": bpb, "sound": sound}
