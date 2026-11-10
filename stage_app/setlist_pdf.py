"""stage_app/setlist_pdf.py: the setlist of an exported Stage Monitor page, as a PDF.

Two layouts:

* ``big``: the setlist to tape to the floor, A4 portrait, one cue list per
  page, the song names as large as fits, the tempo and the tuning small on
  the right;
* ``cards``: A4 landscape, a table with the song cards (tempo, tuning, who
  starts, the note and each player's line).

The words come from the page (as exported) and the column titles from the
app's language.  The PDF uses the two standard Helvetica fonts, so text
outside Western European scripts prints as ``?``: the app then prints the
column titles in English.  Uses ``core.pdf.assemble_pdf``; standard library
otherwise.
"""

from __future__ import annotations

import datetime
import zlib
from typing import Callable, List

from core.pdf import assemble_pdf

LAYOUTS = ("big", "cards")
A4 = (595.0, 842.0)

# Helvetica and Helvetica-Bold widths (1/1000 em) for ASCII 32..126 (Adobe AFM).
_W1 = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + \
      [278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556,
       833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
       333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333,
       500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_W2 = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + \
      [333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611,
       833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
       333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389,
       556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584]


def width(s: str, size: float, bold: bool = False) -> float:
    """Width of *s* in points (characters outside ASCII count as an average letter)."""
    tbl = _W2 if bold else _W1
    return sum(tbl[ord(c) - 32] if 32 <= ord(c) <= 126 else 556 for c in s) * size / 1000.0


def fit(s: str, size: float, room: float, bold: bool = False) -> str:
    """*s*, cut with ``...`` so it fits in *room* points."""
    if width(s, size, bold) <= room:
        return s
    while s and width(s + "...", size, bold) > room:
        s = s[:-1]
    return (s.rstrip() + "...") if s else ""


def printable(s: str) -> bool:
    """True when the standard fonts can print *s* (Western European text)."""
    try:
        str(s).encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def _pdf(s: str) -> bytes:
    b = str(s).encode("cp1252", errors="replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class _Page:
    def __init__(self):
        self.ops: List[bytes] = []

    def color(self, r: float, g: float, b: float) -> None:
        self.ops.append(f"{r:.3f} {g:.3f} {b:.3f} rg".encode())

    def rect(self, x, y, w, h, col) -> None:
        self.color(*col)
        self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f".encode())

    def line(self, x1, y1, x2, y2, col=(0.75, 0.75, 0.75), w=0.5) -> None:
        self.ops.append(f"{col[0]:.3f} {col[1]:.3f} {col[2]:.3f} RG {w} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S".encode())

    def text(self, x, y, s, size, bold=False, col=(0, 0, 0), right=False) -> None:
        if not s:
            return
        if right:
            x -= width(s, size, bold)
        self.color(*col)
        self.ops.append(b"BT /" + (b"F2" if bold else b"F1") + f" {size:.2f} Tf {x:.2f} {y:.2f} Td (".encode()
                        + _pdf(s) + b") Tj ET")

    def stream(self) -> bytes:
        return zlib.compress(b"\n".join(self.ops))


GREY = (0.40, 0.40, 0.40)
AMBER = (0.80, 0.48, 0.05)


def _meta(card: dict) -> List[str]:
    out = []
    if card.get("bpm"):
        out.append(f"{card['bpm']} BPM")
    if card.get("tuning"):
        out.append(str(card["tuning"]))
    return out


def _header(pg: _Page, W: float, H: float, title: str, label: str, n: int, pn: int, t: Callable) -> float:
    m = 36.0
    pg.text(m, H - 52, fit(title or label, 22, W - 2 * m - 120, True), 22, bold=True)
    if title and label and label != title:
        pg.text(m, H - 72, fit(label, 12, W - 2 * m - 120), 12, col=GREY)
    pg.text(W - m, H - 50, t("{0} songs").replace("{0}", str(n)), 10, col=GREY, right=True)
    pg.text(W - m, H - 64, datetime.date.today().isoformat(), 10, col=GREY, right=True)
    if pn > 1:
        pg.text(W - m, H - 78, t("Page {0}").replace("{0}", str(pn)), 10, col=GREY, right=True)
    pg.line(m, H - 86, W - m, H - 86, col=(0.2, 0.2, 0.2), w=1)
    return H - 86


def _big(title: str, lst: dict, t: Callable) -> List[bytes]:
    W, H = A4
    m, bottom = 36.0, 40.0
    songs = lst["songs"]
    pages: List[bytes] = []
    top = H - 86 - 14
    avail = top - bottom
    n = max(1, len(songs))
    size = min(40.0, avail / (1 + 1.5 * (n - 1)))      # the first line takes its size, each next one 1.5×
    size = max(size, 16.0)
    num_w = width("00", size, True) + size * 0.6
    for s in songs:
        meta = "  ".join(_meta(s["card"]))
        room = W - 2 * m - num_w - (width(meta, size * 0.42) + 12 if meta else 0)
        while size > 16 and width(s["name"], size, True) > room:
            size -= 1
            num_w = width("00", size, True) + size * 0.6
            room = W - 2 * m - num_w - (width(meta, size * 0.42) + 12 if meta else 0)
    lh = size * 1.5
    per = max(1, int((avail - size) / lh + 1e-6) + 1)
    chunks = [songs[i:i + per] for i in range(0, len(songs), per)] or [[]]
    k = 0
    for pn, chunk in enumerate(chunks, 1):
        pg = _Page()
        _header(pg, W, H, title, lst["label"], len(songs), pn, t)
        y = top - size
        for s in chunk:
            k += 1
            meta = "  ".join(_meta(s["card"]))
            pg.text(m, y, f"{k:02d}", size * 0.55, bold=True, col=GREY)
            room = W - 2 * m - num_w - (width(meta, size * 0.42) + 12 if meta else 0)
            pg.text(m + num_w, y, fit(s["name"], size, room, True), size, bold=True)
            if meta:
                pg.text(W - m, y + size * 0.1, meta, size * 0.42, col=AMBER if s.get("tc") else GREY, right=True)
            y -= lh
        pages.append(pg.stream())
    return pages


def _cards(title: str, lst: dict, t: Callable) -> List[bytes]:
    W, H = A4[1], A4[0]
    m, bottom = 30.0, 30.0
    cols = [("#", 26), (t("Song"), 0), (t("BPM"), 44), (t("Tuning"), 90), (t("Starts"), 150), (t("Note"), 0)]
    flex = (W - 2 * m - sum(w for _, w in cols)) / 2
    widths = [w or flex for _, w in cols]
    xs, x = [], m
    for w in widths:
        xs.append(x)
        x += w
    fs, rh = 10.0, 20.0
    pages: List[bytes] = []
    songs = lst["songs"]
    rows = []
    for k, s in enumerate(songs, 1):
        c = s["card"]
        note = str(c.get("note") or s.get("note") or "")
        players = "; ".join(f"{p.get('who')}: {p.get('note')}" for p in c.get("players") or []
                            if isinstance(p, dict) and (p.get("who") or p.get("note")))
        rows.append([f"{k:02d}", s["name"], str(c.get("bpm") or ""), str(c.get("tuning") or ""),
                     str(c.get("starts") or ""), "  |  ".join(x for x in (note, players) if x), bool(s.get("tc"))])
    pn = 0
    i = 0
    while True:
        pn += 1
        pg = _Page()
        y = _header(pg, W, H, title, lst["label"], len(songs), pn, t) - 10
        pg.rect(m, y - rh, W - 2 * m, rh, (0.12, 0.12, 0.14))
        for (lbl, _w), cx in zip(cols, xs):
            pg.text(cx + 4, y - rh + 6.5, lbl, fs, bold=True, col=(1, 1, 1))
        y -= rh
        while i < len(rows) and y - rh >= bottom:
            r = rows[i]
            if i % 2 == 0:
                pg.rect(m, y - rh, W - 2 * m, rh, (0.95, 0.95, 0.95))
            for j, (val, cx, cw) in enumerate(zip(r[:6], xs, widths)):
                bold = j in (0, 1) or (j == 3 and r[6])
                col = AMBER if (j == 3 and r[6]) else (0, 0, 0)
                pg.text(cx + 4, y - rh + 6.5, fit(val, fs, cw - 8, bold), fs, bold=bold, col=col)
            y -= rh
            i += 1
        pages.append(pg.stream())
        if i >= len(rows):
            break
    return pages


def build(page: dict, layout: str = "big", t: Callable = lambda s: s) -> bytes:
    """The PDF of every cue list of *page* (what ``folder.read`` returns)."""
    if layout not in LAYOUTS:
        layout = "big"
    pages: List[bytes] = []
    sizes = []
    title = str(page.get("title") or "")
    for lst in page.get("lists") or []:
        new = (_big if layout == "big" else _cards)(title, lst, t)
        pages += new
        sizes += [A4 if layout == "big" else (A4[1], A4[0])] * len(new)
    if not pages:
        raise ValueError("There is no song to print.")
    return assemble_pdf(pages, sizes[0][0], sizes[0][1], sizes=sizes)
