"""
core/cabling/outputs.py — what the crew gets
============================================

From an evaluated plan (:func:`core.cabling.plan.evaluate`):

* :func:`numbered` — every physical cable with a number, in load-in order;
* :func:`plot_svg` / :func:`plot_pdf` — the cabling plot: the stage from
  above, each chain in its colour, cable lengths, the computer, the
  splitter, adapters and terminators;
* :func:`pick_list` (+ CSV, PDF, text ticket) — what goes in the bag, the
  spares, and what to buy; venue items are left out;
* :func:`labels` (+ A4 label sheet PDF, text ticket) — one label per cable;
* :func:`load_in` — the order to lay the cables, chain by chain.

Every file is a download (a new file, never written over anything).
Deterministic: same plan, same bytes.
"""

from __future__ import annotations

import csv
import io
import zlib
from typing import Dict, List, Tuple

from core.cabling import kit as kit_mod
from core.cabling.units import fmt
from core.pdf import _pdf_str, assemble_pdf

COLOURS = ["#14b8a6", "#d97706", "#7c3aed", "#2563eb", "#db2777", "#65a30d", "#dc2626", "#0891b2"]
FEED = "#64748b"
RADIO = "#7c3aed"            # 3.15.0: what goes by radio


def _clean(s) -> str:
    from core.showbook import _pdf_clean
    s = str(s).replace("♂", " male").replace("♀", " female").replace("Ω", "Ohm").replace("·", "-")
    return _pdf_clean(s)


def chain_colour(n: int, w: dict) -> str:
    if w.get("links") and w["links"][0]["to"] and w.get("feed"):
        return FEED
    return COLOURS[n % len(COLOURS)]


def _is_feed(w: dict, items: Dict[str, dict]) -> bool:
    return bool(w["links"]) and all(not l.get("fixture") for l in w["links"]) and \
        all(l["to"] in {it["name"] for it in items.values() if it["kind"] in ("splitter", "node", "wireless_rx")}
            for l in w["links"])


def numbered(ev: dict, plan: dict) -> List[dict]:
    """Every cable of the plan, numbered: ``[{n, length, name, type, chain,
    chain_n, colour, from, to, joined, house}]``.  Feeds first, then the
    chains in their order, each from its output outwards."""
    items = {it["id"]: it for it in plan["tonight"]["items"]}
    house = {f["name"] for f in ev["fixtures"] if f["owner"] == "venue"}
    short = {it["name"]: it["name"].split(" ")[0] for it in items.values() if it["kind"] != "fixture"}
    order = sorted(range(len(ev["chains"])), key=lambda k: (not _is_feed(ev["chains"][k], items), k))
    out, n, colour_n = [], 0, 0
    for k in order:
        w = ev["chains"][k]
        feed = _is_feed(w, items)
        colour = FEED if feed else COLOURS[colour_n % len(COLOURS)]
        if not feed:
            colour_n += 1
        w["colour"] = colour
        w["feed"] = feed
        label = w["name"] if not feed else "Feed"
        for i, link in enumerate(w["links"]):
            cabs = link.get("cables") or []
            if not cabs and link.get("missing_m"):
                cabs = [{"name": f"(to buy) {fmt(link['missing_m'])}", "length": link["missing_m"], "type": "dmx",
                         "missing": True}]
            for j, c in enumerate(cabs):
                n += 1
                out.append({"n": n, "length": c["length"], "name": c["name"], "type": c.get("type", "dmx"),
                            "chain": label, "chain_n": k, "colour": colour,
                            "from": short.get(link["from"], link["from"]), "to": short.get(link["to"], link["to"]),
                            "joined": len(cabs) > 1, "part": j + 1 if len(cabs) > 1 else 0,
                            "missing": bool(c.get("missing")), "house": link["to"] in house,
                            "to_full": link["to"], "source": c.get("source", "")})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# the plot (one drawing, two renderers)
# ─────────────────────────────────────────────────────────────────────────────

def _drawing(ev: dict, plan: dict, rig: dict) -> Tuple[List[tuple], tuple]:
    """Shapes in mm: ("rect", x0, z0, x1, z1, fill, stroke, dash), ("line",
    pts, colour, width, dash), ("circle", x, z, r, fill, stroke), ("ring", x,
    z, r, stroke, dash), ("text", x, z, s, size, colour, anchor)."""
    st = rig["stage"]
    sh: List[tuple] = []
    sh.append(("rect", 0, 0, st["w"], st["d"], "#f1f5f9", "#475569", None))
    sh += _stage_dims(st, ev.get("controller") or {}, bool(rig.get("stage_show")))
    band = [] if plan.get("hide_band") else rig["keep_out"]   # 3.11.0: the meshes can be hidden
    for k in band:
        sh.append(("rect", k["x0"], k["z0"], k["x1"], k["z1"], "#fee2e2", "#ef4444", (4, 3)))
    for k in band:                                 # names on top of every box
        if k.get("label"):
            sh.append(("text", k["x0"] + 80, k["z0"] + 170, k["label"][:24], 110, "#b91c1c", "start"))
    for w in plan.get("walkways", []):
        sh.append(("rect", w["x0"], w["z0"], w["x1"], w["z1"], "#dbeafe", "#3b82f6", (2, 2)))
    for t in ev.get("trusses", []):
        sh.append(("line", [(t["x0"] - 200, t["z"]), (t["x1"] + 200, t["z"])], "#334155", 120, None))
    nums = numbered(ev, plan)
    wanted = []                                    # 3.15.0: cable labels, placed once everything is drawn
    for w in ev["chains"]:
        colour = w.get("colour", COLOURS[0])
        for link in w["links"]:
            pts = [tuple(p) for p in link["route"]["points"]]
            sh.append(("line", pts, colour, 45, (6, 3) if link["conn"] in ("rj45", "wireless") else None))
            if len(pts) >= 2 and (link.get("cables") or link.get("missing_m")):
                if link.get("cables"):
                    L, col = " + ".join(fmt(c["length"]) for c in link["cables"]), colour
                    if link.get("mark") in ("borrowed", "venue"):
                        L += f" ({link['mark']})"
                else:                              # none in the kit is long enough: the length to buy
                    L, col = f"{fmt(link['missing_m'])} to buy", "#dc2626"
                wanted.append((pts, L, col))
    terms = []
    names: List[tuple] = []                        # 3.15.0: fixture names, placed where they are free
    for w in ev["chains"]:
        if w.get("terminator"):
            last = w["links"][-1]["route"]["points"][-1] if w["links"] else None
            if last:
                ok = w["terminator"].get("id") is not None and not any(
                    i["code"] == "C002" and w["terminator"]["at"] in i["text"] for i in ev["issues"])
                terms.append((last, ok))
    for f in ev["fixtures"]:
        if not f.get("place"):
            continue
        x, z = f["place"]["x"], f["place"]["z"]
        venue = f["owner"] == "venue"
        if f.get("radio"):                         # 3.15.0: fed by radio: a dashed ring and the word
            sh.append(("ring", x, z, 250, RADIO, (3, 2)))
            sh.append(("text", x - 290, z + 40, "radio", 110, RADIO, "end"))
        sh.append(("circle", x, z, 170, "#ffffff" if venue else "#fecaca", "#334155"))
        names.append((x, z, f["name"]))
    for u in ev.get("units", []):                  # 3.15.0: wireless units the plan places
        if u["item"] in plan.get("places", {}) and u["kind"] == "wireless_tx":
            continue
        sh.append(("rect", u["x"] - 130, u["z"] - 90, u["x"] + 130, u["z"] + 90, "#ede9fe", RADIO, None))
        sh.append(("text", u["x"], u["z"] + 45, "RX" if u["kind"] == "wireless_rx" else "TX", 100, RADIO, "middle"))
    # 3.11.0: the terminator sits inside the last device, drawn after the fixtures so it is never hidden
    for last, ok in terms:
        sh.append(("circle", last[0], last[1], 120, "#ffffff" if ok else "#fee2e2", "#16a34a" if ok else "#dc2626"))
        sh.append(("text", last[0], last[1] + 52, "T", 150, "#16a34a" if ok else "#dc2626", "middle"))
    ctl = ev["controller"]
    sh.append(("rect", ctl["x"] - 300, ctl["z"] - 200, ctl["x"] + 300, ctl["z"] + 200, "#e2e8f0", "#0f172a", None))
    sh.append(("text", ctl["x"], ctl["z"] + 380, "Computer", 130, "#0f172a", "middle"))
    for iid, p in sorted(plan.get("places", {}).items()):
        if iid == "controller":
            continue
        sh.append(("rect", p["x"] - 180, p["z"] - 110, p["x"] + 180, p["z"] + 110, "#ccfbf1", "#0f766e", None))
        name = next((it["name"] for it in plan["tonight"]["items"] if it["id"] == iid), iid)
        sh.append(("text", p["x"], p["z"] + 300, name.split(" ")[0], 120, "#0f766e", "middle"))
    sh += _fixture_names(names, sh)
    sh += _cable_labels(wanted, sh)
    xs = [s[1] for s in sh if s[0] in ("rect", "circle", "ring", "text")] + [s[3] for s in sh if s[0] == "rect"]
    zs = [s[2] for s in sh if s[0] in ("rect", "circle", "ring", "text")] + [s[4] for s in sh if s[0] == "rect"]
    for s in sh:
        if s[0] == "tag":
            xs += [s[1] - s[6] / 2, s[1] + s[6] / 2]
            zs += [s[2] - s[7] / 2, s[2] + s[7] / 2]
    for s in sh:
        if s[0] == "line":
            xs += [p[0] for p in s[1]]
            zs += [p[1] for p in s[1]]
    pad = 500
    x0, z0, x1, z1 = min(xs) - pad, min(zs) - pad, max(xs) + pad, max(zs) + pad
    lx = max(x0 + 2300, x1 - 6200)                 # the legend, bottom right (3.15.0: kept inside the plot)
    if band:
        z1 += 250
        sh.append(("rect", lx, z1 - 330, lx + 250, z1 - 170, "#fee2e2", "#ef4444", (4, 3)))
        sh.append(("text", lx + 320, z1 - 190, "Band floor (meshes and the space round them): cables go round it", 120,
                   "#475569", "start"))
    if any(l["conn"] == "wireless" for w in ev["chains"] for l in w["links"]):   # 3.15.0
        z1 += 250
        sh.append(("line", [(lx, z1 - 240), (lx + 250, z1 - 240)], RADIO, 45, (6, 3)))
        sh.append(("text", lx + 320, z1 - 190, "By radio, no cable (RX: receiver, TX: transmitter; "
                   "a dashed ring marks a fixture fed by radio)", 120, "#475569", "start"))
    return sh, (x0, z0, x1, z1)


def _stage_dims(st: dict, ctl: dict, tonight: bool) -> List[tuple]:
    """The stage's width over its back edge and its depth on the side away
    from the computer, as dimension lines (3.17.0)."""
    w, d = st["w"], st["d"]
    grey = "#64748b"
    out = []
    zt = -330                                      # the width, over the back edge
    out.append(("line", [(0, zt), (w, zt)], grey, 14, None))
    for x in (0, w):
        out.append(("line", [(x, zt - 90), (x, zt + 90)], grey, 14, None))
    out.append(("line", [(0, zt), (110, zt - 55), (110, zt + 55), (0, zt)], grey, 14, None))
    out.append(("line", [(w, zt), (w - 110, zt - 55), (w - 110, zt + 55), (w, zt)], grey, 14, None))
    out.append(("text", w / 2, zt - 70, f"{fmt(w / 1000)} wide" + (" (tonight)" if tonight else ""), 140, grey, "middle"))
    left = (ctl.get("x", w) or 0) >= w / 2         # the depth goes on the side away from the computer
    xd = -330 if left else w + 330
    out.append(("line", [(xd, 0), (xd, d)], grey, 14, None))
    for z in (0, d):
        out.append(("line", [(xd - 90, z), (xd + 90, z)], grey, 14, None))
    out.append(("line", [(xd, 0), (xd - 55, 110), (xd + 55, 110), (xd, 0)], grey, 14, None))
    out.append(("line", [(xd, d), (xd - 55, d - 110), (xd + 55, d - 110), (xd, d)], grey, 14, None))
    out.append(("text", xd + (-90 if left else 90), d / 2, f"{fmt(d / 1000)} deep", 140, grey, "end" if left else "start"))
    return out


LABEL_SIZE = 125            # mm: the height of a cable label's text on the plot
LABEL_PAD = 45


def _text_box(x, z, txt, size, anchor) -> tuple:
    """The box (x0, z0, x1, z1) a text takes on the plot, roughly."""
    w = len(str(txt)) * size * 0.56
    x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
    return (x0, z - size * 0.85, x0 + w, z + size * 0.2)


def _overlap(a, b) -> float:
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dz = min(a[3], b[3]) - max(a[1], b[1])
    return dx * dz if dx > 0 and dz > 0 else 0.0


def _seg_hits_box(p, q, bx) -> bool:
    """Does the segment p-q pass through the box?"""
    x0, z0, x1, z1 = bx
    if max(p[0], q[0]) < x0 or min(p[0], q[0]) > x1 or max(p[1], q[1]) < z0 or min(p[1], q[1]) > z1:
        return False
    for k in range(9):                             # a few points along it are enough at this scale
        t = k / 8
        x, z = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
        if x0 <= x <= x1 and z0 <= z <= z1:
            return True
    return False


def _fixture_names(names, sh) -> List[tuple]:
    """Each fixture's name under it, or above, beside it when that covers
    less of the other fixtures, boxes and names (3.15.0)."""
    boxes = [(s[1] - s[3], s[2] - s[3], s[1] + s[3], s[2] + s[3]) for s in sh if s[0] == "circle"]
    boxes += [(s[1], s[2], s[3], s[4]) for s in sh if s[0] == "rect" and (s[3] - s[1]) * (s[4] - s[2]) < 400 * 400 * 4]
    out = []
    for x, z, name in names:
        best = None
        for k, (dx, dz, anchor) in enumerate(((0, 330, "middle"), (0, -230, "middle"), (230, 45, "start"),
                                             (-230, 45, "end"), (0, 470, "middle"), (0, -370, "middle"))):
            bx = _text_box(x + dx, z + dz, name, 120, anchor)
            cost = sum(_overlap(bx, b) for b in boxes) + k * 2000
            if best is None or cost < best[0]:
                best = (cost, ("text", x + dx, z + dz, name, 120, "#0f172a", anchor), bx)
        out.append(best[1])
        boxes.append(best[2])
    return out


def _cable_labels(wanted, sh) -> List[tuple]:
    """Cable lengths as labels on a white tag (3.15.0), each where it covers
    least: on its cable when that is free, else beside it with a thin leader
    to the cable.  Deterministic: tried in the order of the chains, each
    against the fixtures, names, boxes, other cables and labels already set."""
    boxes = []
    for s in sh:
        if s[0] == "circle":
            boxes.append((s[1] - s[3], s[2] - s[3], s[1] + s[3], s[2] + s[3]))
        elif s[0] == "text":
            boxes.append(_text_box(s[1], s[2], s[3], s[4], s[6]))
        elif s[0] == "rect" and (s[3] - s[1]) * (s[4] - s[2]) < 400 * 400 * 4:   # small boxes, not the stage
            boxes.append((s[1], s[2], s[3], s[4]))
    segs = [(i, (s[1][k], s[1][k + 1])) for i, s in enumerate(sh) if s[0] == "line"
            for k in range(len(s[1]) - 1)]
    out: List[tuple] = []
    placed = []
    for pts, txt, col in wanted:
        own = [(pts[k], pts[k + 1]) for k in range(len(pts) - 1)]
        w = len(txt) * LABEL_SIZE * 0.56 + 2 * LABEL_PAD
        h = LABEL_SIZE + 2 * LABEL_PAD
        best = None
        order = sorted(range(len(own)), key=lambda k: -((own[k][1][0] - own[k][0][0]) ** 2
                                                       + (own[k][1][1] - own[k][0][1]) ** 2))
        for rank, k in enumerate(order[:4]):
            (ax, az), (bx_, bz) = own[k]
            L = ((bx_ - ax) ** 2 + (bz - az) ** 2) ** 0.5 or 1.0
            nx, nz = -(bz - az) / L, (bx_ - ax) / L        # across the cable
            for t in (0.5, 0.3, 0.7):
                px, pz = ax + (bx_ - ax) * t, az + (bz - az) * t
                for d in (0, 260, -260, 420, -420, 650, -650):
                    cx, cz = px + nx * d, pz + nz * d
                    if d:                          # keep the tag clear of its own cable
                        cx += nx * (w / 2 if d > 0 else -w / 2) * abs(nx) * 0.6
                        cz += nz * (h / 2 if d > 0 else -h / 2) * abs(nz) * 0.6
                    box = (cx - w / 2, cz - h / 2, cx + w / 2, cz + h / 2)
                    cost = sum(_overlap(box, b) for b in boxes) / 1000 * 3
                    cost += sum(_overlap(box, b) for b in placed) / 1000 * 6
                    cost += sum(40 for _, (p, q) in segs if (p, q) not in own and _seg_hits_box(p, q, box))
                    cost += abs(d) / 25 + rank * 8 + abs(t - 0.5) * 20
                    if not d and L < w * 1.1:
                        cost += 60                 # the tag would hide a short cable
                    if best is None or cost < best[0] - 1e-6:
                        best = (cost, cx, cz, px, pz, d, box)
        if best is None:
            continue
        _, cx, cz, px, pz, d, box = best
        placed.append(box)
        if d:                                      # a leader from the tag to its cable
            ex = min(max(px, box[0]), box[2])
            ez = min(max(pz, box[1]), box[3])
            out.append(("line", [(ex, ez), (px, pz)], col, 14, None))
            out.append(("circle", px, pz, 38, col, col))
        out.append(("tag", cx, cz, txt, LABEL_SIZE, col, w, h))
    return out


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def plot_svg(ev: dict, plan: dict, rig: dict, title: str = "") -> str:
    """The cabling plot as one SVG (mm units, audience at the bottom)."""
    sh, (x0, z0, x1, z1) = _drawing(ev, plan, rig)
    w, h = x1 - x0, z1 - z0
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {z0:.0f} {w:.0f} {h:.0f}" '
           f'role="img" aria-label="{_esc(title or "Cabling plot")}" font-family="sans-serif">']
    for s in sh:
        if s[0] == "rect":
            _, a, b, c, d, fill, stroke, dash = s
            da = f' stroke-dasharray="{dash[0] * 20} {dash[1] * 20}"' if dash else ""
            out.append(f'<rect x="{a:.0f}" y="{b:.0f}" width="{c - a:.0f}" height="{d - b:.0f}" fill="{fill}" '
                       f'stroke="{stroke}" stroke-width="20"{da}/>')
        elif s[0] == "line":
            _, pts, col, wd, dash = s
            da = f' stroke-dasharray="{dash[0] * 20} {dash[1] * 20}"' if dash else ""
            out.append(f'<polyline points="{" ".join(f"{p[0]:.0f},{p[1]:.0f}" for p in pts)}" fill="none" '
                       f'stroke="{col}" stroke-width="{wd}" stroke-linejoin="round"{da}/>')
        elif s[0] == "circle":
            _, x, z, r, fill, stroke = s
            out.append(f'<circle cx="{x:.0f}" cy="{z:.0f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="25"/>')
        elif s[0] == "tag":
            _, x, z, txt, size, col, w, h = s
            out.append(f'<rect x="{x - w / 2:.0f}" y="{z - h / 2:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{h / 2:.0f}" '
                       f'fill="#ffffff" fill-opacity="0.94" stroke="{col}" stroke-width="18"/>'
                       f'<text x="{x:.0f}" y="{z + size * 0.36:.0f}" font-size="{size}" font-weight="600" fill="{col}" '
                       f'text-anchor="middle">{_esc(txt)}</text>')
        elif s[0] == "ring":
            _, x, z, r, stroke, dash = s
            out.append(f'<circle cx="{x:.0f}" cy="{z:.0f}" r="{r}" fill="none" stroke="{stroke}" stroke-width="35" '
                       f'stroke-dasharray="{dash[0] * 20} {dash[1] * 20}"/>')
        elif s[0] == "text":
            _, x, z, txt, size, col, anchor = s
            out.append(f'<text x="{x:.0f}" y="{z:.0f}" font-size="{size}" fill="{col}" '      # 3.15.0: a white halo
                       f'stroke="#ffffff" stroke-width="{size * 0.28:.0f}" stroke-linejoin="round" paint-order="stroke" '
                       f'text-anchor="{anchor}">{_esc(txt)}</text>')
    out.append(f'<text x="{x0 + 200:.0f}" y="{z1 - 150:.0f}" font-size="160" fill="#475569">AUDIENCE ↓</text>')
    out.append("</svg>")
    return "\n".join(out)


def _hexrgb(h: str) -> str:
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return f"{r:.3f} {g:.3f} {b:.3f}"


def _plot_stream(ev, plan, rig, title, W, H, top_pad=40, bottom=20, side=20) -> bytes:
    sh, (x0, z0, x1, z1) = _drawing(ev, plan, rig)
    k = min((W - 2 * side) / (x1 - x0), (H - top_pad - bottom) / (z1 - z0))
    ox = side + ((W - 2 * side) - (x1 - x0) * k) / 2

    def X(x):
        return ox + (x - x0) * k

    def Y(z):
        return H - top_pad - (z - z0) * k

    ops = [f"BT /F2 14 Tf {side:.1f} {H - 24:.1f} Td ({_pdf_str(_clean(title or 'Cabling plot'))}) Tj ET"]
    for s in sh:
        if s[0] == "rect":
            _, a, b, c, d, fill, stroke, dash = s
            ops.append(f"{_hexrgb(fill)} rg {_hexrgb(stroke)} RG 0.6 w " + ("[3 2] 0 d " if dash else "[] 0 d ")
                       + f"{X(a):.2f} {Y(d):.2f} {(c - a) * k:.2f} {(d - b) * k:.2f} re B")
        elif s[0] == "line":
            _, pts, col, wd, dash = s
            seg = " ".join(f"{X(p[0]):.2f} {Y(p[1]):.2f} {'m' if i == 0 else 'l'}" for i, p in enumerate(pts))
            ops.append(f"{_hexrgb(col)} RG {max(0.6, wd * k):.2f} w 1 J 1 j " + ("[4 2] 0 d " if dash else "[] 0 d ")
                       + seg + " S")
        elif s[0] == "circle":
            _, x, z, r, fill, stroke = s
            cx, cy, rr = X(x), Y(z), r * k
            c = 0.5523 * rr
            ops.append(f"{_hexrgb(fill)} rg {_hexrgb(stroke)} RG 0.6 w [] 0 d "
                       f"{cx + rr:.2f} {cy:.2f} m {cx + rr:.2f} {cy + c:.2f} {cx + c:.2f} {cy + rr:.2f} {cx:.2f} {cy + rr:.2f} c "
                       f"{cx - c:.2f} {cy + rr:.2f} {cx - rr:.2f} {cy + c:.2f} {cx - rr:.2f} {cy:.2f} c "
                       f"{cx - rr:.2f} {cy - c:.2f} {cx - c:.2f} {cy - rr:.2f} {cx:.2f} {cy - rr:.2f} c "
                       f"{cx + c:.2f} {cy - rr:.2f} {cx + rr:.2f} {cy - c:.2f} {cx + rr:.2f} {cy:.2f} c B")
        elif s[0] == "tag":
            _, x, z, txt, size, col, w, h = s
            ops.append(f"1 1 1 rg {_hexrgb(col)} RG 0.5 w [] 0 d "
                       f"{X(x - w / 2):.2f} {Y(z + h / 2):.2f} {w * k:.2f} {h * k:.2f} re B")
            sz = max(5.0, size * k)
            t = _clean(txt)
            ops.append(f"{_hexrgb(col)} rg BT /F2 {sz:.1f} Tf {X(x) - len(t) * sz * 0.27:.2f} "
                       f"{Y(z + size * 0.36):.2f} Td ({_pdf_str(t)}) Tj ET")
        elif s[0] == "ring":
            _, x, z, r, stroke, dash = s
            cx, cy, rr = X(x), Y(z), r * k
            c = 0.5523 * rr
            ops.append(f"{_hexrgb(stroke)} RG 0.9 w [2 1.5] 0 d "
                       f"{cx + rr:.2f} {cy:.2f} m {cx + rr:.2f} {cy + c:.2f} {cx + c:.2f} {cy + rr:.2f} {cx:.2f} {cy + rr:.2f} c "
                       f"{cx - c:.2f} {cy + rr:.2f} {cx - rr:.2f} {cy + c:.2f} {cx - rr:.2f} {cy:.2f} c "
                       f"{cx - rr:.2f} {cy - c:.2f} {cx - c:.2f} {cy - rr:.2f} {cx:.2f} {cy - rr:.2f} c "
                       f"{cx + c:.2f} {cy - rr:.2f} {cx + rr:.2f} {cy - c:.2f} {cx + rr:.2f} {cy:.2f} c S")
        elif s[0] == "text":
            _, x, z, txt, size, col, anchor = s
            sz = max(5.0, size * k)
            t = _clean(txt)
            tx = X(x) - (len(t) * sz * 0.25 if anchor == "middle" else 0)
            ops.append(f"{_hexrgb(col)} rg BT /F1 {sz:.1f} Tf {tx:.2f} {Y(z):.2f} Td ({_pdf_str(t)}) Tj ET")
    ops.append(f"0.3 0.3 0.4 rg BT /F1 8 Tf {side:.1f} 8 Td (Audience at the bottom. "
               f"Lengths in m, slack included.) Tj ET")
    return zlib.compress("\n".join(ops).encode("latin-1", "replace"))


def plot_pdf(ev: dict, plan: dict, rig: dict, title: str = "") -> bytes:
    """The cabling plot on one A4 landscape page."""
    W, H = 842.0, 595.0
    return assemble_pdf([_plot_stream(ev, plan, rig, title, W, H)], W, H)


# ─────────────────────────────────────────────────────────────────────────────
# pick list
# ─────────────────────────────────────────────────────────────────────────────

def pick_list(ev: dict, plan: dict) -> dict:
    """``{"bag": [{what, count}], "spares": [...], "buy": [...]}``."""
    items = {it["id"]: it for it in plan["tonight"]["items"]}
    bag: Dict[str, int] = {}

    def add(what, n=1):
        bag[what] = bag.get(what, 0) + n
    used_dev = set()
    n_used: Dict[str, int] = {}
    for c in plan["chains"]:
        used_dev.add(c["source"]["item"])
        used_dev |= {d["item"] for d in c["devices"] if d.get("item")}
        for d in c["devices"]:
            if d.get("item"):
                n_used[d["item"]] = n_used.get(d["item"], 0) + 1
    for iid in sorted(used_dev):
        it = items.get(iid)
        if it and it.get("count", 0) > 0 and it.get("owner") != "venue" and it.get("power") != "computer":
            n = min(n_used.get(iid, 1), it["count"]) if it["kind"] == "wireless_rx" else 1   # 3.15.0
            add(it["name"] + (" + power supply" if it.get("power") in ("mains", "dc adapter") else ""), n)
    for w in ev["chains"]:
        for a in w["adapters"]:
            if a in items:
                add(items[a]["name"])
        t = w.get("terminator")
        if t and t.get("id") and t["id"] in items:
            add(items[t["id"]]["name"])
    cab: Dict[float, int] = {}
    other: Dict[str, Dict[str, int]] = {"venue": {}, "borrowed": {}}   # 3.11.0: cables not from your kit
    for c in numbered(ev, plan):
        if c.get("source") in other:
            what = c["name"].rsplit(" (", 1)[0]
            other[c["source"]][what] = other[c["source"]].get(what, 0) + 1
        elif not c["missing"]:
            key = (c["name"])
            add(key)
            cab[c["length"]] = cab.get(c["length"], 0) + 1
    # terminators beyond the kit are in "buy"; count what the kit covers
    for k, v in list(bag.items()):
        it = next((i for i in items.values() if i["name"] == k), None)
        if it and v > it.get("count", 0) and it["kind"] in ("terminator", "adapter"):
            bag[k] = it.get("count", 0)
    spares = []
    for it in sorted(items.values(), key=lambda i: (i.get("length", 0), i["name"])):
        if it["kind"] == "cable" and it.get("length") in cab:
            left = it["count"] - bag.get(it["name"], 0)
            if left > 0:
                spares.append({"what": it["name"], "count": 1})
    return {"bag": [{"what": k, "count": v} for k, v in sorted(bag.items()) if v > 0],
            "spares": spares, "buy": list(ev.get("shopping", [])),
            "venue": [{"what": k, "count": v} for k, v in sorted(other["venue"].items())],
            "borrowed": [{"what": k, "count": v} for k, v in sorted(other["borrowed"].items())]}


def pick_list_csv(pl: dict) -> str:
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(["Section", "Item", "Count"])
    for sec, key in (("Bag", "bag"), ("Spare", "spares"), ("To buy", "buy"),
                     ("From the venue", "venue"), ("Borrowed", "borrowed")):
        for r in pl.get(key, []):
            wr.writerow([sec, r["what"], r["count"]])
    return buf.getvalue()


def pick_list_text(pl: dict, show: str, date: str, width: int = 32) -> str:
    lines = [show.upper()[:width], f"DMX cabling · {date}"[:width], "-" * width]

    def block(title, rows):
        if rows:
            lines.append(title)
            for r in rows:
                cnt = f"{r['count']} x "
                lines.append((cnt + r["what"])[:width])
            lines.append("-" * width)
    block("IN THE BAG", pl["bag"])
    block("SPARES", pl["spares"])
    block("TO BUY", pl["buy"])
    block("FROM THE VENUE", pl.get("venue", []))
    block("BORROWED", pl.get("borrowed", []))
    return "\n".join(lines) + "\n"


def _table_pages(title: str, sub: str, sections: List[Tuple[str, List[List[str]]]], W=595.0, H=842.0):
    pages, ops, y = [], [], H - 40

    def head():
        nonlocal ops, y
        ops = [f"BT /F2 15 Tf 36 {H - 40:.1f} Td ({_pdf_str(_clean(title))}) Tj ET",
               f"0.35 0.35 0.45 rg BT /F1 9 Tf 36 {H - 56:.1f} Td ({_pdf_str(_clean(sub))}) Tj ET 0 0 0 rg"]
        y = H - 84
    head()
    for name, rows in sections:
        if y < 90:
            pages.append(zlib.compress("\n".join(ops).encode("latin-1", "replace")))
            head()
        ops.append(f"0.15 0.2 0.3 rg BT /F2 11 Tf 36 {y:.1f} Td ({_pdf_str(_clean(name))}) Tj ET 0 0 0 rg")
        y -= 18
        for r in rows:
            if y < 50:
                pages.append(zlib.compress("\n".join(ops).encode("latin-1", "replace")))
                head()
            x = 36
            for i, cell in enumerate(r):
                wcol = [40, 300, 120, 120][i] if i < 4 else 80
                ops.append(f"BT /F1 9.5 Tf {x:.1f} {y:.1f} Td ({_pdf_str(_clean(cell))}) Tj ET")
                x += wcol
            y -= 15
        y -= 10
    pages.append(zlib.compress("\n".join(ops).encode("latin-1", "replace")))
    return pages


def pick_list_pdf(pl: dict, show: str, date: str) -> bytes:
    secs = []
    for name, key in (("In the bag", "bag"), ("Spares", "spares"), ("To buy", "buy"),
                      ("From the venue", "venue"), ("Borrowed", "borrowed")):
        if pl.get(key):
            secs.append((name, [["[ ]", f"{r['count']} x {r['what']}"] for r in pl[key]]))
    pages = _table_pages(f"{show} - DMX pick list", f"Cabling plan of {date}", secs)
    return assemble_pdf(pages, 595.0, 842.0)


# ─────────────────────────────────────────────────────────────────────────────
# labels and load-in order
# ─────────────────────────────────────────────────────────────────────────────

def label_lines(c: dict) -> Tuple[str, str]:
    top = f"#{c['n']} · {fmt(c['length'])} · {c['chain'].split(' ')[-2] + ' ' + c['chain'].split(' ')[-1] if ' OUT ' in c['chain'] else c['chain']}"
    bottom = f"{c['from']} → {c['to']}" + (" (HOUSE)" if c["house"] else "") + (
        f" · part {c['part']}" if c["part"] else "")
    return top, bottom


def labels_text(nums: List[dict], width: int = 32) -> str:
    out = []
    for c in nums:
        if c["missing"]:
            continue
        t, b = label_lines(c)
        out += [t[:width], b[:width], "-" * width]
    return "\n".join(out) + "\n"


def labels_pdf(nums: List[dict], show: str) -> bytes:
    """A4 sheets of 3 × 8 labels (70 × 37 mm), a stripe in the chain's colour."""
    W, H = 595.0, 842.0
    cols, rows = 3, 8
    lw, lh = W / cols, H / rows
    pages, ops = [], []
    k = 0
    for c in nums:
        if c["missing"]:
            continue
        if k and k % (cols * rows) == 0:
            pages.append(zlib.compress("\n".join(ops).encode("latin-1", "replace")))
            ops = []
        i = k % (cols * rows)
        x, y = (i % cols) * lw, H - (i // cols + 1) * lh
        t, b = label_lines(c)
        ops.append(f"{_hexrgb(c['colour'])} rg {x + 8:.1f} {y + 10:.1f} 6 {lh - 20:.1f} re f 0 0 0 rg")
        ops.append(f"BT /F2 12 Tf {x + 20:.1f} {y + lh - 30:.1f} Td ({_pdf_str(_clean(t))}) Tj ET")
        ops.append(f"BT /F1 9 Tf {x + 20:.1f} {y + lh - 48:.1f} Td ({_pdf_str(_clean(b)[:44])}) Tj ET")
        ops.append(f"0.4 0.4 0.5 rg BT /F1 7 Tf {x + 20:.1f} {y + 14:.1f} Td ({_pdf_str(_clean(show)[:40])}) Tj ET 0 0 0 rg")
        k += 1
    pages.append(zlib.compress("\n".join(ops).encode("latin-1", "replace")))
    return assemble_pdf(pages, W, H)


def load_in(ev: dict, plan: dict) -> List[str]:
    """The order to lay the cables: computer and interface, splitter, the
    feed, then each chain from its output outwards, terminators last."""
    items = {it["id"]: it for it in plan["tonight"]["items"]}
    nums = numbered(ev, plan)
    steps = []
    ctl = plan["controller"]
    where = {"stand": ctl["side"].replace("-", " ") + (" wing" if "stage" in ctl["side"] else ""),
             "foh": f"front of house, {fmt(ctl['distance_m'])} from the stage", "auto": "where the plan puts it"}
    ifaces = sorted({c["source"]["item"] for c in plan["chains"] if items.get(c["source"]["item"], {}).get("kind") == "interface"
                     and items[c["source"]["item"]].get("power") != "computer"})
    names = ", ".join(items[i]["name"] for i in ifaces)
    steps.append(f"Computer and {names} at the {where[ctl['mode']]}." if names
                 else f"Computer at the {where[ctl['mode']]}.")
    for w in ev["chains"]:
        for a in {a["at"]: a for l in w["links"] for a in l["adapters"]}.values():
            steps.append(f"{a['name']} on {a['at']}.")
    for iid, p in sorted(plan.get("places", {}).items()):
        if iid != "controller" and iid in items:
            steps.append(f"{items[iid]['name']} at {fmt(round(p['x'] / 1000, 1))} from the left, "
                         f"{fmt(round(p['z'] / 1000, 1))} from the back; power it.")
    for u in ev.get("units", []):                  # 3.15.0
        if u["item"] in plan.get("places", {}) and u["kind"] == "wireless_tx":
            continue
        steps.append(f"{u['name']} next to {u['near']}; power it.")
    by_chain: Dict[int, List[dict]] = {}
    for c in nums:
        by_chain.setdefault(c["chain_n"], []).append(c)
    for k in sorted(by_chain, key=lambda k: by_chain[k][0]["n"]):
        cs = by_chain[k]
        w = ev["chains"][k]
        hops = ", ".join(f"#{c['n']} {fmt(c['length'])} to {c['to']}" for c in cs)
        line = f"{cs[0]['chain']}: {hops}."
        t = w.get("terminator")
        if t:
            line += f" Terminator on {t['at']}."
        steps.append(line)
    for iid in sorted({c["source"]["item"] for c in plan["chains"]} | {d["item"] for c in plan["chains"]
                                                                       for d in c["devices"] if d.get("item")}):
        it = items.get(iid)
        if it and it["kind"] == "splitter" and it.get("termination") == "switch":
            steps.append(f"{it['name']}: switch its termination on.")
    for w in ev["chains"]:
        for i in w["issues"]:
            if i["code"] == "C009":
                steps.append(f"{i['where']}: check its termination; without a switch, a terminator on its thru.")
    steps.append("Start QLC+ and run PANIC RESET: every fixture should go dark.")
    return steps
