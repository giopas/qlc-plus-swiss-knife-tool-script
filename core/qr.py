"""core/qr.py — a small QR code encoder (3.9.0), pure Python, no dependency.

Byte mode, error correction level M, versions 1 to 6 (up to 106 bytes), which
is plenty for the tablet's address.  `svg(text)` returns black modules on a
white square with a 4-module quiet zone, so it scans on a dark theme too.
Follows ISO/IEC 18004; checked in the tests by decoding the image.
"""

# (version): (total codewords, ec codewords per block, blocks)  — level M
_M = {1: (26, 10, 1), 2: (44, 16, 1), 3: (70, 26, 1),
      4: (100, 18, 2), 5: (134, 24, 2), 6: (172, 16, 4)}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34]}
MAX_BYTES = 106

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs_remainder(data, n):
    gen = [1]
    for i in range(n):
        nxt = [0] * (len(gen) + 1)
        for j, c in enumerate(gen):
            nxt[j] ^= c
            nxt[j + 1] ^= _mul(c, _EXP[i])
        gen = nxt
    rem = [0] * n
    for b in data:
        f = b ^ rem[0]
        rem = rem[1:] + [0]
        for i in range(n):
            rem[i] ^= _mul(gen[i + 1], f)
    return rem


def _codewords(raw, version):
    total, ecc, blocks = _M[version]
    ndata = total - ecc * blocks
    bits = [0, 1, 0, 0]
    bits += [(len(raw) >> i) & 1 for i in range(7, -1, -1)]
    for b in raw:
        bits += [(b >> i) & 1 for i in range(7, -1, -1)]
    cap = ndata * 8
    bits += [0] * min(4, cap - len(bits))
    bits += [0] * (-len(bits) % 8)
    data = [int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(data) < ndata:
        data.append(pad)
        pad ^= 0xEC ^ 0x11
    short = blocks - total % blocks
    size_short = total // blocks - ecc
    chunks, pos = [], 0
    for i in range(blocks):
        n = size_short + (1 if i >= short else 0)
        chunks.append(data[pos:pos + n])
        pos += n
    eccs = [_rs_remainder(c, ecc) for c in chunks]
    out = []
    for i in range(max(len(c) for c in chunks)):
        for c in chunks:
            if i < len(c):
                out.append(c[i])
    for i in range(ecc):
        for e in eccs:
            out.append(e[i])
    return out


def _penalty(m):
    n = len(m)
    score = 0
    for grid in (m, [list(r) for r in zip(*m)]):
        for row in grid:
            run, prev = 1, row[0]
            for v in row[1:]:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + run - 5
                    run, prev = 1, v
            if run >= 5:
                score += 3 + run - 5
            s = ''.join('1' if v else '0' for v in row)
            for pat in ('10111010000', '00001011101'):
                i = s.find(pat)
                while i != -1:
                    score += 40
                    i = s.find(pat, i + 1)
    for y in range(n - 1):
        for x in range(n - 1):
            if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                score += 3
    dark = sum(sum(1 for v in r if v) for r in m)
    score += 10 * (abs(dark * 100 // (n * n) - 50) // 5)
    return score


_MASKS = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
          lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
          lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
          lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0]


def encode(text):
    """The modules of the QR code for `text` as a list of rows of booleans."""
    raw = text.encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise ValueError(f'Too long for a QR code ({len(raw)} bytes, at most {MAX_BYTES})')
    version = next(v for v in sorted(_M)
                   if len(raw) <= _M[v][0] - _M[v][1] * _M[v][2] - 2)
    size = version * 4 + 17
    mod = [[False] * size for _ in range(size)]
    fn = [[False] * size for _ in range(size)]

    def put(x, y, dark):
        if 0 <= x < size and 0 <= y < size:
            mod[y][x] = dark
            fn[y][x] = True

    for i in range(size):
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                put(cx + dx, cy + dy, max(abs(dx), abs(dy)) not in (2, 4))
    pos = _ALIGN[version]
    for i, cy in enumerate(pos):
        for j, cx in enumerate(pos):
            if (i == 0 and j == 0) or (i == 0 and j == len(pos) - 1) or (i == len(pos) - 1 and j == 0):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    put(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)

    def format_bits(mask):
        data = mask   # level M is 00
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        return ((data << 10) | rem) ^ 0x5412

    def draw_format(mask):
        b = format_bits(mask)
        bit = lambda i: (b >> i) & 1 == 1
        for i in range(6):
            put(8, i, bit(i))
        put(8, 7, bit(6))
        put(8, 8, bit(7))
        put(7, 8, bit(8))
        for i in range(9, 15):
            put(14 - i, 8, bit(i))
        for i in range(8):
            put(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            put(8, size - 15 + i, bit(i))
        put(8, size - 8, True)

    draw_format(0)
    cw = _codewords(raw, version)
    i = 0
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                up = ((right + 1) & 2) == 0
                y = size - 1 - vert if up else vert
                if not fn[y][x] and i < len(cw) * 8:
                    mod[y][x] = (cw[i >> 3] >> (7 - (i & 7))) & 1 == 1
                    i += 1
        right -= 2
    best = None
    for mask in range(8):
        trial = [row[:] for row in mod]
        for y in range(size):
            for x in range(size):
                if not fn[y][x] and _MASKS[mask](x, y):
                    trial[y][x] = not trial[y][x]
        # the format bits depend on the mask, so redraw them on the trial
        mod_backup = mod
        mod = trial
        draw_format(mask)
        mod = mod_backup
        p = _penalty(trial)
        if best is None or p < best[0]:
            best = (p, trial)
    return best[1]


def svg(text, quiet=4):
    m = encode(text)
    n = len(m)
    d = ''.join(f'M{x + quiet} {y + quiet}h1v1h-1z' for y, r in enumerate(m) for x, v in enumerate(r) if v)
    t = n + 2 * quiet
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {t} {t}" shape-rendering="crispEdges">'
            f'<rect width="{t}" height="{t}" fill="#fff"/><path d="{d}" fill="#000"/></svg>')
