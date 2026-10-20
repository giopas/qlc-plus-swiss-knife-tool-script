"""
core/stage_layouts.py — stage layouts (v3.8.0)
==============================================
A *stage layout* is the stage and the band as a thing you keep: the stage type
and size, the drum riser and backline, the members by role (vocals, guitar,
bass, drums, keys) and where they stand, wedges, a backdrop or curtain, and
the walkways.  A new show starts from one, the way *My kit* is the base of
tonight's kit in Cabling.

Idea (not code) from the stage layouts and band members of mjcmatrix's fork of
QLC+ (https://github.com/mjcmatrix/qlcplus/wiki, by Matt C).

What goes into a show is what upstream QLC+ 5 stores: the stage type and size
and the meshes with their places (``<Monitor><MeshItem>``).  Everything that
reads the stage then follows by itself: the Look Builder's *places on the
stage* aim at the members, Cabling's band floor is the footprint of the
meshes.  Colours and walkways are not stored by QLC+, so they stay in the
layout (the walkways can be handed to Cabling's plan: :func:`walkways_for`).

A layout is JSON (``qsk-stage-layout/1``)::

    {"name": "Full band", "description": "...",
     "stage": {"type": 2, "w": 8, "h": 4, "d": 6},                # metres
     "items": [{"role": "drums", "name": "Drums", "model": "generic/cube.obj",
                "x": 0, "z": 1500, "bottom": 400,                # mm: from the centre line,
                "rot": [0, 0, 0], "scale": [0.3, 0.45, 0.3],      #     from the back edge, above the floor
                "size": [600, 900, 600], "colour": "#336699"}],   # size: footprint box, mm (optional)
     "walkways": [{"x0": -3000, "z0": 5000, "x1": 3000, "z1": 5600, "ramp": false, "label": ""}]}

A model is ``generic/cube.obj`` (QLC+'s own block) or a file of your mesh
folders, by its path inside the folder (never an absolute path, so a layout
can be shared).  When a model is not on this computer a block of the same
size stands in its place, and the report says so.
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Dict, List, Optional

from core import stage3d as s3

FORMAT = "qsk-stage-layout/1"
CUBE = "generic/cube.obj"
CUBE_MM = 2000.0                       # QLC+'s generic cube is 2 m on a side
ROLES = ("vocals", "guitar", "bass", "drums", "keys", "riser", "backline", "wedge", "backdrop", "walkway", "other")
MEMBER_ROLES = ("vocals", "guitar", "bass", "drums", "keys")
MAX_ITEMS = 120
MAX_FILE = 1024 * 1024

# what a mesh is, from its name (first match wins)
_ROLE_WORDS = [
    ("riser", re.compile(r"\b(riser|podium|platform|deck)\b", re.I)),
    ("wedge", re.compile(r"\b(wedge|monitor|foldback)\b", re.I)),
    ("backdrop", re.compile(r"\b(backdrop|curtain|banner|drape|screen|backline wall|led wall)\b", re.I)),
    ("walkway", re.compile(r"\b(walkway|catwalk|ramp|runway)\b", re.I)),
    ("backline", re.compile(r"\b(amp|amps|cab|cabinet|stack|backline|speaker|case|rack)\b", re.I)),
    ("vocals", re.compile(r"\b(sing\w*|vocal\w*|voice|lead|front ?(man|woman)|mc|choir|backing)\b", re.I)),
    ("drums", re.compile(r"\b(drum\w*|percussion\w*)\b", re.I)),
    ("bass", re.compile(r"\bbass\w*\b", re.I)),
    ("guitar", re.compile(r"\b(guitar\w*|gtr)\b", re.I)),
    ("keys", re.compile(r"\b(key\w*|synth\w*|piano|organ)\b", re.I)),
]


class LayoutError(ValueError):
    pass


def user_dir() -> str:
    """Your own layouts (files made by *Save as layout* or imported from the Library)."""
    return os.environ.get("QSK_STAGE_LAYOUTS") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "stage_layouts")


def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "").strip()).strip("_")[:60]


def role_of(name: str, model: str = "") -> str:
    """The role a mesh plays, from its name (else its file's name)."""
    for text in (name or "", os.path.splitext(os.path.basename(model or ""))[0].replace("_", " ")):
        for role, rx in _ROLE_WORDS:
            if rx.search(text):
                return role
    return "other"


# ─────────────────────────────────────────────────────────────────────────────
# clean (also the check for a layout that comes from the Library)
# ─────────────────────────────────────────────────────────────────────────────

def _num(v, lo, hi, what, default=None):
    if v in (None, ""):
        if default is None:
            raise LayoutError(f"{what} is missing")
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise LayoutError(f"{what} is not a number")
    if not lo <= f <= hi:
        raise LayoutError(f"{what} must be between {lo:g} and {hi:g}")
    return f


def _vec(v, what, lo, hi, default):
    if v in (None, ""):
        return list(default)
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise LayoutError(f"{what} needs three numbers")
    return [round(_num(x, lo, hi, what), 4) for x in v]


def _model(m) -> str:
    m = str(m or CUBE).strip().replace("\\", "/")
    if not m:
        return CUBE
    if m.startswith("/") or re.match(r"^[A-Za-z]:", m) or ".." in m.split("/"):
        raise LayoutError("a model is a name inside your mesh folder, not a path on this computer")
    if not m.lower().endswith(".obj"):
        raise LayoutError("a model is an .obj file")
    return m[:200]


def _colour(c) -> str:
    c = str(c or "").strip()
    return c.lower() if re.fullmatch(r"#[0-9a-fA-F]{6}", c) else ""


def clean(d: dict, *, name: str = "") -> dict:
    """The layout as stored; :class:`LayoutError` says what is wrong."""
    if not isinstance(d, dict):
        raise LayoutError("not a stage layout")
    nm = str(name or d.get("name") or "").strip()[:80]
    if not nm:
        raise LayoutError("the layout needs a name")
    st = d.get("stage") or {}
    if not isinstance(st, dict):
        raise LayoutError("the stage is not valid")
    stage = {"type": int(_num(st.get("type", 2), 0, len(s3.STAGE_TYPES) - 1, "the stage type", 2)),
             "w": round(_num(st.get("w"), 1, 100, "the stage width (m)", 8.0), 3),
             "h": round(_num(st.get("h"), 1, 30, "the stage height (m)", 4.0), 3),
             "d": round(_num(st.get("d"), 1, 100, "the stage depth (m)", 6.0), 3)}
    raw = d.get("items") or []
    if not isinstance(raw, list):
        raise LayoutError("the items are not a list")
    if len(raw) > MAX_ITEMS:
        raise LayoutError(f"a layout holds at most {MAX_ITEMS} items")
    items = []
    for i, it in enumerate(raw, 1):
        if not isinstance(it, dict):
            raise LayoutError(f"item {i} is not valid")
        try:
            model = _model(it.get("model"))
            iname = str(it.get("name") or "").strip()[:60]
            role = str(it.get("role") or "").strip().lower() or role_of(iname, model)
            if role not in ROLES:
                role = "other"
            row = {"role": role, "name": iname or role.capitalize(), "model": model,
                   "x": round(_num(it.get("x", 0), -100000, 100000, "x"), 1),
                   "z": round(_num(it.get("z", 0), -100000, 100000, "z"), 1),
                   "bottom": round(_num(it.get("bottom", 0), -5000, 50000, "bottom"), 1),
                   "rot": _vec(it.get("rot"), "rot", -360, 360, (0, 0, 0)),
                   "scale": _vec(it.get("scale"), "scale", 0.001, 1000, (1, 1, 1))}
            if it.get("size") not in (None, ""):
                row["size"] = [round(v) for v in _vec(it.get("size"), "size", 1, 100000, (1, 1, 1))]
            if _colour(it.get("colour")):
                row["colour"] = _colour(it.get("colour"))
        except LayoutError as e:
            raise LayoutError(f"item {i} ({it.get('name') or '?'}): {e}")
        items.append(row)
    walks = []
    for i, w in enumerate(d.get("walkways") or [], 1):
        if not isinstance(w, dict):
            raise LayoutError(f"walkway {i} is not valid")
        try:
            r = {"x0": _num(w.get("x0"), -100000, 100000, "x0"), "z0": _num(w.get("z0"), -100000, 100000, "z0"),
                 "x1": _num(w.get("x1"), -100000, 100000, "x1"), "z1": _num(w.get("z1"), -100000, 100000, "z1")}
        except LayoutError as e:
            raise LayoutError(f"walkway {i}: {e}")
        r = {k: round(v, 1) for k, v in r.items()}
        r["ramp"] = bool(w.get("ramp"))
        r["label"] = str(w.get("label") or "")[:40]
        walks.append(r)
    out = {"format": FORMAT, "name": nm, "description": str(d.get("description") or "")[:300],
           "stage": stage, "items": items}
    if walks[:20]:
        out["walkways"] = walks[:20]
    if len(json.dumps(out)) > MAX_FILE:
        raise LayoutError("the layout is too large")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# built-in starting points (blocks of QLC+'s own cube: they work everywhere)
# ─────────────────────────────────────────────────────────────────────────────

def _block(role, name, x, z, w, d, h, bottom=0, colour=""):
    """A block *w* × *d* × *h* mm standing at *x* (from the centre) and *z* (from the back)."""
    it = {"role": role, "name": name, "model": CUBE, "x": x, "z": z, "bottom": bottom,
          "rot": [0, 0, 0], "scale": [w / CUBE_MM, h / CUBE_MM, d / CUBE_MM], "size": [w, h, d]}
    if colour:
        it["colour"] = colour
    return it


def _person(role, name, x, z, bottom=0):
    return _block(role, name, x, z, 500, 500, 1750, bottom)


def _builtin() -> List[dict]:
    full = {
        "name": "Full band", "description": "Singer, guitar, bass, keys and drums on a riser, backline, two wedges and a backdrop.",
        "stage": {"type": 2, "w": 8, "h": 4, "d": 6},
        "items": [
            _block("riser", "Riser", 0, 1100, 2400, 2000, 400),
            _person("drums", "Drums", 0, 1100, 400),
            _person("bass", "Bass", 1900, 2600),
            _person("guitar", "Guitar", -1900, 2600),
            _person("keys", "Keys", 3000, 2000),
            _person("vocals", "Singer", 0, 3400),
            _block("backline", "Amp 1", -2200, 700, 700, 450, 800),
            _block("backline", "Amp 2", 2200, 700, 700, 450, 800),
            _block("wedge", "Wedge 1", -600, 4200, 600, 450, 350),
            _block("wedge", "Wedge 2", 600, 4200, 600, 450, 350),
            _block("backdrop", "Backdrop", 0, 150, 7600, 100, 2800, 0, "#101018"),
        ]}
    acoustic = {
        "name": "Acoustic", "description": "Two players and a singer at the front of a small stage, no riser.",
        "stage": {"type": 1, "w": 5, "h": 3, "d": 4},
        "items": [
            _person("vocals", "Singer", 0, 2600),
            _person("guitar", "Guitar", -1100, 2200),
            _person("keys", "Keys", 1300, 2000),
            _block("wedge", "Wedge 1", -500, 3300, 600, 450, 350),
            _block("wedge", "Wedge 2", 600, 3300, 600, 450, 350),
        ]}
    festival = {
        "name": "Festival", "description": "A wide, deep stage with a drum riser, side fills, a backdrop and a walkway to the front.",
        "stage": {"type": 3, "w": 12, "h": 6, "d": 8},
        "items": [
            _block("riser", "Riser", 0, 1500, 3000, 2400, 600),
            _person("drums", "Drums", 0, 1500, 600),
            _person("bass", "Bass", 2600, 3600),
            _person("guitar", "Guitar", -2600, 3600),
            _person("keys", "Keys", 4400, 2800),
            _person("vocals", "Singer", 0, 5200),
            _block("backline", "Amp 1", -3200, 900, 800, 500, 900),
            _block("backline", "Amp 2", 3200, 900, 800, 500, 900),
            _block("wedge", "Wedge 1", -1100, 6200, 600, 450, 350),
            _block("wedge", "Wedge 2", 0, 6200, 600, 450, 350),
            _block("wedge", "Wedge 3", 1100, 6200, 600, 450, 350),
            _block("backdrop", "Backdrop", 0, 150, 11600, 100, 4000, 0, "#101018"),
        ],
        "walkways": [{"x0": -600, "z0": 6700, "x1": 600, "z1": 8000, "ramp": True, "label": "Front walkway"}]}
    return [clean(x) for x in (full, acoustic, festival)]


def builtin() -> List[dict]:
    return copy.deepcopy(_builtin())


def _summary(lay: dict) -> dict:
    roles: Dict[str, int] = {}
    for it in lay["items"]:
        roles[it["role"]] = roles.get(it["role"], 0) + 1
    return {"items": len(lay["items"]), "roles": roles, "members": sum(roles.get(r, 0) for r in MEMBER_ROLES),
            "walkways": len(lay.get("walkways") or []), "stage": lay["stage"]}


def list_layouts() -> List[dict]:
    """Built-in layouts first, then yours: ``[{id, label, description, builtin, items, roles, members, walkways, stage}]``."""
    out = [{"id": "builtin:" + slug(b["name"]).lower(), "label": b["name"], "description": b["description"],
            "builtin": True, **_summary(b)} for b in _builtin()]
    try:
        names = sorted(f for f in os.listdir(user_dir()) if f.endswith(".json"))
    except OSError:
        names = []
    for fn in names:
        lay = _read(os.path.join(user_dir(), fn))
        if lay:
            out.append({"id": fn[:-5], "label": lay["name"], "description": lay["description"],
                        "builtin": False, **_summary(lay)})
    return out


def _read(path: str) -> Optional[dict]:
    try:
        if os.path.getsize(path) > MAX_FILE:
            return None
        with open(path, encoding="utf-8") as fh:
            return clean(json.load(fh))
    except (OSError, ValueError):
        return None


def get(layout_id: str) -> Optional[dict]:
    """A layout by its id (``builtin:full_band`` or the file name of yours) or by its name."""
    key = str(layout_id or "").strip()
    if not key:
        return None
    for b in _builtin():
        if key == "builtin:" + slug(b["name"]).lower() or key.lower() == b["name"].lower():
            return b
    if re.fullmatch(r"[A-Za-z0-9_-]{1,60}", key):
        lay = _read(os.path.join(user_dir(), key + ".json"))
        if lay:
            return lay
    for row in list_layouts():
        if not row["builtin"] and row["label"].lower() == key.lower():
            return _read(os.path.join(user_dir(), row["id"] + ".json"))
    return None


def reserved(name: str) -> bool:
    return any(b["name"].lower() == name.strip().lower() for b in _builtin())


def save(layout: dict, name: str = "") -> dict:
    """Keep a layout as yours (replacing one of the same name).  Built-in names are refused."""
    lay = clean(layout, name=name)
    if reserved(lay["name"]):
        raise LayoutError(f"'{lay['name']}' is a built-in layout: choose another name")
    sid = slug(lay["name"]) or "layout"
    os.makedirs(user_dir(), exist_ok=True)
    with open(os.path.join(user_dir(), sid + ".json"), "w", encoding="utf-8") as fh:
        json.dump(lay, fh, indent=1, ensure_ascii=False)
    return {"id": sid, "layout": lay}


def delete(layout_id: str) -> bool:
    key = str(layout_id or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", key):
        return False
    try:
        os.remove(os.path.join(user_dir(), key + ".json"))
        return True
    except OSError:
        return False


def own() -> Dict[str, dict]:
    """``{name: layout}`` of yours (for the Library)."""
    out = {}
    for row in list_layouts():
        if not row["builtin"]:
            lay = _read(os.path.join(user_dir(), row["id"] + ".json"))
            if lay:
                out[lay["name"]] = lay
    return out


# ─────────────────────────────────────────────────────────────────────────────
# from a show / into a show
# ─────────────────────────────────────────────────────────────────────────────

def _model_name(res: str, dirs) -> str:
    """The model as a layout keeps it: the cube, or the path inside a mesh folder."""
    r = (res or "").replace("\\", "/")
    if r == CUBE or r.endswith("/" + CUBE):
        return CUBE
    for d in dirs:
        base = os.path.abspath(d).replace("\\", "/").rstrip("/") + "/"
        if r.startswith(base):
            return r[len(base):]
    return os.path.basename(r) or CUBE


def from_root(root, name: str, *, description: str = "", qxw_path: str = "", mesh_dirs=None,
              include_hidden: bool = False) -> dict:
    """*Save as layout*: the stage and the meshes of the show as a layout.  A mesh
    whose model file is missing has no place and is left out (``skipped``).
    Returns ``{layout, skipped}``."""
    dirs = list(mesh_dirs if mesh_dirs is not None else s3.library_dirs())
    st = s3.stage(root)
    items, skipped = [], []
    for m in s3.meshes(root, qxw_path, dirs):
        if m.get("hidden") and not include_hidden:
            continue
        p = m.get("place")
        if not p:
            skipped.append(m["label"])
            continue
        model = _model_name(m["res"], dirs)
        iname = m["label"]
        row = {"role": role_of(iname, model), "name": iname, "model": model,
               "x": p["x"] - st["w"] * 500, "z": p["z"], "bottom": p["bottom"],
               "rot": m["rot"], "scale": m["scale"], "size": [max(p["w"], 1), max(p["h"], 1), max(p["d"], 1)]}
        items.append(row)
    lay = clean({"name": name, "description": description,
                 "stage": {"type": st["type"], "w": st["w"], "h": st["h"], "d": st["d"]}, "items": items})
    return {"layout": lay, "skipped": skipped}


def _find_model(model: str, dirs, qxw_path: str) -> Optional[str]:
    """The *Res* to write for a model, or None when this computer does not have it."""
    if model == CUBE:
        return CUBE
    path = s3.resolve(model, qxw_path, dirs)
    if path:
        return path
    base = os.path.basename(model).lower()
    for d in dirs:
        for dp, _sub, files in os.walk(d):
            for f in files:
                if f.lower() == base:
                    return os.path.join(dp, f)
    return None


def apply(root, layout: dict, *, qxw_path: str = "", mesh_dirs=None, mode: str = "replace",
          set_stage: bool = True) -> dict:
    """Put a layout into the show's 3D stage (*root*, a working copy without namespaces).

    *mode* ``replace`` removes the meshes that are there first, ``add`` keeps them.
    *set_stage* takes the layout's stage type and size; without it the stage stays
    and the members keep their distance from the centre line and the back edge.
    Returns ``{added, replaced, stage, missing: [model names], outside: [names], colours: n, walkways: n}``.
    """
    if mode not in ("replace", "add"):
        raise LayoutError("mode is replace or add")
    lay = clean(layout)
    dirs = list(mesh_dirs if mesh_dirs is not None else s3.library_dirs())
    kw = {"qxw_path": qxw_path, "mesh_dirs": dirs}
    removed = 0
    if mode == "replace":
        mon = s3._monitor(root)
        for el in list(mon.findall("MeshItem")) if mon is not None else []:
            mon.remove(el)
            removed += 1
    if set_stage:
        s = lay["stage"]
        s3.set_stage(root, type=s["type"], w=s["w"], h=s["h"], d=s["d"], keep_meshes=(mode == "add"), **kw)
    st = s3.stage(root)
    added, missing, outside = [], [], []
    for it in lay["items"]:
        res = _find_model(it["model"], dirs, qxw_path)
        rot, scale = it["rot"], it["scale"]
        if res is None:                       # the file is not here: a block of the same size
            if it["model"] not in missing:
                missing.append(it["model"])
            res = CUBE
            sz = it.get("size") or [500, 1000, 500]
            rot, scale = [0, 0, 0], [sz[0] / CUBE_MM, sz[1] / CUBE_MM, sz[2] / CUBE_MM]
        x = st["w"] * 500 + it["x"]
        z = it["z"]
        r = s3.add_mesh(root, res, name=it["name"], **kw)
        s3.set_transform(root, r["id"], rot=rot, scale=scale, keep_floor=True, **kw)
        s3.move_to(root, r["id"], x=x, z=z, bottom=it["bottom"], **kw)
        added.append(r["id"])
        if not (0 <= x <= st["w"] * 1000 and 0 <= z <= st["d"] * 1000):
            outside.append(it["name"])
    return {"added": len(added), "ids": added, "replaced": removed, "stage": s3.stage(root),
            "missing": missing, "outside": outside,
            "colours": sum(1 for i in lay["items"] if i.get("colour")),
            "walkways": len(lay.get("walkways") or [])}


def walkways_for(layout: dict, stage_w_mm: float) -> List[dict]:
    """The layout's walkways as Cabling's plan wants them: ``x`` from the stage's
    left edge (the layout keeps them from the centre line), ``z`` from the back."""
    lay = clean(layout)
    out = []
    for w in lay.get("walkways") or []:
        xa, xb = sorted((stage_w_mm / 2 + w["x0"], stage_w_mm / 2 + w["x1"]))
        za, zb = sorted((w["z0"], w["z1"]))
        out.append({"x0": round(xa), "z0": round(za), "x1": round(xb), "z1": round(zb),
                    "ramp": bool(w["ramp"]), "label": w.get("label") or ""})
    return out
