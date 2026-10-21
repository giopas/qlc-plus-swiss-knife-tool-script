"""WCAG contrast of the colour pairs declared in static/css/tokens.css (3.9.5, stage A).

Text pairs must reach 4.5:1 in the three themes (DESIGN_v2.md section 5).  A soft
background is a translucent colour, so it is laid over the surface it sits on
before the ratio is computed.  ``--text-faint`` is for placeholders, disabled
controls and drawn guides, not for reading; it only has to reach 3:1 against
the surface (the sidebar labels move to ``--text-dim`` in stage B).
"""
import re
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "tokens.css"
THEMES = {"dark": r'(?::root, )?\[data-theme="dark"\]', "grey": r'\[data-theme="grey"\]',
          "light": r'\[data-theme="light"\]'}


def _block(theme):
    text = CSS.read_text(encoding="utf-8")
    m = re.search(THEMES[theme] + r"\s*\{(.*?)\n\}", text, re.S)
    assert m, theme
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1)))


def _rgba(v):
    v = v.strip()
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    m = re.match(r"rgba?\(([^)]*)\)", v)
    p = [float(x) for x in m.group(1).split(",")]
    return (p[0], p[1], p[2], p[3] if len(p) > 3 else 1.0)


def _over(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def _lum(c):
    def ch(x):
        x /= 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _pairs(t):
    surf = {k: _rgba(t[k]) for k in ("--bg", "--surface-0", "--surface-1", "--surface-2")}
    out = []
    for fg in ("--text", "--text-dim"):
        for s, bg in surf.items():
            out.append((fg + " on " + s, _rgba(t[fg]), bg, 4.5))
    for fg in ("--accent", "--success-text", "--warning-text", "--error-text", "--orange"):
        for s in ("--bg", "--surface-0", "--surface-1"):
            out.append((fg + " on " + s, _rgba(t[fg]), surf[s], 4.5))
    out.append(("--accent-contrast on --accent", _rgba(t["--accent-contrast"]), _rgba(t["--accent"]), 4.5))
    out.append(("--orange-contrast on --orange", _rgba(t["--orange-contrast"]), _rgba(t["--orange"]), 4.5))
    for k in ("success", "warning", "error"):
        for s in ("--surface-0", "--surface-1"):
            bg = _over(_rgba(t["--%s-soft" % k]), surf[s])
            out.append(("--%s-text on --%s-soft over %s" % (k, k, s), _rgba(t["--%s-text" % k]), bg, 4.5))
    bg = _over(_rgba(t["--accent-soft"]), surf["--surface-0"])
    out.append(("--accent on --accent-soft", _rgba(t["--accent"]), bg, 4.5))
    for s in ("--bg", "--surface-0", "--surface-1"):
        out.append(("--text-faint on " + s + " (3:1)", _rgba(t["--text-faint"]), surf[s], 3.0))
    return out


@pytest.mark.parametrize("theme", list(THEMES))
def test_text_pairs_pass(theme):
    t = _block(theme)
    bad = ["%s: %.2f < %.1f" % (n, ratio(fg, bg), need)
           for n, fg, bg, need in _pairs(t) if ratio(fg, bg) < need]
    assert not bad, "\n".join(bad)


def test_every_theme_declares_the_same_tokens():
    names = {th: set(_block(th)) for th in THEMES}
    base = names["dark"]
    for th, n in names.items():
        assert n == base, (th, sorted(n ^ base))
