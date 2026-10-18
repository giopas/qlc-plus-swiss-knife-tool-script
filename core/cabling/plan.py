"""
core/cabling/plan.py — the plan file
====================================

``<show>.cabling.json`` sits next to the show without the ``_vN`` suffix, so
every version of the show shares it (like the Stage Monitor's
``<show>.stage.json``).  It holds what belongs to tonight, never to QLC+:

* ``tonight`` — tonight's inventory (a copy of your kit, adjusted);
* ``owners`` — choices made on the Kit step: ``{fixture id: "venue" |
  "borrowed" | "mine"}``;
* ``controller`` — where the computer is: ``mode`` ``stand`` (where I
  stand), ``foh`` (front of house, with ``distance_m`` and ``route``) or
  ``auto`` (the planner chooses), and ``side`` for ``stand``;
* ``chains`` — each ``{"source": {"item", "port"}, "devices": [...]}``, a
  device being ``{"fixture": id}`` or ``{"item": kit item id}``, and
  ``cables`` (kit cable ids per hop, or null).

:func:`evaluate` walks every chain against the show and the inventory and
returns the chains with their links and all the checks.
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Dict, List, Optional

from core.cabling import chain as chain_mod
from core.cabling import kit as kit_mod
from core.cabling import rig as rig_mod

SIDECAR_SUFFIX = ".cabling.json"
PLAN_VERSION = 1
CONTROLLER_MODES = ("stand", "foh", "auto")
SIDES = ("stage-left", "stage-right", "back", "front")
ROUTES = ("wall", "taped", "overhead", "unknown")

DEFAULT_CONTROLLER = {"mode": "stand", "side": "stage-left", "distance_m": 12.0, "route": "unknown"}


def sidecar_path(qxw_path: str) -> str:
    folder = os.path.dirname(os.path.abspath(qxw_path))
    stem = re.sub(r"_v\d+$", "", os.path.splitext(os.path.basename(qxw_path))[0])
    return os.path.join(folder, stem + SIDECAR_SUFFIX)


def clean_controller(c) -> dict:
    c = c if isinstance(c, dict) else {}
    out = dict(DEFAULT_CONTROLLER)
    if c.get("mode") in CONTROLLER_MODES:
        out["mode"] = c["mode"]
    if c.get("side") in SIDES:
        out["side"] = c["side"]
    try:
        d = float(c.get("distance_m", out["distance_m"]))
        out["distance_m"] = round(d, 1) if 0.5 <= d <= 200 else DEFAULT_CONTROLLER["distance_m"]
    except (TypeError, ValueError):
        pass
    if c.get("route") in ROUTES:
        out["route"] = c["route"]
    return out


def _clean_chain(ch) -> Optional[dict]:
    if not isinstance(ch, dict) or not isinstance(ch.get("source"), dict):
        return None
    src = ch["source"]
    try:
        portn = int(src.get("port", 0))
    except (TypeError, ValueError):
        return None
    devs = []
    for d in ch.get("devices") or []:
        if isinstance(d, dict) and str(d.get("fixture", "")).strip().isdigit():
            devs.append({"fixture": str(d["fixture"]).strip()})
        elif isinstance(d, dict) and d.get("item"):
            devs.append({"item": str(d["item"])[:60]})
    cables = [str(c)[:60] if c else None for c in (ch.get("cables") or [])][:len(devs)]
    return {"source": {"item": str(src.get("item") or "")[:60], "port": portn},
            "devices": devs, "cables": cables, "label": str(ch.get("label") or "")[:60]}


def clean_plan(p) -> dict:
    p = p if isinstance(p, dict) else {}
    out = {"version": PLAN_VERSION,
           "tonight": kit_mod.clean_inventory(p.get("tonight") or {}),
           "owners": {str(k): v for k, v in (p.get("owners") or {}).items()
                      if str(k).isdigit() and v in kit_mod.OWNERS},
           "controller": clean_controller(p.get("controller")),
           "chains": [c for c in (_clean_chain(x) for x in p.get("chains") or []) if c]}
    out["tonight"].pop("dropped", None)
    return out


def new_plan(base: Optional[dict] = None) -> dict:
    """A first plan: tonight is a copy of your kit, the controller where you stand."""
    return clean_plan({"tonight": kit_mod.tonight_from(base if base is not None else kit_mod.load_base())})


def load_plan(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            return clean_plan(json.load(fh))
    except (OSError, ValueError):
        return None


def save_plan(plan: dict, path: str) -> str:
    data = json.dumps(clean_plan(plan), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(data)
    os.replace(tmp, path)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# evaluate
# ─────────────────────────────────────────────────────────────────────────────

def _items(inv: dict) -> Dict[str, dict]:
    return {it["id"]: it for it in inv.get("items", [])}


def evaluate(plan: dict, rig: dict) -> dict:
    """Walk every chain of *plan* on *rig* (:func:`core.cabling.rig.read_rig`).

    Returns ``{"fixtures": [... with owner], "chains": [walked], "issues":
    [...], "summary": {"errors", "warnings", "info"}}``.  Plan-level checks:
    C004 (two universes on one chain), C006 (a used universe no chain
    feeds), C013 (fixture with no position), C014 (no interface in the kit
    matches a universe's output), and every fixture not on a chain."""
    plan = clean_plan(plan)
    inv = plan["tonight"]
    items = _items(inv)
    owners = {m["id"]: m for m in rig_mod.match_inventory(rig, inv, plan["owners"])}
    fx = {}
    for f in rig["fixtures"]:
        f = dict(f)
        f["owner"] = owners[f["id"]]["owner"]
        f["item_id"] = owners[f["id"]]["item_id"]
        fx[f["id"]] = f
    walked, issues = [], []
    on_chain: Dict[str, int] = {}
    for n, ch in enumerate(plan["chains"]):
        src = items.get(ch["source"]["item"])
        outs = [p for p in (src or {}).get("ports", []) if p["role"] in ("out", "thru")]
        if src is None or not 0 <= ch["source"]["port"] < len(outs):
            issues.append(chain_mod._issue("C006", f"Chain {n + 1} starts from an output that is not in tonight's kit."))
            continue
        devs = []
        for d in ch["devices"]:
            if "fixture" in d and d["fixture"] in fx:
                f = fx[d["fixture"]]
                devs.append(chain_mod.fixture_device(f, items.get(f["item_id"]) if f["item_id"] else None))
                on_chain[d["fixture"]] = n
            elif "item" in d and d["item"] in items:
                devs.append(dict(items[d["item"]]))
        cables = [items.get(c) if c else None for c in ch["cables"]]
        w = chain_mod.walk(src, outs[ch["source"]["port"]], devs, inv, cables, ch["label"])
        unis = sorted({fx[d["fixture"]]["universe"] for d in ch["devices"] if d.get("fixture") in fx})
        if len(unis) > 1:
            w["issues"].append(chain_mod._issue("C004", f"{w['name']} carries universes "
                                                + ", ".join(str(int(u) + 1) for u in unis) + ".", w["name"],
                                                "Move the fixtures, or use another output."))
        w["universes"] = unis
        walked.append(w)
    issues += chain_mod.check(walked, inv)
    for u in rig_mod.used_universes(rig):
        uni = next((x for x in rig["universes"] if x["id"] == u), {"id": u, "output": None})
        if rig_mod.interface_for(uni, inv) is None:
            out = (uni.get("output") or {}).get("name") or "no output"
            issues.append(chain_mod._issue("C014", f"Universe {int(u) + 1} goes to {out}; no interface in "
                                           "tonight's kit matches it.", fix="Add the interface to the kit, "
                                           "or change the universe's output in QLC+."))
    missing = [f for f in fx.values() if f["id"] not in on_chain]
    if plan["chains"] and missing:
        issues.append(chain_mod._issue("C006", "Not on any chain: " + ", ".join(f["name"] for f in missing) + ".",
                                       fix="Add them to a chain."))
    for f in fx.values():
        if f["place"] is None:
            issues.append(chain_mod._issue("C013", f"{f['name']} is not on the 3D stage; its route is estimated.",
                                           f["name"], "Place it in Stage & Meshes."))
    allis = [i for w in walked for i in w["issues"]] + issues
    summary = {s: sum(1 for i in allis if i["severity"] == s) for s in ("error", "warning", "info")}
    return {"fixtures": list(fx.values()), "chains": walked, "issues": issues, "summary": summary}


def not_in_inventory(plan: dict, rig: dict) -> List[dict]:
    """Fixtures of the show that are not in tonight's inventory and have no
    owner chosen: the *Found in the show* panel, grouped by model."""
    groups: Dict[tuple, dict] = {}
    for m, f in zip(rig_mod.match_inventory(rig, clean_plan(plan)["tonight"], clean_plan(plan)["owners"]),
                    rig["fixtures"]):
        if m["owner"] is None:
            k = (f["manufacturer"], f["model"])
            g = groups.setdefault(k, {"manufacturer": f["manufacturer"], "model": f["model"],
                                      "ids": [], "names": [], "reason": m["reason"]})
            g["ids"].append(f["id"])
            g["names"].append(f["name"])
    return list(groups.values())
