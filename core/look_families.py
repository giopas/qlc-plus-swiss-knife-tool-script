"""
core/look_families.py — what a fixture group can do, its role, and the looks
and movement effects of the Look Builder's families (3.3.0).

The QLC+ 5.3 Show Wizard sorts what it makes into families (Colour,
Intensity, Movement, Matrix) and greys out what no group can do.  This module
gives the Look Builder the same picture:

``group_caps``   what a group's fixtures can do, read from their definitions:
                 colour mixing, a colour wheel, gobos, a strobe, pan/tilt, a
                 grid for RGB matrices.
``suggest_role`` one of the wizard's nine roles from the group's name first,
                 then from what it can do.
``gobo_list``    the static gobos of a group (not the shake or scroll slots).
``place_values`` pan/tilt channel values that aim each moving head at a point
                 on the stage, the way a QLC+ Position3D palette does.
``efx``          a QLC+ EFX function (fly out and in, circle, figure eight,
                 audience sweep), in the form QLC+ 5.2.2 and 5.3 both read.

Swiss Knife's rule stays: every look is a whole state (every channel of its
fixtures set).  Movement effects are EFX, which only move pan and tilt; the
relative ones ride on the aim of the look that is playing.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, Iterable, List, Optional, Tuple

from core import capability_map as cm
from core import palettes as P

# The wizard's roles (stagewizard.h, FixtureRole), in its order
ROLES = ("Key", "Fill", "Back", "Side", "Effect", "Strip", "Blinder", "Hazer", "Floor")

_ROLE_WORDS = (
    ("Blinder", r"blind|strob|audience"),
    ("Back", r"\bback|rear|upstage|behind"),
    ("Key", r"\bfront|\bkey\b|\bspot|downstage"),
    ("Side", r"\bside|\bboom|\bwing|column|\bpar\b|\bpars\b"),
    ("Floor", r"\bfloor|\bground|\bdeck|uplight"),
    ("Strip", r"\bstrip|\bbar\b|\bbars\b|batten|pixel|\bled\s*bar"),
    ("Hazer", r"\bhaz|\bfog|\bsmoke"),
    ("Effect", r"\beffect|\bfx\b|\bbeam|\blaser|\bmoving|\bmover|\bhead"),
    ("Fill", r"\bfill|\bwash"),
)

CAP_LABELS = {
    "mix": "Colour mixing", "wheel": "Colour wheel", "gobo": "Gobo", "strobe": "Strobe",
    "moves": "Moves", "dimmer": "Dimmer", "grid": "Grid",
}

# Movement effects: label, QLC+ algorithm, relative, swing in degrees (pan, tilt),
# propagation, cycle ms
EFX_KINDS = {
    "fly_out": ("Fly out", "Line", False, (0.0, 0.0), "Parallel", 20000),
    "fly_in": ("Fly in", "Line", False, (0.0, 0.0), "Parallel", 20000),
    "circle": ("Circle", "Circle", True, (50.0, 50.0), "Serial", 10000),
    "eight": ("Figure eight", "Eight", True, (50.0, 50.0), "Serial", 10000),
    "sweep": ("Audience sweep", "Line", True, (60.0, 8.0), "Parallel", 10000),
}
FLY_HEIGHT, FLY_X, FLY_Y = 70, 83, 75       # the wizard's fly values, raw DMX


# ─────────────────────────────────────────────────────────────────────────────
# capabilities
# ─────────────────────────────────────────────────────────────────────────────

def _layout(fx: dict):
    d = fx.get("def")
    if not d:
        return []
    return cm._layout(d, fx["mode"])


def fixture_caps(fx: dict) -> set:
    """What one fixture can do (see :data:`CAP_LABELS`); empty without a definition."""
    lay = _layout(fx)
    if not lay:
        return {"dimmer"} if fx.get("generic") else set()
    out = set()
    roles = {cm._role(cd) for _, _, cd in lay}
    if all(r in roles for r in ("Red", "Green", "Blue")):
        out.add("mix")
    if any(cm._is_wheel(cd) for _, _, cd in lay):
        out.add("wheel")
    if any(_static_gobos(cd) for _, _, cd in lay):
        out.add("gobo")
    if any(cd.get("group") == "Shutter" and any(cm._shutter_kind(c) == "strobe"
                                                 for c in cd.get("capabilities") or [])
           for _, _, cd in lay):
        out.add("strobe")
    if any((cd.get("group") or "") in ("Pan", "Tilt") for _, _, cd in lay):
        out.add("moves")
    if "Dimmer" in roles or "mix" in out:
        out.add("dimmer")
    return out


def group_caps(fxs: List[dict], grid: Optional[Tuple[int, int]] = None) -> dict:
    """``{caps: [...], all: [...], model, movers: [ids], strobes: [ids], gobos}``
    for the fixtures *fxs* of a group.  ``caps`` holds what at least one
    fixture can do, ``all`` what every fixture with a definition can do."""
    per = {fx["id"]: fixture_caps(fx) for fx in fxs}
    known = [c for c in per.values() if c]
    caps = set().union(*known) if known else set()
    every = set.intersection(*known) if known else set()
    if grid and grid[0] * grid[1] >= 2 and caps & {"mix", "dimmer"}:
        caps.add("grid")
        every.add("grid")
    models: Dict[str, int] = {}
    for fx in fxs:
        models[fx["model"]] = models.get(fx["model"], 0) + 1
    model = ", ".join(f"{n} × {m}" for m, n in models.items())
    return {"caps": [c for c in CAP_LABELS if c in caps], "all": [c for c in CAP_LABELS if c in every],
            "labels": [CAP_LABELS[c] for c in CAP_LABELS if c in caps],
            "model": model,
            "movers": [f for f, c in per.items() if "moves" in c],
            "strobes": [f for f, c in per.items() if "strobe" in c],
            "gobos": len(gobo_list(fxs))}


def suggest_role(name: str, caps: Iterable[str]) -> str:
    """One of :data:`ROLES`: from the group's name, else from what it can do."""
    n = (name or "").lower().replace("_", " ")
    for role, rx in _ROLE_WORDS:
        if re.search(rx, n):
            return role
    caps = set(caps)
    if "moves" in caps:
        return "Effect"
    if "strobe" in caps and "mix" not in caps:
        return "Blinder"
    if "grid" in caps and "mix" in caps:
        return "Strip"
    return "Fill" if "mix" in caps or "wheel" in caps else "Key"


# Families the wizard pre-ticks for a role (used by "Start from" on the screen)
ROLE_FAMILIES = {
    "Key": ("colour", "levels", "places"), "Fill": ("colour", "levels"),
    "Back": ("colour", "gobo", "strobe", "efx"), "Side": ("colour", "chase", "matrix"),
    "Effect": ("colour", "gobo", "efx"), "Strip": ("colour", "matrix"),
    "Blinder": ("blinder", "strobe"), "Hazer": (), "Floor": ("colour", "chase"),
}


# ─────────────────────────────────────────────────────────────────────────────
# gobos
# ─────────────────────────────────────────────────────────────────────────────

_NOT_STATIC = re.compile(r"shake|scroll|rotat|rainbow|spin|index|\bfx\b|effect|wobble", re.I)


def _static_gobos(chdef: dict) -> List[dict]:
    """The gobo wheel's static gobos (no open slot, no shake or scroll)."""
    return [c for c in cm._gobo_slots(chdef)
            if not cm._is_open_slot(c) and not _NOT_STATIC.search(c.get("label") or "")
            and (c.get("label") or "").strip().lower() not in ("white", "no gobo")]


def gobo_list(fxs: List[dict]) -> List[str]:
    """Names of the static gobos of the group's largest gobo wheel, in wheel
    order (``Gobo 1``, ``Gobo 2``…, or the definition's own names)."""
    best: List[dict] = []
    for fx in fxs:
        for _, _, cd in _layout(fx):
            g = _static_gobos(cd)
            if len(g) > len(best):
                best = g
    return [(c.get("label") or f"Gobo {k + 1}").strip() for k, c in enumerate(best)]


def gobo_value(fx: dict, n: int) -> Optional[Tuple[int, int]]:
    """``(channel, value)`` that puts static gobo *n* (1-based) on *fx*'s
    wheel; wraps on a smaller wheel; None when it has no gobo wheel."""
    for i, _, cd in _layout(fx):
        g = _static_gobos(cd)
        if g:
            c = g[(n - 1) % len(g)]
            return i, int(c.get("min", 0))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# places on the stage
# ─────────────────────────────────────────────────────────────────────────────

def places(root: ET.Element) -> List[dict]:
    """``[{name, x, y, z}]`` in metres: the stage centre, the audience and each
    musician model placed in Stage & Meshes (as the 3.2.0 upgrade finds them)."""
    from core import upgrade53 as U
    show = U._Show(root, None)
    out = []
    w, _h, d = show.R.stage.grid
    out.append({"name": "Centre", "x": w / 2, "y": 0.0, "z": d / 2})
    out.append({"name": "Audience", "x": w / 2, "y": 0.0, "z": d * U.AUDIENCE_DEPTH})
    from core import stage3d
    seen = {"centre", "audience"}
    for m in stage3d.meshes(root):
        if m.get("hidden"):
            continue
        name = U._mesh_name(m)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        pl = m.get("place")
        if pl:
            x, z = pl["x"] / 1000.0, pl["z"] / 1000.0
        else:
            x, z = m["pos"][0] / 1000.0 + 0.25, m["pos"][2] / 1000.0 + 0.25
        out.append({"name": name, "x": round(min(max(x, 0.0), w), 2), "y": 0.0,
                    "z": round(min(max(z, 0.0), d), 2)})
    return out


def place_values(root: ET.Element, defs, fids: Iterable[str], place: dict) -> Dict[str, Dict[int, int]]:
    """``{fixture id: {pan/tilt channel: value}}`` aiming each moving head of
    *fids* at *place* (``{x, y, z}`` metres), like a QLC+ Position3D palette."""
    R = P.Resolver(root, defs)
    models = [R.models[f] for f in fids if R.models.get(f) is not None]
    val = f"{place['x']:g},{place.get('y', 0):g},{place['z']:g}"
    return P.palette_values(P.Palette("aim", "Position3D", "", val), models, R.stage)


# ─────────────────────────────────────────────────────────────────────────────
# EFX
# ─────────────────────────────────────────────────────────────────────────────

def _swing(degrees: float, max_deg: float) -> int:
    """EFX width/height (raw DMX, ± around the offset) for a swing of *degrees*
    on a fixture whose full DMX range spans *max_deg* (the wizard's rule)."""
    if max_deg <= 0:
        max_deg = 360.0
    return max(1, min(127, int(round(degrees * 127.5 / max_deg))))


def _rotation(root: ET.Element, fid: str) -> Tuple[float, float]:
    mon = root.find("Monitor")
    for it in (mon.findall("FxItem") if mon is not None else []):
        if it.get("ID") == fid:
            try:
                return float(it.get("XRot", 0) or 0), float(it.get("YRot", 0) or 0)
            except ValueError:
                return 0.0, 0.0
    return 0.0, 0.0


def efx(root: ET.Element, fid: int, name: str, path: str, kind: str, movers: List[dict]) -> ET.Element:
    """An EFX function moving *movers* (fixture infos with pan/tilt).

    *kind* is a key of :data:`EFX_KINDS`.  Circle, figure eight and the
    audience sweep are relative: they ride on the aim of the look that is
    playing.  Fly out and in are absolute and set the aim themselves, mirrored
    for a head turned upstage or hanging the other way up, as the wizard does.
    No ``DimmerControl``: QLC+ 5.2.2 doesn't have it."""
    label, algo, relative, (dp, dt), prop, cycle = EFX_KINDS[kind]
    first = movers[0]
    pan_max = cm._range(first["def"], "pan") if first.get("def") else 0.0
    tilt_max = cm._range(first["def"], "tilt") if first.get("def") else 0.0
    fn = ET.Element("Function", {"ID": str(fid), "Type": "EFX", "Name": name, "Path": path})
    n = len(movers)
    for k, fx in enumerate(movers):
        f = ET.SubElement(fn, "Fixture")
        ET.SubElement(f, "ID").text = fx["id"]
        ET.SubElement(f, "Head").text = "0"
        ET.SubElement(f, "Mode").text = "0"
        ET.SubElement(f, "Direction").text = "Backward" if kind == "fly_in" else "Forward"
        ET.SubElement(f, "StartOffset").text = str(k * 360 // n if (kind in ("fly_out", "fly_in") and n) else 0)
    ET.SubElement(fn, "PropagationMode").text = prop
    ET.SubElement(fn, "Speed", {"FadeIn": "1000", "FadeOut": "0", "Duration": str(cycle)})
    ET.SubElement(fn, "Direction").text = "Backward" if kind == "fly_in" else "Forward"
    ET.SubElement(fn, "RunOrder").text = "Loop"
    ET.SubElement(fn, "Algorithm").text = algo
    if kind in ("fly_out", "fly_in"):
        xrot, yrot = _rotation(root, first["id"])
        x_off = 255 - FLY_X if 90.0 < abs(yrot) % 360 < 270.0 else FLY_X
        y_off = 255 - FLY_Y if abs(abs(xrot) % 360 - 180.0) < 90.0 else FLY_Y
        width, height = 0, FLY_HEIGHT
    else:
        x_off = y_off = 127
        width, height = _swing(dp, pan_max), _swing(dt, tilt_max)
    ET.SubElement(fn, "Width").text = str(width)
    ET.SubElement(fn, "Height").text = str(height)
    ET.SubElement(fn, "Rotation").text = "0"
    ET.SubElement(fn, "StartOffset").text = "0"
    ET.SubElement(fn, "IsRelative").text = "1" if relative else "0"
    for axis, off, freq, phase in (("X", x_off, 2, 90), ("Y", y_off, 3, 0)):
        a = ET.SubElement(fn, "Axis", {"Name": axis})
        ET.SubElement(a, "Offset").text = str(off)
        ET.SubElement(a, "Frequency").text = str(freq)
        ET.SubElement(a, "Phase").text = str(phase)
    return fn
