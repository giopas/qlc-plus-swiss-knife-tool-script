"""
Upgrade a QLC+ 5 show to what QLC+ 5.3 offers (3.2.0).

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
=========  ===========================================================  ========

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
import math
import os
import re
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, Iterable, List, Optional, Tuple

from core import palettes as P
from core import qxw_io
from core import wizard_repair as W

STEPS = ("folders", "palettes", "allgroup", "grids", "positions", "frame", "hide", "lock")
DEFAULT_STEPS = ("folders", "palettes", "allgroup", "positions", "hide")
ONLY_53 = ("positions", "lock")
TARGETS = ("5.3", "5.2.2")

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

BUTTON = W.BUTTON
GAP = W.GAP
MARGIN = W.MARGIN
TOP = 60                          # first row inside the frame (below its header)
SLIDER = (75, 335)
XYPAD = (295, 295)
RED = "4294901760"
LOOK_BG = "4282664004"


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
                    "xypad": [f for f in ids if f in movers] if ids and all(f in movers for f in ids) else []})
    return out


def _ws(el: ET.Element, x: int, y: int, w: int, h: int, visible: bool) -> None:
    ET.SubElement(el, "WindowState", {"Visible": "True" if visible else "False", "X": str(x),
                                      "Y": str(y), "Width": str(w), "Height": str(h)})


def _frame_flags(el: ET.Element, header: bool = True) -> None:
    for tag, val in (("AllowResize", "True"), ("ShowHeader", "True" if header else "False"),
                     ("ShowEnableButton", "True"), ("Collapsed", "False"), ("Disabled", "False")):
        ET.SubElement(el, tag).text = val


def _btn(nid, caption: str, fid: str, x: int, y: int, *, page: Optional[int] = None,
         visible: bool = True, bg: str = LOOK_BG) -> ET.Element:
    attrs = {"Caption": caption[:32], "ID": str(nid())}
    if page:
        attrs["Page"] = str(page)
    b = ET.Element("Button", attrs)
    _ws(b, x, y, BUTTON, BUTTON, visible)
    app = ET.SubElement(b, "Appearance")
    ET.SubElement(app, "BackgroundColor").text = bg
    ET.SubElement(b, "Function", {"ID": fid})
    ET.SubElement(b, "Action").text = "Toggle"
    return b


def _build_frame(show: _Show, work, pages: List[dict], acts) -> None:
    from core import vc_ops
    vc = work.find("VirtualConsole")
    if vc is None:
        vc = ET.SubElement(work, "VirtualConsole")
    page_id = vc_ops.new_page(work, FRAME_CAPTION)["page_id"]
    page_el = next(p for p in vc if p.get("ID") == page_id)
    pw, ph = 1920, 1080
    st = page_el.find("WindowState")
    if st is not None:
        try:
            pw, ph = int(st.get("Width", pw)), int(st.get("Height", ph))
        except ValueError:
            pass
    counter = [vc_ops._next_id(vc)]

    def nid():
        counter[0] += 1
        return counter[0] - 1

    fw, fh = pw - 2 * MARGIN, ph - 2 * MARGIN
    fr = ET.Element("Frame", {"Caption": FRAME_CAPTION, "ID": str(nid())})
    _ws(fr, MARGIN, MARGIN, fw, fh, True)
    _frame_flags(fr)
    ET.SubElement(fr, "Multipage", {"PagesNum": str(len(pages)), "CurrentPage": "0"})
    for i, p in enumerate(pages):
        ET.SubElement(fr, "Shortcut", {"Page": str(i), "Name": p["name"]})
    page_el.append(fr)
    panic = W._panic_script(work)
    names = {fid: (show.fns[fid].get("Name") or "") for fid in show.fns}
    st_ = show.R.stage
    floor = (st_.grid[0] / 2, 0.0, st_.grid[2] / 2)
    per_page: List[str] = []

    for i, p in enumerate(pages):
        vis = i == 0
        placed_l, placed_e, lost = 0, 0, []
        if panic:
            fr.append(_btn(nid, "PANIC RESET", panic, fw - MARGIN - BUTTON, TOP, page=i, visible=vis, bg=RED))
        cx = MARGIN
        y_col = TOP + BUTTON + GAP
        if p["slider"]:
            s = ET.Element("Slider", {"Caption": "Intensity", "ID": str(nid()), "WidgetStyle": "Slider",
                                      "InvertedAppearance": "false"})
            if i:
                s.set("Page", str(i))
            _ws(s, MARGIN, y_col, SLIDER[0], SLIDER[1], vis)
            app = ET.SubElement(s, "Appearance")
            ET.SubElement(app, "BackgroundColor").text = LOOK_BG
            ET.SubElement(s, "SliderMode", {"ValueDisplayStyle": "Exact"}).text = "Level"
            lv = ET.SubElement(s, "Level", {"LowLimit": "0", "HighLimit": "255", "Value": "0"})
            for f, c in p["slider"]:
                ET.SubElement(lv, "Channel", {"Fixture": f}).text = str(c)
            fr.append(s)
            cx = MARGIN + SLIDER[0] + GAP
        avail = fw - cx - MARGIN
        y = y_col
        # looks: one at a time, in a solo frame
        if p["looks"]:
            cols = max(1, min(len(p["looks"]), (avail - 2 * MARGIN + GAP) // (BUTTON + GAP)))
            room_rows = max(0, (fh - MARGIN - y - MARGIN + GAP) // (BUTTON + GAP))
            rows = min(math.ceil(len(p["looks"]) / cols), room_rows)
            n = min(len(p["looks"]), rows * cols)
            if n:
                sw = 2 * MARGIN + cols * BUTTON + (cols - 1) * GAP
                sh = 2 * MARGIN + rows * BUTTON + (rows - 1) * GAP
                solo = ET.Element("SoloFrame", {"Caption": "Looks", "ID": str(nid())})
                if i:
                    solo.set("Page", str(i))
                _ws(solo, cx, y, sw, sh, vis)
                _frame_flags(solo, header=False)
                for k, fid in enumerate(p["looks"][:n]):
                    solo.append(_btn(nid, names[fid], fid, MARGIN + (k % cols) * (BUTTON + GAP),
                                     MARGIN + (k // cols) * (BUTTON + GAP)))
                fr.append(solo)
                placed_l = n
                y += sh + GAP
            lost += p["looks"][n:]
        # effects: toggles, row by row
        if p["effects"]:
            per_row = max(1, (avail + GAP) // (BUTTON + GAP))
            k = 0
            for fid in p["effects"]:
                bx = cx + (k % per_row) * (BUTTON + GAP)
                by = y + (k // per_row) * (BUTTON + GAP)
                if by + BUTTON > fh - MARGIN:
                    lost.append(fid)
                    continue
                fr.append(_btn(nid, names[fid], fid, bx, by, page=i, visible=vis))
                k += 1
            placed_e = k
            if k:
                y += math.ceil(k / per_row) * (BUTTON + GAP)
        # moving heads: an XY pad that aims at the stage floor in QLC+ 5.3
        pad = False
        if p["xypad"]:
            # below the slider and below everything right of it (the pad is wider)
            px = MARGIN
            py = max(y_col + (SLIDER[1] + GAP if p["slider"] else 0), y)
            if py + XYPAD[1] <= fh - MARGIN:
                xy = ET.Element("XYPad", {"Caption": "Position", "ID": str(nid())})
                if i:
                    xy.set("Page", str(i))
                xy.set("InvertedAppearance", "0")
                xy.set("FloorControl", "1")
                _ws(xy, px, py, XYPAD[0], XYPAD[1], vis)
                ET.SubElement(xy, "Appearance")
                for f in p["xypad"]:
                    ET.SubElement(xy, "Fixture", {"ID": f, "Head": "0"})
                ET.SubElement(xy, "Window", {"hMin": "0", "hMax": "255", "vMin": "0", "vMax": "255"})
                ET.SubElement(xy, "Pan", {"Position": "0"})
                ET.SubElement(xy, "Tilt", {"Position": "0"})
                ET.SubElement(xy, "FloorPosition", {"X": _fmt(floor[0]), "Y": "0", "Z": _fmt(floor[2])})
                fr.append(xy)
                pad = True
            else:
                lost.append("XY pad")
        bits = []
        if p["slider"]:
            bits.append("intensity slider")
        if placed_l:
            bits.append(f"{placed_l} look(s)")
        if placed_e:
            bits.append(f"{placed_e} effect(s)")
        if pad:
            bits.append(f"XY pad for {len(p['xypad'])} moving head(s)")
        per_page.append(f"page '{p['name']}': " + (", ".join(bits) or "empty"))
        if lost:
            per_page.append(f"page '{p['name']}': no room for " + ", ".join(names.get(x, x) for x in lost))
    acts.append({"step": "frame", "action": f"VC page '{FRAME_CAPTION}' with a {len(pages)}-page frame, "
                                            "one page per group (pick the page in the frame's header)"})
    acts.extend({"step": "frame", "action": t} for t in per_page)


# ═════════════════════════════════════════════════════════════════════════════
# analyse
# ═════════════════════════════════════════════════════════════════════════════

def analyse(root, defs=None, target: str = "5.3") -> dict:
    """What :func:`upgrade` can do on this show, step by step:
    ``{version, target, wizard, known, lights, steps: [{id, count, items,
    only53, note}], defaults}``."""
    if isinstance(root, ET.ElementTree):
        root = root.getroot()
    root = qxw_io.strip_ns(copy.deepcopy(root))
    target = target if target in TARGETS else "5.3"
    if P.is_wizard_show(root):
        return _wizard_analysis(root, target)
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
    ]
    for s in steps:
        s["only53"] = s["id"] in ONLY_53
        s.setdefault("note", "")
    return {"version": root.findtext("Creator/Version") or "", "target": target,
            "wizard": P.is_wizard_show(root), "known": known, "lights": lights,
            "steps": steps,
            "defaults": [s for s in DEFAULT_STEPS if not (target != "5.3" and s in ONLY_53)]}


WIZARD_NOTE = "The QLC+ Show Wizard made this show: Wizard Repair finishes it."
WIZARD_OWN = ("folders", "palettes", "allgroup", "grids", "positions", "frame")


def _wizard_analysis(root, target: str) -> dict:
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
        else:
            steps.append({"id": sid, "count": len(lock), "items": [], "note": ""})
    for s in steps:
        s["only53"] = s["id"] in ONLY_53
    return {"version": root.findtext("Creator/Version") or "", "target": target, "wizard": True,
            "known": 0, "lights": len(_lights(root)), "steps": steps,
            "defaults": ["hide"]}


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
    target = target if target in TARGETS else "5.3"
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

    acts.sort(key=lambda a: STEPS.index(a["step"]))
    return work, acts
