"""
Upgrade a QLC+ 5 show to what QLC+ 5.3 offers (3.2.0), up to the latest
QLC+ Swiss Knife knows: 5.3.1 (3.13.0, ``core/qlc531.py``).

Shows made with QLC+ 5.0 to 5.2, by hand or by Swiss Knife, open in QLC+ 5.3
as they are: the source of 5.2.2 and 5.3.0 shows no change in how an older
workspace loads, apart from the script syntax the Doctor already reads.  What
an older show lacks is what the 5.3 Show Wizard gives a new one.  Each step
below adds one of those things; nothing in the show is rewritten unless a
step says so, and every step is deterministic.

=========  ===========================================================  ========
Step       What it adds                                                 QLC+
=========  ===========================================================  ========
folders    a folder (``Path``) for every function that has none, by     5.2.2
           what it does: Looks/<group>, Chasers/<chaser> (with its
           steps), Effects/<group>, Collections, Setlist, Safety …
palettes   Dimmer Full / Half / Off, the Shutter palettes the rig can   5.2.2
           take, a Color palette for each colour the looks use; names
           and values as the Show Wizard writes them
allgroup   an *All Fixtures* group when no group holds the whole rig    5.2.2
grids      group grids from the stage, front row first (rewrites the   5.2.2
           grids, so not ticked by default)
positions  ``Position3D`` palettes: stage centre, the audience, each    5.3
           musician model placed on the stage
frame      a *Groups* page: one page per group in a multipage frame,   5.2.2
           with an intensity slider, the group's looks in a solo
           frame, its effects, and an XY pad for moving heads
hide       page-switch fixtures hidden in 2D and 3D                     5.2.2
lock       placed fixtures locked in 2D and 3D                          5.3
dimmerpal  looks whose lit lights all share one dimmer level take it  5.3
           from a Dimmer palette (*Dimmer Full*, *Dimmer 80%* …); dark
           lights keep their 0, the rest of the look is unchanged; only
           when the look plays exactly the same (3.21.0, not ticked by
           default)
crossuni…  an old cross-universe flag (``True``) written as ``Fill``    5.3.1
           where QLC+ 5.3.1 would patch the fixture to other
           addresses (Doctor D027); ``Fill`` keeps the 5.3.0
           addresses and every QLC+ 5 reads it
=========  ===========================================================  ========

The target ``"5.3"`` means the latest QLC+ 5.3 (5.3.1 today); ``"5.3.1"`` and
``"5.3.0"`` are taken as the same target, since the steps are the same.

The XY pads list their fixtures one by one and set ``FloorControl``: QLC+ 5.3
aims them at a point on the stage floor, QLC+ 5.2.2 ignores the flag and
uses them as plain pan/tilt pads.  A pad that lists only a group would do
nothing in 5.2.2.

Swiss Knife's own rule stays: no step generates a scene that sets only part
of a fixture (principle 5).  Positions are palettes and XY pads, not
position-only scenes.
"""

from __future__ import annotations

import copy
import os
import re
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, Iterable, List, Optional, Tuple

from core import palettes as P
from core import qlc531, qxw_io
from core import wizard_repair as W

STEPS = ("folders", "palettes", "allgroup", "grids", "positions", "frame", "hide", "lock",
         "dimmerpal", "crossuniverse")
DEFAULT_STEPS = ("folders", "palettes", "allgroup", "positions", "hide", "crossuniverse")
ONLY_53 = ("positions", "lock", "dimmerpal")
TARGETS = ("5.3", "5.2.2")
LATEST = qlc531.LATEST_TEXT


def target_of(value) -> str:
    """``"5.3"`` for any QLC+ 5.3 release (``"5.3.1"``, ``"5.3.0"``), ``"5.2.2"``
    as it is; anything else is the latest."""
    v = str(value or "").strip()
    if v == "5.2.2":
        return "5.2.2"
    return "5.3"


def newer_than_known(version_text: str) -> bool:
    """The file was saved by a QLC+ newer than the one Swiss Knife knows."""
    nums = tuple(int(n) for n in re.findall(r"\d+", version_text or "")[:3])
    return bool(nums) and nums > qlc531.LATEST

# Folder names (English, like the Show Wizard's own)
F_SAFETY = "Safety"
F_SETLIST = "Setlist"
F_LOOKS = "Looks"
F_CHASERS = "Chasers"
F_EFFECTS = "Effects"
F_COLLECTIONS = "Collections"
F_SCRIPTS = "Scripts"
F_SHOWS = "Shows"
F_MEDIA = "Media"

ALL_GROUP = "All Fixtures"
FRAME_CAPTION = "Groups"

# The Show Wizard's palettes (stagewizard_functions.cpp): name, type, value
WIZARD_DIMMERS = (("Dimmer Full", "255"), ("Dimmer Half", "128"), ("Dimmer Off", "0"))
WIZARD_SHUTTERS = (("Shutter Open", "7,100"), ("Shutter Closed", "8,100"),
                   ("Strobe Slow", "9,20"), ("Strobe Fast", "9,85"))
# colour word (core.scene_words) → palette name and value; the first eleven
# are the wizard's, in its order, the others cover the words it has no
# palette for
COLOURS = (
    ("white", "White", "#ffffff000000"), ("red", "Red", "#ff0000000000"),
    ("green", "Green", "#00ff00000000"), ("blue", "Blue", "#0000ff000000"),
    ("cyan", "Cyan", "#00ffff000000"), ("magenta", "Magenta", "#ff00ff000000"),
    ("yellow", "Yellow", "#ffff00000000"), ("amber", "Amber", "#ffbf00000000"),
    ("lime", "Lime", "#bfff00000000"), ("orange", "Orange", "#ff8000000000"),
    ("pink", "Pink", "#ff557f000000"),
    ("warm white", "Warm White", "#ffc98a000000"), ("cool white", "Cool White", "#c8dcff000000"),
    ("teal", "Teal", "#00ff80000000"), ("violet", "Violet", "#8000ff000000"),
    ("purple", "Purple", "#bf00ff000000"),
)

# Musician models: a mesh whose name or file says what it is
PERSON_RE = re.compile(r"^(sing|vocal|voice|drum|bass|guitar|key|synth|piano|dj|musician|player|"
                       r"perform|sax|violin|cello|brass|trumpet|percussion|person|actor|dancer|"
                       r"presenter|host|mc)", re.I)
PRIMITIVE_RE = re.compile(r"^(cube|sphere|cylinder|cone|plane|torus)\b", re.I)
JUNK_WORDS = {"meshy", "ai", "char", "character", "model", "obj", "generic", "mesh", "final", "v1", "v2"}
AUDIENCE_DEPTH = 1.2              # the wizard's "Audience" point: 1.2 × stage depth



# ═════════════════════════════════════════════════════════════════════════════
# Reading the show
# ═════════════════════════════════════════════════════════════════════════════

def _eng(root):
    return W._eng(root)


def _fns(root) -> List[ET.Element]:
    return _eng(root).findall("Function")


_num = W._num


def _clean(name: str) -> str:
    """A function or group name usable as one folder level."""
    return re.sub(r"\s+", " ", (name or "").replace("/", "-").replace("\\", "-")).strip() or "Unnamed"


def _defs_dict(defs) -> dict:
    from core.doctor.checks import _normalise_defs
    return _normalise_defs(defs)


def _infra(root) -> set:
    return set(P.infrastructure_fixtures(root))


def _lights(root) -> List[str]:
    """Fixture IDs that are lights (not page-switch dimmers), in file order."""
    infra = _infra(root)
    return [f.findtext("ID") for f in _eng(root).findall("Fixture")
            if f.findtext("ID") is not None and f.findtext("ID") not in infra]


def _groups(root) -> List[ET.Element]:
    """Fixture groups of lights only (a group with a page-switch fixture is
    the wizard's infrastructure), in file order."""
    infra = _infra(root)
    return [g for g in _eng(root).findall("FixtureGroup")
            if P.group_fixture_ids(g) and not (set(P.group_fixture_ids(g)) & infra)]


def _cuelist_chasers(root) -> set:
    vc = root.find("VirtualConsole")
    out = set()
    for cl in (vc.iter("CueList") if vc is not None else []):
        t = (cl.findtext("Chaser") or "").strip()
        if t:
            out.add(t)
    return out


def _panic_family(root) -> set:
    """The PANIC RESET script(s) and the functions they start."""
    from core import script_cmds
    from core.doctor.checks import PANIC_RE
    out = set()
    for f in _fns(root):
        if f.get("Type") == "Script" and PANIC_RE.search(f.get("Name") or ""):
            out.add(f.get("ID"))
            for c in f.findall("Command"):
                out |= {fid for verb, fid in script_cmds.func_refs(c.text) if verb == "start"}
    return out


def _scene_fixture_sets(root, R: "P.Resolver") -> Dict[str, frozenset]:
    infra = _infra(root)
    return {f.get("ID"): frozenset(x for x in R.scene_fixtures(f) if x not in infra)
            for f in _fns(root) if f.get("Type") == "Scene"}


def _function_fixtures(fn: ET.Element, fns: Dict[str, ET.Element], sets: Dict[str, frozenset],
                       groups: Dict[str, ET.Element], seen=None) -> frozenset:
    """Fixtures a function acts on: a scene's own, a chaser's or collection's
    steps, an RGB matrix's group, an EFX's fixtures."""
    seen = set() if seen is None else seen
    fid = fn.get("ID")
    if fid in seen:
        return frozenset()
    seen.add(fid)
    t = fn.get("Type")
    if t == "Scene":
        return sets.get(fid, frozenset())
    if t == "RGBMatrix":
        g = groups.get((fn.findtext("FixtureGroup") or "").strip())
        return frozenset(P.group_fixture_ids(g)) if g is not None else frozenset()
    if t == "EFX":
        return frozenset(x.findtext("ID") for x in fn.findall("Fixture") if x.findtext("ID"))
    if t in ("Chaser", "Collection", "Sequence"):
        out = set()
        if t == "Sequence":                 # steps hold values for its bound scene
            kids = [fn.get("BoundScene")] if fn.get("BoundScene") else []
        else:
            kids = [(s.text or "").strip() for s in fn.findall("Step")]
        for k in kids:
            if k in fns:
                out |= _function_fixtures(fns[k], fns, sets, groups, seen)
        return frozenset(out)
    return frozenset()


class _Show:
    """What the steps need to know about a workspace, read once."""

    def __init__(self, root, defs=None):
        from core.doctor.checks import _Workspace
        self.root = root
        self.defs = _defs_dict(defs)
        self.R = P.Resolver(root, self.defs)
        ws = _Workspace(root, self.defs)
        self.ws = ws
        self.parents = ws.parents
        self.vc_refs = ws.vc_refs
        self.fns = {f.get("ID"): f for f in _fns(root)}
        self.groups = _groups(root)
        self.groups_by_id = {g.get("ID"): g for g in _eng(root).findall("FixtureGroup")}
        self.lights = _lights(root)
        self.sets = _scene_fixture_sets(root, self.R)
        self.cuelists = _cuelist_chasers(root)
        self.panic = _panic_family(root)

    def fixtures_of(self, fn: ET.Element) -> frozenset:
        return _function_fixtures(fn, self.fns, self.sets, self.groups_by_id)

    def group_for(self, fx: frozenset) -> Optional[ET.Element]:
        """The (first) group whose fixtures are exactly *fx*."""
        if not fx:
            return None
        for g in self.groups:
            if frozenset(P.group_fixture_ids(g)) == fx:
                return g
        return None

    def step_parents(self, fid: str) -> List[str]:
        """Chasers that use *fid* as a step (and nothing else uses it)."""
        if self.vc_refs.get(fid):
            return []
        ps = self.parents.get(fid) or set()
        out = []
        for p in sorted(ps, key=_num):
            pf = self.fns.get(p)
            if pf is None or pf.get("Type") not in ("Chaser", "Sequence"):
                return []
            out.append(p)
        return out

    def movers(self) -> List[str]:
        """Lights with pan and tilt (needs their definitions)."""
        out = []
        for f in self.lights:
            m = self.R.models.get(f)
            if m is not None and any(c.group == "Pan" for c in m.channels) \
                    and any(c.group == "Tilt" for c in m.channels):
                out.append(f)
        return out

    def known(self) -> int:
        return sum(1 for f in self.lights if self.R.models.get(f) is not None)


# ═════════════════════════════════════════════════════════════════════════════
# 1. folders
# ═════════════════════════════════════════════════════════════════════════════

def folder_plan(show: _Show) -> Dict[str, str]:
    """``{function id: path}`` for every function with no ``Path`` yet."""
    memo: Dict[str, str] = {}

    def home(fid: str, depth: int = 0) -> str:
        if fid in memo:
            return memo[fid]
        fn = show.fns[fid]
        if fn.get("Path"):
            memo[fid] = fn.get("Path")
            return memo[fid]
        t = fn.get("Type")
        path: str
        if fid in show.panic:
            path = F_SAFETY
        elif fid in show.cuelists:
            path = F_SETLIST
        else:
            sp = show.step_parents(fid)
            if len(sp) == 1 and depth < 8 and sp[0] != fid:
                parent = show.fns[sp[0]]
                path = f"{home(sp[0], depth + 1)}/{_clean(parent.get('Name'))}"
            elif t == "Scene":
                g = show.group_for(show.sets.get(fid, frozenset()))
                path = f"{F_LOOKS}/{_clean(g.findtext('Name'))}" if g is not None else F_LOOKS
            elif t == "RGBMatrix":
                g = show.groups_by_id.get((fn.findtext("FixtureGroup") or "").strip())
                path = f"{F_EFFECTS}/{_clean(g.findtext('Name'))}" if g is not None else F_EFFECTS
            elif t == "EFX":
                path = F_EFFECTS
            elif t in ("Chaser", "Sequence"):
                path = F_CHASERS
            elif t == "Collection":
                path = F_COLLECTIONS
            elif t == "Script":
                path = F_SCRIPTS
            elif t == "Show":
                path = F_SHOWS
            elif t in ("Audio", "Video"):
                path = F_MEDIA
            else:
                path = _clean(t or "Other")
        memo[fid] = path
        return path

    out = {}
    for fid, fn in show.fns.items():
        if fn.get("Path"):
            continue
        out[fid] = home(fid)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# 2. palettes
# ═════════════════════════════════════════════════════════════════════════════

def _colour_words(show: _Show) -> List[str]:
    """Colour words of the looks (each lit fixture of each scene), in order of
    first use."""
    from core import look_builder, scene_words
    info = look_builder._fixture_info(show.root, show.defs)
    seen: List[str] = []
    for fid, fn in show.fns.items():
        if fn.get("Type") != "Scene" or fid in show.panic:
            continue
        for _n, w in scene_words.fixture_words(fn, info):
            w = w.replace(" strobe", "")
            if w.startswith("dim "):
                w = w[4:]
            if w != "off" and w not in seen:
                seen.append(w)
    return seen


def palette_plan(show: _Show) -> List[Tuple[str, str, str]]:
    """``[(name, type, value)]`` to add: the wizard's Dimmer palettes, the
    Shutter palettes the rig can take, a Color palette per colour the looks
    use.  Only palettes that do something on at least one light, and none
    the show already has (same type and value, or same name)."""
    have = P.read_palettes(show.root)
    have_tv = {(p.type, p.value.lower()) for p in have.values()}
    have_n = {(p.type, p.name.lower()) for p in have.values()}
    models = [show.R.models[f] for f in show.lights if show.R.models.get(f) is not None]
    out: List[Tuple[str, str, str]] = []

    def works(ptype: str, value: str) -> bool:
        pal = P.Palette("x", ptype, "", value)
        return bool(P.palette_values(pal, models, show.R.stage))

    def add(name, ptype, value):
        if (ptype, value.lower()) in have_tv or (ptype, name.lower()) in have_n:
            return
        if works(ptype, value):
            out.append((name, ptype, value))

    for name, val in WIZARD_DIMMERS:
        add(name, "Dimmer", val)
    for name, val in WIZARD_SHUTTERS:
        add(name, "Shutter", val)
    used = set(_colour_words(show))
    for word, name, val in COLOURS:
        if word in used:
            add(name, "Color", val)
    return out


def _insert_engine(root, el: ET.Element, after: Tuple[str, ...]) -> None:
    eng = _eng(root)
    kids = list(eng)
    last = max([i for i, c in enumerate(kids) if c.tag in after] + [-1])
    if last < 0:
        first_fn = next((i for i, c in enumerate(kids) if c.tag == "Function"), len(kids))
        last = first_fn - 1
    eng.insert(last + 1, el)


def _next_palette_id(root) -> int:
    ids = [int(p.get("ID")) for p in _eng(root).findall("Palette") if (p.get("ID") or "").isdigit()]
    return max(ids + [-1]) + 1


def _add_palette(root, name: str, ptype: str, value: str) -> str:
    pid = str(_next_palette_id(root))
    _insert_engine(root, ET.Element("Palette", {"ID": pid, "Type": ptype, "Name": name, "Value": value}),
                   ("Fixture", "FixtureGroup", "Palette"))
    return pid


# ═════════════════════════════════════════════════════════════════════════════
# 3. the All Fixtures group, 4. grids
# ═════════════════════════════════════════════════════════════════════════════

def _positions(root) -> Dict[str, Tuple[float, float, float]]:
    st = P.read_stage(root)
    return {f: (v[0], v[1], v[2]) for f, v in st.items.items()}


def needs_all_group(show: _Show) -> bool:
    lights = frozenset(show.lights)
    return bool(lights) and not any(frozenset(P.group_fixture_ids(g)) == lights for g in show.groups)


def _heads(show: _Show, fid: str) -> int:
    m = show.R.models.get(fid)
    return max(1, len(m._declared_heads)) if m is not None else 1


def _group_rows(show: _Show, ids: List[str]) -> List[List[str]]:
    pos = _positions(show.root)
    if any(i in pos for i in ids):
        return W.lines_of(ids, pos)
    return [list(ids)]


def _group_el(gid: str, name: str, show: _Show, rows: List[List[str]]) -> ET.Element:
    g = ET.Element("FixtureGroup", {"ID": gid})
    ET.SubElement(g, "Name").text = name
    width = max(sum(_heads(show, f) for f in r) for r in rows)
    ET.SubElement(g, "Size", {"X": str(width), "Y": str(len(rows))})
    for y, r in enumerate(rows):
        x = (width - sum(_heads(show, f) for f in r)) // 2
        for f in r:
            for h in range(_heads(show, f)):
                ET.SubElement(g, "Head", {"X": str(x), "Y": str(y), "Fixture": f}).text = str(h)
                x += 1
    return g


def grid_plan(show: _Show) -> List[dict]:
    """Groups whose grid differs from the lines their fixtures form on the
    stage: ``[{id, name, now, new, rows}]``.  Only groups with one head per
    fixture and every fixture placed in 3D."""
    pos = _positions(show.root)
    out = []
    for g in show.groups:
        ids = P.group_fixture_ids(g)
        if len(ids) < 2 or len(g.findall("Head")) != len(ids) or not all(i in pos for i in ids):
            continue
        rows = W.lines_of(ids, pos)
        new = sorted(W._grid_cells(rows), key=lambda c: (c[1], c[0]))
        now = W._current_cells(g)
        if new == now:
            continue
        sz = g.find("Size")
        out.append({"id": g.get("ID"), "name": g.findtext("Name") or "",
                    "now": [int(sz.get("X", 0)) if sz is not None else 0,
                            int(sz.get("Y", 0)) if sz is not None else 0],
                    "new": [max((len(r) for r in rows), default=0), len(rows)],
                    "rows": rows})
    return out


# ═════════════════════════════════════════════════════════════════════════════
# 5. positions
# ═════════════════════════════════════════════════════════════════════════════

def _fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _mesh_name(m: dict) -> Optional[str]:
    """A musician's name from the mesh (its own name, else its file), or None
    when the mesh is not a person (a cube, a riser, an amp)."""
    stem = os.path.splitext(os.path.basename(m.get("res") or ""))[0]
    name = (m.get("name") or "").strip()
    words_of = lambda t: [w for w in re.split(r"[_\-\s.]+", t) if w and w.lower() not in JUNK_WORDS]  # noqa: E731
    if name:
        # a cube or a sphere stands for a person only when its name says so
        if PRIMITIVE_RE.match(stem) and not any(PERSON_RE.match(w) for w in words_of(name)):
            return None
        return name
    if not stem or PRIMITIVE_RE.match(stem):
        return None
    words = words_of(stem)
    first = next((i for i, w in enumerate(words) if PERSON_RE.match(w)), None)
    if first is None:
        return None
    return " ".join(w[:1].upper() + w[1:] for w in words[first:])


def position_plan(show: _Show) -> List[Tuple[str, str]]:
    """``[(name, "x,y,z")]`` Position3D palettes (metres, X from the left,
    Z from the back, Y up): the stage centre, the audience and every
    musician model on the stage.  [] without moving heads."""
    from core import stage3d
    if not show.movers():
        return []
    st = show.R.stage
    w, _h, d = st.grid
    have = {(p.type, p.name.lower()) for p in P.read_palettes(show.root).values()}
    out: List[Tuple[str, str]] = []
    names = set()

    def add(name, x, z):
        base, n = name, 2
        while name.lower() in names:
            name = f"{base} {n}"
            n += 1
        names.add(name.lower())
        if ("Position3D", name.lower()) not in have:
            out.append((name, f"{_fmt(x)},0,{_fmt(z)}"))

    add("Centre", w / 2, d / 2)
    add("Audience", w / 2, d * AUDIENCE_DEPTH)
    for m in stage3d.meshes(show.root):
        if m.get("hidden"):
            continue
        name = _mesh_name(m)
        if not name:
            continue
        pl = m.get("place")
        if pl:
            x, z = pl["x"] / 1000.0, pl["z"] / 1000.0
        else:
            # model file not found here: its box starts at XPos/ZPos (mm);
            # half a person's width (0.25 m) gets close enough to the middle
            x, z = m["pos"][0] / 1000.0 + 0.25, m["pos"][2] / 1000.0 + 0.25
        add(name, min(max(x, 0.0), w), min(max(z, 0.0), d))
    return out


# ═════════════════════════════════════════════════════════════════════════════
# 6. the Groups page
# ═════════════════════════════════════════════════════════════════════════════

def groups_frame(root) -> Optional[ET.Element]:
    vc = root.find("VirtualConsole")
    if vc is None:
        return None
    for fr in vc.iter("Frame"):
        if fr.get("Caption") == FRAME_CAPTION and fr.find("Multipage") is not None:
            return fr
    return None


def _intensity_channels(show: _Show, ids: Iterable[str]) -> List[Tuple[str, int]]:
    """``[(fixture, channel)]``: master dimmer, else each head's dimmer."""
    out = []
    for f in ids:
        m = show.R.models.get(f)
        if m is None:
            continue
        mi = m.master_intensity()
        if mi is not None:
            out.append((f, mi))
            continue
        for h in range(len(m.heads)):
            c = m.head_map(h).get(("Intensity", True))
            if c is not None and (f, c) not in out:
                out.append((f, c))
    return out


def page_plan(show: _Show) -> List[dict]:
    """One page per group: ``[{group, name, fixtures, looks, effects,
    slider, xypad}]`` (function IDs in ID order).  A look is a scene on
    exactly the group's fixtures that no chaser plays (a button and a chaser
    step never share a scene); an effect is a chaser, RGB matrix or EFX on
    exactly those fixtures."""
    movers = set(show.movers())
    used_as_step = {k for k, ps in show.parents.items()
                    if any(show.fns.get(p) is not None and show.fns[p].get("Type") in ("Chaser", "Sequence")
                           for p in ps)}
    out = []
    seen = set()
    for g in show.groups:
        ids = P.group_fixture_ids(g)
        fx = frozenset(ids)
        if fx in seen:                   # two groups of the same fixtures: one page
            continue
        seen.add(fx)
        looks, effects = [], []
        for fid in sorted(show.fns, key=_num):
            fn = show.fns[fid]
            if fid in show.panic or fid in show.cuelists:
                continue
            t = fn.get("Type")
            if t == "Scene":
                if fid in used_as_step or show.sets.get(fid) != fx:
                    continue
                looks.append(fid)
            elif t in ("Chaser", "RGBMatrix", "EFX"):
                if show.fixtures_of(fn) == fx:
                    effects.append(fid)
        out.append({"group": g.get("ID"), "name": g.findtext("Name") or "", "fixtures": ids,
                    "looks": looks, "effects": effects,
                    "slider": _intensity_channels(show, ids),
                    "xypad": [f for f in ids if f in movers]})
    return out


def _build_frame(show: _Show, work, pages: List[dict], acts) -> None:
    from core import vc_group_pages as VP
    names = {fid: (show.fns[fid].get("Name") or "") for fid in show.fns}
    st_ = show.R.stage
    floor = (st_.grid[0] / 2, 0.0, st_.grid[2] / 2)
    vpages = [{"name": p["name"], "slider": p["slider"], "looks": [p["looks"]], "effects": p["effects"],
               "xypad": p["xypad"]} for p in pages]
    _pid, per_page = VP.build(work, FRAME_CAPTION, vpages, names, floor=floor, panic=W._panic_script(work))
    acts.append({"step": "frame", "action": f"VC page '{FRAME_CAPTION}' with a {len(pages)}-page frame, "
                                            "one page per group (pick the page in the frame's header)"})
    acts.extend({"step": "frame", "action": t} for t in per_page)


# ═════════════════════════════════════════════════════════════════════════════
# analyse
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# 9. cross-universe fixtures (QLC+ 5.3.1)
# ═════════════════════════════════════════════════════════════════════════════

def cross_plan(ws) -> List[Tuple[str, str]]:
    """``(fixture id, name)`` of each fixture with an old cross-universe flag
    that QLC+ 5.3.1 patches to other addresses than 5.3.0 (Doctor D027)."""
    from core.doctor.checks import _d027_legacy_cross
    return [(f.ref["fixture"], ws.fixtures[f.ref["fixture"]]["name"]) for f in _d027_legacy_cross(ws)]


def analyse(root, defs=None, target: str = "5.3") -> dict:
    """What :func:`upgrade` can do on this show, step by step:
    ``{version, target, wizard, known, lights, steps: [{id, count, items,
    only53, note}], defaults}``."""
    if isinstance(root, ET.ElementTree):
        root = root.getroot()
    root = qxw_io.strip_ns(copy.deepcopy(root))
    target = target_of(target)
    if P.is_wizard_show(root):
        return _known(root, _wizard_analysis(root, target, defs))
    show = _Show(root, defs)
    folders = folder_plan(show)
    by_folder: Dict[str, int] = {}
    for p in folders.values():
        by_folder[p] = by_folder.get(p, 0) + 1
    pals = palette_plan(show)
    grids = grid_plan(show)
    pos = position_plan(show)
    pages = [] if groups_frame(root) is not None else page_plan(show)
    hide = W.visible_infrastructure(root)
    lock = W.unlocked(root)
    known, lights = show.known(), len(show.lights)
    need_defs = "Needs the fixture definitions: only %d of %d lights have one." % (known, lights) \
        if known < lights else ""
    steps = [
        {"id": "folders", "count": len(folders),
         "items": [f"{p}: {n}" for p, n in sorted(by_folder.items(), key=lambda kv: kv[0].lower())]},
        {"id": "palettes", "count": len(pals),
         "items": [f"{t}: {n}" for n, t, _v in pals], "note": need_defs},
        {"id": "allgroup", "count": 1 if needs_all_group(show) else 0,
         "items": [f"{ALL_GROUP}: {lights} fixture(s)"] if needs_all_group(show) else []},
        {"id": "grids", "count": len(grids),
         "items": [f"{g['name']}: {g['now'][0]}×{g['now'][1]} → {g['new'][0]}×{g['new'][1]}" for g in grids]},
        {"id": "positions", "count": len(pos),
         "items": [f"{n} ({v} m)" for n, v in pos],
         "note": "" if show.movers() else ("No moving heads in the rig." if not need_defs else need_defs)},
        {"id": "frame", "count": len(pages),
         "items": [f"{p['name']}: {len(p['looks'])} look(s), {len(p['effects'])} effect(s)"
                   + (", XY pad" if p["xypad"] else "") for p in pages],
         "note": "" if groups_frame(root) is None else f"The show already has a '{FRAME_CAPTION}' frame."},
        {"id": "hide", "count": len(hide), "items": [f"fixture {i}" for i in hide]},
        {"id": "lock", "count": len(lock), "items": []},
        _dimmer_step(show),
        _cross_step(show.ws),
    ]
    for s in steps:
        s["only53"] = s["id"] in ONLY_53
        s.setdefault("note", "")
    return _known(root, {"version": root.findtext("Creator/Version") or "", "target": target,
                         "wizard": P.is_wizard_show(root), "known": known, "lights": lights,
                         "steps": steps,
                         "defaults": [s for s in DEFAULT_STEPS if not (target != "5.3" and s in ONLY_53)]})


def _dimmer_step(show: _Show) -> dict:
    plan = dimmer_plan(show)
    need = show.known() < len(show.lights)
    note = _dimmer_note(plan)
    if need and not plan["moves"]:
        note = "Needs the fixture definitions: only %d of %d lights have one." % (show.known(), len(show.lights))
    return {"id": "dimmerpal", "count": len(plan["moves"]), "items": _dimmer_items(plan), "note": note}


def _cross_step(ws) -> dict:
    from core.doctor.checks import _d026_no_fit
    plan = cross_plan(ws)
    nofit = list(_d026_no_fit(ws))
    note = (f"{len(nofit)} fixture(s) run past channel 512 and QLC+ moves them to address 1: "
            f"the Workspace Doctor (D026) can let them continue in the next universe.") if nofit else ""
    return {"id": "crossuniverse", "count": len(plan),
            "items": [f"fixture {fid} '{name}'" for fid, name in plan], "note": note,
            "ready": not plan and not nofit}


def _known(root, out: dict) -> dict:
    """The latest QLC+ Swiss Knife knows, and a note when the file is newer."""
    out["latest"] = LATEST
    out["newer"] = newer_than_known(out.get("version", ""))
    cross = next((s for s in out.get("steps", []) if s["id"] == "crossuniverse"), {})
    out["ready"] = bool(cross.get("ready")) and not out["newer"]   # nothing 5.3.1 reads differently
    return out


WIZARD_NOTE = "The QLC+ Show Wizard made this show: Wizard Repair finishes it."
WIZARD_OWN = ("folders", "palettes", "allgroup", "grids", "positions", "frame", "dimmerpal")


def _wizard_analysis(root, target: str, defs=None) -> dict:
    """A Show Wizard show already has folders, palettes, positions and a
    page per group; Wizard Repair finishes it.  Only hiding and locking are
    left here."""
    hide = W.visible_infrastructure(root)
    lock = W.unlocked(root)
    steps = []
    for sid in STEPS:
        if sid in WIZARD_OWN:
            steps.append({"id": sid, "count": 0, "items": [], "note": WIZARD_NOTE})
        elif sid == "hide":
            steps.append({"id": sid, "count": len(hide), "items": [f"fixture {i}" for i in hide], "note": ""})
        elif sid == "crossuniverse":
            from core.doctor.checks import _Workspace
            steps.append(_cross_step(_Workspace(root, _defs_dict(defs))))
        else:
            steps.append({"id": sid, "count": len(lock), "items": [], "note": ""})
    for s in steps:
        s["only53"] = s["id"] in ONLY_53
    return {"version": root.findtext("Creator/Version") or "", "target": target, "wizard": True,
            "known": 0, "lights": len(_lights(root)), "steps": steps,
            "defaults": ["hide", "crossuniverse"]}



# ═════════════════════════════════════════════════════════════════════════════
# 9. dimmer from palettes (3.21.0)
# ═════════════════════════════════════════════════════════════════════════════
#
# A look moves to a Dimmer palette only when it will play exactly as before.
# QLC+ 5.3 applies a scene's palettes to its own fixtures, then the scene's
# own values win (``Scene::write``, mirrored in ``palettes.Resolver``).  So:
#
# * every lit light of the look (one with a dimmer above 0) must set *all*
#   the channels a Dimmer palette sets on it (the master dimmer and each
#   head's dimmer) to the same level L, the same L for every lit light;
# * those channels leave the look, and a ``<Palette>`` of level L comes in;
# * a dark light keeps its 0 as its own value, which wins over the palette;
#   a dark light that never declared its dimmer gets an explicit 0 (dimmer is
#   a highest-value-wins channel, so 0 and "not set" play the same);
# * looks bound to a Sequence, layer scenes, the PANIC family and looks with
#   a light of unknown definition are left alone;
# * the result is checked with the Resolver: what the look sets after must
#   equal what it set before, or the look is left as it was.

def _dimmer_channels(show: _Show, fid: str) -> List[int]:
    """Channels a Dimmer palette sets on fixture *fid* (empty when unknown)."""
    m = show.R.models.get(fid)
    if m is None:
        return []
    vals = P.palette_values(P.Palette("x", "Dimmer", "", "255"), [m], show.R.stage)
    return sorted(vals.get(fid, {}).keys())


def _pairs(text: str) -> Dict[int, int]:
    nums = [x.strip() for x in (text or "").split(",") if x.strip()]
    out: Dict[int, int] = {}
    for c, v in zip(nums[0::2], nums[1::2]):
        try:
            out[int(c)] = int(v)
        except ValueError:
            pass
    return out


def _sequence_scenes(root) -> set:
    return {f.get("BoundScene") for f in _fns(root)
            if f.get("Type") == "Sequence" and f.get("BoundScene") is not None}


def _dimmer_candidate(show: _Show, fn: ET.Element, skip: set):
    """``(level, {fixture id: new FixtureVal text})`` when *fn* can take its
    dimmer from a palette, else ``(None, reason)``."""
    fid = fn.get("ID")
    if fn.get("Type") != "Scene" or fid in skip:
        return None, "skip"
    if P.scene_palettes(fn) or P.scene_groups(fn):
        return None, "palette"                  # already a palette or group look
    vals = _children_fixture_vals(fn)
    if not vals:
        return None, "empty"
    level = None
    new: Dict[str, str] = {}
    lit_any = False
    for v in vals:
        f = v.get("ID")
        chans = _dimmer_channels(show, f)
        if not chans:
            return None, "unknown"
        pairs = _pairs(v.text or "")
        dims = [pairs.get(c) for c in chans]
        if all(d in (None, 0) for d in dims):
            for c in chans:                     # dark: an explicit 0 wins over the palette
                pairs[c] = 0
            new[f] = P.fixture_val_text(pairs)
            continue
        if any(d is None for d in dims) or len(set(dims)) != 1:
            return None, "levels"
        if level is None:
            level = dims[0]
        elif dims[0] != level:
            return None, "levels"
        lit_any = True
        for c in chans:
            pairs.pop(c, None)
        new[f] = P.fixture_val_text(pairs)
    if not lit_any:
        return None, "dark"
    return level, new


def _children_fixture_vals(fn: ET.Element) -> List[ET.Element]:
    return [c for c in fn if c.tag == "FixtureVal" or c.tag.endswith("}FixtureVal")]


def _plays_same(show: _Show, before: ET.Element, after: ET.Element, extra_pal: P.Palette) -> bool:
    """The look after the change sets the same values as before (dimmer
    channels not set before count as 0)."""
    R = show.R
    old = R.resolve(before)
    saved = dict(R.palettes)
    R.palettes[extra_pal.id] = extra_pal
    try:
        nw = R.resolve(after)
    finally:
        R.palettes = saved
    for f in set(old) | set(nw):
        a, b = dict(old.get(f, {})), dict(nw.get(f, {}))
        for c in _dimmer_channels(show, f):
            a.setdefault(c, 0)
            b.setdefault(c, 0)
        if a != b:
            return False
    return True


def dimmer_plan(show: _Show) -> dict:
    """What *dimmerpal* would do: ``{moves: [(scene id, level, new texts)],
    levels: {level: n}, left: {reason: n}, total}``."""
    skip = _sequence_scenes(show.root) | set(show.panic)
    moves, left = [], {}
    levels: Dict[int, int] = {}
    total = 0
    for fn in _fns(show.root):
        if fn.get("Type") != "Scene":
            continue
        if not _children_fixture_vals(fn) or not P.has_values(fn):
            continue
        if P.scene_layer(fn, show.R):
            left["layer"] = left.get("layer", 0) + 1
            total += 1
            continue
        total += 1
        level, new = _dimmer_candidate(show, fn, skip)
        if level is None:
            left[new] = left.get(new, 0) + 1
            continue
        after = copy.deepcopy(fn)
        for v in _children_fixture_vals(after):
            v.text = new.get(v.get("ID"), v.text)
        ET.SubElement(after, "Palette", {"ID": "__dimmer__"})
        if not _plays_same(show, fn, after, P.Palette("__dimmer__", "Dimmer", "", str(level))):
            left["different"] = left.get("different", 0) + 1
            continue
        moves.append((fn.get("ID"), level, new))
        levels[level] = levels.get(level, 0) + 1
    return {"moves": moves, "levels": levels, "left": left, "total": total}


DIMMER_NAMES = {255: "Dimmer Full", 128: "Dimmer Half", 0: "Dimmer Off"}
LEFT_WORDS = {
    "levels": "Stay as they are: {0} look(s) with lit lights at different levels",
    "unknown": "Stay as they are: {0} look(s) with a light that has no definition",
    "dark": "Stay as they are: {0} look(s) with every light dark",
    "skip": "Stay as they are: {0} look(s) that are the PANIC RESET or belong to a sequence",
    "layer": "Stay as they are: {0} layer look(s)",
    "different": "Stay as they are: {0} look(s) that would not play the same",
    "palette": "Stay as they are: {0} look(s) that already use palettes",
    "empty": "Stay as they are: {0} look(s) with no values",
}


def _dimmer_palette_for(root, level: int) -> str:
    """The id of a flat Dimmer palette at *level*, made when there is none."""
    for p in _eng(root).findall("Palette"):
        if p.get("Type") == "Dimmer" and p.get("Value") == str(level) \
                and (p.get("Fan") or "Flat") == "Flat":
            return p.get("ID")
    name = DIMMER_NAMES.get(level) or f"Dimmer {int(round(level * 100 / 255))}%"
    taken = {p.get("Name") for p in _eng(root).findall("Palette")}
    if name in taken:
        name = f"{name} ({level})"
    return _add_palette(root, name, "Dimmer", str(level))


def _level_name(lv: int) -> str:
    return DIMMER_NAMES.get(lv) or "Dimmer %d%%" % round(lv * 100 / 255)


def _dimmer_items(plan: dict, reasons: bool = True) -> List[str]:
    items = [f"{_level_name(lv)}: {n} look(s)" for lv, n in sorted(plan["levels"].items(), reverse=True)]
    if reasons:
        items += [LEFT_WORDS.get(k, k + ": {0}").replace("{0}", str(n))
                  for k, n in sorted(plan["left"].items(), key=lambda kv: -kv[1])]
    return items


def _dimmer_note(plan: dict) -> str:
    if not plan["total"]:
        return ""
    stay = sum(plan["left"].values())
    return (f"{len(plan['moves'])} of {plan['total']} looks can take their dimmer from a palette; "
            f"the other {stay} stay as they are.")


# ═════════════════════════════════════════════════════════════════════════════
# upgrade
# ═════════════════════════════════════════════════════════════════════════════

def upgrade(root, defs=None, steps: Iterable[str] = DEFAULT_STEPS,
            target: str = "5.3") -> Tuple[ET.Element, List[dict]]:
    """Apply the *steps* to a copy of *root*; ``(new root, actions)``, each
    action ``{step, action}``.  With *target* ``"5.2.2"`` the 5.3-only steps
    are skipped.  Nothing is removed."""
    if isinstance(root, ET.ElementTree):
        root = root.getroot()
    work = qxw_io.strip_ns(copy.deepcopy(root))
    target = target_of(target)
    want = [s for s in STEPS if s in set(steps) and not (target != "5.3" and s in ONLY_53)]
    if P.is_wizard_show(work):
        want = [s for s in want if s not in WIZARD_OWN]
    acts: List[dict] = []

    def act(step, text):
        acts.append({"step": step, "action": text})

    show = _Show(work, defs)

    # 2. palettes (before the folders: nothing else depends on them)
    if "palettes" in want:
        for name, ptype, val in palette_plan(show):
            pid = _add_palette(work, name, ptype, val)
            act("palettes", f"palette {pid} '{name}' ({ptype} {val})")

    # 5. positions
    if "positions" in want:
        for name, val in position_plan(show):
            pid = _add_palette(work, name, "Position3D", val)
            act("positions", f"palette {pid} '{name}' (Position3D {val} m)")

    # 3. the All Fixtures group
    if "allgroup" in want and needs_all_group(show):
        gid = str(max([int(g.get("ID")) for g in _eng(work).findall("FixtureGroup")
                       if (g.get("ID") or "").isdigit()] + [-1]) + 1)
        rows = _group_rows(show, show.lights)
        g = _group_el(gid, ALL_GROUP, show, rows)
        _insert_engine(work, g, ("Fixture", "FixtureGroup"))
        act("allgroup", f"group {gid} '{ALL_GROUP}': {len(show.lights)} fixture(s), "
                        f"grid {g.find('Size').get('X')}×{g.find('Size').get('Y')}")
        show = _Show(work, defs)

    # 4. grids
    if "grids" in want:
        groups = {g.get("ID"): g for g in _eng(work).findall("FixtureGroup")}
        for ch in grid_plan(show):
            g = groups[ch["id"]]
            heads = {h.get("Fixture"): (h.text or "0") for h in g.findall("Head")}
            for h in g.findall("Head"):
                g.remove(h)
            sz = g.find("Size")
            if sz is None:
                sz = ET.SubElement(g, "Size")
            sz.set("X", str(ch["new"][0]))
            sz.set("Y", str(ch["new"][1]))
            for x, y, f in sorted(W._grid_cells(ch["rows"]), key=lambda c: (c[1], c[0])):
                ET.SubElement(g, "Head", {"X": str(x), "Y": str(y), "Fixture": f}).text = heads.get(f, "0")
            act("grids", f"group '{ch['name']}': grid {ch['now'][0]}×{ch['now'][1]} → "
                         f"{ch['new'][0]}×{ch['new'][1]}, rows front to back, columns as they hang")
        show = _Show(work, defs)

    # 6. the Groups page
    if "frame" in want and groups_frame(work) is None:
        pages = page_plan(show)
        if pages:
            _build_frame(show, work, pages, acts)

    # 1. folders
    if "folders" in want:
        plan = folder_plan(show)
        by_folder: Dict[str, int] = {}
        for fid, path in plan.items():
            show.fns[fid].set("Path", path)
            by_folder[path] = by_folder.get(path, 0) + 1
        for path, n in sorted(by_folder.items(), key=lambda kv: kv[0].lower()):
            act("folders", f"{path}: {n} function(s)")

    # 7. hide, 8. lock
    if "hide" in want:
        ids = W.visible_infrastructure(work)
        for it in W._fx_items(work):
            if it.get("ID") in ids:
                it.set("Hidden", "True")
        if ids:
            act("hide", f"{len(ids)} page-switch fixture(s) hidden in the 2D and 3D views")
    if "lock" in want:
        ids = W.unlocked(work)
        for it in W._fx_items(work):
            if it.get("ID") in ids:
                it.set("Locked", "True")
        if ids:
            act("lock", f"{len(ids)} fixture(s) locked in the 2D and 3D views (QLC+ 5.3)")

    # dimmer from palettes (3.21.0): last of the look changes, on a fresh read
    if "dimmerpal" in want:
        plan = dimmer_plan(_Show(work, defs))
        fns = {f.get("ID"): f for f in _fns(work)}
        pal_ids: Dict[int, str] = {}
        for sid, level, new in plan["moves"]:
            if level not in pal_ids:
                pal_ids[level] = _dimmer_palette_for(work, level)
            fn = fns[sid]
            for v in _children_fixture_vals(fn):
                if v.get("ID") in new:
                    v.text = new[v.get("ID")] or None
            ET.SubElement(fn, "Palette", {"ID": pal_ids[level]})
        for lv, n in sorted(plan["levels"].items(), reverse=True):
            act("dimmerpal", f"{n} look(s) now take their dimmer from the palette '{_level_name(lv)}'")
        if plan["moves"]:
            act("dimmerpal", _dimmer_note(plan))

    # 9. cross-universe fixtures (QLC+ 5.3.1)
    if "crossuniverse" in want:
        plan = dict(cross_plan(_Show(work, defs).ws))
        for fx in _eng(work).findall("Fixture"):
            fid = (fx.findtext("ID") or "").strip()
            if fid in plan:
                qlc531.set_cross_mode(fx, qlc531.FILL)
                act("crossuniverse", f"fixture {fid} '{plan[fid]}': cross-universe flag set to 'Fill', "
                                     f"the addresses QLC+ 5.3.0 gave it")

    acts.sort(key=lambda a: STEPS.index(a["step"]))
    return work, acts
