"""
core/setlist_tempo.py — per-song tempo in the setlist (v3.8.0)
===============================================================
A setlist line may carry a tempo: ``Song name | 128BPM`` (spaces, case and the
``BPM`` word optional after a ``|``; without the bar the word ``BPM`` is
needed, so ``99 Luftballons`` and ``Route 66`` stay song titles).

Idea (not code) from the *Show Tempo Sections* of mjcmatrix's fork of QLC+
(https://github.com/mjcmatrix/qlcplus/wiki, by Matt C).

Swiss Knife's chasers run on time, with no BPM speed dial, so a tempo means
step times: one step lasts ``beats`` beats, ``60000 / bpm * beats`` ms.
:func:`fit_chaser` rewrites the steps of a chaser *copy* that way and keeps
each step's proportion of fade to hold; :func:`chaser_fit` only looks.
Both leave alone what cannot follow a tempo (a scene, a chaser that follows
QLC+'s own tempo, steps that wait for the pedal).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

BPM_MIN, BPM_MAX = 20.0, 400.0
BEATS_MIN, BEATS_MAX = 0.125, 64.0
HOLD_INFINITE = 4294967294               # QLC+'s "wait for Go" sentinel
TOLERANCE_MS = 5                          # a step within 5 ms of the wanted time fits

_NUM = r"(\d{2,3}(?:[.,]\d+)?)"
_BAR = re.compile(r"^(.*?)\s*\|\s*" + _NUM + r"\s*(?:bpm)?\s*$", re.I)
_WORD = re.compile(r"^(.*?)[\s\-–—,;:@(\[]+" + _NUM + r"\s*bpm[\s)\]]*$", re.I)
_VALUE = re.compile(r"^\s*" + _NUM + r"\s*(?:bpm)?\s*$", re.I)


def fmt(v: float) -> str:
    """128.0 → '128', 127.5 → '127.5'."""
    return f"{float(v):g}"


def parse_value(text) -> Optional[float]:
    """'128', '128BPM', ' 127,5 bpm ' → 128.0, 128.0, 127.5; anything else None.
    A value outside 20 to 400 is None as well."""
    m = _VALUE.match(str(text if text is not None else ""))
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return v if BPM_MIN <= v <= BPM_MAX else None


def split_line(line: str) -> Tuple[str, Optional[str], bool]:
    """``(name, bpm, rejected)``.  *bpm* is a string such as ``'128'`` or None.
    *rejected* is True when a tempo was written but is not between 20 and 400
    (the name is then returned without it)."""
    for rx in (_BAR, _WORD):
        m = rx.match(line)
        if m and m.group(1).strip():
            v = float(m.group(2).replace(",", "."))
            if BPM_MIN <= v <= BPM_MAX:
                return m.group(1).strip(), fmt(v), False
            return m.group(1).strip(), None, True
    return line, None, False


def clean_bpm(value) -> str:
    """The BPM of a row as stored: '' or a number as text (20 to 400)."""
    if value in (None, ""):
        return ""
    v = parse_value(value)
    return fmt(v) if v is not None else ""


def clean_beats(value) -> str:
    """Beats per step as stored: '' (meaning 1) or a number as text (1/8 to 64)."""
    if value in (None, ""):
        return ""
    try:
        v = float(str(value).replace(",", "."))
    except ValueError:
        return ""
    return fmt(v) if BEATS_MIN <= v <= BEATS_MAX else ""


def step_ms(bpm, beats=1) -> int:
    """One step in ms: *beats* beats at *bpm*."""
    b = float(beats) if beats not in (None, "") else 1.0
    return int(round(60000.0 / float(bpm) * b))


def _i(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _steps(fn) -> List:
    return [s for s in fn if s.tag.split("}")[-1] == "Step"]


def _why_not(fn) -> str:
    """Why this function cannot follow a tempo; '' when it can."""
    if fn is None:
        return "no function"
    if fn.get("Type") != "Chaser":
        return "not a chaser"
    tt = next((c for c in fn if c.tag.split("}")[-1] == "TempoType"), None)
    if tt is not None and (tt.text or "").strip() == "Beats":
        return "follows the QLC+ tempo"
    steps = _steps(fn)
    if not steps:
        return "no steps"
    if any(_i(s.get("Hold")) >= HOLD_INFINITE for s in steps):
        return "steps wait for the pedal"
    return ""


def chaser_fit(fn, bpm, beats=1) -> Dict:
    """Does the chaser *fn* (an element) already run at *bpm*?  ``{status, now_ms, want_ms, why}``
    where status is ``ok``, ``off`` (a step is not one step time long) or ``na``
    (it cannot follow a tempo; *why* says why)."""
    want = step_ms(bpm, beats)
    why = _why_not(fn)
    if why:
        return {"status": "na", "now_ms": 0, "want_ms": want, "why": why}
    times = [_i(s.get("FadeIn")) + _i(s.get("Hold")) for s in _steps(fn)]
    bad = [t for t in times if abs(t - want) > TOLERANCE_MS]
    now = max(set(times), key=times.count)
    return {"status": "off" if bad else "ok", "now_ms": now, "want_ms": want, "why": ""}


def fit_chaser(fn, bpm, beats=1) -> Dict:
    """Rewrite the steps of the chaser *fn* to one step time at *bpm*; the fade
    in and out of every step keep their share of the step.  Returns the same as
    :func:`chaser_fit` with ``status`` ``fitted``, ``ok`` (nothing to change) or ``na``."""
    r = chaser_fit(fn, bpm, beats)
    if r["status"] != "off":
        return r
    want = r["want_ms"]
    for s in _steps(fn):
        d = _i(s.get("FadeIn")) + _i(s.get("Hold"))
        fi, fo = _i(s.get("FadeIn")), _i(s.get("FadeOut"))
        if d > 0:
            fi_new = min(want, int(round(want * fi / d)))
            fo_new = min(want, int(round(want * fo / d)))
        else:
            fi_new = fo_new = 0
        s.set("FadeIn", str(fi_new))
        s.set("Hold", str(want - fi_new))
        s.set("FadeOut", str(fo_new))
    spd = next((c for c in fn if c.tag.split("}")[-1] == "Speed"), None)
    if spd is not None:                  # the chaser's own (common) values follow
        d0 = _i(spd.get("Duration"))
        fi0, fo0 = _i(spd.get("FadeIn")), _i(spd.get("FadeOut"))
        spd.set("Duration", str(want))
        if d0 > 0 and d0 < HOLD_INFINITE:
            spd.set("FadeIn", str(min(want, int(round(want * fi0 / d0)))))
            spd.set("FadeOut", str(min(want, int(round(want * fo0 / d0)))))
    r["status"] = "fitted"
    return r
