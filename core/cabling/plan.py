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
  ``cables`` (kit cable ids per hop, or null: picked from the stock);
* ``places`` — ``{"controller" | item id: {"x", "z", "h"}}`` in mm, as on
  the 3D stage (X from the left edge seen from the audience, Z from the
  back edge); an interface not placed sits at the controller, a splitter
  not placed too;
* ``walkways`` — ``[{"x0", "z0", "x1", "z1", "ramp"}]``; ``outlets`` —
  power outlets ``[{"x", "z"}]``; ``slack_m`` at each cable end.

Stage left is the performers' left, the audience's right: the high X side.

:func:`evaluate` walks every chain against the show and the inventory and
returns the chains with their links and all the checks.
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Dict, List, Optional

from core.cabling import cables as cables_mod
from core.cabling import chain as chain_mod
from core.cabling import kit as kit_mod
from core.cabling import rig as rig_mod
from core.cabling import route as route_mod

SIDECAR_SUFFIX = ".cabling.json"
PLAN_VERSION = 1
CONTROLLER_MODES = ("stand", "foh", "auto")
SIDES = ("stage-left", "stage-right", "back", "front")
ROUTES = ("wall", "taped", "overhead", "unknown")

DEFAULT_CONTROLLER = {"mode": "stand", "side": "stage-left", "distance_m": 12.0, "route": "unknown"}
USB_MAX_MM = 5000
LONG_CHAIN_M = 300
DAISY_FIXTURES, DAISY_M = 8, 30
OFFSTAGE = 1000             # mm beside / behind / in front of the stage for the controller


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


def _num(v, default, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return round(f, 2) if lo <= f <= hi else default


def _clean_point(v) -> Optional[dict]:
    if not isinstance(v, dict):
        return None
    try:
        x, z = float(v["x"]), float(v["z"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-100000 <= x <= 100000 and -100000 <= z <= 300000):
        return None
    out = {"x": round(x), "z": round(z)}
    if v.get("h") is not None:
        out["h"] = round(_num(v.get("h"), 0, 0, 20000))
    return out


def _clean_rect(v) -> Optional[dict]:
    if not isinstance(v, dict):
        return None
    try:
        x0, z0, x1, z1 = (float(v[k]) for k in ("x0", "z0", "x1", "z1"))
    except (KeyError, TypeError, ValueError):
        return None
    return {"x0": round(min(x0, x1)), "z0": round(min(z0, z1)), "x1": round(max(x0, x1)),
            "z1": round(max(z0, z1)), "ramp": bool(v.get("ramp")), "label": str(v.get("label") or "")[:40]}


def _clean_places(v) -> dict:
    out = {}
    for k, p in (v or {}).items() if isinstance(v, dict) else []:
        k = re.sub(r"[^A-Za-z0-9_.-]", "", str(k))[:60]
        pt = _clean_point(p)
        if k and pt:
            out[k] = pt
    return out


def clean_plan(p) -> dict:
    p = p if isinstance(p, dict) else {}
    out = {"version": PLAN_VERSION,
           "places": _clean_places(p.get("places")),
           "walkways": [w for w in (_clean_rect(x) for x in p.get("walkways") or []) if w][:20],
           "outlets": [o for o in (_clean_point(x) for x in p.get("outlets") or []) if o][:20],
           "slack_m": _num(p.get("slack_m"), cables_mod.SLACK_M, 0, 3),
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


def controller_point(plan: dict, rig: dict) -> dict:
    """Where the computer is (mm).  A placed controller wins; otherwise the
    preference: a wing (stage left is the high-X side), behind or in front of
    the stage, front of house at its distance; ``auto`` starts at the
    stage-left wing until the planner moves it."""
    if "controller" in plan.get("places", {}):
        return dict(plan["places"]["controller"], h=0)
    w, d = rig["stage"]["w"], rig["stage"]["d"]
    c = plan["controller"]
    if c["mode"] == "foh":
        return {"x": w // 2, "z": d + round(c["distance_m"] * 1000), "h": 0}
    side = c["side"]
    if side == "stage-right":
        return {"x": -OFFSTAGE, "z": d - 500, "h": 0}
    if side == "back":
        return {"x": w // 2, "z": -OFFSTAGE // 2, "h": 0}
    if side == "front":
        return {"x": w // 2, "z": d + OFFSTAGE // 2, "h": 0}
    return {"x": w + OFFSTAGE, "z": d - 500, "h": 0}


def floor_for(plan: dict, rig: dict, extra_front: int = 0) -> tuple:
    """The :class:`route.Floor` and :class:`route.Router` for a plan."""
    trs = route_mod.trusses(rig["fixtures"])
    ctl = controller_point(plan, rig)
    front = max(route_mod.FRONT, ctl["z"] - rig["stage"]["d"] + 1000, extra_front)
    floor = route_mod.Floor(rig["stage"], [(k["x0"], k["z0"], k["x1"], k["z1"]) for k in rig["keep_out"]],
                            plan.get("walkways", []), [(t["z"], t["x0"], t["x1"]) for t in trs], front=front)
    return floor, route_mod.Router(floor), trs


def _fixture_point(f: dict, rig: dict, trs: List[dict]) -> dict:
    if f.get("place"):
        p = f["place"]
        tr = next((t["id"] for t in trs if f["id"] in t["fixtures"]), None)
        return {"x": p["x"], "z": p["z"], "h": max(0, p["bottom"]), "truss": tr}
    return {"x": rig["stage"]["w"] // 2, "z": rig["stage"]["d"] // 2, "h": 0, "estimated": True}


def item_point(plan: dict, rig: dict, item_id: str, items: Dict[str, dict]) -> dict:
    """Where a kit device stands: placed, or at the controller."""
    if item_id in plan.get("places", {}):
        p = plan["places"][item_id]
        return {"x": p["x"], "z": p["z"], "h": p.get("h", 0)}
    return controller_point(plan, rig)


def root_source(plan: dict, n: int, items: Dict[str, dict], seen=None) -> Optional[dict]:
    """The interface or node at the start of chain *n*: through a splitter,
    the chain that feeds that splitter."""
    seen = seen or set()
    if n in seen:
        return None
    seen.add(n)
    src = items.get(plan["chains"][n]["source"]["item"])
    if src is None or src["kind"] in ("interface", "node"):
        return src
    for m, ch in enumerate(plan["chains"]):
        if any(d.get("item") == src["id"] for d in ch["devices"]):
            return root_source(plan, m, items, seen)
    return None


def evaluate(plan: dict, rig: dict) -> dict:
    """Walk every chain of *plan* on *rig* (:func:`core.cabling.rig.read_rig`):
    ports, routes on the floor, lengths, cables from tonight's stock, checks.

    Returns ``{"fixtures", "chains", "issues", "summary", "totals",
    "controller", "trusses", "shopping"}``.  Each walked chain has its
    ``links`` with ``route`` (points, length), ``need_m`` and ``cables``."""
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
    floor, router, trs = floor_for(plan, rig)
    ctl = controller_point(plan, rig)
    walked, issues = [], []
    on_chain: Dict[str, int] = {}
    hops = []
    for n, ch in enumerate(plan["chains"]):
        src = items.get(ch["source"]["item"])
        outs = [p for p in (src or {}).get("ports", []) if p["role"] in ("out", "thru")]
        if src is None or not 0 <= ch["source"]["port"] < len(outs):
            issues.append(chain_mod._issue("C006", f"Chain {n + 1} starts from an output that is not in tonight's kit."))
            continue
        devs, pts = [], [item_point(plan, rig, src["id"], items)]
        for d in ch["devices"]:
            if "fixture" in d and d["fixture"] in fx:
                f = fx[d["fixture"]]
                devs.append(chain_mod.fixture_device(f, items.get(f["item_id"]) if f["item_id"] else None))
                pts.append(_fixture_point(f, rig, trs))
                on_chain[d["fixture"]] = n
            elif "item" in d and d["item"] in items:
                devs.append(dict(items[d["item"]]))
                pts.append(item_point(plan, rig, d["item"], items))
        fixed = [items.get(c) if c else None for c in ch["cables"]]
        fixed += [None] * (len(devs) - len(fixed))
        w = chain_mod.walk(src, outs[ch["source"]["port"]], devs, inv, fixed, ch["label"])
        w["source"] = ch["source"]
        w["n"] = n
        unis = sorted({fx[d["fixture"]]["universe"] for d in ch["devices"] if d.get("fixture") in fx})
        if len(unis) > 1:
            w["issues"].append(chain_mod._issue("C004", f"{w['name']} carries universes "
                                                + ", ".join(str(int(u) + 1) for u in unis) + ".", w["name"],
                                                "Move the fixtures, or use another output."))
        w["universes"] = unis
        for i, link in enumerate(w["links"]):
            r = router.hop(pts[i], pts[i + 1])
            link["route"] = r
            link["need_m"] = cables_mod.need_m(r["length"], plan["slack_m"])
            if link["conn"] in ("xlr3", "xlr5") and not fixed[i]:
                hops.append({"key": f"{n}:{i}", "need": link["need_m"], "conn": link["conn"]})
            elif fixed[i]:
                link["cables"] = [{"id": fixed[i]["id"], "name": fixed[i]["name"],
                                   "length": fixed[i]["length"], "type": fixed[i].get("type", "dmx")}]
                if fixed[i]["length"] < link["need_m"]:
                    w["issues"].append(chain_mod._issue(
                        "C005", f"{fixed[i]['name']} is too short for {link['from']} → {link['to']} "
                        f"({link['need_m']:g} m needed).", link["to"], "Let the planner pick the cable."))
            else:
                link["cables"] = []
        w["points"] = pts
        walked.append(w)
    assigned = cables_mod.assign(hops, inv)
    for n, w in enumerate(walked):
        total = 0.0
        for i, link in enumerate(w["links"]):
            got = assigned["by_hop"].get(f"{w['n']}:{i}")
            if got is not None:
                link["cables"] = got["cables"]
                link["joined"] = got["joined"]
                link["missing_m"] = got["missing"]
                if got["joined"]:
                    w["issues"].append(chain_mod._issue(
                        "C011", f"{link['from']} → {link['to']}: two cables joined ("
                        + " + ".join(f"{c['length']:g} m" for c in got["cables"]) + ").", link["to"],
                        "A single longer cable, or a shorter route."))
                if got["mic"]:
                    w["issues"].append(chain_mod._issue("C010", f"{link['from']} → {link['to']}: a microphone "
                                                        "cable is used for DMX.", link["to"],
                                                        "Use a 110 Ω DMX cable."))
            total += sum(c["length"] for c in link.get("cables", []))
            r = link["route"]
            for wi in r.get("walkways", []):
                wk = plan["walkways"][wi]
                if not wk["ramp"]:
                    w["issues"].append(chain_mod._issue(
                        "C007", f"{link['from']} → {link['to']} crosses the walkway"
                        + (f" {wk['label']}" if wk["label"] else "") + ".", link["to"],
                        "Tape it, use a cable ramp, or go round."))
            if r.get("audience") and plan["controller"]["mode"] == "foh" and plan["controller"]["route"] == "unknown":
                w["issues"].append(chain_mod._issue(
                    "C017", f"{link['from']} → {link['to']} runs {round(r['flat'] / 1000)} m across the audience "
                    "floor by a route not confirmed.", link["to"],
                    "Say how it goes (along a wall, taped, overhead), or use a node or a wireless pair."))
        w["total_m"] = round(total, 1)
        if total > LONG_CHAIN_M:
            w["issues"].append(chain_mod._issue("C011", f"{w['name']}: {total:g} m of cable on one chain.",
                                                w["name"], "Split it with a splitter output."))
        src = items.get(w["source"]["item"])
        nfx = sum(1 for d in plan["chains"][w["n"]]["devices"] if "fixture" in d)
        if src and src["kind"] in ("interface", "node") and (nfx > DAISY_FIXTURES or (nfx and total > DAISY_M)):
            w["issues"].append(chain_mod._issue(
                "C012", f"{w['name']}: {nfx} fixtures and {total:g} m on one daisy chain: "
                "one that fails darkens every one after it.", w["name"],
                "Use a splitter output for each group."))
    issues += chain_mod.check(walked, inv)
    # interfaces: USB reach, and the show's output
    for it in kit_mod.by_kind(inv, "interface"):
        if any(c["source"]["item"] == it["id"] for c in plan["chains"]):
            p = item_point(plan, rig, it["id"], items)
            dist = ((p["x"] - ctl["x"]) ** 2 + (p["z"] - ctl["z"]) ** 2) ** 0.5
            if dist > USB_MAX_MM and "usb" in [q["conn"] for q in it["ports"]]:
                issues.append(chain_mod._issue(
                    "C016", f"{it['name']} is {dist / 1000:.1f} m from the computer: USB reaches 5 m.",
                    it["name"], "Keep the interface by the computer and run DMX instead."))
    if plan["controller"]["mode"] == "auto":
        near = [o for o in plan["outlets"] if ((o["x"] - ctl["x"]) ** 2 + (o["z"] - ctl["z"]) ** 2) ** 0.5 <= 3000]
        if not near:
            issues.append(chain_mod._issue("C016", "No power outlet marked within 3 m of the controller.",
                                           fix="Mark the outlets on Places, or bring an extension."))
    issues += _universe_checks(plan, rig, fx, items)
    used_dev = sorted({c["source"]["item"] for c in plan["chains"]}
                      | {d["item"] for c in plan["chains"] for d in c["devices"] if d.get("item")})
    for iid in used_dev:
        it = items.get(iid)
        if it is not None and it["count"] < 1:
            issues.append(chain_mod._issue("C005", f"{it['name']} is not in tonight's kit.", it["name"],
                                           f"Add it to the kit, or buy one.", {"what": it["name"], "count": 1}))
    missing = [f for f in fx.values() if f["id"] not in on_chain]
    if plan["chains"] and missing:
        issues.append(chain_mod._issue("C006", "Not on any chain: " + ", ".join(f["name"] for f in missing) + ".",
                                       fix="Add them to a chain."))
    for f in fx.values():
        if f["place"] is None:
            issues.append(chain_mod._issue("C013", f"{f['name']} is not on the 3D stage; its route is estimated.",
                                           f["name"], "Place it in Stage & Meshes."))
    for m in assigned["missing"]:
        issues.append(chain_mod._issue(
            "C005", f"{m['count']} × {kit_mod.CONNECTOR_LABEL[m['conn']]} cable of {m['length']:g} m missing.",
            fix=f"Add {m['count']} × {m['length']:g} m to the shopping list."))
    allis = [i for w in walked for i in w["issues"]] + issues
    summary = {s: sum(1 for i in allis if i["severity"] == s) for s in ("error", "warning", "info")}
    links = [l for w in walked for l in w["links"] if l.get("route")]
    totals = {"cable_m": round(sum(w["total_m"] for w in walked), 1),
              "longest_m": max((l["need_m"] for l in links if l["conn"] in ("xlr3", "xlr5")), default=0),
              "joined": sum(1 for l in links if l.get("joined")),
              "crossings": sum(len(l["route"].get("walkways", [])) + int(bool(l["route"].get("audience")))
                               for l in links),
              "open_floor_m": round(sum(l["route"].get("open_floor_m", 0) for l in links), 1),
              "adapters": sum(len(w["adapters"]) for w in walked),
              "chains": len(walked)}
    return {"fixtures": list(fx.values()), "chains": walked, "issues": issues, "summary": summary,
            "totals": totals, "controller": ctl, "trusses": trs, "shopping": shopping(walked, issues, assigned)}


def _universe_checks(plan, rig, fx, items) -> List[dict]:
    out = []
    by_uni: Dict[str, set] = {}
    for n, ch in enumerate(plan["chains"]):
        src = root_source(plan, n, items)
        for d in ch["devices"]:
            if d.get("fixture") in fx and src is not None:
                by_uni.setdefault(fx[d["fixture"]]["universe"], set()).add(src["id"])
    for u in rig_mod.used_universes(rig):
        uni = next((x for x in rig["universes"] if x["id"] == u), {"id": u, "output": None})
        o = uni.get("output") or {}
        feeders = [items[i] for i in sorted(by_uni.get(u, ()))]
        if plan["chains"] and feeders:
            bad = [f for f in feeders if (f.get("plugin") or "").lower() != (o.get("plugin") or "").lower()]
            if bad:
                out.append(chain_mod._issue(
                    "C014", f"Universe {int(u) + 1} goes to {o.get('plugin') or 'no output'} in the show, "
                    f"but the plan feeds it from {bad[0]['name']}.", fix="Change the plan, or the universe's "
                    "output in QLC+ (Inputs/Outputs)."))
        elif rig_mod.interface_for(uni, plan["tonight"]) is None:
            out.append(chain_mod._issue("C014", f"Universe {int(u) + 1} goes to {o.get('name') or 'no output'}; "
                                        "no interface in tonight's kit matches it.",
                                        fix="Add the interface to the kit, or change the universe's output in QLC+."))
    return out


def shopping(walked: List[dict], issues: List[dict], assigned: dict) -> List[dict]:
    """What to buy: the cables missing, and everything a check put on the
    list (adapters, terminators, a device the kit lacks): ``[{what, count}]``."""
    out = [{"what": f"{kit_mod.CONNECTOR_LABEL[m['conn']]} DMX cable {m['length']:g} m", "count": m["count"]}
           for m in assigned["missing"]]
    for i in issues + [i for w in walked for i in w["issues"]]:
        if i.get("buy"):
            out.append(dict(i["buy"]))
    merged: Dict[str, int] = {}
    for o in out:
        merged[o["what"]] = merged.get(o["what"], 0) + o["count"]
    return [{"what": k, "count": v} for k, v in sorted(merged.items())]


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
