"""
core/cabling/route.py — where a cable can go, and how long it is
=================================================================

The floor around the stage is a grid of 25 cm cells, seen from above:
``x`` from the stage's left edge as seen from the audience, ``z`` from the
back edge towards the audience (the 3D monitor's own axes, in mm).  The grid
reaches past the stage into the wings, behind it, and in front of it as far
as the controller needs (front of house).

What a cell costs a cable:

* a **run** — the stage's edges, the back wall, a truss line — costs 1;
* open floor costs 3, so cables keep to runs where they can;
* the audience floor (in front of the stage) costs 3 and is reported;
* a **walkway** costs 3 and is reported unless it has a ramp;
* the **band floor** (meshes plus the space round them, 50 cm unless the plan
  says otherwise) costs 10, so cables go round it,
  but where it covers a stage edge the edge still costs 2: a cable may run
  along the front lip under the singer's feet, taped, rather than make a
  long detour.  The metres crossed are reported (away from the two ends:
  a fixture standing in the band floor has to be reached).

Height: a device has a height (its underside, mm).  Two devices on the same
**truss** (hung fixtures in a row at one height) are joined along it; any
other hop goes down to the floor and up again, so the climb is added.

Deterministic: same input, same paths (ties broken by cell order).
"""

from __future__ import annotations

import heapq
import math
from typing import Dict, List, Optional, Tuple

CELL = 250                 # mm
WING = 2000                # mm of floor beside the stage
BACK = 1000                # mm behind the stage
FRONT = 1500               # mm in front of the stage (more for front of house)
RUN_EDGE = 300             # mm from an edge that counts as on the edge run
COST_RUN, COST_FLOOR, COST_ENTRY = 1.0, 3.0, 20.0
COST_BAND, COST_BAND_EDGE = 10.0, 2.0
BAND_FREE_MM = 1000         # band floor this close to an end is not reported
TRUSS_GAP = 2500           # mm: hung fixtures closer than this, at one height, share a truss
TRUSS_DZ = 400
TRUSS_DH = 250
FLOOR_MM = 2000            # a device lower than this is reached from the floor directly


def trusses(fixtures: List[dict], hung_mm: int = 1500) -> List[dict]:
    """Rows of hung fixtures at one height and depth: ``[{id, z, h, x0, x1,
    fixtures: [ids]}]``.  A single hung fixture is not a truss."""
    hung = sorted([f for f in fixtures if f.get("place") and f["place"]["bottom"] > hung_mm],
                  key=lambda f: (round(f["place"]["bottom"] / 100), round(f["place"]["z"] / 100), f["place"]["x"]))
    rows: List[List[dict]] = []
    for f in hung:
        p = f["place"]
        for r in rows:
            q = r[-1]["place"]
            if (abs(q["bottom"] - p["bottom"]) <= TRUSS_DH and abs(q["z"] - p["z"]) <= TRUSS_DZ
                    and abs(q["x"] - p["x"]) <= TRUSS_GAP):
                r.append(f)
                break
        else:
            rows.append([f])
    out = []
    for r in rows:
        if len(r) < 2:
            continue
        xs = [f["place"]["x"] for f in r]
        out.append({"id": f"truss{len(out) + 1}",
                    "z": round(sum(f["place"]["z"] for f in r) / len(r)),
                    "h": round(sum(f["place"]["bottom"] for f in r) / len(r)),
                    "x0": min(xs), "x1": max(xs), "fixtures": [f["id"] for f in r]})
    return out


class Floor:
    """The grid and its costs.  ``stage`` is ``{"w", "d"}`` in mm."""

    def __init__(self, stage: dict, keep_out=(), walkways=(), truss_lines=(), front: int = FRONT,
                 extra_runs=()):
        self.w, self.d = int(stage["w"]), int(stage["d"])
        self.x0, self.z0 = -WING, -BACK
        self.x1, self.z1 = self.w + WING, self.d + max(FRONT, int(front))
        self.nx = int(math.ceil((self.x1 - self.x0) / CELL)) + 1
        self.nz = int(math.ceil((self.z1 - self.z0) / CELL)) + 1
        self.keep_out = [tuple(r) for r in keep_out]
        self.walkways = list(walkways)
        n = self.nx * self.nz
        self.cost = [COST_FLOOR] * n
        self.closed = [False] * n
        self.walk = [None] * n          # index of the walkway a cell is on
        self.audience = [False] * n
        self.band = [False] * n
        for i in range(self.nx):
            for k in range(self.nz):
                x, z = self.pos(i, k)
                c = self.idx(i, k)
                on_stage = 0 <= x <= self.w and 0 <= z <= self.d
                near_edge = on_stage and (x <= RUN_EDGE or x >= self.w - RUN_EDGE or z <= RUN_EDGE
                                          or z >= self.d - RUN_EDGE)
                # just off the stage, along its sides and back wall: a run too
                off_edge = (not on_stage and z <= self.d and
                            (-RUN_EDGE <= x <= self.w + RUN_EDGE) and (-RUN_EDGE <= z))
                if near_edge or off_edge:
                    self.cost[c] = COST_RUN
                if z > self.d + RUN_EDGE:
                    self.audience[c] = True
                for (a, b, e, f) in self.keep_out:
                    if a <= x <= e and b <= z <= f:
                        self.band[c] = True
                        self.cost[c] = COST_BAND_EDGE if (near_edge or off_edge) else COST_BAND
                        break
                for wi, wk in enumerate(self.walkways):
                    if wk["x0"] <= x <= wk["x1"] and wk["z0"] <= z <= wk["z1"]:
                        self.walk[c] = wi
        for (za, xa, xb) in truss_lines:            # the floor under a truss line is a run
            self._line_run(xa, za, xb, za)
        for (xa, za, xb, zb) in extra_runs:
            self._line_run(xa, za, xb, zb)

    def _line_run(self, xa, za, xb, zb):
        steps = max(1, int(max(abs(xb - xa), abs(zb - za)) / (CELL / 2)))
        for s in range(steps + 1):
            x = xa + (xb - xa) * s / steps
            z = za + (zb - za) * s / steps
            i, k = self.cell(x, z)
            c = self.idx(i, k)
            if not self.closed[c] and not self.band[c]:
                self.cost[c] = COST_RUN

    # grid helpers
    def idx(self, i, k):
        return k * self.nx + i

    def pos(self, i, k):
        return self.x0 + i * CELL, self.z0 + k * CELL

    def cell(self, x, z):
        i = min(max(int(round((x - self.x0) / CELL)), 0), self.nx - 1)
        k = min(max(int(round((z - self.z0) / CELL)), 0), self.nz - 1)
        return i, k

    def dijkstra(self, x, z):
        """Cost and parent of every cell from the point (x, z).  The start's
        own cell and its neighbours inside a keep-out may be crossed."""
        si, sk = self.cell(x, z)
        start = self.idx(si, sk)
        n = self.nx * self.nz
        dist = [math.inf] * n
        par = [-1] * n
        dist[start] = 0.0
        heap = [(0.0, start)]
        diag = math.sqrt(2)
        while heap:
            d, c = heapq.heappop(heap)
            if d > dist[c]:
                continue
            ci, ck = c % self.nx, c // self.nx
            for di, dk, m in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
                              (1, 1, diag), (1, -1, diag), (-1, 1, diag), (-1, -1, diag)):
                ni, nk = ci + di, ck + dk
                if not (0 <= ni < self.nx and 0 <= nk < self.nz):
                    continue
                nc = self.idx(ni, nk)
                if self.closed[nc]:
                    if c != start and not self.closed[c]:
                        continue
                    step = COST_ENTRY        # leaving a device inside the keep-out
                else:
                    step = (self.cost[c] + self.cost[nc]) / 2
                nd = d + step * m
                if nd < dist[nc] - 1e-9:
                    dist[nc] = nd
                    par[nc] = c
                    heapq.heappush(heap, (nd, nc))
        return dist, par

    def path(self, tree, x, z) -> Optional[List[int]]:
        """Cells from the tree's start to the point (x, z); a point inside a
        keep-out is reached from the nearest open cell."""
        dist, par = tree
        i, k = self.cell(x, z)
        c = self.idx(i, k)
        if dist[c] == math.inf:
            best, bc = math.inf, None
            for di in range(-6, 7):
                for dk in range(-6, 7):
                    ni, nk = i + di, k + dk
                    if 0 <= ni < self.nx and 0 <= nk < self.nz:
                        nc = self.idx(ni, nk)
                        v = dist[nc] + COST_ENTRY * math.hypot(di, dk)
                        if v < best:
                            best, bc = v, nc
            if bc is None:
                return None
            cells = self._walk_back(par, bc)
            return cells + [c]
        return self._walk_back(par, c)

    @staticmethod
    def _walk_back(par, c):
        out = []
        while c != -1:
            out.append(c)
            c = par[c]
        return out[::-1]

    def describe(self, cells: List[int], start_xz, end_xz) -> dict:
        """Horizontal length (mm), the polyline, and what it crosses."""
        pts = [start_xz] + [self.pos(c % self.nx, c // self.nx) for c in cells[1:-1]] + [end_xz]
        pts = _simplify(pts)
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
        walks = sorted({self.walk[c] for c in cells if self.walk[c] is not None})
        floor_cells = sum(1 for c in cells if self.cost[c] > COST_RUN and not self.audience[c])
        band_cells = 0
        for c in cells:
            if self.band[c]:
                x, z = self.pos(c % self.nx, c // self.nx)
                if min(math.hypot(x - start_xz[0], z - start_xz[1]),
                       math.hypot(x - end_xz[0], z - end_xz[1])) > BAND_FREE_MM:
                    band_cells += 1
        return {"length": round(length), "points": [[round(p[0]), round(p[1])] for p in pts],
                "walkways": walks, "audience": any(self.audience[c] for c in cells),
                "open_floor_m": round(floor_cells * CELL / 1000, 2),
                "band_m": round(band_cells * CELL / 1000, 2)}


def _simplify(pts):
    """Drop points on a straight line (keeps the corners)."""
    if len(pts) < 3:
        return list(pts)
    out = [pts[0]]
    for a, b in zip(pts[1:], pts[2:]):
        p = out[-1]
        cross = (a[0] - p[0]) * (b[1] - p[1]) - (a[1] - p[1]) * (b[0] - p[0])
        if abs(cross) > 1e-6:
            out.append(a)
    out.append(pts[-1])
    return out


class Router:
    """Distances between points on one :class:`Floor`, with height.

    A point is ``{"x", "z", "h", "truss"?}``; ``h`` is its height (mm).
    Trees are cached per start point."""

    def __init__(self, floor: Floor):
        self.floor = floor
        self._trees: Dict[Tuple[int, int], tuple] = {}

    def _tree(self, x, z):
        key = self.floor.cell(x, z)
        if key not in self._trees:
            self._trees[key] = self.floor.dijkstra(x, z)
        return self._trees[key]

    def hop(self, a: dict, b: dict) -> dict:
        """The cable route from *a* to *b*: ``{"length" (mm, with the climb),
        "flat", "climb", "points", "walkways", "audience", "open_floor_m"}``."""
        if a.get("truss") and a.get("truss") == b.get("truss"):
            flat = math.hypot(b["x"] - a["x"], b["z"] - a["z"])
            climb = abs(a.get("h", 0) - b.get("h", 0))
            return {"length": round(flat + climb), "flat": round(flat), "climb": round(climb),
                    "points": [[a["x"], a["z"]], [b["x"], b["z"]]], "walkways": [],
                    "audience": False, "open_floor_m": 0.0, "band_m": 0.0, "truss": a["truss"]}
        tree = self._tree(a["x"], a["z"])
        cells = self.floor.path(tree, b["x"], b["z"])
        if cells is None:
            flat = math.hypot(b["x"] - a["x"], b["z"] - a["z"]) * 1.5
            d = {"length": round(flat), "points": [[a["x"], a["z"]], [b["x"], b["z"]]], "walkways": [],
                 "audience": False, "open_floor_m": round(flat / 1000, 2), "band_m": 0.0, "estimated": True}
        else:
            d = self.floor.describe(cells, (a["x"], a["z"]), (b["x"], b["z"]))
        climb = _climb(a.get("h", 0)) + _climb(b.get("h", 0))
        d["flat"] = d["length"]
        d["climb"] = climb
        d["length"] = d["flat"] + climb
        return d


def _climb(h) -> int:
    """Up a stand or truss leg to a device at height *h* (mm); a device on
    the floor or a low stand is reached directly."""
    h = h or 0
    return int(h) if h > 600 else 0
