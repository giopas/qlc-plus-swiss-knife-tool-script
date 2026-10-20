"""
core/cabling/auto.py — the automatic plan
=========================================

Proposes two or three ways to cable the show, each a complete plan (the same
shape as one made by hand, so it can be changed afterwards) with its
evaluation, compared on total cable, longest hop, crossings, adapters and
what is missing.

How one alternative is built, per universe:

1. **Where the computer is** comes from the controller preference (where I
   stand, front of house, or chosen by the planner among a few spots).
2. **Groups**: hung fixtures on one truss form one group; the others are
   grouped by where they stand (left, centre, right × back, front of the
   stage).  A group of one joins the group it saves most cable with.  When
   there are more groups than splitter outputs, the two whose merge costs
   least are merged, until they fit.
3. **Order inside a group**: the order that needs least cable from the
   splitter (exact up to 9 fixtures, nearest neighbour plus 2-opt above).
4. The splitter tries a few places (at the computer, along the back wall,
   the sides) and keeps the best.

The alternatives: *splitter on stage*, *splitter at the computer*, *one
daisy chain* (no splitter); from front of house: *one long DMX feed* and
*a node on the network*; when the planner chooses: the best spots for the
computer.  Devices the kit lacks (a splitter, a node) are proposed anyway,
marked missing (C005), so the comparison shows what buying one would give.

Deterministic: same show, same kit, same places, same plans.
"""

from __future__ import annotations

import copy
import itertools
from typing import Dict, List, Optional, Tuple

from core.cabling import kit as kit_mod
from core.cabling import plan as plan_mod
from core.cabling import rig as rig_mod

EXACT_MAX = 9


def fid_key(fid: str):
    """Fixture ids in order: the show's (numbers) first, then the ones found
    on the day (``x1``, ``x2``…)."""
    return (0, int(fid)) if fid.isdigit() else (1, int(fid[1:]) if fid[1:].isdigit() else 0)


# ─────────────────────────────────────────────────────────────────────────────
# ordering
# ─────────────────────────────────────────────────────────────────────────────

def order(start: int, nodes: List[int], dist) -> Tuple[List[int], float]:
    """Open path from *start* through every node, least total ``dist``."""
    if not nodes:
        return [], 0.0
    if len(nodes) <= EXACT_MAX:
        return _held_karp(start, nodes, dist)
    return _two_opt(start, _nearest(start, nodes, dist), dist)


def _held_karp(start, nodes, dist):
    n = len(nodes)
    best: Dict[Tuple[int, int], Tuple[float, int]] = {}
    for i in range(n):
        best[(1 << i, i)] = (dist(start, nodes[i]), -1)
    for size in range(2, n + 1):
        for subset in itertools.combinations(range(n), size):
            mask = 0
            for i in subset:
                mask |= 1 << i
            for j in subset:
                pm = mask & ~(1 << j)
                cand = None
                for k in subset:
                    if k == j:
                        continue
                    c = best[(pm, k)][0] + dist(nodes[k], nodes[j])
                    if cand is None or c < cand[0] - 1e-9:
                        cand = (c, k)
                best[(mask, j)] = cand
    full = (1 << n) - 1
    end = min(range(n), key=lambda j: (best[(full, j)][0], j))
    total = best[(full, end)][0]
    path, mask, j = [], full, end
    while j != -1:
        path.append(nodes[j])
        pj = best[(mask, j)][1]
        mask &= ~(1 << j)
        j = pj
    return path[::-1], total


def _nearest(start, nodes, dist):
    left, path, cur = list(nodes), [], start
    while left:
        nxt = min(left, key=lambda x: (dist(cur, x), x))
        path.append(nxt)
        left.remove(nxt)
        cur = nxt
    return path


def _cost(start, path, dist):
    tot, cur = 0.0, start
    for p in path:
        tot += dist(cur, p)
        cur = p
    return tot


def _two_opt(start, path, dist):
    best, bc = list(path), _cost(start, path, dist)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                c = _cost(start, cand, dist)
                if c < bc - 1e-6:
                    best, bc, improved = cand, c, True
    return best, bc


# ─────────────────────────────────────────────────────────────────────────────
# groups
# ─────────────────────────────────────────────────────────────────────────────

def zones(fixtures: List[dict], stage: dict, trusses: List[dict]) -> List[List[str]]:
    """Fixture ids grouped by truss, then by where they stand."""
    on_truss = {fid: t["id"] for t in trusses for fid in t["fixtures"]}
    groups: Dict[str, List[str]] = {}
    w, d = stage["w"], stage["d"]
    for f in fixtures:
        if f["id"] in on_truss:
            key = on_truss[f["id"]]
        elif f.get("place"):
            x, z = f["place"]["x"], f["place"]["z"]
            col = "left" if x < w / 3 else ("right" if x > 2 * w / 3 else "centre")
            row = "back" if z < d / 2 else "front"
            key = f"{row}-{col}"
        else:
            key = "unplaced"
        groups.setdefault(key, []).append(f["id"])
    return [groups[k] for k in sorted(groups)]


class _Costs:
    """Distances between named points (splitter, fixtures), cached."""

    def __init__(self, router, points: Dict[str, dict]):
        self.router, self.points, self.cache = router, points, {}

    def __call__(self, a, b):
        k = (a, b) if a <= b else (b, a)
        if k not in self.cache:
            self.cache[k] = self.router.hop(self.points[a], self.points[b])["length"] / 1000 + 1.0
        return self.cache[k]


def _chain_cost(src, ids, cost):
    return order(src, list(ids), cost)


def build_groups(src: str, fixtures: List[dict], stage: dict, trusses, cost, outputs: int,
                 drive: int = kit_mod.DEFAULT_DRIVE) -> List[Tuple[List[str], float]]:
    """Ordered chains ``[(fixture ids, metres)]`` for one source point."""
    gs = [sorted(g, key=fid_key) for g in zones(fixtures, stage, trusses)]
    trussy = {fid for t in trusses for fid in t["fixtures"]}

    def merged_cost(a, b):
        return _chain_cost(src, a + b, cost)[1]

    # a group of one joins the group it saves most with (never a truss's own group alone)
    changed = True
    while changed:
        changed = False
        singles = [g for g in gs if len(g) == 1 and g[0] not in trussy]
        for s in singles:
            others = [g for g in gs if g is not s]
            if not others:
                break
            here = _chain_cost(src, s, cost)[1]
            best = min(others, key=lambda g: (merged_cost(g, s) - _chain_cost(src, g, cost)[1] - here, g[0]))
            if len(best) + 1 <= drive:
                gs.remove(s)
                best.extend(s)
                changed = True
                break
    while len(gs) > max(1, outputs):
        best = None
        for i, a in enumerate(gs):
            for b in gs[i + 1:]:
                if len(a) + len(b) > drive:
                    continue
                extra = merged_cost(a, b) - _chain_cost(src, a, cost)[1] - _chain_cost(src, b, cost)[1]
                key = (extra, a[0], b[0])
                if best is None or key < best[0]:
                    best = (key, a, b)
        if best is None:
            break
        _k, a, b = best
        gs.remove(b)
        a.extend(b)
    out = []
    for g in gs:
        path, c = _chain_cost(src, g, cost)
        out.append((path, c))
    out.sort(key=lambda pc: fid_key(pc[0][0]) if pc[0] else (0, 0))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# alternatives
# ─────────────────────────────────────────────────────────────────────────────

def _ensure(tonight: dict, kind: str, preset: str) -> str:
    """The id of a usable item of *kind* in tonight's kit; a missing one is
    added from the preset with count 0 (shown as missing)."""
    have = kit_mod.by_kind(tonight, kind)
    if have:
        return have[0]["id"]
    item = copy.deepcopy(kit_mod.PRESETS[preset])
    item["count"] = 0
    item["owner"] = "mine"
    tonight["items"].append(kit_mod.clean_item(item))
    kit_mod._number(tonight["items"])
    return tonight["items"][-1]["id"]


def _outs(item: dict) -> List[int]:
    """Indexes (in out+thru order, as plan chains count them) of real outputs."""
    ports = [p for p in item["ports"] if p["role"] in ("out", "thru")]
    return [i for i, p in enumerate(ports) if p["role"] == "out"]


def _interface_for_uni(rig, uni_id, tonight) -> str:
    uni = next((u for u in rig["universes"] if u["id"] == uni_id), {"id": uni_id, "output": None})
    it = rig_mod.interface_for(uni, tonight)
    return it["id"] if it else _ensure(tonight, "interface", "enttec_usb_pro")


def _free_outs(item: dict, used: Dict[Tuple[str, int], int]) -> List[int]:
    """Outputs of *item* with a socket left (one per unit you own)."""
    units = max(item.get("count", 0), 1)
    return [o for o in _outs(item) if used.get((item["id"], o), 0) < units]


def _interface_with_room(rig, uni_id, tonight, used) -> str:
    """The interface for a universe that still has a free output: the one the
    show names first, then any other; when every one is taken, one more is
    added from the preset with count 0 (shown as missing)."""
    first = _interface_for_uni(rig, uni_id, tonight)
    items = {it["id"]: it for it in tonight["items"]}
    dmx = [it["id"] for it in kit_mod.by_kind(tonight, "interface")
           if it["id"] != first and any(p["conn"] in ("xlr3", "xlr5") for p in it["ports"] if p["role"] == "out")]
    for iid in [first] + dmx:
        if _free_outs(items[iid], used):
            return iid
    item = copy.deepcopy(kit_mod.PRESETS["enttec_usb_pro"])
    item.update(count=0, owner="mine", name=f"{item['name']} (universe {int(uni_id) + 1})")
    tonight["items"].append(kit_mod.clean_item(item))
    kit_mod._number(tonight["items"])
    return tonight["items"][-1]["id"]


CLEAR_MM = 700


def _clear_of_fixtures(spot: dict, rig: dict) -> dict:
    """*spot*, moved a little when a fixture (or what hangs above) is on it,
    so the plot shows both."""
    pts = [(f["place"]["x"], f["place"]["z"]) for f in rig["fixtures"] if f.get("place")]
    w, d = rig["stage"]["w"], rig["stage"]["d"]
    on_stage = 0 <= spot["x"] <= w and 0 <= spot["z"] <= d
    for dx, dz in ((0, 0), (0, 600), (600, 0), (-600, 0), (600, 600), (-600, 600), (1200, 0), (-1200, 0), (0, 1200)):
        x, z = spot["x"] + dx, spot["z"] + dz
        if on_stage:                               # a splitter on the stage stays on it
            x, z = min(max(x, 150), w - 150), min(max(z, 150), d - 150)
        if all((x - a) ** 2 + (z - b) ** 2 >= CLEAR_MM ** 2 for a, b in pts):
            return {**spot, "x": x, "z": z}
    return spot


def splitter_spots(stage: dict, ctl: dict) -> List[Tuple[str, dict]]:
    w, d = stage["w"], stage["d"]
    return [("at the computer", None),
            ("back wall, centre", {"x": w // 2, "z": 150}),
            ("back wall, stage right", {"x": round(w * 0.15), "z": 150}),
            ("back wall, stage left", {"x": round(w * 0.85), "z": 150}),
            ("stage-left side", {"x": w - 150, "z": d // 2}),
            ("stage-right side", {"x": 150, "z": d // 2})]


def _fill(plan: dict, rig: dict, src_item: str, src_point_key: Optional[str], via: Optional[str],
          via_place: Optional[dict], router, trs, mode: str) -> dict:
    """Chains for every universe: ``via`` is the splitter/node item (or None:
    straight from the interface)."""
    p = copy.deepcopy(plan)
    p["chains"] = []
    items = {it["id"]: it for it in p["tonight"]["items"]}
    if via and via_place:
        p["places"][via] = _clear_of_fixtures(dict(via_place), rig)
    unis = rig_mod.used_universes(rig)
    used: Dict[Tuple[str, int], int] = {}
    for n, u in enumerate(unis):
        fxs = [f for f in rig["fixtures"] if f["universe"] == u]
        items = {it["id"]: it for it in p["tonight"]["items"]}
        use_via = via if (via and (n == 0 or items[via]["kind"] == "node")) else None
        if use_via and n == 0 and items[use_via]["kind"] == "splitter":
            iface = _interface_with_room(rig, u, p["tonight"], used)
            items = {it["id"]: it for it in p["tonight"]["items"]}
            port = _free_outs(items[iface], used)[0]
            used[(iface, port)] = used.get((iface, port), 0) + 1
            p["chains"].append({"source": {"item": iface, "port": port}, "devices": [{"item": use_via}],
                                "label": "Feed"})
        if use_via:
            source = use_via
        elif src_item and items.get(src_item, {}).get("kind") == "node":
            source = src_item
        else:
            source = _interface_with_room(rig, u, p["tonight"], used)
            items = {it["id"]: it for it in p["tonight"]["items"]}
        start = plan_mod.item_point(p, rig, source, items)
        outs = _free_outs(items[source], used) or _outs(items[source])[-1:]
        if items[source]["kind"] == "node":
            outs = outs[:1]                        # each output of a node is one universe
        pts = {"S": start}
        for f in fxs:
            pts[f["id"]] = plan_mod._fixture_point(f, rig, trs)
        cost = _Costs(router, pts)
        drive = min((items[source]["ports"][0].get("drive", kit_mod.DEFAULT_DRIVE),
                     kit_mod.DEFAULT_DRIVE))
        if mode == "daisy":
            chains = [order("S", [f["id"] for f in fxs], cost)]
        else:
            chains = build_groups("S", fxs, rig["stage"], trs, cost, len(outs), drive)
        for k, (ids, _c) in enumerate(chains):
            port = outs[k] if k < len(outs) else outs[-1]
            used[(source, port)] = used.get((source, port), 0) + 1
            p["chains"].append({"source": {"item": source, "port": port},
                                "devices": [{"fixture": i} for i in ids], "label": ""})
    _feed_nodes(p)
    return plan_mod.clean_plan(p)


def _ensure_lan(tonight: dict) -> str:
    """The computer's network port in tonight's kit (it is the computer: count 1)."""
    have = [it for it in kit_mod.by_kind(tonight, "interface")
            if any(q["role"] == "out" and q["conn"] == "rj45" for q in it["ports"])]
    if have:
        return have[0]["id"]
    item = copy.deepcopy(kit_mod.PRESETS["computer_lan"])
    item.update(count=1, owner="mine")
    tonight["items"].append(kit_mod.clean_item(item))
    kit_mod._number(tonight["items"])
    return tonight["items"][-1]["id"]


def _feed_nodes(p: dict) -> None:
    """Every node used gets a network cable from the computer (one chain)."""
    items = {it["id"]: it for it in p["tonight"]["items"]}
    fed = {d.get("item") for c in p["chains"] for d in c["devices"]}
    nodes = sorted({c["source"]["item"] for c in p["chains"]
                    if items.get(c["source"]["item"], {}).get("kind") == "node"} - fed)
    for k, node in enumerate(nodes):
        lan = _ensure_lan(p["tonight"])
        p["chains"].insert(k, {"source": {"item": lan, "port": 0}, "devices": [{"item": node}], "label": "Network"})


def _wireless(base: dict, rig: dict, a: dict, tonight: dict) -> Optional[dict]:
    """*a* (a plan with a splitter fed from the computer) with the feed sent by
    radio: transmitter at the computer, receiver by the splitter."""
    p = copy.deepcopy(a["plan"])
    tx = _ensure(p["tonight"], "wireless_tx", "wireless_tx")
    rx = _ensure(p["tonight"], "wireless_rx", "wireless_rx")
    feed = next((c for c in p["chains"] if c.get("label") == "Feed"), None)
    if feed is None:
        return None
    sp = feed["devices"][-1].get("item")
    feed["devices"] = [{"item": tx}, {"item": rx}] + feed["devices"]
    feed["cables"] = []
    spot = p["places"].get(sp)
    if spot:
        p["places"][rx] = {"x": spot["x"], "z": max(spot["z"] - 450, 100), "h": 0}
    return plan_mod.clean_plan(p)


def score(ev: dict) -> float:
    t = ev["totals"]
    missing = sum(1 for i in ev["issues"] if i["code"] == "C005")
    devices = sum(1 for i in ev["issues"] if i["code"] == "C005" and i.get("where"))
    errors = ev["summary"]["error"]
    allis = ev["issues"] + [i for c in ev["chains"] for i in c["issues"]]
    daisy = sum(1 for i in allis if i["code"] == "C012")      # one failing fixture darkens the rest
    radio = sum(1 for c in ev["chains"] for l in c["links"] if l.get("conn") == "wireless")   # a cable is surer
    band = sum(l["route"].get("band_m", 0) for c in ev["chains"] for l in c["links"] if l.get("route"))
    return round(t["cable_m"] + 0.5 * t["open_floor_m"] + 4 * t["crossings"] + 3 * t["joined"]
                 + 15 * missing + 40 * devices + 5 * errors + 10 * daisy + 2 * band + 5 * radio, 2)


def _alt(key, name, p, rig, note="") -> dict:
    ev = plan_mod.evaluate(p, rig)
    t = ev["totals"]
    return {"key": key, "name": name, "note": note, "plan": p, "evaluation": ev, "score": score(ev),
            "cable_m": t["cable_m"], "longest_m": t["longest_m"], "crossings": t["crossings"],
            "adapters": t["adapters"], "joined": t["joined"], "summary": ev["summary"],
            "missing": [s for s in ev["shopping"]]}


def _best_splitter(base, rig, router, trs, splitter, iface):
    ctl = plan_mod.controller_point(base, rig)
    best = None
    for label, spot in splitter_spots(rig["stage"], ctl):
        if spot is None:
            continue
        p = _fill(base, rig, iface, None, splitter, dict(spot, h=0), router, trs, "split")
        a = _alt("", label, p, rig)
        if best is None or (a["score"], label) < (best[0]["score"], best[1]):
            best = (a, label)
    return best


def alternatives(plan: dict, rig: dict) -> List[dict]:
    """Two or three alternatives for the plan's controller preference, best
    first.  The input plan's tonight, owners, walkways, outlets and slack are
    kept; its chains and places are replaced (a placed controller stays)."""
    base = plan_mod.clean_plan(plan)
    rig = plan_mod.with_extras(rig, base)
    base["chains"] = []
    base["places"] = {k: v for k, v in base["places"].items() if k == "controller"}
    tonight = base["tonight"]
    uni0 = rig_mod.used_universes(rig)[:1]
    iface = _interface_for_uni(rig, uni0[0], tonight) if uni0 else _ensure(tonight, "interface", "enttec_usb_pro")
    mode = base["controller"]["mode"]
    out: List[dict] = []
    if mode == "auto":
        cands = []
        w, d = rig["stage"]["w"], rig["stage"]["d"]
        spots = [("stage-left wing", {"x": w + 1000, "z": d - 500}),
                 ("stage-right wing", {"x": -1000, "z": d - 500}),
                 ("behind the stage", {"x": w // 2, "z": -500}),
                 ("under the truss", {"x": w // 2, "z": 150})]
        splitter = _ensure(tonight, "splitter", "lixada_1x8")
        for label, spot in spots:
            p = copy.deepcopy(base)
            p["places"]["controller"] = dict(spot)
            floor, router, trs = plan_mod.floor_for(p, rig)
            pl = _fill(p, rig, iface, None, splitter, dict(spot, h=0), router, trs, "split")
            cands.append(_alt("", f"Computer {label}", pl, rig, "splitter next to it"))
        cands.sort(key=lambda a: (a["score"], a["name"]))
        out = cands[:3]
    elif mode == "foh":
        floor, router, trs = plan_mod.floor_for(base, rig)
        splitter = _ensure(tonight, "splitter", "lixada_1x8")
        best = _best_splitter(base, rig, router, trs, splitter, iface)
        if best:
            a = best[0]
            a["name"] = "One long DMX feed"
            a["note"] = f"splitter {best[1]}"
            out.append(a)
        node = _ensure(tonight, "node", "artnet_node_2")
        nb = None
        for label, spot in splitter_spots(rig["stage"], plan_mod.controller_point(base, rig)):
            if spot is None:
                continue
            pl = _fill(base, rig, node, None, node, dict(spot, h=0), router, trs, "split")
            a = _alt("", "Node on the network", pl, rig, f"node {label}, no DMX cable across the audience")
            if nb is None or (a["score"], label) < (nb[0]["score"], nb[1]):
                nb = (a, label)
        if nb:
            out.append(nb[0])
        if best:                                   # the same, the feed by radio (no cable across the audience)
            wp = _wireless(base, rig, best[0], tonight)
            if wp:
                out.append(_alt("", "Wireless to the stage", wp, rig,
                                f"transmitter at the computer, receiver by the splitter ({best[1]})"))
    else:
        floor, router, trs = plan_mod.floor_for(base, rig)
        splitter = _ensure(tonight, "splitter", "lixada_1x8")
        best = _best_splitter(base, rig, router, trs, splitter, iface)
        if best:
            a = best[0]
            a["name"] = "Splitter on stage"
            a["note"] = best[1]
            out.append(a)
        pl = _fill(base, rig, iface, None, splitter, None, router, trs, "split")
        out.append(_alt("", "Splitter at the computer", pl, rig, "short feed, longer runs"))
        pl = _fill(base, rig, iface, None, None, None, router, trs, "daisy")
        out.append(_alt("", "One daisy chain", pl, rig, "no splitter"))
        if best and kit_mod.by_kind(tonight, "wireless_tx") and kit_mod.by_kind(tonight, "wireless_rx"):
            wp = _wireless(base, rig, best[0], tonight)
            if wp:
                out.append(_alt("", "Wireless to the stage", wp, rig,
                                f"transmitter at the computer, receiver by the splitter ({best[1]})"))
    out.sort(key=lambda a: (a["score"], a["name"]))
    for k, a in enumerate(out):
        a["key"] = "ABCDEF"[k]
        a["best"] = k == 0
    return out
