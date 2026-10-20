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
                            "to_full": link["to"]})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# the plot (one drawing, two renderers)
# ─────────────────────────────────────────────────────────────────────────────

def _drawing(ev: dict, plan: dict, rig: dict) -> Tuple[List[tuple], tuple]:
    """Shapes in mm: ("rect", x0, z0, x1, z1, fill, stroke, dash), ("line",
    pts, colour, width, dash), ("circle", x, z, r, fill, stroke), ("text", x,
    z, s, size, colour, anchor)."""
    st = rig["stage"]
    sh: List[tuple] = []
    sh.append(("rect", 0, 0, st["w"], st["d"], "#f1f5f9", "#475569", None))
    for k in rig["keep_out"]:
        sh.append(("rect", k["x0"], k["z0"], k["x1"], k["z1"], "#fee2e2", "#ef4444", (4, 3)))
    for k in rig["keep_out"]:                      # names on top of every box
        if k.get("label"):
            sh.append(("text", k["x0"] + 80, k["z0"] + 170, k["label"][:24], 110, "#b91c1c", "start"))
    for w in plan.get("walkways", []):
        sh.append(("rect", w["x0"], w["z0"], w["x1"], w["z1"], "#dbeafe", "#3b82f6", (2, 2)))
    for t in ev.get("trusses", []):
        sh.append(("line", [(t["x0"] - 200, t["z"]), (t["x1"] + 200, t["z"])], "#334155", 120, None))
    nums = numbered(ev, plan)
    for w in ev["chains"]:
        colour = w.get("colour", COLOURS[0])
        for link in w["links"]:
            pts = [tuple(p) for p in link["route"]["points"]]
            sh.append(("line", pts, colour, 45, (6, 3) if link["conn"] in ("rj45", "wireless") else None))
            if len(pts) >= 2 and (link.get("cables") or link.get("missing_m")):
                a, b = pts[len(pts) // 2 - 1], pts[len(pts) // 2]
                if link.get("cables"):
                    L, col = " + ".join(fmt(c["length"]) for c in link["cables"]), colour
                else:                              # none in the kit is long enough: the length to buy
                    L, col = f"{fmt(link['missing_m'])} to buy", "#dc2626"
                sh.append(("text", (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 80, L, 150, col, "middle"))
        if w.get("terminator"):
            last = w["links"][-1]["route"]["points"][-1] if w["links"] else None
            if last:
                ok = w["terminator"].get("id") is not None and not any(
                    i["code"] == "C002" and w["terminator"]["at"] in i["text"] for i in ev["issues"])
                sh.append(("circle", last[0] + 220, last[1] - 220, 110, "#ffffff" if ok else "#fee2e2",
                           "#16a34a" if ok else "#dc2626"))
                sh.append(("text", last[0] + 220, last[1] - 170, "T", 150, "#16a34a" if ok else "#dc2626", "middle"))
    for f in ev["fixtures"]:
        if not f.get("place"):
            continue
        x, z = f["place"]["x"], f["place"]["z"]
        venue = f["owner"] == "venue"
        sh.append(("circle", x, z, 170, "#ffffff" if venue else "#fecaca", "#334155"))
        sh.append(("text", x, z + 330, f["name"], 120, "#0f172a", "middle"))
    ctl = ev["controller"]
    sh.append(("rect", ctl["x"] - 300, ctl["z"] - 200, ctl["x"] + 300, ctl["z"] + 200, "#e2e8f0", "#0f172a", None))
    sh.append(("text", ctl["x"], ctl["z"] + 380, "Computer", 130, "#0f172a", "middle"))
    for iid, p in sorted(plan.get("places", {}).items()):
        if iid == "controller":
            continue
        sh.append(("rect", p["x"] - 180, p["z"] - 110, p["x"] + 180, p["z"] + 110, "#ccfbf1", "#0f766e", None))
        name = next((it["name"] for it in plan["tonight"]["items"] if it["id"] == iid), iid)
        sh.append(("text", p["x"], p["z"] + 300, name.split(" ")[0], 120, "#0f766e", "middle"))
    xs = [s[1] for s in sh if s[0] in ("rect", "circle", "text")] + [s[3] for s in sh if s[0] == "rect"]
    zs = [s[2] for s in sh if s[0] in ("rect", "circle", "text")] + [s[4] for s in sh if s[0] == "rect"]
    for s in sh:
        if s[0] == "line":
            xs += [p[0] for p in s[1]]
            zs += [p[1] for p in s[1]]
    pad = 500
    x0, z0, x1, z1 = min(xs) - pad, min(zs) - pad, max(xs) + pad, max(zs) + pad
    if rig["keep_out"]:                            # the legend, bottom right
        z1 += 250
        sh.append(("rect", x1 - 3700, z1 - 330, x1 - 3450, z1 - 170, "#fee2e2", "#ef4444", (4, 3)))
        sh.append(("text", x1 - 3380, z1 - 190, "Band floor (meshes + 50 cm): cables go round it", 120,
                   "#475569", "start"))
    return sh, (x0, z0, x1, z1)


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
        elif s[0] == "text":
            _, x, z, txt, size, col, anchor = s
            out.append(f'<text x="{x:.0f}" y="{z:.0f}" font-size="{size}" fill="{col}" '
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
    for c in plan["chains"]:
        used_dev.add(c["source"]["item"])
        used_dev |= {d["item"] for d in c["devices"] if d.get("item")}
    for iid in sorted(used_dev):
        it = items.get(iid)
        if it and it.get("count", 0) > 0 and it.get("owner") != "venue" and it.get("power") != "computer":
            add(it["name"] + (" + power supply" if it.get("power") in ("mains", "dc adapter") else ""))
    for w in ev["chains"]:
        for a in w["adapters"]:
            if a in items:
                add(items[a]["name"])
        t = w.get("terminator")
        if t and t.get("id") and t["id"] in items:
            add(items[t["id"]]["name"])
    cab: Dict[float, int] = {}
    for c in numbered(ev, plan):
        if not c["missing"]:
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
            "spares": spares, "buy": list(ev.get("shopping", []))}


def pick_list_csv(pl: dict) -> str:
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(["Section", "Item", "Count"])
    for sec, key in (("Bag", "bag"), ("Spare", "spares"), ("To buy", "buy")):
        for r in pl[key]:
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
    for name, key in (("In the bag", "bag"), ("Spares", "spares"), ("To buy", "buy")):
        if pl[key]:
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
