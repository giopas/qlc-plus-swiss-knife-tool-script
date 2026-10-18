"""
core/cabling/rig.py — what the show says
========================================

Reads the show in progress, never changes it:

* the stage (size, floor) and every fixture on it: name, patch, place
  (centre X from the left edge, Z from the back edge, underside height, in
  mm, as :func:`core.stage3d.fixtures` gives it), DMX connector from its
  ``.qxf`` (``Physical/Technical DmxConnector``) and power draw;
* the universes and the output each one is patched to
  (``InputOutputMap/Universe/Output``);
* the band floor: the footprint of every mesh on the stage (members, riser,
  backline), the keep-out for cables.

:func:`match_inventory` then says, per fixture, whose it is: matched to a
fixture model in tonight's inventory (*mine* or *borrowed*), marked *venue*,
or not in the inventory at all.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, List, Optional

from core import stage3d
from core.cabling import kit as kit_mod

TRUSS_MM = 1500          # underside above this: hung (truss, stand, PA top)
KEEP_OUT_MARGIN = 500    # mm around a mesh footprint


def _key(manufacturer: str, model: str):
    return ((manufacturer or "").strip().lower(), (model or "").strip().lower())


def universes(root: ET.Element) -> List[dict]:
    """``[{id, name, output: {plugin, name, line} | None}]`` in file order."""
    eng = root.find("Engine")
    iom = eng.find("InputOutputMap") if eng is not None else None
    out = []
    for u in (iom.findall("Universe") if iom is not None else []):
        o = u.find("Output")
        out.append({"id": u.get("ID", ""), "name": u.get("Name", ""),
                    "output": None if o is None else {"plugin": o.get("Plugin", ""),
                                                      "name": o.get("Name", ""),
                                                      "line": o.get("Line", "0")}})
    return out


def _patch(root: ET.Element) -> Dict[str, dict]:
    eng = root.find("Engine")
    out = {}
    for f in (eng.findall("Fixture") if eng is not None else []):
        fid = (f.findtext("ID") or "").strip()

        def t(tag):
            return (f.findtext(tag) or "").strip()
        try:
            addr = int(t("Address"))
            chans = int(t("Channels") or 0)
        except ValueError:
            addr, chans = 0, 0
        out[fid] = {"manufacturer": t("Manufacturer"), "model": t("Model"), "mode": t("Mode"),
                    "name": t("Name"), "universe": t("Universe") or "0",
                    "address": addr + 1, "channels": chans}
    return out


def read_rig(root: ET.Element, qxf_defs: Optional[dict] = None, qxw_path: str = "",
             mesh_dirs=()) -> dict:
    """Everything the planner needs from the show.

    ``qxf_defs`` is ``{(manufacturer, model) lower-case: parse_qxf() dict}``
    (:func:`core.doctor.load_qxf_defs`).  A fixture whose definition is
    missing or says nothing about its connector gets 3-pin, marked
    ``connector_known: False`` (C101)."""
    qxf_defs = qxf_defs or {}
    st = stage3d.stage(root)
    patch = _patch(root)
    placed = {f["id"]: f for f in stage3d.fixtures(root, qxf_defs)}
    fixtures = []
    for fid, p in patch.items():
        d = qxf_defs.get(_key(p["manufacturer"], p["model"])) or {}
        phys = d.get("physical") or {}
        conns, known = kit_mod.connectors_from_qxf(phys.get("dmx_connector", ""))
        pl = placed.get(fid)
        place = None
        if pl is not None:
            place = {"x": pl["place"]["x"], "z": pl["place"]["z"], "bottom": pl["place"]["bottom"]}
        fixtures.append({
            "id": fid, "name": p["name"] or f"Fixture {fid}",
            "manufacturer": p["manufacturer"], "model": p["model"], "mode": p["mode"],
            "universe": p["universe"], "address": p["address"], "channels": p["channels"],
            "place": place, "hung": bool(place and place["bottom"] > TRUSS_MM),
            "conns": conns, "connector_known": known,
            "definition": bool(d), "power": phys.get("power"),
        })
    fixtures.sort(key=lambda f: (int(f["id"]) if f["id"].isdigit() else 1 << 30, f["id"]))
    keep_out = []
    for m in stage3d.meshes(root, qxw_path, mesh_dirs):
        pl = m.get("place")
        if not pl or m.get("hidden"):
            continue
        keep_out.append({"id": m["id"], "label": m["label"],
                         "x0": pl["x0"] - KEEP_OUT_MARGIN, "z0": pl["z0"] - KEEP_OUT_MARGIN,
                         "x1": pl["x0"] + pl["w"] + KEEP_OUT_MARGIN,
                         "z1": pl["z0"] + pl["d"] + KEEP_OUT_MARGIN})
    return {"stage": {"w": round(st["w"] * 1000), "d": round(st["d"] * 1000),
                      "h": round(st["h"] * 1000), "type": st["type_name"]},
            "fixtures": fixtures, "universes": universes(root), "keep_out": keep_out}


def used_universes(rig: dict) -> List[str]:
    return sorted({f["universe"] for f in rig["fixtures"]}, key=lambda u: int(u) if u.isdigit() else 1 << 30)


def interface_for(universe: dict, inventory: dict) -> Optional[dict]:
    """The interface in the inventory that matches a universe's output (by the
    preset's ``match`` words in the output's name, then by plugin)."""
    o = universe.get("output") or {}
    name = (o.get("name") or "").lower()
    plugin = (o.get("plugin") or "").lower()
    ifaces = kit_mod.by_kind(inventory, "interface") + kit_mod.by_kind(inventory, "node")
    for it in ifaces:
        if any(w and w in name for w in it.get("match") or []):
            return it
    for it in ifaces:
        if plugin and (it.get("plugin") or "").lower() == plugin:
            return it
    return None


def match_inventory(rig: dict, inventory: dict, owners: Optional[Dict[str, str]] = None) -> List[dict]:
    """Whose is each fixture?  ``[{id, owner, item_id, reason}]``.

    ``owners`` holds choices made on the Kit step (``{fixture id: "venue" |
    "borrowed" | "mine"}``); they win.  Otherwise a fixture is matched to a
    *fixture* item of the same manufacturer and model, in fixture-ID order,
    until that item's count runs out.  ``owner`` is ``None`` for a fixture
    not in the inventory (reason ``missing`` or ``count``)."""
    owners = owners or {}
    left: Dict[tuple, List[List]] = {}
    for it in kit_mod.by_kind(inventory, "fixture"):
        left.setdefault(_key(it.get("manufacturer", ""), it.get("model", "")), []).append([it, it["count"]])
    out = []
    for f in rig["fixtures"]:
        chosen = owners.get(f["id"])
        k = _key(f["manufacturer"], f["model"])
        slot = next((s for s in left.get(k, []) if s[1] > 0), None)
        if chosen == "venue":
            out.append({"id": f["id"], "owner": "venue", "item_id": None, "reason": "chosen"})
            continue
        if slot is not None:
            slot[1] -= 1
            owner = chosen if chosen in kit_mod.OWNERS else slot[0].get("owner", "mine")
            out.append({"id": f["id"], "owner": owner, "item_id": slot[0]["id"], "reason": "matched"})
        elif chosen in kit_mod.OWNERS:
            out.append({"id": f["id"], "owner": chosen, "item_id": None, "reason": "chosen"})
        else:
            out.append({"id": f["id"], "owner": None, "item_id": None,
                        "reason": "count" if k in left else "missing"})
    return out
