"""
Copy colours from one fixture to another, in every look of the show (3.23.0).

Asked while making a show for a smaller stage: *this PAR should show the
colours that one shows*, in every scene, while keeping its own brightness,
position and everything else. The Function Porter's *plays like* only adds a
new light to the looks it is missing from; Brightness changes levels and never
colours. Here, for each pair (target ← source):

* every **scene** and every **sequence step** that sets the source gets the
  source's colour on the target's colour channels (RGB and the other emitters,
  the colour wheel, colour macro channels);
* ``brightness="keep"`` (default): the target keeps its own brightness. Its
  dimmer is not touched, and without a dimmer the new colour is as bright as
  its old one. A look where the target is dark stays dark; a look where the
  source is dark leaves the target as it is.
  ``brightness="source"``: the target also takes the source's level, so it
  looks exactly like the source (dark when the source is dark);
* the two fixtures can be different types: the colour is translated by
  capability (``core.capability_map``: RGB, RGBW, a colour wheel's nearest
  slot);
* ``add=True`` also puts the target into the looks that set the source but not
  the target. There it *plays like* the source (``core.rig_grow.wire``: every
  channel, the source's level).

Not changed, and said in the report: looks that take their colour from a
palette (QLC+ 5.3), RGB matrices (they run on a fixture group), scripts.

Pure functions on an un-namespaced workspace root, deterministic.
"""
from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set, Tuple

from core import capability_map as cm

BRIGHTNESS = ("keep", "source")


# ── what a fixture can do ───────────────────────────────────────────────────

def _infos(root: ET.Element) -> dict:
    from core.porter import _fixture_infos
    return _fixture_infos(root)


def _def_of(info: dict, defs: dict):
    return (defs or {}).get((info["manufacturer"].strip().lower(), info["model"].strip().lower()))


def can_colour(defn: Optional[dict], mode: str) -> bool:
    """True when the mode mixes colour (red, green and blue) or has a colour wheel."""
    if not cm.can_translate(defn, mode):
        return False
    lay = cm._layout(defn, mode)
    roles = {cm._role(cd) for _, _, cd in lay if not cd.get("byte")}
    return all(r in roles for r in cm._MIX_ROLES) or any(cm._is_wheel(cd) for _, _, cd in lay)


def colour_channels(defn: dict, mode: str) -> Set[int]:
    """Channel indices that make the colour: the emitters (not the dimmer),
    the colour wheel and any other channel of the *Colour* group (macros)."""
    out = set()
    for i, _n, cd in cm._layout(defn, mode):
        role = cm._role(cd)
        if role and role != "Dimmer":
            out.add(i)
        elif (cd.get("group") or "") == "Colour":
            out.add(i)
    return out


def dimmer_channels(defn: dict, mode: str) -> Set[int]:
    return {i for i, _n, cd in cm._layout(defn, mode) if cm._role(cd) == "Dimmer"}


def fixtures(root: ET.Element, defs: dict) -> List[dict]:
    """The show's fixtures with what they can do and how many looks set them."""
    from core.rig_grow import usage
    used = usage(root)
    rows = []
    for fid, inf in _infos(root).items():
        d = _def_of(inf, defs)
        rows.append({"id": fid, "name": inf["name"], "model": inf["model"], "mode": inf["mode"],
                     "known": cm.can_translate(d, inf["mode"]),
                     "colour": can_colour(d, inf["mode"]), "looks": used.get(fid, 0)})
    return rows


# ── the colour of one fixture in one look ──────────────────────────────────

def _pairs(text: str) -> Dict[int, int]:
    return cm._pairs(text or "")


def _text(vals: Dict[int, int]) -> str:
    return ",".join(f"{c},{vals[c]}" for c in sorted(vals))


def _peak(c) -> float:
    return max(c) if c else 0.0


class _Pair:
    """Turns the source's values in a look into the target's new values."""

    def __init__(self, sdef, smode, tdef, tmode, brightness: str):
        self.sdef, self.smode, self.tdef, self.tmode = sdef, smode, tdef, tmode
        self.brightness = brightness
        self.colour = colour_channels(tdef, tmode)
        self.dimmer = dimmer_channels(tdef, tmode)
        self.same = sdef is tdef and smode == tmode

    def new_values(self, src: Dict[int, int], tgt: Dict[int, int]) -> Tuple[Optional[Dict[int, int]], str]:
        """``(target values, why)``; ``None`` = leave the target as it is."""
        st = cm.decode(self.sdef, self.smode, src)
        level = 1.0 if st.level is None else st.level
        colour = st.colour if st.colour is not None else (1.0, 1.0, 1.0)
        out = dict(tgt)
        if self.brightness == "source":
            if self.same:
                for c in self.colour | self.dimmer:
                    if c in src:
                        out[c] = src[c]
                    else:
                        out.pop(c, None)
                return out, ""
            enc, _notes = cm.encode(self.tdef, self.tmode, st)
            for c in self.colour | self.dimmer:
                out[c] = enc[c]
            return out, ""
        # keep: only the hue moves, the target's own brightness stays
        peak = _peak(colour)
        if level <= 0 or peak <= 0:
            return None, "source dark"
        ts = cm.decode(self.tdef, self.tmode, tgt)
        if ts.colour_source == "mix":
            keep = _peak(ts.colour)
        elif ts.colour_source == "wheel":
            keep = 1.0
        else:                                   # target was white / no colour set yet
            mix = [v for c, v in tgt.items() if c in self.colour]
            keep = (max(mix) / 255.0) if mix else 1.0
        if keep <= 0:
            return None, "target dark"
        k = keep / peak
        want = cm.LookState(level=1.0, colour=tuple(min(1.0, x * k) for x in colour),
                            white=None if st.white is None else min(1.0, st.white * k),
                            colour_source=st.colour_source)
        enc, _notes = cm.encode(self.tdef, self.tmode, want)
        for c in self.colour:
            out[c] = enc[c]
        return out, ""


# ── the whole show ──────────────────────────────────────────────────────────

def _seq_items(text: str) -> List[Tuple[str, str]]:
    from core.rig_grow import _seq_items
    return _seq_items(text)


def copy_colours(root: ET.Element, plan: Dict[str, str], defs: dict,
                 brightness: str = "keep", add: bool = False, functions=None) -> dict:
    """Copy the colours in *plan* (``target id → source id``). Changes *root*
    in place. Returns the report::

        {"pairs": {target: {source, scenes, steps, added, same, dark}},
         "problems": {target: why}, "not_changed": [lines], "total": n}
    """
    if brightness not in BRIGHTNESS:
        raise ValueError(f"brightness must be one of {', '.join(BRIGHTNESS)}")
    plan = {str(t): str(s) for t, s in (plan or {}).items() if s not in (None, "")}
    rep = {"pairs": {}, "problems": {}, "not_changed": [], "total": 0,
           "brightness": brightness, "add": bool(add)}
    eng = root.find("Engine")
    if eng is None or not plan:
        return rep
    infos = _infos(root)
    pairs: Dict[str, _Pair] = {}
    for t, s in plan.items():
        ti, si = infos.get(t), infos.get(s)
        if not ti or not si:
            rep["problems"][t] = f"fixture {t if not ti else s} is not in the show"
            continue
        if t == s:
            rep["problems"][t] = "a fixture cannot copy its own colours"
            continue
        td, sd = _def_of(ti, defs), _def_of(si, defs)
        miss = [x for x, d in ((si, sd), (ti, td)) if not cm.can_translate(d, x["mode"])]
        if miss:
            rep["problems"][t] = (f"the fixture definition (.qxf) of {miss[0]['model']} "
                                  f"({miss[0]['mode']}) was not found; put the .qxf next to the "
                                  "show or in QLC+'s own fixtures folder")
            continue
        if not can_colour(td, ti["mode"]):
            rep["problems"][t] = f"'{ti['name']}' cannot make colours (no RGB and no colour wheel)"
            continue
        if not can_colour(sd, si["mode"]):
            rep["problems"][t] = f"'{si['name']}' has no colours to copy (no RGB and no colour wheel)"
            continue
        pairs[t] = _Pair(sd, si["mode"], td, ti["mode"], brightness)
        rep["pairs"][t] = {"source": s, "scenes": 0, "steps": 0, "added": 0, "same": 0, "dark": 0}

    only = None if functions is None else set(map(str, functions))
    absent: Dict[str, Set[str]] = {t: set() for t in pairs}
    panic = _panic(root)
    from core.porter import _complete, _neutral_maps
    neutral = _neutral_maps(infos, defs)

    def one(t: str, src_text: str, tgt_text: str) -> Optional[str]:
        st = rep["pairs"][t]
        new, why = pairs[t].new_values(_pairs(src_text), _pairs(tgt_text))
        if new is None:
            st["dark"] += 1
            return None
        txt, was = _text(new), _text(_pairs(tgt_text))
        if neutral.get(t):                      # every channel declared (no LTP bleed)
            txt, was = _complete(txt, neutral[t]), _complete(was, neutral[t])
        if txt == was:
            st["same"] += 1
            return None
        return txt

    for fn in eng.findall("Function"):
        ftype = fn.get("Type")
        if ftype not in ("Scene", "Sequence"):
            continue
        if only is not None and fn.get("ID", "") not in only:
            continue
        if fn.get("ID", "") in panic:
            rep["panic"] = rep.get("panic", 0) + 1
            continue
        vals = {fv.get("ID", ""): fv for fv in fn.findall("FixtureVal")}
        if ftype == "Scene":
            for t, p in pairs.items():
                s = plan[t]
                if s not in vals:
                    continue
                if t not in vals:
                    absent[t].add(fn.get("ID", ""))
                    continue
                txt = one(t, vals[s].text or "", vals[t].text or "")
                if txt is not None:
                    vals[t].text = txt
                    rep["pairs"][t]["scenes"] += 1
        else:
            for step in fn.findall("Step"):
                items = _seq_items(step.text or "")
                d = dict(items)
                changed = False
                for t in pairs:
                    s = plan[t]
                    if s not in d:
                        continue
                    if t not in d:
                        absent[t].add(fn.get("ID", ""))
                        continue
                    txt = one(t, d[s], d[t])
                    if txt is not None:
                        d[t] = txt
                        rep["pairs"][t]["steps"] += 1
                        changed = True
                if changed:
                    step.text = ":".join(f"{f}:{d[f]}" for f, _ in items)
                    step.set("Values", str(sum(len(_pairs(v)) for v in d.values())))

    if add:
        from core.rig_grow import wire
        for t in pairs:
            fids = absent[t]
            if not fids:
                continue
            w = wire(root, {t: plan[t]}, defs, functions=fids - panic)
            got = w["fixtures"].get(t) or {}
            rep["pairs"][t]["added"] = got.get("scenes", 0) + got.get("steps", 0)
            if t in w["problems"]:
                rep["problems"][t] = w["problems"][t]
    else:
        for t in pairs:
            rep["pairs"][t]["absent"] = len(absent[t])

    rep["total"] = sum(p["scenes"] + p["steps"] + p["added"] for p in rep["pairs"].values())
    rep["not_changed"] = not_changed(root, plan)
    return rep


def _panic(root: ET.Element) -> Set[str]:
    """The PANIC RESET looks: never given colours (they must stay dark)."""
    from core.doctor.checks import PANIC_RE
    from core.upgrade53 import _panic_family
    out = set(_panic_family(root))
    eng = root.find("Engine")
    for fn in eng.findall("Function") if eng is not None else []:
        if PANIC_RE.search(fn.get("Name") or ""):
            out.add(fn.get("ID", ""))
    return out


def not_changed(root: ET.Element, plan: Dict[str, str]) -> List[str]:
    """What a colour copy does not reach, each with what to do."""
    eng = root.find("Engine")
    if eng is None:
        return []
    involved = set(plan) | set(plan.values())
    groups = {g.get("ID", ""): (g.findtext("Name") or g.get("ID", ""),
                                {h.get("Fixture", "") for h in g.findall("Head")})
              for g in eng.findall("FixtureGroup")}
    pal, mats = 0, set()
    for fn in eng.findall("Function"):
        ftype = fn.get("Type")
        if ftype == "Scene" and fn.find("Palette") is not None:
            heads = set()
            for g in fn.findall("FixtureGroup"):
                heads |= groups.get(g.get("ID", ""), ("", set()))[1]
            if heads & involved:
                pal += 1
        elif ftype == "RGBMatrix":
            gname, heads = groups.get((fn.findtext("FixtureGroup") or "").strip(), ("", set()))
            if heads & involved:
                mats.add(fn.get("Name", ""))
    lines = []
    if pal:
        lines.append(f"{pal} palette look(s) take their colour from a QLC+ palette and were left "
                     "as they are: change the palette, or the fixture group, in QLC+.")
    if mats:
        lines.append(f"RGB matrices ({', '.join(sorted(mats))}) make their own colours on a fixture "
                     "group and were left as they are.")
    return lines


def summary_lines(rep: dict, names: Optional[Dict[str, str]] = None) -> List[str]:
    names = names or {}
    n = lambda i: names.get(i, i)   # noqa: E731
    out = []
    for t, st in rep.get("pairs", {}).items():
        bits = []
        if st["scenes"]:
            bits.append(f"{st['scenes']} scene(s)")
        if st["steps"]:
            bits.append(f"{st['steps']} sequence step(s)")
        if st.get("added"):
            bits.append(f"added to {st['added']} look(s)")
        line = (f"'{n(t)}' takes the colours of '{n(st['source'])}': "
                + (", ".join(bits) if bits else "nothing to change"))
        extra = []
        if st["same"]:
            extra.append(f"{st['same']} already the same")
        if st["dark"]:
            extra.append(f"{st['dark']} left as they are (one of the two is dark)")
        if st.get("absent"):
            extra.append(f"{st['absent']} look(s) set '{n(st['source'])}' but not '{n(t)}'")
        if extra:
            line += " (" + "; ".join(extra) + ")"
        out.append(line)
    for t, why in rep.get("problems", {}).items():
        out.append(f"'{n(t)}' not changed: {why}")
    if rep.get("panic"):
        out.append("The PANIC RESET looks were left as they are.")
    return out + list(rep.get("not_changed", []))


def run(root: ET.Element, plan: Dict[str, str], defs: dict, brightness: str = "keep",
        add: bool = False) -> dict:
    """Copy on a copy of *root* + Doctor gate: ``{"root", "report", "lines",
    "doctor", "blocked"}``. *blocked* when the result has new Doctor errors."""
    from core.doctor import check
    new = copy.deepcopy(root)
    rep = copy_colours(new, plan, defs, brightness, add)
    before, after = check(root, defs), check(new, defs)
    key = lambda f: (f.code, f.location, f.message)   # noqa: E731
    old = {key(f) for f in before.findings}
    fresh = [f for f in after.findings if key(f) not in old and f.severity != "info"]
    doc = {"new_errors": [f"{f.code} {f.location}: {f.message}" for f in fresh if f.severity == "error"],
           "new_warnings": [f"{f.code} {f.location}: {f.message}" for f in fresh if f.severity == "warning"]}
    names = {i: inf["name"] for i, inf in _infos(new).items()}
    return {"root": new, "report": rep, "lines": summary_lines(rep, names), "doctor": doc,
            "blocked": bool(doc["new_errors"])}
