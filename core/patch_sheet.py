"""core/patch_sheet.py — the Patch sheet (Show Paperwork): every fixture by
universe and address, with a DIP-switch diagram for setting it on the rig,
an optional event line and logo — as a page of the paperwork PDF, as a
narrow ticket for a 58 / 80 mm thermal printer (PDF or plain text), and as
CSV.

Inspired by OH Show's QLC+ patch tools (apps.fewday.go.yn.fr/QLC), cited in
QLC+ issue #2086.

DIP switches: switch *n* has the value 2^(n−1) (switch 1 = 1, switch 9 =
256); a switch is ON when its bit is set in the DMX start address (1–512).
Ten switches cover 512; most fixtures have 9 or 10 (on some the 10th is a
function switch, not an address bit).
"""

from __future__ import annotations

import zlib
from typing import Optional

from core.pdf import assemble_pdf, _pdf_str

DIP_CHOICES = (9, 10)
RECEIPTS = {"58": 164.4, "80": 226.8}          # paper widths in points
TEXT_COLS = {"58": 32, "80": 48}


def dip_on(address: int, switches: int = 10) -> list[int]:
    """Switch numbers that are ON for a DMX start address (1-based)."""
    a = int(address)
    return [n for n in range(1, switches + 1) if a & (1 << (n - 1))]


def build(state: dict, channels: dict, switches: int = 10) -> dict:
    """{universes: [{universe, fixtures: [...], used}], total, switches}.
    *channels*: {fixture id: channel count}."""
    switches = switches if switches in DIP_CHOICES else 10
    by_uni: dict[int, list] = {}
    for fid, info in state.get("fixture_map", {}).items():
        u, a = int(info.get("universe", 1)), int(info.get("address", 1))
        ch = int(channels.get(fid) or 0)
        model = info.get("model", "")
        mfg = info.get("manufacturer", "")
        if mfg and model.startswith(mfg + " "):
            model = model[len(mfg) + 1:]
        on = dip_on(a, switches)
        by_uni.setdefault(u, []).append({
            "id": fid, "name": info.get("name", ""), "manufacturer": mfg, "model": model,
            "mode": info.get("mode", ""), "universe": u, "address": a, "channels": ch,
            "end": a + ch - 1 if ch else a, "dip": on,
            "dip_fits": a < (1 << switches),
        })
    unis = []
    for u in sorted(by_uni):
        fx = sorted(by_uni[u], key=lambda f: (f["address"], f["name"]))
        unis.append({"universe": u, "fixtures": fx,
                     "used": (fx[0]["address"], max(f["end"] for f in fx)) if fx else (0, 0)})
    return {"universes": unis, "switches": switches,
            "total": sum(len(u["fixtures"]) for u in unis)}


def rows(sheet: dict) -> list[list]:
    """CSV rows: the #2086 columns first (universe, address, manufacturer,
    model, mode, name), then channels, last address, DIP switches ON."""
    out = []
    for u in sheet["universes"]:
        for f in u["fixtures"]:
            out.append([f["universe"], f["address"], f["manufacturer"], f["model"], f["mode"], f["name"],
                        f["channels"], f["end"], " ".join(map(str, f["dip"]))])
    return out


CSV_HEADERS = ["universe", "address", "manufacturer", "model", "mode", "name",
               "channels", "last_address", "dip_on"]


# ── drawing ─────────────────────────────────────────────────────────────────

def draw_dip(emit, x: float, y: float, on: list[int], switches: int, sw: float = 7.0,
             h: float = 12.0, numbers: bool = True, fsize: float = 4.5,
             style: str = "colour") -> float:
    """Draw a DIP-switch block at (x, y) = bottom-left; returns its width.
    *emit* takes raw PDF operators.  Like the real part (and OH Show's
    sheet): a blue body, one slot per switch, the lever UP = ON.
    style "print" (thermal paper): no fill, black outlines, black levers."""
    gap = 1.2
    w = switches * (sw + gap) + gap
    if style == "print":
        emit(f"0 0 0 RG 0.6 w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")
    else:
        emit("0.02 0.33 0.80 rg")
        emit(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
    lever_h = (h - 2.4) / 2
    for n in range(1, switches + 1):
        sx = x + gap + (n - 1) * (sw + gap)
        ly = y + 1.2 + (lever_h if n in on else 0)
        if style == "print":
            emit(f"0 0 0 RG 0.4 w {sx:.2f} {y + 1.2:.2f} {sw:.2f} {h - 2.4:.2f} re S")
            emit("0 0 0 rg")
        else:
            emit("0.17 0.17 0.20 rg")
            emit(f"{sx:.2f} {y + 1.2:.2f} {sw:.2f} {h - 2.4:.2f} re f")
            emit("1 1 1 rg")
        emit(f"{sx + 0.8:.2f} {ly + 0.6:.2f} {sw - 1.6:.2f} {lever_h - 1.2:.2f} re f")
        if numbers:
            emit("0 0 0 rg")
            tx = sx + sw / 2 - (fsize * 0.28 if n < 10 else fsize * 0.55)
            emit(f"BT /F1 {fsize} Tf {tx:.2f} {y - fsize - 0.6:.2f} Td ({n}) Tj ET")
    return w


def _clean(s) -> str:
    from core.showbook import _pdf_clean
    return _pdf_clean(s)


def receipt_pdf(sheet: dict, show_name: str, date: str, event: str = "",
                width: str = "80", logo=None) -> bytes:
    """One long ticket (a new page every ~5 m) for a thermal printer."""
    W = RECEIPTS.get(str(width), RECEIPTS["80"])
    pad, lh = 8.0, 10.0
    small = W < 200
    blocks: list[tuple[float, list[str]]] = []      # (height, ops relative to block top)

    def text(ops, x, y, s, sz, bold=False):
        ops.append(f"BT /{'F2' if bold else 'F1'} {sz} Tf {x:.2f} {y:.2f} Td ({_pdf_str(_clean(s))}) Tj ET")

    def trunc(s, sz, maxw):
        s = _clean(s)
        n = max(4, int(maxw / (sz * 0.5)))
        return s if len(s) <= n else s[:n - 1] + "~"

    # header block
    ops, y = [], 0.0
    if logo is not None:
        from core.pdf_image import fit
        lw, lhh = fit(logo, W - 2 * pad, 60)
        ops.append(f"q {lw:.2f} 0 0 {lhh:.2f} {(W - lw) / 2:.2f} {y - lhh:.2f} cm /Logo Do Q")
        y -= lhh + 6
    for s, sz, b in ((event, 11, True), (show_name, 9 if event else 11, not event),
                     (f"DMX patch - {date}", 8, False),
                     (f"{sheet['total']} fixture(s), DIP: {sheet['switches']} switches, ON = lever up", 7, False)):
        if s:
            y -= sz + 3
            text(ops, pad, y, trunc(s, sz, W - 2 * pad), sz, b)
    y -= 6
    ops.append(f"0 0 0 RG 0.6 w {pad:.2f} {y:.2f} m {W - pad:.2f} {y:.2f} l S")
    blocks.append((-y + 4, ops))

    for u in sheet["universes"]:
        ops = []
        y = -14.0
        ops.append(f"0 0 0 rg {pad:.2f} {y - 2:.2f} {W - 2 * pad:.2f} 14 re f")
        ops.append("1 1 1 rg")
        text(ops, pad + 4, y + 2, f"UNIVERSE {u['universe']}  ({len(u['fixtures'])})", 9, True)
        ops.append("0 0 0 rg")
        blocks.append((-y + 6, ops))
        for f in u["fixtures"]:
            ops, y = [], 0.0
            y -= 13
            text(ops, pad, y, f"{f['address']:03d}" + (f"-{f['end']:03d}" if f['end'] != f['address'] else ""), 12, True)
            text(ops, pad + (62 if not small else 58), y + 1, trunc(f["name"], 8, W - pad * 2 - 62), 8, True)
            y -= lh
            text(ops, pad, y, trunc(f"{f['manufacturer']} {f['model']}".strip(), 7, W - 2 * pad), 7)
            y -= lh - 1
            text(ops, pad, y, trunc(f"{f['mode']} - {f['channels']} ch" if f["channels"] else f["mode"], 7,
                                    W - 2 * pad), 7)
            y -= 4
            sw = 8.0 if not small else 6.4
            y -= 13
            dw = draw_dip(ops.append, pad, y, f["dip"], sheet["switches"], sw=sw, h=13,
                          style="print")          # thermal paper: outlines, black levers
            ops.append("0 0 0 rg")
            on = ", ".join(map(str, f["dip"])) or "none"
            if f["dip_fits"]:
                text(ops, pad + dw + 4, y + 4, trunc(f"ON {on}", 7, W - pad - (pad + dw + 4)), 7, True)
            else:
                text(ops, pad + dw + 4, y + 4, "> switches", 7, True)
            y -= 12
            ops.append(f"0.6 0.6 0.6 RG 0.3 w [1 1.5] 0 d {pad:.2f} {y:.2f} m {W - pad:.2f} {y:.2f} l S [] 0 d")
            blocks.append((-y + 3, ops))

    # pages of at most ~5 m (PDF limit 14 400 pt)
    MAXH = 14000.0
    pages, sizes, cur, cur_h = [], [], [], pad
    for bh, bops in blocks:
        if cur and cur_h + bh > MAXH:
            pages.append(cur); sizes.append(cur_h + pad); cur, cur_h = [], pad
        cur.append((cur_h, bops)); cur_h += bh
    if cur:
        pages.append(cur); sizes.append(cur_h + pad)
    streams, dims = [], []
    for page, H in zip(pages, sizes):
        out = []
        for top, bops in page:
            out.append(f"q 1 0 0 1 0 {H - top:.2f} cm")
            out.extend(bops)
            out.append("Q")
        streams.append(zlib.compress("\n".join(out).encode("latin-1", "replace")))
        dims.append((W, H))
    return assemble_pdf(streams, W, dims[0][1], images={"Logo": logo} if logo is not None else None,
                        sizes=dims)


def receipt_text(sheet: dict, show_name: str, date: str, event: str = "", width: str = "80") -> str:
    """Plain text (ASCII) for printer apps: 32 or 48 characters a line."""
    cols = TEXT_COLS.get(str(width), 48)
    sw = sheet["switches"]
    line = "-" * cols
    out = []
    for s in (event, show_name, f"DMX patch - {date}"):
        if s:
            out.append(_clean(s)[:cols])
    out += [f"{sheet['total']} fixture(s)  DIP 1..{sw}, #=ON"[:cols], line]
    for u in sheet["universes"]:
        out.append(f"== UNIVERSE {u['universe']} ({len(u['fixtures'])}) ".ljust(cols, "=")[:cols])
        for f in u["fixtures"]:
            rng = f"{f['address']:03d}" + (f"-{f['end']:03d}" if f["end"] != f["address"] else "")
            out.append(f"{rng}  {_clean(f['name'])}"[:cols])
            out.append(f"  {_clean(f['manufacturer'] + ' ' + f['model']).strip()}"[:cols])
            mode = _clean(f["mode"]) + (f" - {f['channels']} ch" if f["channels"] else "")
            out.append(f"  {mode}"[:cols])
            bar = "".join("#" if n in f["dip"] else "." for n in range(1, sw + 1))
            on = ",".join(map(str, f["dip"])) or "none"
            out.append(f"  DIP [{bar}] ON {on}"[:cols] if f["dip_fits"] else "  DIP: address above the switches"[:cols])
            out.append(line)
    return "\n".join(out) + "\n"
