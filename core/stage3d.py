"""
core/stage3d.py — Stage and meshes (WORKPLAN Phase 2.5)
======================================================
Read and place the 3D *meshes* (OBJ models of band members, risers,
truss …) of a QLC+ 5 workspace, and the stage itself.

How QLC+ 5.2 stores and places a mesh (``qmlui/mainview3d.cpp``,
``engine/src/monitorproperties.cpp``)::

    <Monitor …>
      <Grid Width="5" Height="3" Depth="5" Units="0"/>   stage size (m, or ft if Units="1")
      <StageItem>0</StageItem>                            0 simple ground · 1 simple box · 2 rock · 3 theatre
      <MeshItem ID="0" XPos="325" YPos="-755" ZPos="2500"  (always written, mm)
                XRot=".." YRot=".." ZRot=".."             (degrees, only when ≠ 0)
                XScale=".." YScale=".." ZScale=".."       (factor, only when ≠ 1)
                Name=".."                                  (optional)
                Res="/abs/path.obj | generic/cube.obj"/>   (absolute, QLC+ mesh folder, or workspace-relative)

The mesh vertices are **not** re-centred.  QLC+ moves the model by::

    T = (XPos/1000 − gridW/2 + extX/2,  YPos/1000 + extY/2,  ZPos/1000 − gridD/2 + extZ/2)
    world(v) = T + R · (S · v)         R = Rx·Ry·Rz (fromAxesAndAngles), S = scale

where *ext* is the size of the model's bounding box **before** scaling.  So
XPos/YPos/ZPos are not the position of anything you can see: a model whose
feet are at y = 0 in the OBJ (most character models) needs a negative YPos
to stand on the floor.  This module shows and edits what you can see —
the centre of the model on the stage and the height of its lowest point
above the floor — and converts back to XPos/YPos/ZPos.

The floor: the ground slab of *Simple box*, *Rock* and *Theatre* stages has
its top at y = 0; the *Simple ground* slab (0.2 m thick) is centred on 0,
so its top is at y = 0.1 m.  Z grows towards the audience (ZPos 0 = back
edge), X from the left edge as seen from the front.
"""

from __future__ import annotations

import copy
import json
import math
import os
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, List, Optional, Tuple

from core import qxw_io

STAGE_TYPES = ["Simple ground", "Simple box", "Rock stage", "Theatre stage"]
FLOOR_M = {0: 0.1, 1: 0.0, 2: 0.0, 3: 0.0}      # top of the ground slab (m)
FT = 0.3048
# models QLC+ ships (used when the file can't be found here)
BUILTIN_BOUNDS = {"generic/cube.obj": ((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0))}
SYSTEM_MESH_DIRS = [
    "/Applications/QLC+.app/Contents/Resources/Meshes",
    "/Applications/QLC+.app/Contents/Resources/meshes",
    "/Applications/QLC+ 5.app/Contents/Resources/Meshes",
    "/usr/share/qlcplus/meshes", "/usr/local/share/qlcplus/meshes",
    "C:\\QLC+5\\Meshes", "C:\\QLC+\\Meshes",
]

Vec = Tuple[float, float, float]


# ─────────────────────────────────────────────────────────────────────────────
# OBJ files
# ─────────────────────────────────────────────────────────────────────────────

_OBJ_CACHE: Dict[Tuple[str, float], dict] = {}
MAX_SAMPLE = 20000          # vertices kept for exact placement (subsampled above)


def read_obj(path: str) -> dict:
    """Bounding box (and a vertex sample) of an OBJ file:
    ``{"min", "max", "ext", "count", "verts"}`` — cached by path + mtime."""
    key = (os.path.abspath(path), os.path.getmtime(path))
    if key in _OBJ_CACHE:
        return _OBJ_CACHE[key]
    verts: List[Vec] = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith("v "):
                p = line.split()
                try:
                    verts.append((float(p[1]), float(p[2]), float(p[3])))
                except (IndexError, ValueError):
                    continue
    if not verts:
        raise ValueError(f"no vertices in {os.path.basename(path)}")
    mn = tuple(min(v[i] for v in verts) for i in range(3))
    mx = tuple(max(v[i] for v in verts) for i in range(3))
    step = max(1, len(verts) // MAX_SAMPLE)
    sample = verts[::step]
    # the extreme vertices are always part of the sample
    for i in range(3):
        sample.append(min(verts, key=lambda v: v[i]))
        sample.append(max(verts, key=lambda v: v[i]))
    info = {"min": mn, "max": mx, "ext": tuple(mx[i] - mn[i] for i in range(3)),
            "count": len(verts), "verts": sample}
    _OBJ_CACHE[key] = info
    return info


def _box_info(mn: Vec, mx: Vec) -> dict:
    corners = [(x, y, z) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
    return {"min": mn, "max": mx, "ext": tuple(mx[i] - mn[i] for i in range(3)),
            "count": 8, "verts": corners}


def resolve(res: str, qxw_path: str = "", mesh_dirs=()) -> Optional[str]:
    """The file a ``Res`` points to, as QLC+ looks for it: absolute path,
    QLC+ mesh folder, then relative to the workspace (plus *mesh_dirs*)."""
    if not res:
        return None
    cands = []
    if os.path.isabs(res):
        cands.append(res)
    for d in list(mesh_dirs) + SYSTEM_MESH_DIRS:
        cands.append(os.path.join(d, res))
        cands.append(os.path.join(d, os.path.basename(res)))
    if qxw_path:
        cands.append(os.path.join(os.path.dirname(os.path.abspath(qxw_path)), res))
    return next((c for c in cands if os.path.isfile(c)), None)


def mesh_info(res: str, qxw_path: str = "", mesh_dirs=()) -> Tuple[Optional[dict], Optional[str]]:
    path = resolve(res, qxw_path, mesh_dirs)
    if path:
        try:
            return read_obj(path), path
        except (OSError, ValueError):
            return None, path
    r = res.replace("\\", "/")
    b = next((v for k, v in BUILTIN_BOUNDS.items() if r == k or r.endswith("/" + k)), None)
    return (_box_info(*b), None) if b else (None, None)


# ─────────────────────────────────────────────────────────────────────────────
# workspace
# ─────────────────────────────────────────────────────────────────────────────

def _monitor(root: ET.Element, create: bool = False) -> Optional[ET.Element]:
    eng = root.find("Engine")
    mon = eng.find("Monitor") if eng is not None else None
    if mon is None and create:
        mon = ET.SubElement(eng, "Monitor", {"DisplayMode": "0", "ShowLabels": "0"})
        ET.SubElement(mon, "Grid", {"Width": "5", "Height": "3", "Depth": "5", "Units": "0", "POV": "1"})
        ET.SubElement(mon, "StageItem").text = "0"
    return mon


def _f(el, k, d=0.0) -> float:
    try:
        return float(el.get(k, d))
    except (TypeError, ValueError):
        return d


def stage(root: ET.Element) -> dict:
    """``{"type", "type_name", "w", "h", "d" (m), "units", "floor" (m)}``."""
    mon = _monitor(root)
    g = mon.find("Grid") if mon is not None else None
    units = int(_f(g, "Units", 0)) if g is not None else 0
    k = FT if units == 1 else 1.0
    t = 0
    if mon is not None and mon.findtext("StageItem"):
        try:
            t = int(mon.findtext("StageItem").strip())
        except ValueError:
            t = 0
    return {"type": t, "type_name": STAGE_TYPES[t] if 0 <= t < len(STAGE_TYPES) else "?",
            "w": _f(g, "Width", 5) * k if g is not None else 5.0,
            "h": _f(g, "Height", 3) * k if g is not None else 3.0,
            "d": _f(g, "Depth", 5) * k if g is not None else 5.0,
            "units": units, "floor": FLOOR_M.get(t, 0.0)}


def _rot_matrix(rx: float, ry: float, rz: float):
    """R = Rx · Ry · Rz (Qt fromAxesAndAngles(x, y, z))."""
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    Rx = [[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]]
    Ry = [[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]]
    Rz = [[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]]

    def mul(A, B):
        return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(Rx, Ry), Rz)


def _item(el: ET.Element) -> dict:
    return {"id": el.get("ID", ""), "name": el.get("Name", ""), "res": el.get("Res", ""),
            "pos": [_f(el, "XPos"), _f(el, "YPos"), _f(el, "ZPos")],
            "rot": [_f(el, "XRot"), _f(el, "YRot"), _f(el, "ZRot")],
            "scale": [_f(el, "XScale", 1.0), _f(el, "YScale", 1.0), _f(el, "ZScale", 1.0)],
            "hidden": el.get("Hidden", "").lower() == "true"}


def world_box(item: dict, info: dict, st: dict) -> Tuple[Vec, Vec]:
    """World-space bounding box (m) of a placed mesh (from its vertices)."""
    ext = info["ext"]
    p, s = item["pos"], item["scale"]
    T = (p[0] / 1000 - st["w"] / 2 + ext[0] / 2, p[1] / 1000 + ext[1] / 2,
         p[2] / 1000 - st["d"] / 2 + ext[2] / 2)
    R = _rot_matrix(*item["rot"])
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for v in info["verts"]:
        sv = (v[0] * s[0], v[1] * s[1], v[2] * s[2])
        for i in range(3):
            w = T[i] + R[i][0] * sv[0] + R[i][1] * sv[1] + R[i][2] * sv[2]
            lo[i] = min(lo[i], w)
            hi[i] = max(hi[i], w)
    return tuple(lo), tuple(hi)


def placement(item: dict, info: Optional[dict], st: dict) -> Optional[dict]:
    """What you see, in mm: centre X from the left edge, centre Z from the
    back edge, bottom / top height above the floor, footprint size."""
    if info is None:
        return None
    lo, hi = world_box(item, info, st)
    return {"x": round(((lo[0] + hi[0]) / 2 + st["w"] / 2) * 1000),
            "z": round(((lo[2] + hi[2]) / 2 + st["d"] / 2) * 1000),
            "bottom": round((lo[1] - st["floor"]) * 1000),
            "top": round((hi[1] - st["floor"]) * 1000),
            "w": round((hi[0] - lo[0]) * 1000), "h": round((hi[1] - lo[1]) * 1000),
            "d": round((hi[2] - lo[2]) * 1000),
            "x0": round((lo[0] + st["w"] / 2) * 1000), "z0": round((lo[2] + st["d"] / 2) * 1000)}


def meshes(root: ET.Element, qxw_path: str = "", mesh_dirs=()) -> List[dict]:
    """Every MeshItem with its file, size and placement (document order)."""
    mon = _monitor(root)
    st = stage(root)
    out = []
    for el in (mon.findall("MeshItem") if mon is not None else []):
        it = _item(el)
        info, path = mesh_info(it["res"], qxw_path, mesh_dirs)
        it["file"] = path
        it["found"] = info is not None
        it["builtin"] = info is not None and path is None
        it["label"] = it["name"] or os.path.splitext(os.path.basename(it["res"]))[0]
        it["size"] = [round(e * 1000) for e in info["ext"]] if info else None
        it["place"] = placement(it, info, st)
        out.append(it)
    return out


DEFAULT_FX_SIZE = (300.0, 300.0, 300.0)       # mm, when the .qxf has no dimensions


def _fx_size(fx_el: Optional[ET.Element], qxf_defs) -> Tuple[Tuple[float, float, float], bool]:
    """Fixture body size (W, H, D mm) from its .qxf ``<Dimensions>``."""
    if fx_el is not None and qxf_defs:
        key = ((fx_el.findtext("Manufacturer") or "").strip().lower(),
               (fx_el.findtext("Model") or "").strip().lower())
        ph = ((qxf_defs.get(key) or {}).get("physical") or {})
        dims = tuple(float(ph.get(k) or 0) for k in ("width", "height", "depth"))
        if all(d > 0 for d in dims):
            return dims, True
    return DEFAULT_FX_SIZE, False


def fixtures(root: ET.Element, qxf_defs=None) -> List[dict]:
    """Fixtures on the 3D stage with their placement (mm), like meshes.

    QLC+ puts a fixture's (centred) model at ``pos/1000 − stage/2 + size/2``
    (``mainview3d.cpp`` updateFixturePosition), so ``XPos`` / ``ZPos`` are
    its left / back edge and ``YPos`` its underside above y = 0.  The size
    is the .qxf's ``<Dimensions>`` (300 mm cube when unknown); rotation
    (tilt) is ignored for the box."""
    eng = root.find("Engine")
    els = {(f.findtext("ID") or "").strip(): f for f in eng.findall("Fixture")} if eng is not None else {}
    st = stage(root)
    mon = _monitor(root)
    out = []
    for el in (mon.findall("FxItem") if mon is not None else []):
        fid = el.get("ID", "")
        fx = els.get(fid)
        (w, h, d), known = _fx_size(fx, qxf_defs)
        x, y, z = _f(el, "XPos"), _f(el, "YPos"), _f(el, "ZPos")
        bottom = round(y - st["floor"] * 1000)
        out.append({"id": fid, "key": f"f:{fid}",
                    "name": (fx.findtext("Name") or "").strip() if fx is not None else f"Fixture {fid}",
                    "x": x, "y": y, "z": z, "size_known": known,
                    "place": {"x": round(x + w / 2), "z": round(z + d / 2), "bottom": bottom,
                              "top": round(bottom + h), "w": round(w), "h": round(h), "d": round(d),
                              "x0": round(x), "z0": round(z)}})
    return out


def move_fixture(root, fid: str, *, x: Optional[float] = None, z: Optional[float] = None,
                 bottom: Optional[float] = None, qxf_defs=None) -> dict:
    """Place a fixture by its centre (*x* from the left, *z* from the back)
    and the height of its underside above the floor (mm)."""
    mon = _monitor(root)
    el = next((e for e in (mon.findall("FxItem") if mon is not None else []) if e.get("ID") == str(fid)), None)
    if el is None:
        raise StageError(f"Fixture {fid} is not on the 3D stage.")
    before = next(f for f in fixtures(root, qxf_defs) if f["id"] == str(fid))["place"]
    w, d = before["w"], before["d"]
    st = stage(root)
    if x is not None:
        el.set("XPos", _num(round(float(x) - w / 2, 1)))
    if z is not None:
        el.set("ZPos", _num(round(float(z) - d / 2, 1)))
    if bottom is not None:
        el.set("YPos", _num(round(float(bottom) + st["floor"] * 1000, 1)))
    after = next(f for f in fixtures(root, qxf_defs) if f["id"] == str(fid))["place"]
    return {"id": f"f:{fid}", "before": before, "after": after}


# ─────────────────────────────────────────────────────────────────────────────
# edits (on a stripped copy)
# ─────────────────────────────────────────────────────────────────────────────

class StageError(ValueError):
    pass


def _num(v: float) -> str:
    """QLC+-style number: no trailing zeros."""
    v = round(float(v), 4)
    return str(int(v)) if v == int(v) else f"{v:g}"


def _el(root, mid: str) -> ET.Element:
    mon = _monitor(root)
    el = next((e for e in (mon.findall("MeshItem") if mon is not None else []) if e.get("ID") == str(mid)), None)
    if el is None:
        raise StageError(f"Mesh {mid} not found.")
    return el


def _write(el: ET.Element, it: dict) -> None:
    """Write an item back in QLC+'s attribute order and conventions."""
    keep_hidden = el.get("Hidden")
    el.attrib.clear()
    el.set("ID", it["id"])
    if keep_hidden:
        el.set("Hidden", keep_hidden)
    for k, v in zip(("XPos", "YPos", "ZPos"), it["pos"]):
        el.set(k, _num(v))
    for k, v in zip(("XRot", "YRot", "ZRot"), it["rot"]):
        if round(v, 4) != 0:
            el.set(k, _num(v))
    for k, v in zip(("XScale", "YScale", "ZScale"), it["scale"]):
        if round(v, 4) != 1:
            el.set(k, _num(v))
    if it.get("name"):
        el.set("Name", it["name"])
    if it.get("res"):
        el.set("Res", it["res"])


def _info_for(el, qxw_path, mesh_dirs):
    info, _ = mesh_info(el.get("Res", ""), qxw_path, mesh_dirs)
    if info is None:
        raise StageError(f"The model file of mesh {el.get('ID')} can't be found — relink it first.")
    return info


def move_to(root, mid: str, *, x: Optional[float] = None, z: Optional[float] = None,
            bottom: Optional[float] = None, qxw_path: str = "", mesh_dirs=()) -> dict:
    """Place a mesh by what you see: centre *x* (mm from the left edge),
    centre *z* (mm from the back edge), *bottom* (mm above the floor)."""
    el = _el(root, mid)
    it = _item(el)
    info = _info_for(el, qxw_path, mesh_dirs)
    st = stage(root)
    cur = placement(it, info, st)
    lo, hi = world_box(it, info, st)
    if x is not None:
        it["pos"][0] += (float(x) / 1000 - ((lo[0] + hi[0]) / 2 + st["w"] / 2)) * 1000
    if z is not None:
        it["pos"][2] += (float(z) / 1000 - ((lo[2] + hi[2]) / 2 + st["d"] / 2)) * 1000
    if bottom is not None:
        it["pos"][1] += (float(bottom) / 1000 + st["floor"] - lo[1]) * 1000
    it["pos"] = [round(v, 1) for v in it["pos"]]
    _write(el, it)
    return {"id": it["id"], "before": cur, "after": placement(it, info, st)}


def on_floor(root, ids=None, qxw_path: str = "", mesh_dirs=()) -> dict:
    """Put meshes (all when *ids* is None) with their lowest point on the floor."""
    mon = _monitor(root)
    done, skipped = [], []
    for el in (mon.findall("MeshItem") if mon is not None else []):
        if ids is not None and el.get("ID") not in {str(i) for i in ids}:
            continue
        try:
            r = move_to(root, el.get("ID"), bottom=0, qxw_path=qxw_path, mesh_dirs=mesh_dirs)
            if r["before"]["bottom"] != 0:
                done.append(r)
        except StageError:
            skipped.append(el.get("ID"))
    return {"moved": done, "skipped": skipped}


def set_transform(root, mid: str, *, rot=None, scale=None, name=None, res=None,
                  keep_floor: bool = True, qxw_path: str = "", mesh_dirs=()) -> dict:
    """Rotation (°), scale (factors), name, file — keeping the model's visible
    centre and (with *keep_floor*) its height above the floor."""
    el = _el(root, mid)
    it = _item(el)
    st = stage(root)
    info, _ = mesh_info(it["res"], qxw_path, mesh_dirs)
    before = placement(it, info, st) if info else None
    if rot is not None:
        it["rot"] = [float(v) for v in rot]
    if scale is not None:
        sc = [float(v) for v in scale]
        if any(v <= 0 for v in sc):
            raise StageError("Scale must be above 0 %.")
        it["scale"] = sc
    if name is not None:
        it["name"] = str(name).strip()
    if res is not None:
        it["res"] = str(res).strip()
    _write(el, it)
    if before and not res:
        move_to(root, mid, x=before["x"], z=before["z"], bottom=before["bottom"] if keep_floor else None,
                qxw_path=qxw_path, mesh_dirs=mesh_dirs)
    return {"id": mid}


def add_mesh(root, res: str, *, name: str = "", x: Optional[float] = None, z: Optional[float] = None,
             qxw_path: str = "", mesh_dirs=()) -> dict:
    """New mesh (on the floor, at *x*/*z* or the centre of the stage)."""
    info, path = mesh_info(res, qxw_path, mesh_dirs)
    if info is None:
        raise StageError(f"Model file not found: {res}")
    mon = _monitor(root, create=True)
    ids = [int(e.get("ID")) for e in mon.findall("MeshItem") if (e.get("ID") or "").isdigit()]
    mid = str(max(ids + [-1]) + 1)
    el = ET.Element("MeshItem")
    last = mon.findall("MeshItem") or mon.findall("FxItem")
    idx = list(mon).index(last[-1]) + 1 if last else len(mon)
    mon.insert(idx, el)
    st = stage(root)
    _write(el, {"id": mid, "name": name.strip(), "res": res, "pos": [0.0, 0.0, 0.0],
                "rot": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]})
    move_to(root, mid, x=st["w"] * 500 if x is None else x, z=st["d"] * 500 if z is None else z,
            bottom=0, qxw_path=qxw_path, mesh_dirs=mesh_dirs)
    return {"id": mid}


def duplicate_mesh(root, mid: str, dx: float = 500, qxw_path: str = "", mesh_dirs=()) -> dict:
    el = _el(root, mid)
    it = _item(el)
    mon = _monitor(root)
    ids = [int(e.get("ID")) for e in mon.findall("MeshItem") if (e.get("ID") or "").isdigit()]
    new = copy.deepcopy(el)
    new.set("ID", str(max(ids) + 1))
    mon.insert(list(mon).index(mon.findall("MeshItem")[-1]) + 1, new)
    it["pos"][0] += dx
    it["id"] = new.get("ID")
    _write(new, it)
    return {"id": new.get("ID")}


def remove_mesh(root, mid: str) -> dict:
    el = _el(root, mid)
    _monitor(root).remove(el)
    return {"removed": mid}


def set_stage(root, *, type: Optional[int] = None, w=None, h=None, d=None,
              keep_meshes: bool = True, qxw_path: str = "", mesh_dirs=()) -> dict:
    """Stage type / size (m).  With *keep_meshes* the meshes keep their visible
    place (centre from the left/back edge, height above the floor)."""
    before = {m["id"]: m["place"] for m in meshes(root, qxw_path, mesh_dirs)} if keep_meshes else {}
    mon = _monitor(root, create=True)
    g = mon.find("Grid")
    if g is None:
        g = ET.SubElement(mon, "Grid", {"Width": "5", "Height": "3", "Depth": "5", "Units": "0", "POV": "1"})
    k = FT if g.get("Units") == "1" else 1.0
    for key, v in (("Width", w), ("Height", h), ("Depth", d)):
        if v is not None:
            if float(v) <= 0:
                raise StageError("Stage size must be above 0.")
            g.set(key, _num(float(v) / k))
    if type is not None:
        if not 0 <= int(type) < len(STAGE_TYPES):
            raise StageError("Unknown stage type.")
        si = mon.find("StageItem")
        if si is None:
            si = ET.Element("StageItem")
            mon.insert(list(mon).index(g) + 1, si)
        si.text = str(int(type))
    for mid, p in before.items():
        if p:
            move_to(root, mid, x=p["x"], z=p["z"], bottom=p["bottom"], qxw_path=qxw_path, mesh_dirs=mesh_dirs)
    return {"stage": stage(root)}


# ─────────────────────────────────────────────────────────────────────────────
# arrange: stage edges, align, distribute, nudge (one or several meshes)
# ─────────────────────────────────────────────────────────────────────────────

EDGES = ("left", "right", "back", "front", "centre", "centre_x", "centre_z", "floor", "ceiling")
ALIGNS = ("align_left", "align_centre_x", "align_right", "align_back", "align_centre_z",
          "align_front", "align_bottom", "align_top")
SPREADS = ("distribute_x", "distribute_z", "spread_x", "spread_z")
ARRANGE = EDGES + ALIGNS + SPREADS + ("nudge",)


def _placed(root, ids, qxw_path, mesh_dirs, qxf_defs=None) -> Tuple[List[Tuple[str, dict]], List[str]]:
    """Placements of the selected items: mesh ids as they are, fixtures as
    ``f:<id>``."""
    want = [str(i) for i in ids]
    got, skipped = {}, []
    for m in meshes(root, qxw_path, mesh_dirs):
        if m["id"] in want:
            if m["place"]:
                got[m["id"]] = m["place"]
            else:
                skipped.append(m["id"])
    if any(i.startswith("f:") for i in want):
        for f in fixtures(root, qxf_defs):
            if f["key"] in want:
                got[f["key"]] = f["place"]
    missing = [i for i in want if i not in got and i not in skipped]
    if missing:
        raise StageError(f"{', '.join(missing)} not found.")
    return [(i, got[i]) for i in want if i in got], skipped


def arrange(root, ids, action: str, *, margin: float = 0, dx: float = 0, dz: float = 0, dy: float = 0,
            move: str = "all", qxf_defs=None, qxw_path: str = "", mesh_dirs=()) -> dict:
    """Place one or several meshes (all in mm, what you see):

    * stage edges — ``left``/``right``/``back``/``front``/``centre``/
      ``centre_x``/``centre_z`` move the selection **as a group** (the
      meshes keep their spacing) so that it touches that edge (+ *margin*)
      or sits in the middle; ``floor`` / ``ceiling`` act on **each** mesh
      (standing on the floor / hanging with its top at the stage height
      − *margin*);
    * ``align_*`` (2+): left / centre / right edges, back / centre / front,
      bottoms / tops — lined up on the selection's outermost one (centre:
      the selection's centre);
    * ``distribute_x`` / ``distribute_z`` (3+): equal gaps between the
      meshes, the outer two stay; ``spread_x`` / ``spread_z`` (1+): equal
      gaps across the whole stage width / depth (inside *margin*);
    * ``nudge``: move by *dx* (right +), *dz* (front +), *dy* (up +).

    Fixtures take part too (ids ``f:<id>``, placed by their body from the
    .qxf dimensions).  *move* = ``"meshes"`` or ``"fixtures"`` keeps the
    others of the selection where they are, as **references**: they count
    for lining up and spacing but don't move — e.g. a mesh and two fixtures,
    *move meshes*, ``align_centre_x`` → the mesh sits between the fixtures.
    """
    if action not in ARRANGE:
        raise StageError(f"Unknown placement: {action}")
    items, skipped = _placed(root, ids, qxw_path, mesh_dirs, qxf_defs)
    if not items:
        raise StageError("Select at least one mesh whose model file is found.")
    if move not in ("all", "meshes", "fixtures"):
        raise StageError(f"Unknown choice: move {move}")

    def moving(i: str) -> bool:
        return move == "all" or (move == "fixtures") == i.startswith("f:")
    if not any(moving(i) for i, _ in items):
        raise StageError(f"Nothing to move: the selection has no {move}.")
    need = 3 if action in ("distribute_x", "distribute_z") else 2 if action.startswith("align_") else 1
    if len(items) < need:
        raise StageError(f"Select at least {need} items for this.")
    mov = [(i, p) for i, p in items if moving(i)]
    anchors = [(i, p) for i, p in items if not moving(i)]
    ref = anchors or items            # what the line-up is measured on
    st = stage(root)
    W, D, H = st["w"] * 1000, st["d"] * 1000, st["h"] * 1000
    mg = float(margin or 0)

    def box(group):
        return (min(p["x0"] for _, p in group), max(p["x0"] + p["w"] for _, p in group),
                min(p["z0"] for _, p in group), max(p["z0"] + p["d"] for _, p in group))
    moves: Dict[str, dict] = {}                       # id → {x, z, bottom} targets

    def shift(ddx=0.0, ddz=0.0):
        for i, p in mov:
            moves[i] = {"x": p["x"] + ddx, "z": p["z"] + ddz}

    if action in ("left", "right", "back", "front", "centre", "centre_x", "centre_z"):
        x0, x1, z0, z1 = box(mov)
        if action == "left":
            shift(ddx=mg - x0)
        elif action == "right":
            shift(ddx=W - mg - x1)
        elif action == "back":
            shift(ddz=mg - z0)
        elif action == "front":
            shift(ddz=D - mg - z1)
        else:
            shift(ddx=(W / 2 - (x0 + x1) / 2) if action != "centre_z" else 0,
                  ddz=(D / 2 - (z0 + z1) / 2) if action != "centre_x" else 0)
    elif action == "floor":
        for i, p in mov:
            moves[i] = {"bottom": 0}
    elif action == "ceiling":
        for i, p in mov:
            moves[i] = {"bottom": H - mg - p["h"]}
    elif action.startswith("align_"):
        x0, x1, z0, z1 = box(ref)
        for i, p in mov:
            moves[i] = {
                "align_left": {"x": x0 + p["w"] / 2}, "align_right": {"x": x1 - p["w"] / 2},
                "align_centre_x": {"x": (x0 + x1) / 2},
                "align_back": {"z": z0 + p["d"] / 2}, "align_front": {"z": z1 - p["d"] / 2},
                "align_centre_z": {"z": (z0 + z1) / 2},
                "align_bottom": {"bottom": min(q["bottom"] for _, q in ref)},
                "align_top": {"bottom": max(q["top"] for _, q in ref) - p["h"]},
            }[action]
    elif action in SPREADS:
        ax, size, lo_key = ("x", "w", "x0") if action.endswith("_x") else ("z", "d", "z0")
        if action.startswith("spread"):
            order = sorted(mov, key=lambda ip: (ip[1][ax], ip[0]))
            total = sum(p[size] for _, p in order)
            start, end = mg, (W if ax == "x" else D) - mg
            gap = (end - start - total) / (len(order) + 1)
            pos = start + gap
        else:
            # between the outer two of the whole selection (references included)
            order = sorted(items, key=lambda ip: (ip[1][ax], ip[0]))
            total = sum(p[size] for _, p in order)
            start = order[0][1][lo_key]
            end = order[-1][1][lo_key] + order[-1][1][size]
            gap = (end - start - total) / (len(order) - 1)
            pos = start
        for i, p in order:
            if moving(i):
                moves[i] = {ax: pos + p[size] / 2}
            pos += p[size] + gap
    elif action == "nudge":
        for i, p in mov:
            moves[i] = {"x": p["x"] + float(dx or 0), "z": p["z"] + float(dz or 0),
                        "bottom": p["bottom"] + float(dy or 0)}
    moved = []
    for i, t in moves.items():
        if i.startswith("f:"):
            r = move_fixture(root, i[2:], x=t.get("x"), z=t.get("z"), bottom=t.get("bottom"),
                             qxf_defs=qxf_defs)
        else:
            r = move_to(root, i, x=t.get("x"), z=t.get("z"), bottom=t.get("bottom"),
                        qxw_path=qxw_path, mesh_dirs=mesh_dirs)
        if r["before"] != r["after"]:
            moved.append(i)
    placed = {m["id"]: m["place"] for m in meshes(root, qxw_path, mesh_dirs) if m["place"]}
    placed.update({f["key"]: f["place"] for f in fixtures(root, qxf_defs)})
    outside = [i for i in moves if i in placed and (
        placed[i]["x0"] < -1 or placed[i]["z0"] < -1
        or placed[i]["x0"] + placed[i]["w"] > W + 1 or placed[i]["z0"] + placed[i]["d"] > D + 1)]
    return {"moved": moved, "skipped": skipped, "outside": outside}


# ─────────────────────────────────────────────────────────────────────────────
# mesh library (folders of .obj files)
# ─────────────────────────────────────────────────────────────────────────────

def _settings_path() -> str:
    return os.environ.get("QSK_MESH_DIRS") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "mesh_dirs.json")


def library_dirs() -> List[str]:
    try:
        with open(_settings_path(), encoding="utf-8") as fh:
            dirs = json.load(fh).get("dirs", [])
    except (OSError, ValueError):
        dirs = []
    default = os.path.join(os.path.expanduser("~"), "Documents", "QLC+", "Meshes")
    if not dirs and os.path.isdir(default):
        dirs = [default]
    return [d for d in dirs if isinstance(d, str)]


def set_library_dirs(dirs: List[str]) -> List[str]:
    clean = [os.path.abspath(os.path.expanduser(d.strip())) for d in dirs if d and d.strip()]
    missing = [d for d in clean if not os.path.isdir(d)]
    if missing:
        raise StageError("Folder not found: " + ", ".join(missing))
    os.makedirs(os.path.dirname(_settings_path()), exist_ok=True)
    with open(_settings_path(), "w", encoding="utf-8") as fh:
        json.dump({"dirs": clean}, fh, indent=1)
    return clean


def library(dirs=None) -> List[dict]:
    """``[{name, path, folder, bytes}]`` of the .obj files in the library
    folders (recursively, sorted)."""
    out = []
    for d in (dirs if dirs is not None else library_dirs()):
        for base, _sub, files in os.walk(d):
            for f in files:
                if f.lower().endswith(".obj"):
                    p = os.path.join(base, f)
                    out.append({"name": os.path.splitext(f)[0], "path": p,
                                "folder": os.path.relpath(base, d) if base != d else "",
                                "bytes": os.path.getsize(p)})
    out.sort(key=lambda m: (m["folder"].lower(), m["name"].lower()))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Doctor gate + file
# ─────────────────────────────────────────────────────────────────────────────

def report(orig: ET.Element, new: ET.Element, source: str, output: str,
           qxw_path: str = "", mesh_dirs=()) -> str:
    a = {m["id"]: m for m in meshes(orig, qxw_path, mesh_dirs)}
    b = {m["id"]: m for m in meshes(new, qxw_path, mesh_dirs)}
    sa, sb = stage(orig), stage(new)
    lines = ["STAGE AND MESHES REPORT", "=" * 23, f"Source: {source}", f"Output: {output}", ""]
    if (sa["type"], sa["w"], sa["h"], sa["d"]) != (sb["type"], sb["w"], sb["h"], sb["d"]):
        lines.append(f"Stage: {sa['type_name']} {sa['w']:g}×{sa['h']:g}×{sa['d']:g} m → "
                     f"{sb['type_name']} {sb['w']:g}×{sb['h']:g}×{sb['d']:g} m")
    for mid in sorted(set(a) | set(b), key=lambda k: int(k) if k.isdigit() else 0):
        if mid not in b:
            lines.append(f"Removed mesh {mid} '{a[mid]['label']}'")
        elif mid not in a:
            p = b[mid]["place"] or {}
            lines.append(f"Added mesh {mid} '{b[mid]['label']}' at x {p.get('x')} / z {p.get('z')} mm, "
                         f"bottom {p.get('bottom')} mm above the floor")
        else:
            pa, pb = a[mid], b[mid]
            ch = []
            if pa["place"] and pb["place"]:
                for k, t in (("x", "x"), ("z", "z"), ("bottom", "bottom")):
                    if pa["place"][k] != pb["place"][k]:
                        ch.append(f"{t} {pa['place'][k]} → {pb['place'][k]} mm")
            if pa["rot"] != pb["rot"]:
                ch.append(f"rotation {pa['rot']} → {pb['rot']}°")
            if pa["scale"] != pb["scale"]:
                ch.append(f"scale {pa['scale']} → {pb['scale']}")
            if pa["res"] != pb["res"]:
                ch.append(f"file {pa['res']} → {pb['res']}")
            if pa["name"] != pb["name"]:
                ch.append(f"name '{pa['name']}' → '{pb['name']}'")
            if ch:
                lines.append(f"Mesh {mid} '{pb['label']}': " + "; ".join(ch))
    fa = {f["id"]: f for f in fixtures(orig)}
    for f in fixtures(new):
        o = fa.get(f["id"])
        if o and (o["x"], o["y"], o["z"]) != (f["x"], f["y"], f["z"]):
            lines.append(f"Fixture {f['id']} '{f['name']}': X/Y/Z {o['x']:g}/{o['y']:g}/{o['z']:g} → "
                         f"{f['x']:g}/{f['y']:g}/{f['z']:g} mm")
    from core import fixture_groups as fg
    names = {(f.findtext("ID") or "").strip(): (f.findtext("Name") or "").strip()
             for f in (new.find("Engine").findall("Fixture") if new.find("Engine") is not None else [])}
    ga = {g["id"]: g for g in fg.groups(orig)}
    gb = {g["id"]: g for g in fg.groups(new)}
    for gid in sorted(set(ga) | set(gb), key=lambda k: int(k) if k.isdigit() else 0):
        fl = lambda g: ", ".join(names.get(i, i) for i in g["fixtures"])
        if gid not in gb:
            lines.append(f"Removed fixture group {gid} '{ga[gid]['name']}'")
        elif gid not in ga:
            lines.append(f"Added fixture group {gid} '{gb[gid]['name']}': {fl(gb[gid])}")
        elif (ga[gid]["name"], ga[gid]["fixtures"]) != (gb[gid]["name"], gb[gid]["fixtures"]):
            lines.append(f"Fixture group {gid} '{ga[gid]['name']}' → '{gb[gid]['name']}': {fl(gb[gid])}")
    if len(lines) == 5:
        lines.append("(no changes)")
    missing = [m["label"] for m in b.values() if not m["found"]]
    if missing:
        lines += ["", "Model files not found here (QLC+ will skip them if it can't find them either): "
                  + ", ".join(missing)]
    return "\n".join(lines) + "\n"


def report_path(qxw_path: str) -> str:
    return os.path.splitext(qxw_path)[0] + "_stage_report.txt"
