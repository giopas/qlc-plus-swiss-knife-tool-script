"""
Song Builder (3.9.8): build a song's Show from a table of parts.

The song is a table: one row per part with a look (a scene or chaser from the
show), a length, a repeat count and optional fades, plus one music track that is
never cut.  :func:`build` turns the table into ONE Show: the parts back to
back, each part on the track of its name (rows with the same name share a track,
as in a hand-made Show), and the music on its own track.

What QLC+ does (read in its source, 22 to 23 October 2026):
  * a Show item has only a function, a start, a length and a colour; the Show
    runner starts the function at the start and stops it at the end of the item
    and gives it no fade or speed of its own;
  * so a fade is made by the function itself: the tool makes a *copy* of the
    scene with its fade in and out set, and the item points to that copy;
  * a chaser keeps its own run order, so a copy is made with ``Loop`` and its
    steps are timed to the song's tempo when a tempo and beats per step are set.

The table is kept on the Show (attribute ``SwissKnifeSong``) so it can be opened
again; a second build replaces the Show and the copies of the first.
Nothing here opens a file but the music's header, to read its length.

A part can also carry its own ``bpm`` (3.13.0): when set it becomes the tempo in
force from that part onward, so a song that changes speed mid-way (a bridge, an
outro) still works out its bars and beats correctly, part by part, rather than
off one BPM for the whole song.

Music, click and the first beat (3.20.0): besides the music, a song can carry a click
track on a track of its own (``click``: a sound file or a sound in the show, with an
optional output ``device`` that QLC+ stores on the sound's ``<Source Device="…">``), so
the drummer hears the click while the music stays clean.  ``first_beat`` is where bar 1
starts in the music (most recordings do not start on the beat at 0:00): the first part
starts at 0:00 and covers that lead-in, and every bar and beat, the parts after it and
the click count from there.
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Dict, List, Optional

from core import media, setlist_tempo

SONG_ATTR = "SwissKnifeSong"          # on the Show: the table, as JSON
PART_ATTR = "SwissKnifeSongPart"      # on a copy made for the Show: the Show's id
NONE_ID = "4294967295"
LOOK_TYPES = ("Scene", "Chaser", "Collection", "RGBMatrix", "EFX", "Script")
COLORS = ["#d9534f", "#f0ad4e", "#5cb85c", "#5bc0de", "#9b59b6", "#e67e22", "#1abc9c", "#e91e63"]
MUSIC_COLOR = "#4a90d9"
CLICK_COLOR = "#7f8c8d"

MAX_PARTS = 300                       # a table this long is a mistake, and a Show of it would be slow
MAX_ITEMS = 3000                      # parts x repeats in one Show
MAX_MS = 24 * 3600 * 1000             # no part, and no song, lasts a day
UNITS = ("seconds", "bars", "beats")
_END = re.compile(r"^(?:until the end|to the end|to end|until end|till the end|end)$", re.I)
_UNTIL = re.compile(r"^(?:until|till|to|up to)\s+(.+)$", re.I)

_LEN = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(bars?|beats?|ms|s|sec)?$", re.I)
_CLOCK = re.compile(r"^(\d+):(\d{1,2})(?:[.,](\d{1,3}))?$")


def clock(ms: int) -> str:
    """92500 → '1:32.5' (a time a person reads at a glance)."""
    s = ms / 1000
    m = int(s // 60)
    return f"{m}:{s - m * 60:04.1f}"


def _plain(v: float, unit: str, bpm: float, beats_per_bar: int, text: str) -> int:
    """A bare number in the unit the song works in (seconds, bars or beats) → ms."""
    if unit == "seconds":
        return round(v * 1000)
    if bpm <= 0:
        raise ValueError(f"'{text}' needs a tempo: fill in the BPM")
    return round(v * (beats_per_bar if unit == "bars" else 1) * 60000 / bpm)


def parse_length(text, bpm: float = 0, beats_per_bar: int = 4, unit: str = "seconds") -> int:
    """'8 bars', '16 beats', '5s', '0:05', '1500ms' → ms; a bare number is in *unit*
    (the song's choice: seconds, bars or beats)."""
    s = str(text if text is not None else "").strip()
    if not s:
        raise ValueError("a part has no length")
    m = _CLOCK.match(s)
    if m:
        if int(m.group(2)) > 59:
            raise ValueError(f"'{s}': seconds go from 0 to 59")
        return (int(m.group(1)) * 60 + int(m.group(2))) * 1000 + int((m.group(3) or "0").ljust(3, "0"))
    m = _LEN.match(s)
    if not m:
        raise ValueError(f"'{s}' is not a length (5s, 0:05, 8 bars, 16 beats)")
    v, u = float(m.group(1).replace(",", ".")), (m.group(2) or "").lower()
    if not u:
        ms = _plain(v, unit, bpm, beats_per_bar, s)
    elif u.startswith(("bar", "beat")):
        ms = _plain(v, "bars" if u.startswith("bar") else "beats", bpm, beats_per_bar, s)
    else:
        ms = round(v if u == "ms" else v * 1000)
    if ms <= 0:
        raise ValueError(f"'{s}': a part must last more than 0")
    if ms > MAX_MS:
        raise ValueError(f"'{s}' is longer than a day")
    return ms


def parse_point(text, bpm: float = 0, beats_per_bar: int = 4, unit: str = "seconds") -> int:
    """A place in the song, counted from its beginning, for 'until …': a time (1:32, 92s),
    'bar 17', 'beat 65'; a bare number is a second, a bar or a beat as the song works.
    Bars and beats count from 1, so 'bar 1' is the beginning."""
    s = str(text or "").strip()
    m = re.match(r"^(?:bar|measure)\s*(\d+)$", s, re.I)
    if m:
        return _plain(int(m.group(1)) - 1, "bars", bpm, beats_per_bar, s) if int(m.group(1)) >= 1 else _bad(s)
    m = re.match(r"^beat\s*(\d+)$", s, re.I)
    if m:
        return _plain(int(m.group(1)) - 1, "beats", bpm, beats_per_bar, s) if int(m.group(1)) >= 1 else _bad(s)
    m = re.match(r"^\d+(?:[.,]\d+)?$", s)
    if m and unit in ("bars", "beats"):                   # a bare number is a bar (or beat) NUMBER here
        n = float(s.replace(",", "."))
        return _plain(n - 1, unit, bpm, beats_per_bar, s) if n >= 1 else _bad(s)
    return parse_length(s, bpm, beats_per_bar, "seconds")


def _bad(s: str) -> int:
    raise ValueError(f"'{s}': bars and beats start at 1")


def _until_dur(text, t_so_far: int, beats_so_far: float, bpm: float, beats_per_bar: int, unit: str) -> int:
    """How long the current part must still run to reach an 'until' target, counted
    from the song's start.  A clock time ('1:20') is an absolute position in real
    time, so it needs no tempo.  A bar or beat number counts from 1 at the song's
    start, in beats already gone by at each part's own tempo (*beats_so_far*); the
    distance still to go is covered at *bpm*, the only tempo this part can answer
    for (3.13.0: a song whose tempo changes mid-way still resolves correctly, part
    by part)."""
    s = str(text or "").strip()
    m = re.match(r"^(?:bar|measure)\s*(\d+(?:[.,]\d+)?)$", s, re.I)
    if m:
        n = float(m.group(1).replace(",", "."))
        if n < 1:
            _bad(s)
        target_beats = (n - 1) * beats_per_bar
    else:
        m = re.match(r"^beat\s*(\d+(?:[.,]\d+)?)$", s, re.I)
        if m:
            n = float(m.group(1).replace(",", "."))
            if n < 1:
                _bad(s)
            target_beats = n - 1
        else:
            m = re.match(r"^\d+(?:[.,]\d+)?$", s)
            if m and unit in ("bars", "beats"):
                n = float(s.replace(",", "."))
                if n < 1:
                    _bad(s)
                target_beats = (n - 1) * (beats_per_bar if unit == "bars" else 1)
            else:
                return parse_length(s, 0, beats_per_bar, "seconds") - t_so_far
    if bpm <= 0:
        raise ValueError(f"'{s}' needs a tempo: fill in the BPM")
    return round((target_beats - beats_so_far) * 60000 / bpm)


def _is_clock_point(text, unit: str) -> bool:
    """True when an 'until' target is a time counted from 0:00 (1:20, 92s), False for a
    bar or a beat (counted from the first beat)."""
    s = str(text or "").strip()
    if re.match(r"^(?:bar|measure|beat)\s*\d", s, re.I):
        return False
    return not (re.match(r"^\d+(?:[.,]\d+)?$", s) and unit in ("bars", "beats"))


def parse_fade(text) -> int:
    """'2', '2s', '500ms', '' → ms (an empty fade is 0)."""
    s = str(text if text is not None else "").strip()
    if not s:
        return 0
    m = _LEN.match(s)
    if not m or (m.group(2) or "s").lower() not in ("s", "sec", "ms"):
        raise ValueError(f"'{s}' is not a fade (2s, 500ms)")
    v = float(m.group(1).replace(",", "."))
    return round(v if (m.group(2) or "").lower() == "ms" else v * 1000)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ns(el) -> str:
    return el.tag[: el.tag.index("}") + 1] if el.tag.startswith("{") else ""


def _funcs(engine) -> Dict[str, object]:
    return {f.get("ID"): f for f in engine if _local(f.tag) == "Function"}


def _child(el, name: str):
    return next((c for c in el if _local(c.tag) == name), None)


def _set_speed(fn, fade_in: Optional[int], fade_out: Optional[int]) -> None:
    """Set the fades of a copy; None keeps the function's own value."""
    ns = _ns(fn)
    sp = _child(fn, "Speed")
    if sp is None:
        import xml.etree.ElementTree as ET  # nosec B405
        sp = ET.Element(f"{ns}Speed", {"FadeIn": "0", "FadeOut": "0", "Duration": "0"})
        fn.insert(0, sp)
    if fade_in is not None:
        sp.set("FadeIn", str(fade_in))
    if fade_out is not None:
        sp.set("FadeOut", str(fade_out))


def _set_loop(fn) -> bool:
    ro = _child(fn, "RunOrder")
    if ro is None or (ro.text or "").strip() == "Loop":
        return False
    ro.text = "Loop"
    return True


def _clean(spec: dict, lenient: bool = False) -> dict:
    """The table with types and blanks tidied; raises ValueError on what cannot be built.
    *lenient* (the live preview): a half-filled table is accepted, the gaps are noted per part."""
    name = str(spec.get("name") or "").strip()
    if not name and not lenient:
        raise ValueError("give the Show a name")
    if len(name) > 120 or any(ord(c) < 32 for c in name):
        raise ValueError("the Show name is too long or has control characters")
    try:
        bpm = float(spec.get("bpm") or 0)
        bpb = int(spec.get("beats_per_bar") or 4)
    except (TypeError, ValueError):
        raise ValueError("the BPM and the beats per bar must be numbers")
    if bpm and not setlist_tempo.BPM_MIN <= bpm <= setlist_tempo.BPM_MAX:
        raise ValueError("the BPM must be from 20 to 400")
    if not 1 <= bpb <= 16:
        raise ValueError("a bar has 1 to 16 beats")
    unit = str(spec.get("unit") or "seconds")
    if unit not in UNITS:
        raise ValueError("lengths are in seconds, bars or beats")
    raw = spec.get("parts") or []
    if len(raw) > MAX_PARTS:
        raise ValueError(f"a song has at most {MAX_PARTS} parts")
    parts = []
    for n, p in enumerate(raw, 1):
        fid = str(p.get("function_id") or "").strip()
        issue = ""
        if not fid:
            issue = f"part {n} has no look: pick a scene or a chaser"
            if not lenient:
                raise ValueError(issue)
        try:
            rep = int(p.get("repeat") if p.get("repeat") not in (None, "") else 1)
            if not 1 <= rep <= 64:
                raise ValueError
        except (TypeError, ValueError):
            rep = 1
            issue = issue or f"part {n}: repeat must be a whole number from 1 to 64"
            if not lenient:
                raise ValueError(issue)
        beats = str(p.get("beats") or "").strip()
        if beats:
            try:
                if not setlist_tempo.BEATS_MIN <= float(beats.replace(",", ".")) <= setlist_tempo.BEATS_MAX:
                    raise ValueError
            except ValueError:
                issue = issue or f"part {n}: beats per step must be from 1/8 to 64"
                if not lenient:
                    raise ValueError(issue)
        p_bpm = str(p.get("bpm") or "").strip()
        if p_bpm:
            try:
                if not setlist_tempo.BPM_MIN <= float(p_bpm.replace(",", ".")) <= setlist_tempo.BPM_MAX:
                    raise ValueError
            except ValueError:
                issue = issue or f"part {n}: its own BPM must be from {setlist_tempo.BPM_MIN:g} to {setlist_tempo.BPM_MAX:g}"
                if not lenient:
                    raise ValueError(issue)
        parts.append({"name": str(p.get("name") or "").strip()[:120] or f"Part {n}", "function_id": fid,
                      "length": str(p.get("length") or "").strip(), "repeat": rep,
                      "fade_in": str(p.get("fade_in") or "").strip(),
                      "fade_out": str(p.get("fade_out") or "").strip(), "beats": beats, "bpm": p_bpm,
                      "issue": issue})
    if not parts and not lenient:
        raise ValueError("add at least one part")
    music = spec.get("music") or {}
    out_music = {}
    if music.get("function_id"):
        out_music = {"function_id": str(music["function_id"])}
    elif str(music.get("path") or "").strip():
        path = str(music["path"]).strip()
        if len(path) > 1000 or any(ord(c) < 32 for c in path):
            raise ValueError("the music path is not a path")
        out_music = {"path": path, "name": str(music.get("name") or "").strip()[:200],
                     "length": str(music.get("length") or "").strip()}
    lead_text = str(spec.get("first_beat") or "").strip()
    lead = parse_first_beat(lead_text)
    click = spec.get("click") or {}
    out_click = {}
    device = str(click.get("device") or "").strip()
    if len(device) > 200 or any(ord(c) < 32 for c in device):
        raise ValueError("the click's output is not the name of a sound device")
    if click.get("function_id"):
        out_click = {"function_id": str(click["function_id"])}
    elif str(click.get("path") or "").strip():
        path = str(click["path"]).strip()
        if len(path) > 1000 or any(ord(c) < 32 for c in path):
            raise ValueError("the click path is not a path")
        out_click = {"path": path, "name": str(click.get("name") or "").strip()[:200]}
    if out_click and device:
        out_click["device"] = device
    return {"name": name, "bpm": bpm, "beats_per_bar": bpb, "unit": unit, "parts": parts, "music": out_music,
            "first_beat": lead_text if lead else "", "lead_ms": lead, "click": out_click,
            "show_id": str(spec.get("show_id") or "")}


MAX_LEAD_MS = 10 * 60 * 1000          # a first beat ten minutes in is a typing mistake


def parse_first_beat(text) -> int:
    """Where bar 1 starts in the music (3.20.0): '0:01.25', '1.25' (seconds), '1250ms' → ms;
    empty or 0 is the very start."""
    s = str(text if text is not None else "").strip()
    if not s or re.match(r"^0+(?:[.,]0*)?\s*(?:s|sec|ms)?$", s, re.I) or re.match(r"^0+:0{1,2}(?:[.,]0*)?$", s):
        return 0
    try:
        ms = parse_length(s, 0, 4, "seconds")
    except ValueError:
        raise ValueError(f"'{s}' is not a time for the first beat (1.25, 0:01.25, 1250ms)")
    if ms > MAX_LEAD_MS:
        raise ValueError("the first beat must be in the first ten minutes of the music")
    return ms


def resolve(path: str, base_dir: str = "") -> str:
    """The file a music path names: a relative path counts from the show's folder, as QLC+
    reads it (3.13.0; before, it was looked up from where Swiss Knife was started)."""
    if not path or os.path.isabs(path) or not base_dir:
        return path
    return os.path.join(base_dir, path)


def music_info(music: dict, funcs: Dict[str, object], base_dir: str = "", what: str = "music") -> Dict[str, object]:
    """Where the music (or the click, *what*) is and how long: {'name','path','length_ms','source'};
    length_ms may be None.  *path* stays as written (QLC+ stores it so); the file is read from
    the show's folder."""
    if music.get("function_id"):
        f = funcs.get(music["function_id"])
        if f is None or f.get("Type") != "Audio":
            raise ValueError(f"the {what} function is not in the show")
        sp = _child(f, "Speed")
        src = _child(f, "Source")
        return {"name": f.get("Name", ""), "path": (src.text or "").strip() if src is not None else "",
                "length_ms": int(sp.get("Duration", "0")) if sp is not None else None, "source": "function"}
    path = music["path"]
    if os.path.splitext(path)[1].lower() not in media.AUDIO_EXTS:
        raise ValueError(f"the {what} must be a sound file (.wav, .mp3, .ogg, .flac, .m4a)")
    length = media.audio_length_ms(resolve(path, base_dir))
    if length is None and music.get("length"):
        length = parse_length(music["length"])
    return {"name": music.get("name") or os.path.basename(path), "path": path, "length_ms": length, "source": "path"}


def plan(engine, spec: dict, lenient: bool = False, base_dir: str = "") -> Dict[str, object]:
    """What the table makes, without changing anything: part starts, the length, the free
    time and warnings.  *lenient* is for the live preview: a part with no look or a length
    that cannot be read is listed with its ``issue`` and counts for nothing, instead of stopping.
    A part's own BPM (3.13.0), when set, becomes the tempo for it and every part after it
    until the next one that sets its own; lengths and 'until' targets are then worked out
    with that running tempo, part by part, instead of one BPM for the whole song.
    With a first beat (3.20.0) the first part starts at 0:00 and also covers the lead-in
    before it; its length, and every bar and beat, count from the first beat."""
    s = _clean(spec, lenient)
    funcs = _funcs(engine)
    unit, bpb = s["unit"], s["beats_per_bar"]
    mlen, minfo, warns = None, None, []
    if s["music"]:
        try:
            minfo = music_info(s["music"], funcs, base_dir)
            mlen = minfo["length_ms"]
        except ValueError as e:
            if not lenient:
                raise
            warns.append(str(e))
    lead = s["lead_ms"]
    if lead and mlen is not None and lead >= mlen:
        msg = f"the first beat ({clock(lead)}) is not before the end of the music ({clock(mlen)})"
        if not lenient:
            raise ValueError(msg)
        warns.append(msg)
    t, rows, items = 0, [], 0
    beats_elapsed, running_bpm = 0.0, s["bpm"]
    last = len(s["parts"]) - 1
    for n, p in enumerate(s["parts"], 1):
        if p["bpm"]:
            try:
                running_bpm = float(p["bpm"].replace(",", "."))
            except ValueError:
                pass
        bpm = running_bpm
        issue, dur, f = p["issue"], 0, None
        absolute = False                     # a length that already counts from 0:00 (to the end, until 1:20)
        try:
            if not issue:
                f = funcs.get(p["function_id"])
                if f is None:
                    raise ValueError(f"part {n} '{p['name']}': its look is not in the show")
                if f.get("Type") not in LOOK_TYPES:
                    raise ValueError(f"part {n} '{p['name']}': a {f.get('Type')} cannot be a look; pick a scene or a chaser")
            text = p["length"]
            if _END.match(text):
                if n - 1 != last:
                    raise ValueError(f"part {n} '{p['name']}': 'to the end' can only be the last part")
                if p["repeat"] != 1:
                    raise ValueError(f"part {n} '{p['name']}': 'to the end' cannot be repeated")
                if mlen is None:
                    raise ValueError(f"part {n} '{p['name']}': 'to the end' needs the length of the music")
                dur, absolute = mlen - t, True
                if dur <= 0:
                    raise ValueError(f"part {n} '{p['name']}': nothing is left before the end of the music")
            elif _UNTIL.match(text):
                if p["repeat"] != 1:
                    raise ValueError(f"part {n} '{p['name']}': 'until' cannot be repeated")
                target = _UNTIL.match(text).group(1)
                dur = _until_dur(target, t, beats_elapsed, bpm, bpb, unit)
                absolute = _is_clock_point(target, unit)
                if dur <= 0:
                    raise ValueError(f"part {n} '{p['name']}': '{text}' is not after the start of the part ({clock(t)})")
            else:
                dur = parse_length(text, bpm, bpb, unit)
            if dur > MAX_MS:
                raise ValueError(f"part {n} '{p['name']}' is longer than a day")
        except ValueError as e:
            if not lenient:
                raise
            issue, dur = issue or str(e), 0
        if f is not None and dur:
            fi, fo = parse_fade(p["fade_in"]), parse_fade(p["fade_out"])
            if fi + fo > dur:
                warns.append(f"'{p['name']}': the fades ({clock(fi + fo)}) are longer than the part ({clock(dur)})")
        items += p["repeat"] if dur else 0
        if items > MAX_ITEMS:
            raise ValueError(f"the table makes more than {MAX_ITEMS} items: lower the repeats")
        # the first part also covers the lead-in before the first beat (3.20.0); a length
        # that counts from 0:00 (to the end, until 1:20) already holds it
        extra = lead if (n == 1 and lead and dur and not absolute) else 0
        if n == 1 and lead and absolute and 0 < dur <= lead and not issue:
            issue = f"part 1 '{p['name']}' ends before the first beat ({clock(lead)})"
            if not lenient:
                raise ValueError(issue)
            dur = 0
        total = dur * p["repeat"] + extra
        row = {"name": p["name"], "look": f.get("Name", "") if f is not None else "", "start_ms": t,
               "length_ms": dur, "repeat": p["repeat"], "end_ms": t + total, "issue": issue, "bpm": bpm}
        if extra:
            row["lead_ms"] = extra
        rows.append(row)
        counted = total - lead if (n == 1 and lead and total) else total     # the lead-in is before bar 1
        if counted > 0 and bpm:
            beats_elapsed += counted * bpm / 60000.0
        t += total
    if minfo:
        if mlen is None:
            warns.append("the length of the music is not known: type it in (for example 3:45)")
        elif mlen > t:
            warns.append(f"the music is {clock(mlen - t)} longer than the parts: the lights stop first")
        elif mlen < t:
            warns.append(f"the parts run {clock(t - mlen)} past the end of the music")
        if minfo["path"] and media.media_status(minfo["path"], base_dir) == "missing":
            warns.append("the music file is not found on this computer")
    clen = None
    if s["click"]:
        try:
            cinfo = music_info(s["click"], funcs, base_dir, "click")
            clen = cinfo["length_ms"]
            if cinfo["path"] and media.media_status(cinfo["path"], base_dir) == "missing":
                warns.append("the click file is not found on this computer")
            elif clen and clen + 50 < max(t, mlen or 0):
                warns.append(f"the click track stops {clock(max(t, mlen or 0) - clen)} before the song: make it again")
        except ValueError as e:
            if not lenient:
                raise
            warns.append(str(e))
    free = max(mlen - t, 0) if mlen else 0
    return {"parts": rows, "length_ms": t, "music_ms": mlen, "free_ms": free, "lead_ms": lead,
            "click_ms": clen, "warnings": warns}


def build(engine, spec: dict, next_id: int, base_dir: str = ""):
    """Add (or replace) the Show of *spec* in *engine*.  Returns the summary:
    {'show_id', 'name', 'copies': [ids], 'audio_id' (new), 'next_id' (first unused), + plan}."""
    import xml.etree.ElementTree as ET  # nosec B405
    p = plan(engine, spec, base_dir=base_dir)
    s = _clean(spec)
    ns = _ns(engine)
    funcs = _funcs(engine)
    nid = next_id

    def new_id() -> str:
        nonlocal nid
        v = str(nid)
        nid += 1
        return v

    # the Show: reuse the one this table built before, else a new id
    old = funcs.get(s["show_id"]) if s["show_id"] else None
    if old is not None and (old.get("Type") != "Show" or SONG_ATTR not in old.attrib or old.get("SwissKnifeClone")):
        old = None
    show_id = old.get("ID") if old is not None else new_id()
    for f in [f for f in funcs.values() if f.get(PART_ATTR) == show_id]:       # copies of the last build
        engine.remove(f)
    funcs = _funcs(engine)
    if old is not None:
        show = old
        for c in [c for c in show if _local(c.tag) != "TimeDivision"]:
            show.remove(c)
        td = _child(show, "TimeDivision")
        if td is not None:
            td.set("BPM", str(int(s["bpm"] or 120)))
    else:
        show = ET.SubElement(engine, f"{ns}Function", {"ID": show_id, "Type": "Show"})
        ET.SubElement(show, f"{ns}TimeDivision", {"Type": "Time", "BPM": str(int(s["bpm"] or 120))})
    show.set("Name", s["name"])
    keep = dict(s, parts=[{k: v for k, v in p.items() if k != "issue"} for p in s["parts"]])
    keep.pop("show_id", None)                              # the Show's own ID is read from the Show
    keep.pop("lead_ms", None)                              # worked out again from first_beat
    for k in ("first_beat", "click"):                      # a table without them stays as before 3.20.0
        if not keep.get(k):
            keep.pop(k, None)
    show.set(SONG_ATTR, json.dumps(keep, ensure_ascii=False, separators=(",", ":"), sort_keys=True))

    copies: List[str] = []
    tracks: Dict[str, object] = {}
    colour: Dict[str, str] = {}
    t = 0
    for p_in, row in zip(s["parts"], p["parts"]):
        base = funcs[p_in["function_id"]]
        fi, fo = parse_fade(p_in["fade_in"]), parse_fade(p_in["fade_out"])
        use = base
        in_set, out_set = bool(p_in["fade_in"].strip()), bool(p_in["fade_out"].strip())   # "0" is a choice: no fade
        need_copy = in_set or out_set
        typ = base.get("Type")
        fit_beats = p_in["beats"] and row["bpm"] and typ == "Chaser"
        if typ == "Chaser" and (fit_beats or need_copy or (_child(base, "RunOrder") is not None
                                                             and (_child(base, "RunOrder").text or "").strip() != "Loop")):
            need_copy = True
        if need_copy:
            use = copy.deepcopy(base)
            use.attrib.pop("SwissKnifeClone", None)
            use.set("ID", new_id())
            use.set("Name", f"{s['name']} - {p_in['name']} ({base.get('Name', '')})")
            use.set(PART_ATTR, show_id)
            if in_set or out_set:
                _set_speed(use, fi if in_set else None, fo if out_set else None)
            if typ == "Chaser":
                _set_loop(use)
                if fit_beats:
                    setlist_tempo.fit_chaser(use, row["bpm"], float(p_in["beats"].replace(",", ".")))
            engine.append(use)
            copies.append(use.get("ID"))
        key = row["name"]
        if key not in tracks:
            tr = ET.SubElement(show, f"{ns}Track", {"ID": str(len(tracks)), "Name": key,
                                                    "SceneID": NONE_ID, "isMute": "0"})
            tracks[key] = tr
            colour[key] = COLORS[(len(tracks) - 1) % len(COLORS)]
        for r in range(row["repeat"]):
            dur = row["length_ms"] + (row.get("lead_ms", 0) if r == 0 else 0)   # the lead-in (3.20.0)
            ET.SubElement(tracks[key], f"{ns}ShowFunction",
                          {"ID": use.get("ID"), "StartTime": str(t), "Duration": str(dur),
                           "Color": colour[key]})
            t += dur

    def sound_track(spec_part: dict, what: str, track_name: str, colour_: str, device: str = "") -> str:
        """Put a sound on a track of its own from 0:00; returns the id of a new Audio function or ''."""
        mi = music_info(spec_part, funcs, base_dir, what)
        mid, made = spec_part.get("function_id"), ""
        if not mid:                                  # the same file already has a function: use it
            same = [f for f in funcs.values() if f.get("Type") == "Audio" and _child(f, "Source") is not None
                    and (_child(f, "Source").text or "").strip() == mi["path"]]
            if what == "click":
                # a click this tool made follows the output chosen now; any other sound of the
                # same file is used only when it already plays on that output
                own = [f for f in same if f.get(PART_ATTR) == "click"]
                if own:
                    src = _child(own[0], "Source")
                    if device:
                        src.set("Device", device)
                    else:
                        src.attrib.pop("Device", None)
                    same = own
                else:
                    same = [f for f in same if (_child(f, "Source").get("Device") or "") == device]
            if same:
                mid = same[0].get("ID")
        if not mid:
            mid = made = new_id()
            a = ET.SubElement(engine, f"{ns}Function", {"ID": mid, "Type": "Audio", "Name": mi["name"]})
            ET.SubElement(a, f"{ns}Speed", {"FadeIn": "0", "FadeOut": "0", "Duration": str(mi["length_ms"] or 0)})
            ET.SubElement(a, f"{ns}RunOrder").text = "SingleShot"
            src = ET.SubElement(a, f"{ns}Source")
            if device:                               # QLC+ plays it on that output (Audio::saveXML)
                src.set("Device", device)
            src.text = mi["path"]
            a.set(PART_ATTR, what)
        tr = ET.SubElement(show, f"{ns}Track", {"ID": str(len(tracks) + len(extra_tracks)), "Name": track_name,
                                                "SceneID": NONE_ID, "isMute": "0"})
        extra_tracks.append(tr)
        ET.SubElement(tr, f"{ns}ShowFunction", {"ID": mid, "StartTime": "0",
                                                "Duration": str(mi["length_ms"] or p["length_ms"]),
                                                "Color": colour_})
        return made

    extra_tracks: List[object] = []
    audio_id = click_id = ""
    if s["music"]:
        audio_id = sound_track(s["music"], "music", "Music", MUSIC_COLOR)
    if s["click"]:
        click_id = sound_track(s["click"], "click", "Click", CLICK_COLOR, s["click"].get("device", ""))
    refreshed = _refresh_setlist_copies(engine, show)
    return {"show_id": show_id, "name": s["name"], "copies": copies, "audio_id": audio_id,
            "click_id": click_id, "next_id": nid, "setlist_copies": refreshed, **p}


def _refresh_setlist_copies(engine, show) -> List[str]:
    """The Setlist plays its own copy of a Show (marked SwissKnifeClone).  After a
    rebuild the old part copies are gone, so the Setlist's copy must follow the
    new timeline, else it points at lights that no longer exist.  Returns the IDs."""
    sid, done = show.get("ID"), []
    for f in list(engine):
        if _local(f.tag) != "Function" or f.get("Type") != "Show" or f.get("SwissKnifeClone") != sid:
            continue
        for c in [c for c in f if _local(c.tag) != "TimeDivision"]:
            f.remove(c)
        for c in show:
            if _local(c.tag) != "TimeDivision":
                f.append(copy.deepcopy(c))
        td, src = _child(f, "TimeDivision"), _child(show, "TimeDivision")
        if td is not None and src is not None:
            td.set("BPM", src.get("BPM", "120"))
        f.set("Name", show.get("Name", ""))
        if SONG_ATTR in show.attrib:
            f.set(SONG_ATTR, show.get(SONG_ATTR))
        done.append(f.get("ID"))
    return done


def spec_of(show) -> Optional[dict]:
    """The table a Show was built from, or None."""
    raw = show.get(SONG_ATTR)
    if not raw or len(raw) > 200_000:                    # the table of a real song is a few KB
        return None
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    d["show_id"] = show.get("ID")
    return d
