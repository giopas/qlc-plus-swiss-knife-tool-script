"""
core/pdf.py — Raw PDF builder (stdlib only: zlib, datetime)

Functions
---------
assemble_pdf(pages, W, H)                → bytes
build_blueprint_pdf(fixture_data, ...)   → bytes | None
build_setlist_pdf(songs, ...)            → bytes | None
build_table_pdf(rows, headers, ...)      → bytes
"""

import zlib
import datetime


# ──────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────────────

def _hex_to_01(h):
    """Convert '#rrggbb' → (r, g, b) as 0.0–1.0 floats."""
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _pdf_str(s):
    """Escape a string for inclusion in a PDF text object."""
    s = str(s).encode('latin-1', errors='replace').decode('latin-1')
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _format_time(t_str):
    """Convert QLC+ infinite sentinel to 'Inf', otherwise return as-is."""
    if str(t_str) in ("4294967294", "-2"):
        return "Inf"
    return str(t_str)


# ──────────────────────────────────────────────────────────────────────────────
# Core PDF assembly
# ──────────────────────────────────────────────────────────────────────────────

def assemble_pdf(pages, W, H):
    """
    Assemble a multi-page PDF from a list of zlib-compressed page streams.

    Parameters
    ----------
    pages : list[bytes]
        Each element is a zlib-compressed content stream for one page.
    W, H  : float
        Page width and height in PDF points.

    Returns
    -------
    bytes
        Complete PDF file content.
    """
    raw = "%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = []

    def _add(s):
        nonlocal raw
        offsets.append(len(raw))
        raw += s

    def _obj(n, c):
        return f"{n} 0 obj\n{c}\nendobj\n"

    def _sobj(n, data):
        body = data.decode("latin-1")
        return _obj(n,
                    f"<< /Length {len(data)} /Filter /FlateDecode >>\n"
                    f"stream\n{body}\nendstream")

    font_res = "<< /Font << /F1 3 0 R /F2 4 0 R >> >>"
    kids, po, so = [], [], []
    cid = 5
    for ps in pages:
        kids.append(f"{cid} 0 R")
        po.append(_obj(cid,
                       f"<< /Type /Page /Parent 2 0 R "
                       f"/MediaBox [0 0 {W:.2f} {H:.2f}] "
                       f"/Contents {cid + 1} 0 R "
                       f"/Resources {font_res} >>"))
        so.append(_sobj(cid + 1, ps))
        cid += 2

    _add(_obj(1, "<< /Type /Catalog /Pages 2 0 R >>"))
    _add(_obj(2, f"<< /Type /Pages /Kids [{' '.join(kids)}] "
                 f"/Count {len(pages)} >>"))
    _add(_obj(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                 "/Encoding /WinAnsiEncoding >>"))
    _add(_obj(4, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
                 "/Encoding /WinAnsiEncoding >>"))
    for p, s in zip(po, so):
        _add(p)
        _add(s)

    n = cid - 1
    xoff = len(raw)
    raw += f"xref\n0 {n + 1}\n0000000000 65535 f \n"
    for o in offsets:
        raw += f"{o:010d} 00000 n \n"
    raw += f"trailer\n<< /Size {n + 1} /Root 1 0 R >>\nstartxref\n{xoff}\n%%EOF\n"
    return raw.encode("latin-1")


# ──────────────────────────────────────────────────────────────────────────────
# Blueprint PDF
# ──────────────────────────────────────────────────────────────────────────────

def build_blueprint_pdf(fixture_data, show_name="Untitled", doc_date=None,
                        W=1190.0, H=841.0):
    """
    Build a single-page blueprint PDF showing top-view and front-view of
    all fixtures that have 3D position data.

    Parameters
    ----------
    fixture_data : list[dict]
        Each dict must contain:
            name   : str
            patch  : str  (e.g. "U1.001")
            color  : str  (hex, e.g. "#00e5ff")
            x      : float  (mm, width)
            y      : float  (mm, height / ceiling)
            z      : float  (mm, depth / downstage)
            in_3d  : bool
    show_name : str
    doc_date  : str | None  — defaults to today's date
    W, H      : float  — page dimensions in PDF points

    Returns
    -------
    bytes | None
        PDF bytes, or None if no fixtures have 3D position data.
    """
    if doc_date is None:
        doc_date = datetime.date.today().strftime("%Y-%m-%d")

    xv = [f["x"] for f in fixture_data if f.get("in_3d")]
    yv = [f["y"] for f in fixture_data if f.get("in_3d")]
    zv = [f["z"] for f in fixture_data if f.get("in_3d")]
    if not xv:
        return None

    mn_x, mx_x = min(xv), max(xv)
    mn_y, mx_y = min(yv), max(yv)
    mn_z, mx_z = min(zv), max(zv)
    rx = mx_x - mn_x or 1.0
    ry = mx_y - mn_y or 1.0
    rz = mx_z - mn_z or 1.0

    ln = []
    header_col = (0.12, 0.12, 0.18)
    TITLE_H = 36
    pad, pad_r, pad_tb = 72, 52, 28
    sec_h = (H - TITLE_H) / 2.0

    def fc(r, g, b):   ln.append(f"{r:.4f} {g:.4f} {b:.4f} rg")
    def sc(r, g, b):   ln.append(f"{r:.4f} {g:.4f} {b:.4f} RG")
    def lw(w):         ln.append(f"{w} w")

    def rfill(x, y, w, h, col):
        fc(*col)
        ln.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def seg(x1, y1, x2, y2, col, wd=0.5, dsh=None):
        lw(wd)
        sc(*col)
        ln.append(f"[{dsh[0]} {dsh[1]}] 0 d" if dsh else "[] 0 d")
        ln.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def circ(cx, cy, r, fcol, scol):
        k = 0.5523 * r
        fc(*fcol)
        sc(*scol)
        lw(0.6)
        ln.append(
            f"{cx:.2f} {cy + r:.2f} m "
            f"{cx + k:.2f} {cy + r:.2f} {cx + r:.2f} {cy + k:.2f} {cx + r:.2f} {cy:.2f} c "
            f"{cx + r:.2f} {cy - k:.2f} {cx + k:.2f} {cy - r:.2f} {cx:.2f} {cy - r:.2f} c "
            f"{cx - k:.2f} {cy - r:.2f} {cx - r:.2f} {cy - k:.2f} {cx - r:.2f} {cy:.2f} c "
            f"{cx - r:.2f} {cy + k:.2f} {cx - k:.2f} {cy + r:.2f} {cx:.2f} {cy + r:.2f} c B"
        )

    def txt(x, y, s, sz=8, bold=False):
        s = _pdf_str(s)
        ln.append(f"BT {'/F2' if bold else '/F1'} {sz} Tf {x:.2f} {y:.2f} Td ({s}) Tj ET")

    def txt_c(cx, y, s, sz=8, bold=False):
        txt(cx - len(str(s)) * sz * 0.28, y, str(s), sz, bold)

    def fy(yc):
        return H - TITLE_H - yc

    # Title bar
    rfill(0, H - TITLE_H, W, TITLE_H, header_col)
    ln.append("1 1 1 rg")
    txt(10, H - TITLE_H + 14, f"SHOW: {show_name}", sz=14, bold=True)
    txt_c(W / 2, H - TITLE_H + 14, "MASTER BLUEPRINT", sz=9, bold=True)
    ln.append("0.75 0.85 1.0 rg")
    txt(W - 200, H - TITLE_H + 14, f"Date: {doc_date}", sz=8)

    bg  = (1.0, 1.0, 1.0)
    grd = (0.9, 0.9, 0.9)
    stg = (0.75, 0.78, 0.82)
    fgc = (0.0, 0.0, 0.0)

    # Two sections: top-view (Z axis) and front-view (Y axis)
    sections = [
        (mn_z, mx_z, rz, "z", "TOP VIEW (Width vs Depth)"),
        (mn_y, mx_y, ry, "y", "FRONT VIEW (Width vs Height)"),
    ]
    for sec_idx, (mn_v, mx_v, rv, v_axis, title) in enumerate(sections):
        y_off = sec_idx * sec_h
        rfill(0, fy(y_off + sec_h), W, sec_h, bg)
        pw = W - pad - pad_r
        ph = sec_h - 2 * pad_tb
        steps = 10
        for i in range(steps + 1):
            frac = i / steps
            gx = pad + frac * pw
            seg(gx, fy(y_off + pad_tb), gx, fy(y_off + sec_h - pad_tb), grd, 0.35, (3, 4))
            gy = y_off + pad_tb + frac * ph
            seg(pad, fy(gy), W - pad_r, fy(gy), grd, 0.35, (3, 4))
        # Bounding box
        sc(*stg)
        lw(1.5)
        ln.append(f"{pad:.2f} {fy(y_off + sec_h - pad_tb):.2f} {pw:.2f} {ph:.2f} re S")
        txt(pad, fy(y_off + pad_tb) + 8, title, sz=10, bold=True)

        r_dot = 6
        for f in fixture_data:
            if not f.get("in_3d"):
                continue
            fc_col = _hex_to_01(f.get("color", "#888888"))
            nx = pad + ((f["x"] - mn_x) / rx) * pw
            val = f[v_axis]
            frac_v = (mx_v - val) / rv if rv else 0.5
            ny = y_off + pad_tb + frac_v * ph
            circ(nx, fy(ny), r_dot, fc_col, fgc)
            txt_c(nx, fy(ny) - r_dot - 9,  f["name"],          sz=5)
            txt_c(nx, fy(ny) - r_dot - 15, f"[{f['patch']}]",  sz=5)

        # Audience / Backstage labels on top-view only
        if sec_idx == 0:
            band_h = 10
            pw2 = W - pad - pad_r
            # Audience (bottom = downstage)
            label_y_bot = fy(y_off + sec_h - pad_tb)
            rfill(pad, label_y_bot, pw2, band_h, (0.85, 0.72, 0.90))
            fc(0.2, 0.05, 0.3)
            txt_c(pad + pw2 / 2, label_y_bot + 2, "AUDIENCE / DOWNSTAGE", sz=6)
            # Backstage (top = upstage)
            label_y_top = fy(y_off + pad_tb)
            rfill(pad, label_y_top - band_h, pw2, band_h, (0.88, 0.88, 0.92))
            fc(0.25, 0.25, 0.35)
            txt_c(pad + pw2 / 2, label_y_top - band_h + 2, "UPSTAGE / BACKSTAGE", sz=6)

    # Divider between sections
    seg(0, fy(sec_h), W, fy(sec_h), stg, 2.0)

    stream = zlib.compress("\n".join(ln).encode("latin-1"))
    return assemble_pdf([stream], W, H)


# ──────────────────────────────────────────────────────────────────────────────
# Setlist PDF
# ──────────────────────────────────────────────────────────────────────────────

def build_setlist_pdf(songs, slot_label="Setlist", show_name="Untitled",
                      selected_cols=None, include_notes=False,
                      W=842.0, H=595.0):
    """
    Build a multi-page setlist PDF with a formatted song table.

    Parameters
    ----------
    songs : list[dict]
        Each dict: {txt_name, qxw_name, qxw_id, in, hold, out}
    slot_label : str
    show_name  : str
    selected_cols : list[tuple(key, label)] | None
        Keys: "num", "song", "cue", "fade_in", "hold", "fade_out"
        If None, defaults to [(num, #), (song, Song), (cue, Cue),
                               (fade_in, Fade In), (hold, Hold), (fade_out, Fade Out)]
    include_notes : bool
    W, H : float

    Returns
    -------
    bytes | None
    """
    if not songs:
        return None

    if selected_cols is None:
        selected_cols = [
            ("num",      "#"),
            ("song",     "Song"),
            ("cue",      "Cue"),
            ("fade_in",  "Fade In"),
            ("hold",     "Hold"),
            ("fade_out", "Fade Out"),
        ]

    doc_date = datetime.date.today().strftime("%Y-%m-%d")
    header_col = (0.12, 0.12, 0.18)
    row_alt    = (0.95, 0.97, 1.00)

    TITLE_H = 40; T_PAD = 14; ROW_H = 24; HDR_H = 26
    BODY_SZ = 10; HDR_SZ = 10; NUM_SZ = 11
    dark_hdr = (0.22, 0.30, 0.45)

    base_widths = {"num": 28, "song": 0, "cue": 0,
                   "fade_in": 48, "hold": 48, "fade_out": 48}
    usable_w = W - 2 * T_PAD
    fixed_used = sum(base_widths.get(k, 0) for k, _ in selected_cols if base_widths.get(k, 0) > 0)
    flex_keys  = [k for k, _ in selected_cols if base_widths.get(k, 0) == 0]
    notes_min_w = 100 if include_notes else 0
    remaining   = usable_w - fixed_used - notes_min_w
    flex_w = max(60, remaining / len(flex_keys)) if flex_keys else 0

    col_labels, col_w = [], []
    for key, label in selected_cols:
        col_labels.append(label)
        bw = base_widths.get(key, 0)
        col_w.append(bw if bw > 0 else flex_w)
    if include_notes:
        used    = sum(col_w)
        notes_w = max(notes_min_w, usable_w - used)
        col_labels.append("Notes")
        col_w.append(notes_w)

    col_x, cx = [], T_PAD
    for w in col_w:
        col_x.append(cx)
        cx += w

    pages   = []
    cur_ln  = []

    def sc(r, g, b):  cur_ln.append(f"{r:.4f} {g:.4f} {b:.4f} RG")
    def fc(r, g, b):  cur_ln.append(f"{r:.4f} {g:.4f} {b:.4f} rg")
    def lw(w):        cur_ln.append(f"{w} w")

    def rfill(x, y, w, h, col):
        fc(*col)
        cur_ln.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def rbox(x, y, w, h, fcol, scol, wd=0.5):
        fc(*fcol); sc(*scol); lw(wd)
        cur_ln.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re B")

    def txt(x, y, s, sz=8, bold=False):
        s = _pdf_str(s)
        cur_ln.append(
            f"BT {'/F2' if bold else '/F1'} {sz} Tf "
            f"{x:.2f} {y:.2f} Td ({s}) Tj ET")

    def finish_page():
        if cur_ln:
            pages.append(zlib.compress("\n".join(cur_ln).encode("latin-1")))
            cur_ln.clear()

    def draw_header(pn):
        rfill(0, H - TITLE_H, W, TITLE_H, header_col)
        cur_ln.append("1 1 1 rg")
        txt(14, H - TITLE_H + 18, f"SETLIST: {show_name}  ·  {slot_label}", sz=14, bold=True)
        txt(W - 200, H - TITLE_H + 22, f"Date: {doc_date}", sz=9)
        txt(W - 200, H - TITLE_H + 10, f"Page {pn}", sz=9)
        T_TOP = H - TITLE_H - T_PAD
        hy = T_TOP - HDR_H
        for cx2, cw2 in zip(col_x, col_w):
            rbox(cx2, hy, cw2, HDR_H, dark_hdr, (0.1, 0.2, 0.35), 0.3)
        cur_ln.append("1 1 1 rg")
        for lbl, cx2 in zip(col_labels, col_x):
            txt(cx2 + 4, hy + 8, lbl, sz=HDR_SZ, bold=True)
        return hy

    def get_row_values(ri, d):
        vals = []
        for key, _ in selected_cols:
            if key == "num":
                vals.append(f"{ri + 1:02d}")
            elif key == "song":
                raw = d.get("txt_name") or ""
                vals.append(raw[:int(flex_w / (BODY_SZ * 0.5))])
            elif key == "cue":
                raw = d.get("qxw_name") or ""
                vals.append(raw[:int(flex_w / (BODY_SZ * 0.5))])
            elif key == "fade_in":
                vals.append(_format_time(d.get("in", "0")))
            elif key == "hold":
                vals.append(_format_time(d.get("hold", "4294967294")))
            elif key == "fade_out":
                vals.append(_format_time(d.get("out", "0")))
        if include_notes:
            vals.append("")
        return vals

    pn = 1
    cy = draw_header(pn)
    for ri, d in enumerate(songs):
        cy -= ROW_H
        if cy < T_PAD:
            finish_page()
            pn += 1
            cy = draw_header(pn)
            cy -= ROW_H
        rc = row_alt if ri % 2 == 0 else (1.0, 1.0, 1.0)
        for cx2, cw2 in zip(col_x, col_w):
            rbox(cx2, cy, cw2, ROW_H, rc, (0.75, 0.80, 0.88), 0.25)
        cur_ln.append("0 0 0 rg")
        vals = get_row_values(ri, d)
        for vi, v in enumerate(vals):
            is_num = (vi == 0 and selected_cols[0][0] == "num")
            txt(col_x[vi] + 5, cy + 7, v,
                sz=NUM_SZ if is_num else BODY_SZ, bold=is_num)
    finish_page()
    return assemble_pdf(pages, W, H)


# ──────────────────────────────────────────────────────────────────────────────
# Generic table PDF (ID Browser / Functions / VC Widgets)
# ──────────────────────────────────────────────────────────────────────────────

def build_table_pdf(rows, headers, title="Table", W=842.0, H=595.0, fsize=8):
    """
    Build a multi-page table PDF from arbitrary rows/headers.

    Parameters
    ----------
    rows    : list[list]   — each inner list has one value per column
    headers : list[str]    — column header labels
    title   : str          — shown in the page header
    W, H    : float        — page dimensions in PDF points
    fsize   : int          — body font size

    Returns
    -------
    bytes
    """
    T_PAD   = 14
    ROW_H   = fsize + 8
    HDR_H   = fsize + 10
    TITLE_H = 34

    usable_w = W - 2 * T_PAD

    _FIXED = {
        "ID": 40, "Widget ID": 56, "Icon": 20, "": 20,
        "Func ID": 48, "X": 36, "Y": 36, "W": 36, "H": 36, "Type": 80,
    }
    fixed_w = sum(_FIXED.get(h, 0) for h in headers)
    flex_h  = [h for h in headers if _FIXED.get(h, 0) == 0]
    flex_w  = max(50, (usable_w - fixed_w) / max(1, len(flex_h)))

    col_w = [_FIXED.get(h, flex_w) for h in headers]
    total = sum(col_w)
    if total > usable_w:
        scale = usable_w / total
        col_w = [cw * scale for cw in col_w]

    col_x, cx = [], T_PAD
    for cw in col_w:
        col_x.append(cx)
        cx += cw

    hdr_col  = (0.12, 0.12, 0.18)
    alt_col  = (0.93, 0.95, 1.00)
    white    = (1.0, 1.0, 1.0)
    dark_hdr = (0.22, 0.30, 0.45)
    doc_date = datetime.date.today().strftime("%Y-%m-%d")

    pages, cur = [], []

    def sc(r, g, b): cur.append(f"{r:.4f} {g:.4f} {b:.4f} RG")
    def fc(r, g, b): cur.append(f"{r:.4f} {g:.4f} {b:.4f} rg")
    def lw(w):       cur.append(f"{w} w")

    def rfill(x, y, w, h, col):
        fc(*col)
        cur.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def rbox(x, y, w, h, fcol, scol, wd=0.4):
        fc(*fcol); sc(*scol); lw(wd)
        cur.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re B")

    def txt(x, y, s, sz=8, bold=False):
        s = _pdf_str(s)
        cur.append(
            f"BT {'/F2' if bold else '/F1'} {sz} Tf "
            f"{x:.2f} {y:.2f} Td ({s}) Tj ET")

    def finish_page():
        if cur:
            pages.append(zlib.compress("\n".join(cur).encode("latin-1")))
            cur.clear()

    def draw_header(pn):
        rfill(0, H - TITLE_H, W, TITLE_H, hdr_col)
        cur.append("1 1 1 rg")
        txt(T_PAD, H - TITLE_H + 12, title, sz=11, bold=True)
        txt(W - 180, H - TITLE_H + 18, f"Date: {doc_date}", sz=8)
        txt(W - 180, H - TITLE_H + 8,  f"Page {pn}",        sz=8)
        T_TOP = H - TITLE_H - 4
        hy = T_TOP - HDR_H
        for cxi, cwi in zip(col_x, col_w):
            rbox(cxi, hy, cwi, HDR_H, dark_hdr, (0.1, 0.2, 0.35), 0.2)
        cur.append("1 1 1 rg")
        for hdr, cxi in zip(headers, col_x):
            txt(cxi + 3, hy + 4, hdr, sz=fsize, bold=True)
        return hy

    pn = 1
    cy = draw_header(pn)

    for ri, row in enumerate(rows):
        cy -= ROW_H
        if cy < T_PAD + ROW_H:
            finish_page()
            pn += 1
            cy = draw_header(pn)
            cy -= ROW_H
        rc = alt_col if ri % 2 == 0 else white
        for cxi, cwi in zip(col_x, col_w):
            rbox(cxi, cy, cwi, ROW_H, rc, (0.80, 0.84, 0.92), 0.2)
        cur.append("0 0 0 rg")
        for cell, cxi, cwi in zip(row, col_x, col_w):
            cell_s = str(cell) if cell is not None else ""
            max_chars = max(4, int(cwi / (fsize * 0.52)))
            if len(cell_s) > max_chars:
                cell_s = cell_s[:max_chars - 1] + "~"
            txt(cxi + 3, cy + 3, cell_s, sz=fsize)

    finish_page()
    return assemble_pdf(pages, W, H)
