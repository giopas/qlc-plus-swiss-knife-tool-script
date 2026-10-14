"""
Repair a show made by the QLC+ 5.3 Show Wizard (3.1.0).

The QLC+ 5.3.0 Show Wizard builds a whole show in one go: groups, palettes,
looks, effects and a multipage Virtual Console frame.  Two wizard shows
checked on 14 October 2026 showed what it leaves to finish:

* **Lost chasers.** ``StageWizard::makeChaserFromScenes`` adds the step
  scenes of Color Rainbow, Split Color and Strobe Chase to the show but never
  the chaser itself, so those effects exist only as loose scenes.
* **Content with no button.** RGB matrices, the musician key positions,
  Audience Sweep, Dimmer Full/Half, Blinder Hit … are in the function tree
  only.
* **Group grids.** A group's grid is built from depth alone, so fixtures on
  the side columns end up in an order that makes matrix effects jump.
* **Palettes that do nothing.** The Shutter palette asks for one exact
  capability preset (``StrobeSlowToFast``); a fixture whose strobe range is
  ``StrobeFreqRange`` gets nothing (a Clay Paky Sharpy, for one).  A Color
  palette sets colour mixing only, so a colour-wheel fixture stays as it is.
* **No PANIC RESET.** Only Blackout, which does not stop running effects.

:func:`analyse` lists what it finds; :func:`repair` fixes the steps asked
for, on a copy, and says what it did.  Both are deterministic: new IDs are
``max + 1`` in document order and the same show gives the same result.
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, Iterable, List, Optional, Tuple

from core import palettes as P
from core import qxw_io

STEPS = ("chasers", "palettes", "panic", "buttons", "grids", "hide", "lock", "captions")
DEFAULT_STEPS = ("chasers", "palettes", "panic", "buttons", "grids", "hide")

DASH = " – "                     # the wizard's "<group> – <name>" separator (en dash)

# Chasers the wizard means to make and loses (stagewizard_functions.cpp)
LOST_CHASERS = (
    # kind, chaser name, step names, fade ms, hold ms
    ("rainbow", "Color Rainbow",
     ("Rainbow Red", "Rainbow Orange", "Rainbow Yellow", "Rainbow Green",
      "Rainbow Cyan", "Rainbow Blue", "Rainbow Magenta"), 500, 1000),
    ("split", "Split Color", ("Split A", "Split B"), 200, 500),
    ("strobe", "Strobe Chase", ("Strobe Open", "Strobe Closed"), 0, 80),
)

BUTTON = 85                       # the wizard's button size and spacing
GAP = 20
MARGIN = 20
FRAME_HEADER = 40                 # top band of the frame (page selector)
WIZARD_BG = "4282664004"          # background of the wizard's plain buttons

ROW_ORDER = ("Effects", "Matrix", "Positions", "Looks")


# ═════════════════════════════════════════════════════════════════════════════
# Reading the show
# ═════════════════════════════════════════════════════════════════════════════

def _eng(root):
    eng = root.find("Engine")
    if eng is None:
        raise ValueError("The workspace has no Engine.")
    return eng


def _fns(root) -> List[ET.Element]:
    return _eng(root).findall("Function")


def _num(i) -> Tuple[int, str]:
    s = str(i)
    return (0, f"{int(s):012d}") if s.isdigit() else (1, s)


def _wizard_folder(fn: ET.Element) -> Optional[str]:
    """``"Par Group"`` for ``Path="Show Wizard/Par Group/Effects"``; None
    outside a group folder."""
    parts = (fn.get("Path") or "").split("/")
    if len(parts) >= 2 and parts[0] == P.WIZARD_PATH and parts[1] not in ("Page Switch", "Show Cues"):
        return parts[1]
    return None


def _refs(root) -> Tuple[Dict[str, set], Dict[str, list]]:
    """``(parents, widgets)``: functions that use a function, VC widgets that do."""
    from core.doctor.checks import _Workspace
    ws = _Workspace(root, {})
    return ws.parents, ws.vc_refs


def wizard_frame(root) -> Optional[ET.Element]:
    """The multipage frame the wizard built (caption *Show Wizard*)."""
    vc = root.find("VirtualConsole")
    if vc is None:
        return None
    for fr in vc.iter("Frame"):
        if fr.get("Caption") == P.WIZARD_PATH and fr.find("Multipage") is not None:
            return fr
    return None


def frame_pages(frame: Optional[ET.Element]) -> Dict[str, int]:
    """``{page name: page index}`` from the frame's page shortcuts."""
    out: Dict[str, int] = {}
    if frame is None:
        return out
    for sc in frame.findall("Shortcut"):
        try:
            out.setdefault(sc.get("Name") or "", int(sc.get("Page", "0")))
        except ValueError:
            continue
    return out


def _page_of(w: ET.Element) -> int:
    try:
        return int(w.get("Page", "0"))
    except ValueError:
        return 0


def missing_chasers(root) -> List[dict]:
    """Chasers the wizard meant to build and lost:
    ``[{group, kind, name, steps: [ids], fade, hold, path}]``."""
    by_name = {}
    for fn in _fns(root):
        by_name.setdefault(fn.get("Name") or "", fn)
    parents, _w = _refs(root)
    groups = sorted({g for g in (_wizard_folder(f) for f in _fns(root)) if g})
    out = []
    for g in groups:
        for kind, cname, steps, fade, hold in LOST_CHASERS:
            if f"{g}{DASH}{cname}" in by_name:
                continue
            els = [by_name.get(f"{g}{DASH}{s}") for s in steps]
            if any(e is None or e.get("Type") != "Scene" for e in els):
                continue
            if any(parents.get(e.get("ID")) for e in els):
                continue
            out.append({"group": g, "kind": kind, "name": f"{g}{DASH}{cname}",
                        "steps": [e.get("ID") for e in els], "fade": fade, "hold": hold,
                        "path": els[0].get("Path") or f"{P.WIZARD_PATH}/{g}/Effects"})
    return out


def _row_of(fn: ET.Element) -> str:
    t = fn.get("Type")
    name = (fn.get("Name") or "").split(DASH, 1)[-1]
    path = fn.get("Path") or ""
    if t == "RGBMatrix":
        return "Matrix"
    if t in ("Chaser", "Collection", "EFX", "Sequence"):
        return "Positions" if re.search(r"sweep", name, re.I) else "Effects"
    if re.search(r"position|musician", path + " " + name, re.I):
        return "Positions"
    return "Looks"


def orphans(root, extra: Iterable[ET.Element] = ()) -> Dict[str, Dict[str, List[ET.Element]]]:
    """Wizard functions on no button and used by nothing, per group folder and
    row: ``{group: {row: [functions]}}``.  *extra*: functions about to be
    added (the rebuilt chasers), counted as unused."""
    parents, widgets = _refs(root)
    lost_steps = {s for c in missing_chasers(root) for s in c["steps"]}
    out: Dict[str, Dict[str, List[ET.Element]]] = {}
    for fn in list(_fns(root)) + list(extra):
        g = _wizard_folder(fn)
        fid = fn.get("ID")
        if not g or fid in lost_steps:
            continue
        if parents.get(fid) or widgets.get(fid):
            continue
        name = (fn.get("Name") or "").split(DASH, 1)[-1]
        if fn.get("Type") == "Scene" and re.search(r"\boff\b|closed", name, re.I):
            continue                     # "Dimmer Off", "Shutter Closed": nothing to play
        out.setdefault(g, {}).setdefault(_row_of(fn), []).append(fn)
    for g in out:
        for row in out[g]:
            out[g][row].sort(key=lambda f: _num(f.get("ID")))
    return out


# ── group grids ──────────────────────────────────────────────────────────────

LINE_TOL = 500.0                  # mm: fixtures closer than this share a line


def _clusters(ids: List[str], pos: Dict[str, Tuple[float, float, float]], axis: int) -> List[List[str]]:
    srt = sorted(ids, key=lambda i: (pos[i][axis], _num(i)))
    out: List[List[str]] = []
    for i in srt:
        if out and pos[i][axis] - pos[out[-1][-1]][axis] <= LINE_TOL:
            out[-1].append(i)
        else:
            out.append([i])
    return out


def lines_of(ids: List[str], pos: Dict[str, Tuple[float, float, float]]) -> List[List[str]]:
    """The lines a set of fixtures forms on the stage, front line first.

    A fixture belongs to the row it shares with others along a truss (same
    depth) or to the column it shares on a side upright (same X), whichever
    holds more fixtures.  A row runs left to right as seen from the
    audience, a column from the front to the back."""
    placed = [i for i in ids if i in pos]
    if not placed:
        return [list(ids)] if ids else []
    rows = _clusters(placed, pos, 2)
    cols = _clusters(placed, pos, 0)
    row_of = {i: k for k, r in enumerate(rows) for i in r}
    col_of = {i: k for k, c in enumerate(cols) for i in c}
    lines: Dict[Tuple[str, int], List[str]] = {}
    for i in placed:
        h, v = len(rows[row_of[i]]), len(cols[col_of[i]])
        key = ("col", col_of[i]) if (v > h and v >= 2) else ("row", row_of[i])
        lines.setdefault(key, []).append(i)
    out = []
    for (kind, _k), members in lines.items():
        if kind == "row":
            members.sort(key=lambda i: (pos[i][0], _num(i)))
        else:
            members.sort(key=lambda i: (-pos[i][2], _num(i)))
        out.append(members)
    out.sort(key=lambda m: (-sum(pos[i][2] for i in m) / len(m), sum(pos[i][0] for i in m) / len(m)))
    unplaced = [i for i in ids if i not in pos]
    if unplaced:
        out.append(unplaced)
    return out


def proposed_grid(root, group: ET.Element, groups: List[ET.Element]) -> Optional[List[List[str]]]:
    """Rows (front first) for *group*, built from the stage.  A group that is
    the union of two or more other groups (the wizard's *All Groups*) is
    built from their lines.  None when no fixture has a 3D position."""
    st = P.read_stage(root)
    pos = {f: (v[0], v[1], v[2]) for f, v in st.items.items()}
    ids = P.group_fixture_ids(group)
    if not any(i in pos for i in ids):
        return None
    me = set(ids)
    members = [g for g in groups if g is not group
               and set(P.group_fixture_ids(g)) and set(P.group_fixture_ids(g)) < me]
    covered = set().union(*[set(P.group_fixture_ids(g)) for g in members]) if members else set()
    if len(members) >= 2 and covered == me:
        lines = []
        for g in members:
            for ln in lines_of(P.group_fixture_ids(g), pos):
                if ln not in lines:
                    lines.append([i for i in ln if not any(i in x for x in lines)])
        lines = [ln for ln in lines if ln]
        lines.sort(key=lambda m: (-sum(pos[i][2] for i in m if i in pos) / max(1, sum(1 for i in m if i in pos)),
                                  sum(pos[i][0] for i in m if i in pos) / max(1, sum(1 for i in m if i in pos))))
        return lines
    return lines_of(ids, pos)


def _grid_cells(rows: List[List[str]]) -> List[Tuple[int, int, str]]:
    cols = max((len(r) for r in rows), default=0)
    out = []
    for y, r in enumerate(rows):
        off = (cols - len(r)) // 2
        for x, f in enumerate(r):
            out.append((off + x, y, f))
    return out


def _current_cells(group: ET.Element) -> List[Tuple[int, int, str]]:
    out = []
    for h in group.findall("Head"):
        try:
            out.append((int(h.get("X", 0)), int(h.get("Y", 0)), h.get("Fixture", "")))
        except ValueError:
            continue
    return sorted(out, key=lambda c: (c[1], c[0]))


def _wizard_groups(root) -> List[ET.Element]:
    used = set()
    for fn in _fns(root):
        if not (fn.get("Path") or "").startswith(P.WIZARD_PATH):
            continue
        used |= set(P.scene_groups(fn))
        if fn.get("Type") == "RGBMatrix":
            used.add((fn.findtext("FixtureGroup") or "").strip())
    return [g for g in _eng(root).findall("FixtureGroup") if g.get("ID") in used]


def grid_changes(root) -> List[dict]:
    """Wizard groups whose grid differs from the one the stage suggests:
    ``[{id, name, now: [x, y], new: [x, y], rows: [[fixture ids]]}]``."""
    groups = _eng(root).findall("FixtureGroup")
    out = []
    for g in _wizard_groups(root):
        rows = proposed_grid(root, g, groups)
        if not rows:
            continue
        # one head per fixture as the wizard writes it; multi-head groups are left alone
        if len(g.findall("Head")) != len(P.group_fixture_ids(g)):
            continue
        new = sorted(_grid_cells(rows), key=lambda c: (c[1], c[0]))
        now = _current_cells(g)
        if new == now:
            continue
        sz = g.find("Size")
        out.append({"id": g.get("ID"), "name": g.findtext("Name") or "",
                    "now": [int(sz.get("X", 0)) if sz is not None else 0,
                            int(sz.get("Y", 0)) if sz is not None else 0],
                    "new": [max((len(r) for r in rows), default=0), len(rows)],
                    "rows": rows})
    return out


# ── palettes that do nothing on some fixtures ───────────────────────────────

def _palette_fill(pal: "P.Palette", m: "P.FixtureModel") -> Dict[int, int]:
    """Values a fixture needs to do what *pal* asks when QLC+ can't apply the
    palette to it: a Shutter palette through the capability of the same kind
    (open, closed, strobe at the same speed), a Color palette through the
    nearest slot of its colour wheel."""
    from core.capability_map import _is_wheel, _shutter_kind, nearest_wheel_value
    vals: Dict[int, int] = {}
    nums = pal.numbers()
    if pal.type == "Shutter" and len(nums) >= 2:
        pi = int(nums[0])
        preset = P.CAP_PRESETS[pi] if 0 <= pi < len(P.CAP_PRESETS) else ""
        want = ("open" if preset == "ShutterOpen" else "closed" if preset == "ShutterClose"
                else "strobe" if re.match(r"^(Strobe|Pulse|Ramp)", preset) else None)
        if want is None:
            return vals
        for h in range(len(m.heads)):
            for ch in m.shutter_channels(h):
                for cap in m.channel(ch).chdef.get("capabilities") or []:
                    if _shutter_kind(cap) != want:
                        continue
                    lo, hi = int(cap.get("min", 0)), int(cap.get("max", 255))
                    vals[ch] = (lo + hi) // 2 if want != "strobe" else int(lo + (hi - lo) * nums[1] / 100)
                    break
    elif pal.type == "Color":
        rgb, _w = pal.colours()
        if rgb is None:
            return vals
        for c in m.channels:
            if c.group == "Colour" and c.msb and _is_wheel(c.chdef):
                v = nearest_wheel_value(c.chdef, tuple(x / 255.0 for x in rgb))
                if v is not None:
                    vals[c.index] = v
                break
    return vals


def dead_palettes(root, defs) -> List[dict]:
    """Scenes whose Shutter or Color palette leaves some of their fixtures
    untouched (no capability with the palette's exact preset, or a colour
    wheel instead of colour mixing):
    ``[{function, name, palette, fixtures: {id: {channel: value}}}]`` with
    the values those fixtures need to follow the palette."""
    R = P.Resolver(root, defs)
    out = []
    for fn in _fns(root):
        if fn.get("Type") != "Scene":
            continue
        own = {v.get("ID") for v in fn.findall("FixtureVal")}
        for pid in P.scene_palettes(fn):
            pal = R.palettes.get(pid)
            if pal is None or pal.type not in ("Shutter", "Color"):
                continue
            fx = R.scene_fixtures(fn)
            got = R.palette_on(pal, fx)
            add: Dict[str, Dict[int, int]] = {}
            for f in fx:
                m = R.models.get(f)
                if m is None or f in got or f in own:
                    continue
                vals = _palette_fill(pal, m)
                if vals:
                    add[f] = vals
            if add:
                out.append({"function": fn.get("ID"), "name": fn.get("Name") or "",
                            "palette": pal.name, "fixtures": add})
    return out


# ── 3D, captions, panic ──────────────────────────────────────────────────────

def _fx_items(root) -> List[ET.Element]:
    mon = _eng(root).find("Monitor")
    return [] if mon is None else [i for i in mon.findall("FxItem")
                                   if i.get("Head", "0") == "0" and i.get("Linked", "0") == "0"]


def visible_infrastructure(root) -> List[str]:
    infra = set(P.infrastructure_fixtures(root))
    return [i.get("ID") for i in _fx_items(root)
            if i.get("ID") in infra and i.get("Hidden") is None]


def unlocked(root) -> List[str]:
    infra = set(P.infrastructure_fixtures(root))
    return [i.get("ID") for i in _fx_items(root)
            if i.get("ID") not in infra and i.get("Locked") is None]


def blank_gobo_buttons(root, defs) -> List[dict]:
    """Buttons with no caption in the wizard's *Gobos* frames:
    ``[{widget, function, caption}]`` with the caption to give them."""
    fr = wizard_frame(root)
    if fr is None:
        return []
    fns = {f.get("ID"): f for f in _fns(root)}
    R = P.Resolver(root, defs)
    out = []
    for solo in fr.iter("SoloFrame"):
        if solo.get("Caption") != "Gobos":
            continue
        for b in solo.findall("Button"):
            if (b.get("Caption") or "").strip():
                continue
            fe = b.find("Function")
            fn = fns.get(fe.get("ID")) if fe is not None else None
            if fn is None:
                continue
            out.append({"widget": b.get("ID"), "function": fn.get("ID"),
                        "caption": _gobo_label(fn, R)})
    return out


def _gobo_label(fn: ET.Element, R: "P.Resolver") -> str:
    """The gobo's capability label, else the scene name without the group."""
    for v in fn.findall("FixtureVal"):
        m = R.models.get(v.get("ID"))
        nums = [x.strip() for x in (v.text or "").split(",") if x.strip()]
        for c, val in zip(nums[0::2], nums[1::2]):
            ch = m.channel(int(c)) if (m and c.isdigit()) else None
            if ch is not None and ch.group == "Gobo" and val.isdigit():
                for cap in ch.chdef.get("capabilities") or []:
                    if int(cap.get("min", 0)) <= int(val) <= int(cap.get("max", 255)):
                        lbl = (cap.get("label") or "").strip()
                        if lbl:
                            return lbl[:24]
    return (fn.get("Name") or "").split(DASH, 1)[-1][:24]


def _panic_script(root) -> Optional[str]:
    from core.doctor.checks import PANIC_RE
    for f in _fns(root):
        if f.get("Type") == "Script" and PANIC_RE.search(f.get("Name") or ""):
            return f.get("ID")
    return None


def _frame_pages_count(fr: ET.Element) -> int:
    mp = fr.find("Multipage")
    try:
        return int(mp.get("PagesNum", "1")) if mp is not None else 1
    except ValueError:
        return 1


def panic_missing_pages(root) -> List[int]:
    """Pages of the wizard frame with no PANIC RESET button."""
    fr = wizard_frame(root)
    if fr is None:
        return []
    pid = _panic_script(root)
    have = set()
    if pid:
        for b in fr.findall("Button"):
            fe = b.find("Function")
            if fe is not None and fe.get("ID") == pid:
                have.add(_page_of(b))
    return [p for p in range(_frame_pages_count(fr)) if p not in have]


# ═════════════════════════════════════════════════════════════════════════════
# analyse
# ═════════════════════════════════════════════════════════════════════════════

def analyse(root, defs=None) -> dict:
    """What :func:`repair` can do on this show, step by step."""
    if isinstance(root, ET.ElementTree):
        root = root.getroot()
    root = qxw_io.strip_ns(copy.deepcopy(root))
    wizard = P.is_wizard_show(root)
    fr = wizard_frame(root)
    pages = frame_pages(fr)
    lost = missing_chasers(root) if wizard else []
    orph = orphans(root) if wizard else {}
    n_orph = sum(len(v) for g in orph.values() for v in g.values())
    grids = grid_changes(root) if wizard else []
    dead = dead_palettes(root, defs) if wizard else []
    hide = visible_infrastructure(root)
    lock = unlocked(root) if wizard else []
    caps = blank_gobo_buttons(root, defs) if wizard else []
    panic = panic_missing_pages(root) if wizard else []
    steps = [
        {"id": "chasers", "count": len(lost),
         "items": [c["name"] for c in lost]},
        {"id": "palettes", "count": len(dead),
         "items": [f"{d['name']} ({len(d['fixtures'])} fixture(s))" for d in dead]},
        {"id": "buttons", "count": n_orph + len(lost),
         "items": [f"{g}: {row} — " + ", ".join((f.get('Name') or '').split(DASH, 1)[-1] for f in fns)
                   for g, rows in orph.items() for row, fns in rows.items()]
         + [f"{c['group']}: Effects — {c['name'].split(DASH, 1)[-1]} (rebuilt)" for c in lost],
         "pages": sorted(set(orph) | {c["group"] for c in lost}),
         "no_page": sorted(g for g in set(orph) | {c["group"] for c in lost} if g not in pages)},
        {"id": "grids", "count": len(grids),
         "items": [f"{g['name']}: {g['now'][0]}×{g['now'][1]} → {g['new'][0]}×{g['new'][1]}" for g in grids]},
        {"id": "hide", "count": len(hide), "items": [f"fixture {i}" for i in hide]},
        {"id": "lock", "count": len(lock), "items": []},
        {"id": "panic", "count": len(panic) if fr is not None else 0,
         "items": [f"page {p + 1}" for p in panic]},
        {"id": "captions", "count": len(caps), "items": [c["caption"] for c in caps]},
    ]
    steps.sort(key=lambda st: STEPS.index(st["id"]))
    return {"wizard": wizard, "frame": fr is not None, "pages": pages,
            "steps": steps, "defaults": list(DEFAULT_STEPS)}


# ═════════════════════════════════════════════════════════════════════════════
# repair
# ═════════════════════════════════════════════════════════════════════════════

def _max_fid(root) -> int:
    return max([int(f.get("ID")) for f in _fns(root) if (f.get("ID") or "").isdigit()] + [-1])


def _insert_function(root, fn: ET.Element) -> None:
    eng = _eng(root)
    last = max([i for i, c in enumerate(list(eng)) if c.tag in ("Function", "Palette", "FixtureGroup", "Fixture")]
               + [-1])
    eng.insert(last + 1, fn)


def _chaser(fid: str, name: str, path: str, steps: List[str], fade: int, hold: int) -> ET.Element:
    """A looping chaser, common timing, written like QLC+'s own."""
    fn = ET.Element("Function", {"ID": fid, "Type": "Chaser", "Name": name, "Path": path})
    ET.SubElement(fn, "Speed", {"FadeIn": str(fade), "FadeOut": str(fade), "Duration": str(hold)})
    ET.SubElement(fn, "Direction").text = "Forward"
    ET.SubElement(fn, "RunOrder").text = "Loop"
    ET.SubElement(fn, "SpeedModes", {"FadeIn": "Common", "FadeOut": "Common", "Duration": "Common"})
    for n, s in enumerate(steps):
        ET.SubElement(fn, "Step", {"Number": str(n), "FadeIn": str(fade), "Hold": str(hold),
                                   "FadeOut": str(fade)}).text = s
    return fn


def _rect(w: ET.Element) -> Optional[Tuple[int, int, int, int]]:
    st = w.find("WindowState")
    if st is None:
        return None
    try:
        return (int(st.get("X", 0)), int(st.get("Y", 0)), int(st.get("Width", 0)), int(st.get("Height", 0)))
    except ValueError:
        return None


def _overlap(a, b) -> bool:
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])


class _FramePage:
    """Free cells of one page of the wizard frame (85 px buttons, 20 px gap)."""

    def __init__(self, frame: ET.Element, page: int):
        self.frame, self.page = frame, page
        fw = _rect(frame) or (0, 0, 1370, 1045)
        self.w, self.h = fw[2], fw[3]
        self.rects = [r for c in frame if c.tag not in ("WindowState", "Multipage", "Shortcut")
                      and c.find("WindowState") is not None and _page_of(c) == page
                      for r in [_rect(c)] if r]

    def cells(self, below_nav: bool = True) -> List[Tuple[int, int]]:
        """Button cells of the page; the first row (the wizard's page buttons
        and Blackout) is left alone unless *below_nav* is False."""
        top = min((r[1] for r in self.rects), default=MARGIN + FRAME_HEADER)
        out = []
        y = top + (BUTTON + GAP if below_nav and self.rects else 0)
        while y + BUTTON <= self.h - MARGIN:
            x = MARGIN
            while x + BUTTON <= self.w - MARGIN:
                out.append((x, y))
                x += BUTTON + GAP
            y += BUTTON + GAP
        return out

    def take(self, n: int) -> List[Tuple[int, int]]:
        """*n* free cells, side by side on one line when possible, else the
        first free cells in reading order."""
        cells = [c for c in self.cells() if not any(_overlap((c[0], c[1], BUTTON, BUTTON), r)
                                                       for r in self.rects)]
        rows: Dict[int, List[Tuple[int, int]]] = {}
        for c in cells:
            rows.setdefault(c[1], []).append(c)
        pick: List[Tuple[int, int]] = []
        for y in sorted(rows):
            run: List[Tuple[int, int]] = []
            for c in rows[y]:
                if run and c[0] != run[-1][0] + BUTTON + GAP:
                    run = []
                run.append(c)
                if len(run) == n:
                    pick = run
                    break
            if pick:
                break
        if not pick:
            pick = cells[:n]
        for c in pick:
            self.rects.append((c[0], c[1], BUTTON, BUTTON))
        return pick


def _button(vc: ET.Element, caption: str, fid: str, page: int, x: int, y: int,
            visible: bool, flash: bool = False) -> ET.Element:
    from core import vc_ops
    attrs = {"Caption": caption, "ID": str(vc_ops._next_id(vc))}
    if page:
        attrs["Page"] = str(page)
    b = ET.Element("Button", attrs)
    ET.SubElement(b, "WindowState", {"Visible": "True" if visible else "False", "X": str(x),
                                     "Y": str(y), "Width": str(BUTTON), "Height": str(BUTTON)})
    app = ET.SubElement(b, "Appearance")
    ET.SubElement(app, "BackgroundColor").text = WIZARD_BG
    ET.SubElement(b, "Function", {"ID": fid})
    ET.SubElement(b, "Action").text = "Flash" if flash else "Toggle"
    return b


def _caption(fn: ET.Element) -> str:
    return (fn.get("Name") or "").split(DASH, 1)[-1][:32]


def _current_page(fr: ET.Element) -> int:
    mp = fr.find("Multipage")
    try:
        return int(mp.get("CurrentPage", "0")) if mp is not None else 0
    except ValueError:
        return 0


def _add_to_frame(fr: ET.Element, el: ET.Element) -> None:
    fr.append(el)


def repair(root, defs=None, steps: Iterable[str] = DEFAULT_STEPS) -> Tuple[ET.Element, List[dict]]:
    """Apply the repair *steps* to a copy of *root*.

    Returns ``(new root, actions)``; each action is ``{step, action}``.
    Nothing is removed: the repair only adds functions, buttons and flags,
    and re-lays group grids."""
    if isinstance(root, ET.ElementTree):
        root = root.getroot()
    work = qxw_io.strip_ns(copy.deepcopy(root))
    want = [s for s in STEPS if s in set(steps)]
    acts: List[dict] = []

    def act(step, text):
        acts.append({"step": step, "action": text})

    if not P.is_wizard_show(work) and set(want) - {"hide"}:
        want = [s for s in want if s == "hide"]

    # 1. lost chasers
    new_chasers: List[ET.Element] = []
    if "chasers" in want:
        for c in missing_chasers(work):
            fid = str(_max_fid(work) + 1)
            fn = _chaser(fid, c["name"], c["path"], c["steps"], c["fade"], c["hold"])
            _insert_function(work, fn)
            new_chasers.append(fn)
            act("chasers", f"chaser {fid} '{c['name']}' built from its {len(c['steps'])} step scenes "
                           f"({c['fade']} ms fade, {c['hold']} ms hold)")

    # 2. palettes that do nothing on some fixtures
    if "palettes" in want:
        fns = {f.get("ID"): f for f in _fns(work)}
        for d in dead_palettes(work, defs):
            fn = fns[d["function"]]
            for f, vals in sorted(d["fixtures"].items(), key=lambda kv: _num(kv[0])):
                el = next((v for v in fn.findall("FixtureVal") if v.get("ID") == f), None)
                if el is None:
                    el = ET.Element("FixtureVal", {"ID": f})
                    # FixtureVal before FixtureGroup / Palette, as QLC+ writes it
                    first = next((i for i, c in enumerate(list(fn))
                                  if c.tag in ("FixtureGroup", "Palette")), len(list(fn)))
                    fn.insert(first, el)
                    pairs = {}
                else:
                    nums = [x.strip() for x in (el.text or "").split(",") if x.strip()]
                    pairs = {int(a): int(b) for a, b in zip(nums[0::2], nums[1::2])
                             if a.isdigit() and b.isdigit()}
                pairs.update(vals)
                el.text = P.fixture_val_text(pairs)
            act("palettes", f"'{d['name']}': values for {len(d['fixtures'])} fixture(s) "
                            f"that palette '{d['palette']}' leaves untouched")

    # 3. PANIC RESET on every page of the wizard frame
    if "panic" in want and wizard_frame(work) is not None:
        fr = wizard_frame(work)
        vc = work.find("VirtualConsole")
        pid = _panic_script(work)
        if pid is None:
            pid = _make_panic(work, defs)
            act("panic", f"created script {pid} 'PANIC RESET' and scene 'Reset: neutral state' "
                         "(stops everything, then every fixture neutral, intensity 0)")
        cur = _current_page(fr)
        for p in panic_missing_pages(work):
            page = _FramePage(fr, p)
            spot = _panic_spot(page)
            if spot is None:
                act("panic", f"page {p + 1}: no room for the PANIC RESET button")
                continue
            b = _button(vc, "PANIC RESET", pid, p, spot[0], spot[1], p == cur)
            b.find("Appearance/BackgroundColor").text = "4294901760"      # red
            _add_to_frame(fr, b)
            act("panic", f"PANIC RESET button on page {p + 1} at {spot[0]},{spot[1]}")

    # 4. buttons for content on no button
    if "buttons" in want:
        fr = wizard_frame(work)
        pages = frame_pages(fr)
        vc = work.find("VirtualConsole")
        orph = orphans(work)
        cur = _current_page(fr) if fr is not None else 0
        for g in sorted(orph, key=lambda x: pages.get(x, 999)):
            if fr is None or g not in pages:
                continue
            page = _FramePage(fr, pages[g])
            for row in ROW_ORDER:
                fns = orph[g].get(row) or []
                if not fns:
                    continue
                cells = page.take(len(fns))
                placed = 0
                for fn, (x, y) in zip(fns, cells):
                    _add_to_frame(fr, _button(vc, _caption(fn), fn.get("ID"), pages[g], x, y,
                                              pages[g] == cur))
                    placed += 1
                if placed:
                    act("buttons", f"page '{g}': {row} — " + ", ".join(_caption(f) for f in fns[:placed]))
                if placed < len(fns):
                    act("buttons", f"page '{g}': no room for " + ", ".join(_caption(f) for f in fns[placed:]))

    # 5. group grids from the stage
    if "grids" in want:
        groups = {g.get("ID"): g for g in _eng(work).findall("FixtureGroup")}
        for ch in grid_changes(work):
            g = groups[ch["id"]]
            heads = {h.get("Fixture"): (h.text or "0") for h in g.findall("Head")}
            for h in g.findall("Head"):
                g.remove(h)
            sz = g.find("Size")
            if sz is None:
                sz = ET.SubElement(g, "Size")
            sz.set("X", str(ch["new"][0]))
            sz.set("Y", str(ch["new"][1]))
            for x, y, f in sorted(_grid_cells(ch["rows"]), key=lambda c: (c[1], c[0])):
                ET.SubElement(g, "Head", {"X": str(x), "Y": str(y), "Fixture": f}).text = heads.get(f, "0")
            act("grids", f"group '{ch['name']}': grid {ch['now'][0]}×{ch['now'][1]} → "
                         f"{ch['new'][0]}×{ch['new'][1]}, rows front to back, columns as they hang")

    # 6. hide the page dimmers in 2D/3D
    if "hide" in want:
        ids = visible_infrastructure(work)
        for it in _fx_items(work):
            if it.get("ID") in ids:
                it.set("Hidden", "True")
        if ids:
            act("hide", f"{len(ids)} page-switch fixture(s) hidden in the 2D and 3D views")

    # 7. lock placed fixtures
    if "lock" in want:
        ids = unlocked(work)
        for it in _fx_items(work):
            if it.get("ID") in ids:
                it.set("Locked", "True")
        if ids:
            act("lock", f"{len(ids)} fixture(s) locked in the 2D and 3D views (QLC+ 5.3)")

    # 8. captions for the gobo picture buttons (off by default)
    if "captions" in want:
        by_id = {w.get("ID"): w for w in work.iter("Button")}
        n = 0
        for c in blank_gobo_buttons(work, defs):
            w = by_id.get(c["widget"])
            if w is not None:
                w.set("Caption", c["caption"])
                n += 1
        if n:
            act("captions", f"{n} gobo button(s) captioned with the gobo's name")

    return work, acts


def _panic_spot(page: _FramePage) -> Optional[Tuple[int, int]]:
    """Left of the wizard's Blackout button when free, else the first free cell."""
    top_right = min(page.rects, key=lambda r: (r[1], -r[0]), default=None)
    if top_right is not None and top_right[0] > page.w / 2:
        cand = (top_right[0] - BUTTON - GAP, top_right[1])
        if cand[0] >= MARGIN and not any(_overlap((cand[0], cand[1], BUTTON, BUTTON), x)
                                         for x in page.rects):
            page.rects.append((cand[0], cand[1], BUTTON, BUTTON))
            return cand
    got = page.take(1)
    return got[0] if got else None


def _make_panic(root, defs) -> str:
    """PANIC RESET script + neutral scene, the Doctor's D008 recipe."""
    from core.doctor import checks, fixes
    ws = checks._Workspace(root, checks._normalise_defs(defs))
    sid = str(fixes._max_fid(root) + 1)
    scene = ET.Element("Function", {"ID": sid, "Type": "Scene", "Name": "Reset: neutral state"})
    ET.SubElement(scene, "Speed", {"FadeIn": "0", "FadeOut": "0", "Duration": "0"})
    for fxid in ws.fixtures:
        vals = fixes._neutral_values(ws, fxid, intensity_zero=True)
        if vals:
            ET.SubElement(scene, "FixtureVal", {"ID": fxid}).text = fixes._fmt(vals)
    fixes._insert_function(root, scene)
    return fixes._panic_script(root, sid)
