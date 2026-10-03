"""core/pdf_image.py — a logo for the PDFs (Patch sheet): JPEG and PNG read
with the standard library only, turned into PDF image objects.

``load(data) -> PdfImage`` accepts JPEG (baseline or progressive: passed
through as DCTDecode) and PNG (8- or 16-bit, grey, RGB, palette, with or
without alpha; not interlaced).  Alpha becomes a soft mask.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Optional

MAX_BYTES = 4 * 1024 * 1024
MAX_PIXELS = 4096 * 4096


class ImageError(ValueError):
    pass


@dataclass
class PdfImage:
    width: int
    height: int
    colorspace: str            # /DeviceRGB, /DeviceGray, /DeviceCMYK
    data: bytes                # stream data
    filter: str                # /DCTDecode or /FlateDecode
    smask: Optional[bytes] = None   # FlateDecode'd 8-bit alpha, or None
    decode: str = ""           # e.g. "/Decode [1 0 1 0 1 0 1 0]" for Adobe CMYK JPEGs


def load(data: bytes) -> PdfImage:
    if not data:
        raise ImageError("Empty image.")
    if len(data) > MAX_BYTES:
        raise ImageError("The logo is larger than 4 MB.")
    if data[:2] == b"\xff\xd8":
        return _jpeg(data)
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return _png(data)
    raise ImageError("Use a PNG or JPEG image for the logo.")


# ── JPEG ────────────────────────────────────────────────────────────────────

def _jpeg(data: bytes) -> PdfImage:
    i, n = 2, len(data)
    adobe = False
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker == 0xEE:
            adobe = True
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            comps = data[i + 9]
            cs = {1: "/DeviceGray", 3: "/DeviceRGB", 4: "/DeviceCMYK"}.get(comps)
            if not cs or not w or not h:
                raise ImageError("Unsupported JPEG.")
            dec = "/Decode [1 0 1 0 1 0 1 0]" if comps == 4 and adobe else ""
            return PdfImage(w, h, cs, data, "/DCTDecode", decode=dec)
        i += 2 + seg
    raise ImageError("Could not read the JPEG size.")


# ── PNG ─────────────────────────────────────────────────────────────────────

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _png(data: bytes) -> PdfImage:
    pos, idat, plte, trns = 8, [], None, None
    w = h = depth = ctype = interlace = None
    while pos + 8 <= len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, depth, ctype, _c, _f, interlace = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    if not w or not h:
        raise ImageError("Not a valid PNG.")
    if w * h > MAX_PIXELS:
        raise ImageError("The logo is too large (more than 4096 × 4096 pixels).")
    if interlace:
        raise ImageError("Interlaced PNG: save the logo again without interlacing.")
    if depth not in (8, 16) and not (ctype == 3 and depth in (1, 2, 4, 8)) \
            and not (ctype == 0 and depth in (1, 2, 4)):
        raise ImageError(f"Unsupported PNG ({depth}-bit).")
    raw = zlib.decompress(b"".join(idat))
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if chans is None:
        raise ImageError("Unsupported PNG colour type.")
    bits = depth * chans
    bpp = max(1, bits // 8)
    stride = (w * bits + 7) // 8
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif f == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 0xFF
        elif f == 4:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                ul = prev[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + _paeth(left, prev[x], ul)) & 0xFF
        rows.append(bytes(line))
        prev = line

    def samples(line):            # → list of 8-bit samples
        if depth == 8:
            return line
        if depth == 16:
            return line[0::2]
        out, mask = [], (1 << depth) - 1
        for byte in line:
            for sh in range(8 - depth, -1, -depth):
                out.append((byte >> sh) & mask)
        return out[:w * chans]

    color, alpha = bytearray(), bytearray()
    has_alpha = ctype in (4, 6) or (ctype == 3 and trns is not None)
    for line in rows:
        s = samples(line)
        if ctype == 0:
            scale = 255 // ((1 << depth) - 1) if depth < 8 else 1
            color.extend(v * scale for v in s[:w])
        elif ctype == 2:
            color.extend(s[:w * 3])
        elif ctype == 4:
            color.extend(s[0:w * 2:2])
            alpha.extend(s[1:w * 2:2])
        elif ctype == 6:
            for x in range(w):
                color.extend(s[x * 4:x * 4 + 3])
                alpha.append(s[x * 4 + 3])
        else:                      # palette
            if not plte:
                raise ImageError("PNG palette missing.")
            for v in s[:w]:
                color.extend(plte[v * 3:v * 3 + 3] or b"\0\0\0")
                if has_alpha:
                    alpha.append(trns[v] if v < len(trns) else 255)
    cs = "/DeviceGray" if ctype in (0, 4) else "/DeviceRGB"
    smask = zlib.compress(bytes(alpha)) if has_alpha and any(a < 255 for a in alpha) else None
    return PdfImage(w, h, cs, zlib.compress(bytes(color)), "/FlateDecode", smask)


def fit(img: PdfImage, max_w: float, max_h: float) -> tuple[float, float]:
    """Size (points) that fits *img* in max_w × max_h, keeping its shape."""
    s = min(max_w / img.width, max_h / img.height)
    return img.width * s, img.height * s
