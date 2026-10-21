#!/usr/bin/env python3
"""tools/plain_check.py: how plain are the docs? (3.9.6, advisory)

Lists, per page of the wiki and for the README:

* the average sentence length (aim: under 18 words) and the longest sentence;
* how many sentences run past 30 words;
* dashes used as connectors (" — ", " – ", " -- ");
* terms used before they are explained (a term counts as explained when the page
  links to *Words used here*, or when its first use is bold or italic and followed
  by a definition);
* whether the page opens with the *In one minute* box.

It never rewrites anything and always exits 0.  It reads what is written, so
the lists are a place to look, not a verdict.

    python3 tools/plain_check.py                  # every page, one line each
    python3 tools/plain_check.py wiki/Quick-Start.md --detail
    python3 tools/plain_check.py --strict         # exit 1 if a page misses the box
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AVG_AIM = 18
LONG_WORDS = 30
BOX = re.compile(r"in one minute", re.I)
GLOSSARY_LINK = re.compile(r"\[\[\s*Words used here\s*(\|[^\]]*)?\]\]|Words-used-here|Words used here", re.I)

# Terms a newcomer may not know. Each is explained on the Words used here page.
TERMS = [
    "chaser", "fade", "hold", "BPM", "beat", "mesh", "DMX universe", "universe",
    "cue list", "CueList", "LTP", "scene", "submaster", "solo frame", "fixture group",
    "palette", "recipe", "show in progress", "Virtual Console", "PANIC RESET",
    "Show Profile", "patch", "channel", "pan", "tilt", "gobo", "strobe", "MIDI",
    "DIP switch", "terminator", "fan-in", "fan in",
]

DEFINES = re.compile(r"^\s*(\(|is\b|are\b|means\b|=|:|,\s*(a|an|the)\b|—)", re.I)


def strip_markdown(text: str) -> str:
    """Prose only: no code, tables, images, html or link targets."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " code ", text)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", text)
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("|") or re.match(r"^-{3,}$", s) or s.startswith("#"):
            continue
        s = re.sub(r"^(>\s*)+", "", s)
        s = re.sub(r"^([-*]|\d+\.)\s+", "", s)
        lines.append(s)
    return "\n".join(lines)


def sentences(prose: str):
    """Split prose into sentences; a list item or a line is also a boundary."""
    out = []
    for para in re.split(r"\n+", prose):
        para = para.strip()
        if not para:
            continue
        for s in re.split(r"(?<=[.!?:])\s+(?=[A-Z0-9*_‘\"(])", para):
            s = s.strip()
            if s:
                out.append(s)
    return out


def words(s: str):
    return re.findall(r"[\w'’+\-./%]+", re.sub(r"[*_]", "", s))


def dashes(raw: str):
    """Dashes used as connectors, outside code."""
    prose = re.sub(r"```.*?```", " ", raw, flags=re.S)
    prose = re.sub(r"`[^`]*`", " ", prose)
    hits = []
    for n, ln in enumerate(prose.splitlines(), 1):
        if re.search(r"\s(—|–|--)\s|\w—\w", ln):
            hits.append((n, ln.strip()[:90]))
    return hits


def terms_unexplained(raw: str, prose: str):
    if GLOSSARY_LINK.search(raw):
        return []
    found = []
    for t in TERMS:
        m = re.search(r"(?<![\w-])" + re.escape(t) + r"s?(?![\w-])", prose, flags=re.I if t.islower() else 0)
        if not m:
            continue
        # explained in place: **term** or *term* then a definition, or "term (..."
        pat = r"(\*\*|\*|_)" + re.escape(t) + r"s?(\*\*|\*|_)?"
        first_bold = re.search(pat, raw, flags=re.I)
        tail = raw[m.end(): m.end() + 40] if not first_bold else raw[first_bold.end(): first_bold.end() + 40]
        if first_bold and DEFINES.match(tail):
            continue
        if DEFINES.match(raw[m.end(): m.end() + 40]) and "(" in raw[m.end(): m.end() + 3]:
            continue
        found.append(t)
    return found


def check(path: str):
    raw = open(path, encoding="utf-8").read()
    prose = strip_markdown(raw)
    sents = sentences(prose)
    lens = [len(words(s)) for s in sents]
    longest = max(zip(lens, sents), default=(0, ""))
    head = "\n".join(raw.splitlines()[:40])
    return {
        "page": os.path.relpath(path, HERE),
        "sentences": len(sents),
        "avg": (sum(lens) / len(lens)) if lens else 0.0,
        "longest": longest,
        "over": sum(1 for n in lens if n > LONG_WORDS),
        "dashes": dashes(raw),
        "terms": terms_unexplained(raw, prose),
        "box": bool(BOX.search(head)),
        "words": sum(lens),
    }


def default_paths():
    paths = [os.path.join(HERE, "README.md")]
    paths += sorted(glob.glob(os.path.join(HERE, "wiki", "*.md")))
    return [p for p in paths if os.path.isfile(p)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--detail", action="store_true", help="show the longest sentence, dashes and terms per page")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a page lacks the In one minute box")
    a = ap.parse_args(argv)
    paths = a.paths or default_paths()
    rows = [check(p) for p in paths]
    print(f"{'page':38} {'words':>6} {'avg':>5} {'>30':>4} {'dash':>4} {'terms':>5}  box")
    for r in rows:
        flag = "ok " if r["avg"] <= AVG_AIM else "long"
        print(f"{r['page'][-38:]:38} {r['words']:6d} {r['avg']:5.1f} {r['over']:4d} {len(r['dashes']):4d} "
              f"{len(r['terms']):5d}  {'yes' if r['box'] else ('stub' if r['words'] < 60 else 'NO ')} {flag}")
        if a.detail:
            n, s = r["longest"]
            if n:
                print(f"    longest ({n} words): {s[:160]}")
            for ln, txt in r["dashes"][:5]:
                print(f"    dash, line {ln}: {txt}")
            if r["terms"]:
                print("    used before explained: " + ", ".join(r["terms"]))
    # a stub (a few lines that point to another page) needs no box; neither does the README
    missing = [r["page"] for r in rows if not r["box"] and r["words"] >= 60 and not r["page"].endswith("README.md")]
    print(f"\n{len(rows)} pages, {len(missing)} without the In one minute box. Advisory only.")
    return 1 if (a.strict and missing) else 0


if __name__ == "__main__":
    sys.exit(main())
