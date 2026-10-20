"""
core/cabling/cables.py — cables from tonight's stock
====================================================

Each hop of a plan needs its route length plus slack at both ends.  The
cables are handed out from tonight's inventory, **longest hops first**, each
hop getting the shortest DMX cable that is long enough.  When none is long
enough, two cables are joined (the pair with the least spare length) and the
join is reported (C011).  A microphone cable is used only when no DMX cable
fits, and is reported (C010).  What cannot be covered is listed as missing,
rounded up to a length one can buy (C005).

Deterministic: ties go to the lower item id.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from core.cabling import kit as kit_mod
from core.cabling import units as units_mod

SLACK_M = 0.5                         # at each end
BUY_LENGTHS = (1.5, 3, 5, 10, 15, 20, 25, 30, 50)


def need_m(route_mm: float, slack_m: float = SLACK_M) -> float:
    """Metres of cable a route of *route_mm* needs, slack included."""
    return round(route_mm / 1000 + 2 * slack_m, 2)


def buy_length(m: float) -> float:
    """The shortest length sold (in the user's unit) that covers *m* metres."""
    for L in units_mod.buy_lengths_m():
        if L >= m:
            return L
    if units_mod.current() == "ft":
        return round(math.ceil(m / units_mod.FT / 50) * 50 * units_mod.FT, 2)
    return float(math.ceil(m / 10) * 10)


def _pool(inventory: dict, conn: str) -> List[dict]:
    """One entry per physical cable with the given connector, sorted."""
    out = []
    for it in kit_mod.by_kind(inventory, "cable"):
        if it["a"]["conn"] != conn:
            continue
        for n in range(it["count"]):
            out.append({"id": it["id"], "name": it["name"], "length": it["length"], "type": it.get("type", "dmx"),
                        "n": n})
    out.sort(key=lambda c: (c["type"] != "dmx", c["length"], c["id"], c["n"]))
    return out


def assign(hops: List[dict], inventory: dict) -> dict:
    """Hand out cables.  ``hops``: ``[{"key", "need" (m), "conn"}]``.

    Returns ``{"by_hop": {key: {"cables": [{id, name, length, type}],
    "joined", "mic", "missing": m | None}}, "missing": [{conn, length,
    count}], "used": {item id: count}}``."""
    pools: Dict[str, List[dict]] = {}
    by_hop: Dict[str, dict] = {}
    order = sorted(hops, key=lambda h: (-h["need"], str(h["key"])))
    for h in order:
        pool = pools.setdefault(h["conn"], _pool(inventory, h["conn"]))
        res = {"cables": [], "joined": False, "mic": False, "missing": None}
        pick = _single(pool, h["need"])
        if pick is None:
            pair = _pair(pool, h["need"])
            if pair is not None:
                for c in pair:
                    pool.remove(c)
                res["cables"] = [_pub(c) for c in pair]
                res["joined"] = True
                res["mic"] = any(c["type"] == "mic" for c in pair)
            else:
                res["missing"] = buy_length(h["need"])
        else:
            pool.remove(pick)
            res["cables"] = [_pub(pick)]
            res["mic"] = pick["type"] == "mic"
        by_hop[h["key"]] = res
    used: Dict[str, int] = {}
    for r in by_hop.values():
        for c in r["cables"]:
            used[c["id"]] = used.get(c["id"], 0) + 1
    miss: Dict[tuple, int] = {}
    for h in hops:
        m = by_hop[h["key"]]["missing"]
        if m:
            miss[(h["conn"], m)] = miss.get((h["conn"], m), 0) + 1
    return {"by_hop": by_hop, "used": used,
            "missing": [{"conn": c, "length": L, "count": n} for (c, L), n in sorted(miss.items())]}


def _pub(c: dict) -> dict:
    return {"id": c["id"], "name": c["name"], "length": c["length"], "type": c["type"]}


def _single(pool: List[dict], need: float) -> Optional[dict]:
    dmx = [c for c in pool if c["type"] == "dmx" and c["length"] >= need]
    if dmx:
        return dmx[0]
    mic = [c for c in pool if c["type"] == "mic" and c["length"] >= need]
    return mic[0] if mic else None


def _pair(pool: List[dict], need: float):
    best = None
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            tot = a["length"] + b["length"]
            if tot < need:
                continue
            key = (int(a["type"] == "mic") + int(b["type"] == "mic"), tot, a["id"], b["id"])
            if best is None or key < best[0]:
                best = (key, (a, b))
    return best[1] if best else None
