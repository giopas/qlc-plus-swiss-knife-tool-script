"""
core/look_builder.py — Look and Chaser Builder (WORKPLAN Phase 2.3)
===================================================================
Build **looks** (fixture group × palette colour) and **chasers** (a pattern
across a fixture group) into a workspace.  Works on a copy; the result is
written to a new file (``<name>_v<N+1>.qxw``) and checked by the Workspace
Doctor, like every other tool.

Looks
    One Scene per (group, colour).  The colour is written on each fixture by
    capability (``capability_map.encode``): dimmer + RGB(W) mixing, colour
    wheel (nearest slot) or dimmer only — so the same "Amber" works on a PAR
    and on a moving head.  **Every channel is declared**: shutter open,
    pan/tilt centred, gobo/prism/macros at their neutral value (no LTP bleed).

Chasers
    A pattern gives, for each step, which fixtures of the group are *on*
    (in the group's order: left → right, then top → bottom):

    ``all``        all-hit — every fixture together (one colour: on / off);
    ``alternate``  left half / right half (or odd / even);
    ``chase``      one fixture at a time across the group;
    ``pingpong``   across and back (ends not repeated);
    ``buildup``    one more fixture each step;
    ``random``     *n* fixtures per step, from a seeded generator — the same
                   seed always gives the same chaser.

    Colours cycle per step (or per fixture).  *Off* fixtures are dark (their
    dimmer at 0, colour kept, so a fade is a dimmer fade) or a background
    look.  Each distinct step state is one Scene (identical steps share it),
    kept in the function folder of the chaser.  Timing: step time in ms, or
    BPM + note length (1/1 … 1/16); *cut* (no fade) or *fade* (a percentage
    of the step, used for fade in and fade out).

Song presets
    A chaser recipe (pattern, steps, timing, fade, colours …) saved by name —
    built-in ones in ``core/looks/presets.json``, your own in
    ``~/.qlc_swiss_knife/look_presets.json`` (``QSK_LOOK_PRESETS`` overrides).

Preview
    A simulated DMX preview: the values written for each fixture are decoded
    back into the colour they make (``capability_map.decode``) — one strip
    per fixture, one cell per step.

Deterministic: same workspace + same plan → byte-identical output.  New
function IDs follow the highest existing one; an existing PANIC RESET script
gets a ``stopfunction`` for each new look and chaser.
"""

from __future__ import annotations

import copy
import json
import os
import random
import re
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, List, Optional, Tuple

from core import capability_map as cm
from core import qxw_io, script_cmds, vc_ops
from core.quick_start.channel_model import mode_channels

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "looks")
PATTERNS = ("all", "alternate", "chase", "pingpong", "buildup", "random")
PATTERN_LABELS = {"all": "All-hit", "alternate": "Left/right", "chase": "Chase",
                  "pingpong": "Ping-pong", "buildup": "Build-up", "random": "Random"}
NOTES = {"1/1": 4.0, "1/2": 2.0, "1/4": 1.0, "1/8": 0.5, "1/16": 0.25}
DEFAULT_FOLDER = "Look Builder"
PANIC_RE = re.compile(r"panic\s*reset", re.I)
ALL = "all"

RGB = Tuple[float, float, float]


# ─────────────────────────────────────────────────────────────────────────────
# data: palettes and presets
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(name: str) -> dict:
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


def hex_rgb(h: str) -> RGB:
    h = (h or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"not a colour: #{h}")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore


def rgb_hex(c: RGB) -> str:
    return "#" + "".join(f"{max(0, min(255, int(round(x * 255)))):02X}" for x in c)


def palettes() -> Dict[str, dict]:
    """Built-in palettes ``{id: {"label", "colours": [{name, hex, white?}]}}``,
    then your own (``builtin: false``, id ``own:<name>``)."""
    out = {k: {**v, "builtin": True} for k, v in _load_json("palettes.json")["palettes"].items()}
    for p in _user_palettes():
        out["own:" + p["name"]] = {"label": "★ " + p["name"], "colours": p["colours"], "builtin": False}
    return out


def user_palettes_path() -> str:
    return os.environ.get("QSK_LOOK_PALETTES") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "look_palettes.json")


def _user_palettes() -> List[dict]:
    p = user_palettes_path()
    if not os.path.isfile(p):
        return []
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return [x for x in data.get("palettes", []) if isinstance(x, dict) and x.get("name") and x.get("colours")]
    except (OSError, ValueError):
        return []


def save_palette(name: str, colours: list) -> dict:
    """Save (or replace, by name) one of your palettes: ``[{name, hex, white?}]``.
    Built-in palette names are reserved."""
    name = (name or "").strip()
    if not name:
        raise ValueError("A palette needs a name.")
    builtin = _load_json("palettes.json")["palettes"]
    if any(name.lower() in (k.lower(), (v.get("label") or "").lower()) for k, v in builtin.items()):
        raise ValueError(f"'{name}' is a built-in palette — pick another name.")
    cols = []
    for c in colours or []:
        cc = colour(c)
        cols.append({"name": cc["name"], "hex": cc["hex"], **({"white": cc["white"]} if cc["white"] else {})})
    if not cols:
        raise ValueError("A palette needs at least one colour.")
    mine = [p for p in _user_palettes() if p["name"].lower() != name.lower()] + [{"name": name, "colours": cols}]
    path = user_palettes_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"palettes": sorted(mine, key=lambda p: p["name"].lower())}, fh, indent=1)
    return {"name": name, "colours": cols}


def delete_palette(name: str) -> bool:
    mine = _user_palettes()
    keep = [p for p in mine if p["name"].lower() != (name or "").strip().lower()]
    if len(keep) == len(mine):
        return False
    with open(user_palettes_path(), "w", encoding="utf-8") as fh:
        json.dump({"palettes": keep}, fh, indent=1)
    return True


def colour(spec) -> dict:
    """Normalise a colour: a palette colour name ("Amber"), a hex string or
    ``{"name", "hex", "white"}``.  Returns ``{"name", "hex", "white"}``."""
    if isinstance(spec, dict):
        name = (spec.get("name") or "").strip()
        hx = spec.get("hex") or ""
        if not hx and name:
            return colour(name)
        return {"name": name or rgb_hex(hex_rgb(hx)), "hex": rgb_hex(hex_rgb(hx)),
                "white": float(spec.get("white") or 0.0)}
    s = str(spec or "").strip()
    if s.startswith("#") or re.fullmatch(r"[0-9a-fA-F]{6}", s):
        return {"name": rgb_hex(hex_rgb(s)), "hex": rgb_hex(hex_rgb(s)), "white": 0.0}
    for p in palettes().values():
        for c in p["colours"]:
            if c["name"].lower() == s.lower():
                return {"name": c["name"], "hex": c["hex"].upper(), "white": float(c.get("white", 0.0))}
    raise ValueError(f"unknown colour: {s}")


def user_presets_path() -> str:
    return os.environ.get("QSK_LOOK_PRESETS") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "look_presets.json")


def _user_presets() -> List[dict]:
    p = user_presets_path()
    if not os.path.isfile(p):
        return []
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return [x for x in data.get("presets", []) if isinstance(x, dict) and x.get("name")]
    except (OSError, ValueError):
        return []


def presets() -> List[dict]:
    """Built-in presets (``builtin: true``) then your own, by name."""
    out = [{**p, "builtin": True} for p in _load_json("presets.json")["presets"]]
    out += [{**p, "builtin": False} for p in sorted(_user_presets(), key=lambda p: p["name"].lower())]
    return out


POSITIONS = {"Centre": (50, 50), "Left": (30, 50), "Right": (70, 50), "Back": (50, 35), "Front": (50, 65)}


def position(spec) -> Optional[dict]:
    """Normalise a moving-head position: a name ("Left") or ``{"pan", "tilt"}``
    as percent of the range (50 = centre).  None for no position."""
    if spec in (None, "", {}):
        return None
    if isinstance(spec, str):
        key = next((k for k in POSITIONS if k.lower() == spec.strip().lower()), None)
        if key is None:
            raise ValueError(f"unknown position: {spec}")
        pan, tilt = POSITIONS[key]
        return {"name": key, "pan": pan, "tilt": tilt}
    if isinstance(spec, dict):
        if spec.get("name") and spec.get("pan") is None:
            return position(spec["name"])
        try:
            pan, tilt = float(spec.get("pan", 50)), float(spec.get("tilt", 50))
        except (TypeError, ValueError):
            raise ValueError("a position needs pan and tilt as numbers (percent)") from None
        if not (0 <= pan <= 100 and 0 <= tilt <= 100):
            raise ValueError("pan and tilt are percent of the range: 0-100.")
        name = (spec.get("name") or "").strip() or f"Pan {pan:g}% Tilt {tilt:g}%"
        return {"name": name, "pan": pan, "tilt": tilt}
    raise ValueError("bad position")


PRESET_KEYS = ("pattern", "steps", "step_ms", "bpm", "note", "fade", "fade_pct", "colours",
               "colour_mode", "seed", "on_count", "split", "background", "kind", "tempo", "position")


def save_preset(preset: dict) -> dict:
    """Save (or replace, by name) one of your presets.  Built-in names are
    reserved."""
    name = (preset.get("name") or "").strip()
    if not name:
        raise ValueError("A preset needs a name.")
    if any(p["name"].lower() == name.lower() for p in _load_json("presets.json")["presets"]):
        raise ValueError(f"'{name}' is a built-in preset — pick another name.")
    clean = {"name": name}
    clean.update({k: preset[k] for k in PRESET_KEYS if k in preset and preset[k] not in (None, "")})
    chaser_spec(clean)                                     # validate
    mine = [p for p in _user_presets() if p["name"].lower() != name.lower()] + [clean]
    path = user_presets_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"presets": sorted(mine, key=lambda p: p["name"].lower())}, fh, indent=1)
    return clean


def delete_preset(name: str) -> bool:
    mine = _user_presets()
    keep = [p for p in mine if p["name"].lower() != (name or "").strip().lower()]
    if len(keep) == len(mine):
        return False
    with open(user_presets_path(), "w", encoding="utf-8") as fh:
        json.dump({"presets": keep}, fh, indent=1)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# workspace: fixtures and groups
# ─────────────────────────────────────────────────────────────────────────────

def _engine(root):
    return root.find("Engine")


def _stripped(root: ET.Element) -> ET.Element:
    return qxw_io.strip_ns(copy.deepcopy(root)) if root.tag.startswith("{") else root


def _def_key(m: str, mo: str):
    return ((m or "").strip().lower(), (mo or "").strip().lower())


def _fixture_info(root: ET.Element, qxf_defs) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for f in _engine(root).findall("Fixture"):
        def t(tag, d=""):
            return (f.findtext(tag) or d).strip()
        fid = t("ID")
        mfr, model, mode = t("Manufacturer"), t("Model"), t("Mode")
        d = (qxf_defs or {}).get(_def_key(mfr, model))
        ok = cm.can_translate(d, mode)
        generic = mfr.lower() == "generic" and model.lower() in ("generic", "dimmer")
        out[fid] = {"id": fid, "name": t("Name"), "mode": mode, "model": f"{mfr} {model}".strip(),
                    "channels": int(t("Channels", "0") or 0),
                    "def": d if ok else None, "generic": generic and not ok,
                    "kind": cm.kind(d, mode) if ok else ("dimmer" if generic else "unknown")}
    return out


def groups(root: ET.Element, qxf_defs=None) -> List[dict]:
    """``[{id, name, fixtures: [ids in order], supported: n}]`` — "all" first
    (every fixture, in patch order), then the workspace's fixture groups
    (heads ordered by row, then column; a fixture listed once)."""
    r = _stripped(root)
    info = _fixture_info(r, qxf_defs)
    ok = lambda ids: sum(1 for i in ids if info[i]["def"] or info[i]["generic"])  # noqa: E731
    out = [{"id": ALL, "name": "All fixtures", "fixtures": list(info), "supported": ok(list(info))}]
    for g in _engine(r).findall("FixtureGroup"):
        heads = sorted(g.findall("Head"), key=lambda h: (int(h.get("Y", "0") or 0), int(h.get("X", "0") or 0)))
        ids: List[str] = []
        for h in heads:
            fx = h.get("Fixture")
            if fx in info and fx not in ids:
                ids.append(fx)
        out.append({"id": g.get("ID"), "name": (g.findtext("Name") or f"Group {g.get('ID')}").strip(),
                    "fixtures": ids, "supported": ok(ids)})
    return out


def _group(root, qxf_defs, gid) -> dict:
    g = next((x for x in groups(root, qxf_defs) if x["id"] == str(gid)), None)
    if g is None:
        raise ValueError(f"fixture group {gid} not found")
    return g


# ─────────────────────────────────────────────────────────────────────────────
# values
# ─────────────────────────────────────────────────────────────────────────────

def fixture_values(fx: dict, col: Optional[dict], level: float,
                   pos: Optional[dict] = None) -> Tuple[Dict[int, int], List[str]]:
    """Every channel of the fixture for *col* at *level* (0..1).  *col* None
    or level 0 → dark (dimmer 0, colour kept where it has one).  *pos* (see
    :func:`position`) aims fixtures that have pan / tilt; others ignore it."""
    rgb = hex_rgb(col["hex"]) if col else (1.0, 1.0, 1.0)
    white = float(col.get("white") or 0.0) if col else 0.0
    if fx["def"] is not None:
        st = cm.LookState(level=level, colour=rgb, white=white or None,
                          colour_source="mix", shutter="open")
        if pos:
            st.pan, st.tilt = pos["pan"] / 100.0 - 0.5, pos["tilt"] / 100.0 - 0.5
        vals, notes = cm.encode(fx["def"], fx["mode"], st)
        n = max(fx["channels"], len(mode_channels({"mode": fx["mode"]}, fx["def"])))
        for i in range(n):
            vals.setdefault(i, 0)
        if fx["channels"]:
            vals = {c: v for c, v in vals.items() if c < fx["channels"]}
        return vals, notes
    if fx["generic"]:
        v = int(round(max(0.0, min(1.0, level * max(rgb))) * 255))
        return {i: v for i in range(fx["channels"])}, ([] if max(rgb) >= 0.999 or not col
                                                       else ["generic dimmer: intensity only"])
    return {}, ["no fixture definition (.qxf) — skipped"]


def simulate(fx: dict, vals: Dict[int, int]) -> str:
    """The colour a fixture makes with *vals*, as ``#RRGGBB`` (preview)."""
    if not vals:
        return ""
    if fx["def"] is None:
        v = max(vals.values()) / 255.0
        return rgb_hex((v, v, v))
    st = cm.decode(fx["def"], fx["mode"], vals)
    lvl = 1.0 if st.level is None else st.level
    if st.shutter == "closed":
        lvl = 0.0
    c = st.colour if st.colour is not None else (1.0, 1.0, 1.0)
    return rgb_hex(tuple(x * lvl for x in c))


def _pairs_text(vals: Dict[int, int]) -> str:
    return ",".join(f"{c},{vals[c]}" for c in sorted(vals))


# ─────────────────────────────────────────────────────────────────────────────
# chaser patterns and timing
# ─────────────────────────────────────────────────────────────────────────────

def step_time(step_ms=None, bpm=None, note: str = "1/4") -> int:
    """Step time in ms: *step_ms*, or one *note* at *bpm* (a quarter = a beat)."""
    if bpm not in (None, "", 0):
        bpm = float(bpm)
        if not 20 <= bpm <= 400:
            raise ValueError("BPM must be between 20 and 400.")
        if note not in NOTES:
            raise ValueError(f"note length must be one of {', '.join(NOTES)}")
        return int(round(60000.0 / bpm * NOTES[note]))
    ms = int(step_ms or 0)
    if not 20 <= ms <= 600000:
        raise ValueError("Step time must be between 20 ms and 10 minutes.")
    return ms


def pattern_states(pattern: str, n: int, steps: Optional[int] = None, *, seed: int = 0,
                   on_count: int = 1, split: str = "halves", n_colours: int = 1) -> List[List[bool]]:
    """For each step, which of the *n* fixtures are on."""
    if pattern not in PATTERNS:
        raise ValueError(f"unknown pattern: {pattern}")
    if n <= 0:
        return []
    if pattern == "all":
        base = [[True] * n for _ in range(n_colours)] if n_colours > 1 else [[True] * n, [False] * n]
    elif pattern == "alternate":
        if split == "odd_even":
            a = [i % 2 == 0 for i in range(n)]
        else:
            a = [i < (n + 1) // 2 for i in range(n)]
        base = [a, [not x for x in a]] if n > 1 else [[True], [False]]
    elif pattern == "chase":
        base = [[i == k for i in range(n)] for k in range(n)]
    elif pattern == "pingpong":
        order = list(range(n)) + list(range(n - 2, 0, -1))
        base = [[i == k for i in range(n)] for k in order]
    elif pattern == "buildup":
        base = [[i <= k for i in range(n)] for k in range(n)]
    else:  # random
        rng = random.Random(int(seed))
        k = max(1, min(int(on_count or 1), n))
        total = int(steps or 8)
        base, prev = [], None
        for _ in range(total):
            for _try in range(8):
                pick = frozenset(rng.sample(range(n), k))
                if pick != prev or n == k:
                    break
            prev = pick
            base.append([i in pick for i in range(n)])
        return base
    if steps:
        steps = int(steps)
        return [base[i % len(base)] for i in range(steps)]
    return base


def chaser_spec(spec: dict) -> dict:
    """Validate and complete a chaser recipe (returns a new dict)."""
    s = dict(spec)
    s["pattern"] = s.get("pattern") or "chase"
    if s["pattern"] not in PATTERNS:
        raise ValueError(f"unknown pattern: {s['pattern']}")
    s["tempo"] = "beats" if s.get("tempo") == "beats" else "time"
    if s["tempo"] == "beats":
        # QLC+ beats tempo: the chaser follows the BPM of QLC+ itself (VC speed dial / tap),
        # steps are stored in 1/1000 beat; the preview uses the BPM given here (default 120)
        if (s.get("note") or "1/4") not in NOTES:
            raise ValueError(f"note length must be one of {', '.join(NOTES)}")
        s["note"] = s.get("note") or "1/4"
        s["step_ms"] = step_time(None, s.get("bpm") or 120, s["note"])
        s["beat_units"] = int(round(NOTES[s["note"]] * 1000))
    else:
        s["step_ms"] = step_time(s.get("step_ms"), s.get("bpm"), s.get("note") or "1/4")
    s["fade"] = "fade" if s.get("fade") == "fade" else "cut"
    pct = int(s.get("fade_pct") if s.get("fade_pct") not in (None, "") else 100)
    if not 0 <= pct <= 100:
        raise ValueError("Fade must be 0-100 % of the step.")
    s["fade_pct"] = pct
    s["fade_ms"] = int(round(s["step_ms"] * pct / 100.0)) if s["fade"] == "fade" else 0
    if s["tempo"] == "beats":
        s["fade_units"] = int(round(s["beat_units"] * pct / 100.0 / 125.0)) * 125 if s["fade"] == "fade" else 0
    s["position"] = position(s.get("position"))
    cols = s.get("colours") or ["Cold White"]
    s["colours"] = [colour(c) for c in cols]
    s["colour_mode"] = "fixture" if s.get("colour_mode") == "fixture" else "step"
    st = s.get("steps")
    s["steps"] = int(st) if st not in (None, "", 0) else None
    if s["steps"] is not None and not 1 <= s["steps"] <= 256:
        raise ValueError("Steps must be 1-256.")
    s["seed"] = int(s.get("seed") or 0)
    s["on_count"] = int(s.get("on_count") or 1)
    s["split"] = "odd_even" if s.get("split") == "odd_even" else "halves"
    bg = s.get("background")
    if bg:
        s["background"] = {"colour": colour(bg.get("colour") if isinstance(bg, dict) else bg),
                           "level": float((bg.get("level") if isinstance(bg, dict) else None) or 0.3)}
    else:
        s["background"] = None
    s["kind"] = s.get("kind") or "dynamic"
    s["level"] = float(s.get("level") if s.get("level") not in (None, "") else 1.0)
    return s


def chaser_frames(fxs: List[dict], spec: dict) -> Tuple[List[Dict[str, Dict[int, int]]], List[str]]:
    """Per step ``{fixture id: values}`` (supported fixtures only) + notes."""
    s = spec
    usable = [f for f in fxs if f["def"] is not None or f["generic"]]
    states = pattern_states(s["pattern"], len(usable), s["steps"], seed=s["seed"],
                            on_count=s["on_count"], split=s["split"], n_colours=len(s["colours"]))
    notes: List[str] = []
    frames = []
    cols = s["colours"]
    for k, st in enumerate(states):
        fr = {}
        for i, (fx, on) in enumerate(zip(usable, st)):
            col = cols[(i if s["colour_mode"] == "fixture" else k) % len(cols)]
            if on:
                vals, nn = fixture_values(fx, col, s["level"], s.get("position"))
            elif s["background"]:
                vals, nn = fixture_values(fx, s["background"]["colour"], s["background"]["level"],
                                          s.get("position"))
            else:
                vals, nn = fixture_values(fx, col, 0.0, s.get("position"))
            fr[fx["id"]] = vals
            notes += [f"{fx['name']}: {x}" for x in nn]
        frames.append(fr)
    return frames, sorted(set(notes))


# ─────────────────────────────────────────────────────────────────────────────
# XML
# ─────────────────────────────────────────────────────────────────────────────

def _functions(root):
    return _engine(root).findall("Function")


def _insert_function(root, fn: ET.Element) -> None:
    eng = _engine(root)
    kids = list(eng)
    last = max([i for i, c in enumerate(kids) if c.tag in ("Function", "Fixture", "FixtureGroup")] + [-1])
    eng.insert(last + 1, fn)


def _scene(fid: int, name: str, path: str, frame: Dict[str, Dict[int, int]]) -> ET.Element:
    fn = ET.Element("Function", {"ID": str(fid), "Type": "Scene", "Name": name, "Path": path})
    ET.SubElement(fn, "Speed", {"FadeIn": "0", "FadeOut": "0", "Duration": "0"})
    for fx in sorted(frame, key=lambda x: int(x) if x.isdigit() else 0):
        if frame[fx]:
            ET.SubElement(fn, "FixtureVal", {"ID": fx}).text = _pairs_text(frame[fx])
    return fn


def _chaser(fid: int, name: str, path: str, steps: List[int], step_ms: int, fade_ms: int,
            beats: bool = False) -> ET.Element:
    """*step_ms* / *fade_ms* are milliseconds, or — with *beats* — thousandths of
    a beat (QLC+ ``TempoType`` Beats: 1000 = one beat, in 1/8-beat steps)."""
    fn = ET.Element("Function", {"ID": str(fid), "Type": "Chaser", "Name": name, "Path": path})
    if beats:
        ET.SubElement(fn, "TempoType").text = "Beats"
    ET.SubElement(fn, "Speed", {"FadeIn": str(fade_ms), "FadeOut": str(fade_ms), "Duration": str(step_ms)})
    ET.SubElement(fn, "Direction").text = "Forward"
    ET.SubElement(fn, "RunOrder").text = "Loop"
    ET.SubElement(fn, "SpeedModes", {"FadeIn": "Common", "FadeOut": "Common", "Duration": "Common"})
    for i, sid in enumerate(steps):
        ET.SubElement(fn, "Step", {"Number": str(i), "FadeIn": str(fade_ms), "Hold": str(max(0, step_ms - fade_ms)),
                                   "FadeOut": str(fade_ms)}).text = str(sid)
    return fn


def _unique_name(taken: set, name: str) -> str:
    if name.lower() not in taken:
        taken.add(name.lower())
        return name
    k = 2
    while f"{name} ({k})".lower() in taken:
        k += 1
    taken.add(f"{name} ({k})".lower())
    return f"{name} ({k})"


def _name(nom, base: str, group: dict, kind: str, plain_prefix: bool = True) -> str:
    cat = "all" if group["id"] == ALL else f"group:{group['name']}"
    n = nom.name(base, cat, kind) if nom is not None else base
    if n == base and plain_prefix and group["id"] != ALL:
        n = f"{group['name']} · {base}"
    return n


def _panic_add_stops(root, fids: List[str]) -> List[str]:
    """Existing PANIC RESET scripts must also stop the new functions."""
    out = []
    for f in _functions(root):
        if f.get("Type") != "Script" or not PANIC_RE.search(f.get("Name", "")):
            continue
        cmds = f.findall("Command")
        if not any(script_cmds.is_stop(c.text) for c in cmds):
            continue
        at = next((i for i, c in enumerate(list(f)) if c.tag == "Command"
                   and script_cmds.is_start(c.text)), None)
        have = {fid for c in cmds if script_cmds.is_stop(c.text)
                for fid in script_cmds.func_ids(c.text)}
        engine = script_cmds.uses_engine_style(cmds)
        new = [x for x in fids if str(x) not in have]
        for k, x in enumerate(new):
            el = ET.Element("Command")
            el.text = script_cmds.make("stop", x, engine=engine)
            if at is None:
                f.append(el)
            else:
                f.insert(at + k, el)
        if new:
            out.append(f"PANIC RESET script {f.get('ID')} '{f.get('Name')}' also stops the {len(new)} new function(s)")
    return out


# VC: one new page with a SoloFrame per group of looks and one for chasers
BTN_W, BTN_H, GAP, PAD, HEADER = 110, 55, 6, 10, 26


def _qlc_colour(hx: str) -> str:
    r, g, b = (int(x * 255 + 0.5) for x in hex_rgb(hx))
    return str(0xFF000000 | (r << 16) | (g << 8) | b)


def _text_colour(hx: str) -> str:
    r, g, b = hex_rgb(hx)
    return str(0xFF000000 if 0.299 * r + 0.587 * g + 0.114 * b > 0.55 else 0xFFFFFFFF)


def _add_vc(root, caption: str, rows: List[Tuple[str, List[dict]]]) -> List[str]:
    """New page *caption*; each row → a SoloFrame of toggle buttons
    (``{"caption", "fid", "hex"}``)."""
    vc = root.find("VirtualConsole")
    if vc is None:
        vc = ET.SubElement(root, "VirtualConsole")
    pid = vc_ops.new_page(root, caption)["page_id"]
    page = next(p for p in vc if p.get("ID") == pid)
    ws = page.find("WindowState")
    pw = int(ws.get("Width", "1920")) if ws is not None else 1920
    per_row = max(1, (pw - 2 * PAD - 2 * GAP) // (BTN_W + GAP))
    log, y = [], PAD
    for title, btns in rows:
        if not btns:
            continue
        lines = (len(btns) + per_row - 1) // per_row
        cols = min(per_row, len(btns))
        fw = cols * (BTN_W + GAP) + GAP
        fh = HEADER + lines * (BTN_H + GAP) + GAP
        fr = ET.SubElement(page, "SoloFrame", {"Caption": title, "ID": str(vc_ops._next_id(vc))})
        ET.SubElement(fr, "WindowState", {"Visible": "True", "X": str(PAD), "Y": str(y),
                                          "Width": str(fw), "Height": str(fh)})
        ap = ET.SubElement(fr, "Appearance")
        ET.SubElement(ap, "FrameStyle").text = "Sunken"
        ET.SubElement(fr, "ShowHeader").text = "True"
        for k, b in enumerate(btns):
            bx = GAP + (k % per_row) * (BTN_W + GAP)
            by = HEADER + (k // per_row) * (BTN_H + GAP)
            el = ET.SubElement(fr, "Button", {"Caption": b["caption"], "ID": str(vc_ops._next_id(vc)), "Icon": ""})
            ET.SubElement(el, "WindowState", {"Visible": "True", "X": str(bx), "Y": str(by),
                                              "Width": str(BTN_W), "Height": str(BTN_H)})
            a = ET.SubElement(el, "Appearance")
            ET.SubElement(a, "FrameStyle").text = "None"
            if b.get("hex"):
                ET.SubElement(a, "BackgroundColor").text = _qlc_colour(b["hex"])
                ET.SubElement(a, "ForegroundColor").text = _text_colour(b["hex"])
            ET.SubElement(el, "Function", {"ID": str(b["fid"])})
            ET.SubElement(el, "Action").text = "Toggle"
            ET.SubElement(el, "Intensity", {"Adjust": "False"})
        log.append(f"VC: frame '{title}' with {len(btns)} button(s) on page '{caption}'")
        y += fh + GAP * 2
    return log



# ─────────────────────────────────────────────────────────────────────────────
# RGB-matrix patterns for pixel bars
# ─────────────────────────────────────────────────────────────────────────────

# label → (QLC+ script, default colours, duration ms, properties).  Plasma needs a
# preset in QLC+ 5 (its default is "User Defined": mostly black with one colour).
MATRIX_PATTERNS = {
    "Chase":    ("One By One", ["#FF0000"], 300, {}),
    "Even/Odd": ("Even/Odd", ["#0000FF", "#FF8800"], 600, {}),
    "Gradient": ("Gradient", ["#00FFFF", "#9400D3"], 1200, {}),
    "Plasma":   ("Plasma", ["#FF0000"], 500, {"presetIndex": "Rainbow"}),
    "Waves":    ("Waves", ["#0000FF"], 600, {}),
    "Stripes":  ("Stripes", ["#FF0000", "#0000FF"], 800, {"orientation": "Horizontal"}),
}


def _heads(fx: dict) -> int:
    d = fx.get("def")
    if not d:
        return 0
    return len((d.get("mode_heads") or {}).get(fx["mode"]) or [])


def pixel_bars(root: ET.Element, qxf_defs=None) -> List[dict]:
    """Fixtures with several heads (pixels) in their mode — pixel bars, LED
    strips: ``[{id, name, model, heads}]``."""
    info = _fixture_info(_stripped(root), qxf_defs)
    return [{"id": i, "name": f["name"], "model": f["model"], "heads": _heads(f)}
            for i, f in info.items() if _heads(f) >= 2]


def _matrix_group(work: ET.Element, name: str, bars: List[dict], gid: int) -> ET.Element:
    """A fixture group with one row per bar and one column per head."""
    fg = ET.Element("FixtureGroup", {"ID": str(gid)})
    ET.SubElement(fg, "Name").text = name
    width = max(b["heads"] for b in bars)
    ET.SubElement(fg, "Size", {"X": str(width), "Y": str(len(bars))})
    for y, b in enumerate(bars):
        for x in range(b["heads"]):
            ET.SubElement(fg, "Head", {"X": str(x), "Y": str(y), "Fixture": b["id"]}).text = str(x)
    eng = _engine(work)
    last = max([i for i, c in enumerate(list(eng)) if c.tag in ("Fixture", "FixtureGroup")] + [-1])
    eng.insert(last + 1, fg)
    return fg


def _rgbmatrix(fid: int, name: str, path: str, gid: int, script: str, colours: List[str],
               duration: int, props: Dict[str, str]) -> ET.Element:
    fn = ET.Element("Function", {"ID": str(fid), "Type": "RGBMatrix", "Name": name, "Path": path})
    ET.SubElement(fn, "Speed", {"FadeIn": "0", "FadeOut": "0", "Duration": str(duration)})
    ET.SubElement(fn, "Direction").text = "Forward"
    ET.SubElement(fn, "RunOrder").text = "Loop"
    ET.SubElement(fn, "Algorithm", {"Type": "Script"}).text = script
    ET.SubElement(fn, "DimmerControl").text = "1"
    for k, c in enumerate(colours[:5]):
        ET.SubElement(fn, "Color", {"Index": str(k)}).text = _qlc_colour(c)
    ET.SubElement(fn, "ControlMode").text = "RGB"
    ET.SubElement(fn, "FixtureGroup").text = str(gid)
    for k, v in props.items():
        ET.SubElement(fn, "Property", {"Name": k, "Value": v})
    return fn

# ─────────────────────────────────────────────────────────────────────────────
# build
# ─────────────────────────────────────────────────────────────────────────────

def build(root: ET.Element, qxf_defs, plan: dict, nomenclature=None) -> dict:
    """Add the planned looks and chasers to a copy of *root*.

    *plan*::

        {"looks":   [{"group": gid, "colours": [...], "level": 1.0}],
         "chasers": [{"group": gid, "name": "...", **chaser recipe}],
         "folder":  "Look Builder",            # function folder (Path)
         "vc_page": "Looks" | None}            # buttons on a new page

    Returns ``{"root", "log", "notes", "created": {...}, "functions": [...]}``.
    """
    work = qxw_io.strip_ns(copy.deepcopy(root))
    info = _fixture_info(work, qxf_defs)
    all_groups = {g["id"]: g for g in groups(work, qxf_defs)}
    folder = (plan.get("folder") or DEFAULT_FOLDER).strip().strip("/") or DEFAULT_FOLDER
    next_id = max([int(f.get("ID")) for f in _functions(work) if (f.get("ID") or "").isdigit()] + [-1]) + 1
    taken = {(f.get("Name") or "").lower() for f in _functions(work)}
    log: List[str] = []
    notes: List[str] = []
    created = {"looks": 0, "chasers": 0, "step_scenes": 0, "buttons": 0}
    top: List[str] = []
    vc_rows: List[Tuple[str, List[dict]]] = []
    summary: List[dict] = []
    pending: List[ET.Element] = []

    for lk in plan.get("looks") or []:
        g = all_groups.get(str(lk.get("group")))
        if g is None:
            raise ValueError(f"fixture group {lk.get('group')} not found")
        fxs = [info[i] for i in g["fixtures"]]
        level = float(lk.get("level") if lk.get("level") not in (None, "") else 1.0)
        pos = position(lk.get("position"))
        row = []
        for cspec in lk.get("colours") or []:
            col = colour(cspec)
            frame = {}
            for fx in fxs:
                vals, nn = fixture_values(fx, col, level, pos)
                if vals:
                    frame[fx["id"]] = vals
                notes.extend(f"{fx['name']}: {x}" for x in nn)
            if not frame:
                notes.append(f"{g['name']} · {col['name']}: no fixture with a definition — look not created")
                continue
            base = f"{col['name']} @ {pos['name']}" if pos else col["name"]
            name = _unique_name(taken, _name(nomenclature, base, g, "static"))
            pending.append(_scene(next_id, name, f"{folder}/Looks", frame))
            log.append(f"look {next_id} '{name}' — {len(frame)} fixture(s), {col['hex']}"
                       + (f", position {pos['name']} (pan {pos['pan']:g}%, tilt {pos['tilt']:g}%)" if pos else ""))
            summary.append({"id": str(next_id), "type": "Scene", "name": name, "hex": col["hex"]})
            row.append({"caption": base, "fid": next_id, "hex": col["hex"]})
            top.append(str(next_id))
            created["looks"] += 1
            next_id += 1
        vc_rows.append((f"Looks · {g['name']}", row))

    ch_row = []
    for spec in plan.get("chasers") or []:
        g = all_groups.get(str(spec.get("group")))
        if g is None:
            raise ValueError(f"fixture group {spec.get('group')} not found")
        s = chaser_spec(spec)
        fxs = [info[i] for i in g["fixtures"]]
        frames, nn = chaser_frames(fxs, s)
        notes.extend(nn)
        if not frames or not any(frames[0].values()):
            notes.append(f"chaser on {g['name']}: no fixture with a definition — not created")
            continue
        base = (spec.get("name") or "").strip() or \
            f"{PATTERN_LABELS[s['pattern']]} {'/'.join(c['name'] for c in s['colours'])}"
        name = _unique_name(taken, _name(nomenclature, base, g, s["kind"]))
        cid = next_id
        next_id += 1
        path = f"{folder}/Chasers/{name.replace('/', '-')}"
        seen: Dict[str, int] = {}
        step_ids = []
        for fr in frames:
            key = json.dumps({k: sorted(v.items()) for k, v in sorted(fr.items())})
            if key not in seen:
                sname = _unique_name(taken, f"{name} · step {len(seen) + 1}")
                pending.append(_scene(next_id, sname, path, fr))
                seen[key] = next_id
                created["step_scenes"] += 1
                next_id += 1
            step_ids.append(seen[key])
        if s["tempo"] == "beats":
            pending.append(_chaser(cid, name, path, step_ids, s["beat_units"], s["fade_units"], beats=True))
            timing = f"{s['note']} of a beat — follows the QLC+ tempo"
            fade_txt = f"fade {s['fade_units'] / 1000:g} beat" if s["fade_units"] else "cut"
        else:
            pending.append(_chaser(cid, name, path, step_ids, s["step_ms"], s["fade_ms"]))
            timing = f"{s['step_ms']} ms" + (f" ({s['bpm']} BPM, {s.get('note') or '1/4'})" if s.get("bpm") else "")
            fade_txt = f"fade {s['fade_ms']} ms" if s["fade_ms"] else "cut"
        log.append(f"chaser {cid} '{name}' — {PATTERN_LABELS[s['pattern']]}, {len(step_ids)} step(s), "
                   f"{len(seen)} scene(s), {timing}, "
                   + fade_txt + (f", position {s['position']['name']}" if s.get("position") else ""))
        summary.append({"id": str(cid), "type": "Chaser", "name": name, "hex": s["colours"][0]["hex"]})
        ch_row.append({"caption": base, "fid": cid, "hex": s["colours"][0]["hex"]})
        top.append(str(cid))
        created["chasers"] += 1
    vc_rows.append(("Chasers", ch_row))

    mx_row = []
    mx_groups = []
    for spec in plan.get("matrices") or []:
        ids = [str(i) for i in (spec.get("fixtures") or [])]
        bars = [b for b in pixel_bars(work, qxf_defs) if b["id"] in ids]
        if not bars:
            raise ValueError("matrix: pick at least one pixel bar (a fixture with several heads)")
        label = spec.get("pattern") or "Chase"
        if label not in MATRIX_PATTERNS:
            raise ValueError(f"unknown matrix pattern: {label}")
        script, dcols, dur, props = MATRIX_PATTERNS[label]
        cols = [colour(c)["hex"] for c in (spec.get("colours") or dcols)] or dcols
        duration = int(spec.get("duration") or dur)
        if not 20 <= duration <= 600000:
            raise ValueError("matrix speed must be between 20 ms and 10 minutes")
        bname = ", ".join(b["name"] for b in bars) if len(bars) <= 2 else f"{len(bars)} bars"
        gname = _unique_name({(g.findtext("Name") or "").lower() for g in _engine(work).findall("FixtureGroup")},
                             f"Matrix · {bname}")
        gid = max([int(g.get("ID")) for g in _engine(work).findall("FixtureGroup") if (g.get("ID") or "").isdigit()] + [-1]) + 1
        _matrix_group(work, gname, bars, gid)
        mx_groups.append(gname)
        base = (spec.get("name") or "").strip() or f"{bname} · {label}"
        name = _unique_name(taken, _name(nomenclature, base, {"id": ALL, "name": ""}, "matrix"))
        path = f"{folder}/Matrices"
        mid = next_id
        next_id += 1
        pending.append(_rgbmatrix(mid, f"{name} (matrix)", path, gid, script, cols, duration, props))
        # RGB-mode matrices ignore DimmerControl: bars with a master dimmer need it opened first
        dim_vals = {}
        for b in bars:
            fx = _fixture_info(work, qxf_defs)[b["id"]]
            if any(((cd.get("group") or "") == "Intensity" and "dimmer" in n.lower())
                   for n, cd in (fx["def"].get("channel_defs") or {}).items()):
                st = cm.LookState(level=1.0, colour=None, colour_source="none", shutter="open")
                vals, _n = cm.encode(fx["def"], fx["mode"], st)
                n_ch = fx["channels"] or len(vals)
                dim_vals[b["id"]] = {c: v for c, v in vals.items() if c < n_ch}
        target = mid
        if dim_vals:
            sid = next_id
            next_id += 1
            pending.append(_scene(sid, f"{name}: dimmers", path, dim_vals))
            target = next_id
            next_id += 1
            coll = ET.Element("Function", {"ID": str(target), "Type": "Collection", "Name": name, "Path": path})
            ET.SubElement(coll, "Speed", {"FadeIn": "0", "FadeOut": "0", "Duration": "0"})
            for n_, f_ in enumerate((sid, mid)):
                ET.SubElement(coll, "Step", {"Number": str(n_)}).text = str(f_)
            pending.append(coll)
        log.append(f"matrix {target} '{name}' — {label} ({script}) on {bname}: "
                   f"{max(b['heads'] for b in bars)} × {len(bars)} pixels, {duration} ms"
                   + (", dimmers opened by the button" if dim_vals else ""))
        summary.append({"id": str(target), "type": "Collection" if dim_vals else "RGBMatrix",
                        "name": name, "hex": cols[0]})
        mx_row.append({"caption": base, "fid": target, "hex": cols[0]})
        top.append(str(target))
        created["matrices"] = created.get("matrices", 0) + 1
    if mx_row:
        vc_rows.append(("Matrices", mx_row))

    # new functions go in ID order (a chaser gets its ID before its step scenes)
    for fn in sorted(pending, key=lambda f: int(f.get("ID"))):
        _insert_function(work, fn)
    log += _panic_add_stops(work, top)
    if plan.get("vc_page") and top:
        vlog = _add_vc(work, str(plan["vc_page"]).strip() or "Looks", vc_rows)
        created["buttons"] = sum(len(r[1]) for r in vc_rows)
        log += vlog
    return {"root": work, "log": log, "notes": sorted(set(notes)), "created": created,
            "functions": summary}


# ─────────────────────────────────────────────────────────────────────────────
# preview, Doctor gate, files
# ─────────────────────────────────────────────────────────────────────────────

def preview_chaser(root: ET.Element, qxf_defs, spec: dict) -> dict:
    """Simulated DMX preview of one chaser: ``{"step_ms", "fade_ms",
    "fixtures": [{id, name, cells: ["#RRGGBB", …]}], "notes"}``."""
    r = _stripped(root)
    g = _group(r, qxf_defs, spec.get("group", ALL))
    s = chaser_spec(spec)
    info = _fixture_info(r, qxf_defs)
    fxs = [info[i] for i in g["fixtures"]]
    frames, notes = chaser_frames(fxs, s)
    rows = []
    for fx in fxs:
        if fx["def"] is None and not fx["generic"]:
            continue
        rows.append({"id": fx["id"], "name": fx["name"],
                     "cells": [simulate(fx, fr.get(fx["id"], {})) for fr in frames]})
    return {"step_ms": s["step_ms"], "fade_ms": s["fade_ms"], "steps": len(frames),
            "fixtures": rows, "notes": notes,
            "skipped": [fx["name"] for fx in fxs if fx["def"] is None and not fx["generic"]]}


def preview_look(root: ET.Element, qxf_defs, group, colours, level: float = 1.0, pos=None) -> dict:
    r = _stripped(root)
    g = _group(r, qxf_defs, group)
    info = _fixture_info(r, qxf_defs)
    out = []
    for c in colours:
        col = colour(c)
        cells = []
        for i in g["fixtures"]:
            vals, _ = fixture_values(info[i], col, level, position(pos))
            cells.append(simulate(info[i], vals))
        out.append({"colour": col, "cells": cells})
    return {"fixtures": [info[i]["name"] for i in g["fixtures"]], "looks": out}


def format_report(res: dict, source: str, output: str, doctor=None) -> str:
    c = res["created"]
    lines = ["LOOK AND CHASER BUILDER REPORT", "=" * 30,
             f"Source: {source}", f"Output: {output}", "",
             f"Created: {c['looks']} look(s), {c['chasers']} chaser(s) with {c['step_scenes']} step scene(s), "
             + (f"{c['matrices']} matrix pattern(s), " if c.get("matrices") else "")
             + f"{c['buttons']} VC button(s)", "", "CHANGES", "-------"]
    lines += [f"  {x}" for x in res["log"]] or ["  (none)"]
    if res["notes"]:
        lines += ["", "NOTES", "-----"] + [f"  {x}" for x in res["notes"]]
    d = res.get("doctor")
    if d:
        lines += ["", "WORKSPACE DOCTOR", "----------------",
                  f"  Result: {d['total_errors']} error(s), {d['total_warnings']} warning(s)"]
        for k, t in (("new_errors", "NEW ERROR"), ("new_warnings", "new warning")):
            lines += [f"  {t}: {x}" for x in d[k]]
    return "\n".join(lines) + "\n"


def report_path(qxw_path: str) -> str:
    return os.path.splitext(qxw_path)[0] + "_looks_report.txt"


def run(root: ET.Element, qxf_defs, plan: dict, nomenclature=None, source: str = "",
        output: str = "") -> dict:
    """Build + Doctor gate (only findings the original didn't have count;
    new errors block the export)."""
    from core.doctor import check
    res = build(root, qxf_defs, plan, nomenclature)
    before = check(_stripped(root), qxf_defs)
    after = check(res["root"], qxf_defs)

    def key(f):
        return (f.code, f.location, f.message)
    old = {key(f) for f in before.findings}
    new = [f for f in after.findings if key(f) not in old and f.severity != "info"]
    res["doctor"] = {
        "new_errors": [f"{f.code} {f.location}: {f.message}" for f in new if f.severity == "error"],
        "new_warnings": [f"{f.code} {f.location}: {f.message}" for f in new if f.severity == "warning"],
        "total_errors": len(after.errors), "total_warnings": len(after.warnings),
    }
    res["blocked"] = bool(res["doctor"]["new_errors"])
    res["report"] = format_report(res, source, output, after)
    return res


def build_file(path: str, qxf_defs, plan: dict, nomenclature=None,
               out_path: Optional[str] = None) -> dict:
    """Build into a new file (default ``<name>_v<N+1>.qxw``) with
    ``<new name>_looks_report.txt`` next to it.  Never overwrites *path*."""
    tree = qxw_io.load_qxw(path)
    out = out_path or qxw_io.next_version_path(path)
    res = run(tree.getroot(), qxf_defs, plan, nomenclature, os.path.basename(path), os.path.basename(out))
    if res["blocked"]:
        return {**res, "output": None, "report_path": None}
    ET.indent(res["root"], space=" ")
    qxw_io.write_qxw(res["root"], out, protect=[path])
    rp = report_path(out)
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write(res["report"])
    return {**res, "output": out, "report_path": rp}
