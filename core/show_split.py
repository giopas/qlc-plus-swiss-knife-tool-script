"""
Split a Show into one Show per section (3.9.8).

A song's Show is one long timeline.  To play it as cues (verse, chorus 2, bridge)
each section needs its own Show.  The person gives the sections a name and a
start, as a time (``1:32``, ``92.5s``) or as a bar or beat at a tempo
(``bar 17``, ``beat 65``).  Section k runs from its start to the start of
section k+1; the last one runs to the end of the Show.

Rules:
  * The original Show is never changed; the sections are new Shows.
  * An item goes to the section where it *starts*, shifted so that section starts
    at 0.  An item is never cut: QLC+ always plays an item from its beginning, so a
    cut would restart a sound or a chaser in the wrong place.  When an item runs past the cut,
    it is kept whole and listed as a warning.
  * The first section must start at 0, otherwise the items before it would be lost.
"""

from __future__ import annotations

import copy
import re
from typing import Dict, List

from core import media

_TIME_RE = re.compile(r"^(?:(\d+):)?(\d+):(\d{1,2})(?:[.,](\d{1,3}))?$")     # h:mm:ss or m:ss
_SEC_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(s|sec|ms)?$", re.I)
_BAR_RE = re.compile(r"^(?:bar|measure|b)\s*(\d+)(?:\s*[.|:]\s*(\d+))?$", re.I)
_BEAT_RE = re.compile(r"^beat\s*(\d+)$", re.I)


def beat_ms(bpm: float) -> float:
    return 60000.0 / bpm


def parse_position(text: str, bpm: float = 0, beats_per_bar: int = 4) -> int:
    """A start as written by a person → milliseconds.  Raises ValueError with a plain sentence."""
    s = (text or "").strip()
    if not s:
        raise ValueError("a section has no start")
    m = _TIME_RE.match(s)
    if m:
        h, mi, sec, frac = m.groups()
        if int(sec) > 59:
            raise ValueError(f"'{s}': seconds go from 0 to 59")
        ms = (int(h or 0) * 3600 + int(mi) * 60 + int(sec)) * 1000 + int((frac or "0").ljust(3, "0"))
        return ms
    m = _BAR_RE.match(s)
    if m:
        if bpm <= 0:
            raise ValueError(f"'{s}' needs a tempo: fill in the BPM")
        bar, beat = int(m.group(1)), int(m.group(2) or 1)
        if bar < 1 or beat < 1 or beat > beats_per_bar:
            raise ValueError(f"'{s}': bars start at 1 and a bar has {beats_per_bar} beats")
        return round(((bar - 1) * beats_per_bar + (beat - 1)) * beat_ms(bpm))
    m = _BEAT_RE.match(s)
    if m:
        if bpm <= 0:
            raise ValueError(f"'{s}' needs a tempo: fill in the BPM")
        n = int(m.group(1))
        if n < 1:
            raise ValueError(f"'{s}': beats start at 1")
        return round((n - 1) * beat_ms(bpm))
    m = _SEC_RE.match(s)
    if m:
        v = float(m.group(1).replace(",", "."))
        return round(v if (m.group(2) or "").lower() == "ms" else v * 1000)
    raise ValueError(f"'{s}' is not a time (1:32, 92.5s) or a bar or beat (bar 17, beat 65)")


def _name(f) -> str:
    return f.get("Name", "")


def plan(show, sections: List[Dict[str, str]], bpm: float = 0, beats_per_bar: int = 4,
         function_names: Dict[str, str] | None = None) -> Dict[str, object]:
    """What splitting *show* would do, without changing anything.

    *sections*: ``[{"name": "Verse", "at": "0:00"}, …]``.  Returns
    ``{"sections": [{"name", "start_ms", "end_ms", "items"}], "warnings": [str]}``;
    raises ValueError when the sections cannot be used."""
    names = function_names or {}
    if len(sections) < 2:
        raise ValueError("a split needs at least two sections")
    cuts = []
    for n, sec in enumerate(sections, 1):
        nm = (sec.get("name") or "").strip() or f"Section {n}"
        cuts.append((nm, parse_position(sec.get("at", ""), bpm, beats_per_bar)))
    if cuts[0][1] != 0:
        raise ValueError("the first section must start at 0:00, or the items before it would be lost")
    for (a, ta), (b, tb) in zip(cuts, cuts[1:]):
        if tb <= ta:
            raise ValueError(f"'{b}' must start after '{a}'")
    items = media.show_items(show)
    length = media.show_length_ms(show)
    out, warns = [], []
    for k, (nm, start) in enumerate(cuts):
        end = cuts[k + 1][1] if k + 1 < len(cuts) else max(length, start)
        mine = [i for i in items if start <= int(i["start"]) < end]
        for i in mine:
            if int(i["start"]) + int(i["duration"]) > end and k + 1 < len(cuts):
                over = (int(i["start"]) + int(i["duration"]) - end) / 1000
                fn = names.get(str(i["function"]), str(i["function"]))
                warns.append(f"'{fn}' on {i['track'] or 'a track'} starts in '{nm}' and runs {over:g} s past "
                             f"the cut: kept whole in '{nm}', not cut")
        out.append({"name": nm, "start_ms": start, "end_ms": end, "items": len(mine)})
    if cuts[-1][1] >= length and length:
        warns.append(f"'{cuts[-1][0]}' starts at or after the end of the Show: it will be empty")
    return {"sections": out, "warnings": warns}


def build(show, sections: List[Dict[str, str]], first_id: int, bpm: float = 0, beats_per_bar: int = 4,
          function_names: Dict[str, str] | None = None):
    """The new Show elements, one per section (ids from *first_id*), and the plan."""
    p = plan(show, sections, bpm, beats_per_bar, function_names)
    tag = show.tag
    ns = tag[: tag.index("}") + 1] if tag.startswith("{") else ""
    made = []
    items = media.show_items(show)
    for k, sec in enumerate(p["sections"]):
        new = copy.deepcopy(show)
        new.attrib.pop("SwissKnifeClone", None)
        new.set("ID", str(first_id + k))
        new.set("Name", f"{_name(show)} - {sec['name']}")
        for tr in [c for c in new if c.tag == f"{ns}Track"]:
            new.remove(tr)
        track_no = 0
        for tr in [c for c in show if c.tag == f"{ns}Track"]:
            keep = [it for it in tr if it.tag == f"{ns}ShowFunction"
                    and sec["start_ms"] <= int(it.get("StartTime", "0")) < sec["end_ms"]]
            if not keep:
                continue
            nt = copy.deepcopy(tr)
            nt.set("ID", str(track_no))
            track_no += 1
            for it in [c for c in nt if c.tag == f"{ns}ShowFunction"]:
                nt.remove(it)
            for it in keep:
                ni = copy.deepcopy(it)
                ni.set("StartTime", str(int(it.get("StartTime", "0")) - sec["start_ms"]))
                nt.append(ni)
            new.append(nt)
        made.append(new)
    del items
    return made, p
