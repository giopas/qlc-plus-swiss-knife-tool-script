#!/usr/bin/env python3
"""The title and text of a GitHub release, from CHANGELOG.md.

    python3 tools/release_notes.py v3.4.0              # prints the title, then the notes
    python3 tools/release_notes.py v3.4.0 --title      # the title only
    python3 tools/release_notes.py v3.4.0 --out notes.md   # the notes into a file, the title printed

A release heading in CHANGELOG.md carries a short title after the date:

    ## [3.4.0] — 2026-10-16 — One way forward

The release is called "v3.4.0 · One way forward" and its text is that section of
the changelog, with a line pointing to the downloads and the full changelog.
Without a short title, the release is called by its version alone.

The release workflow (.github/workflows/release.yml) runs this when a v* tag is
pushed, so the release on GitHub gets this title and text by itself.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "giopas/qlc-plus-swiss-knife-tool-script"
_HEAD = re.compile(r"^## \[(?P<ver>[^\]]+)\]\s*(?:[—-]\s*(?P<date>\d{4}-\d{2}-\d{2}))?\s*(?:[—-]\s*(?P<title>.+?))?\s*$")


def section(version: str, text: str):
    """(short title, body) of one version's section; ValueError when it is not there."""
    v = version.lstrip("v")
    lines = text.splitlines()
    start = None
    title = ""
    for i, line in enumerate(lines):
        m = _HEAD.match(line)
        if m and m.group("ver") == v:
            start, title = i + 1, (m.group("title") or "").strip()
            break
    if start is None:
        raise ValueError(f"CHANGELOG.md has no section for {v}")
    end = next((j for j in range(start, len(lines)) if lines[j].startswith("## ")), len(lines))
    body = "\n".join(lines[start:end]).strip()
    body = re.sub(r"\n-{3,}\s*$", "", body).strip()          # a trailing --- separator
    return title, body


def release(version: str, text: str):
    """(release title, release notes)."""
    tag = "v" + version.lstrip("v")
    title, body = section(tag, text)
    name = f"{tag} · {title}" if title else tag
    notes = (body + "\n\n---\n\n"
             f"Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. "
             f"The whole history is in the [CHANGELOG](https://github.com/{REPO}/blob/main/CHANGELOG.md).\n")
    return name, notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("version", help="v3.4.0 or 3.4.0")
    ap.add_argument("--title", action="store_true", help="print the release title only")
    ap.add_argument("--out", help="write the notes to this file and print the title")
    ap.add_argument("--changelog", default=os.path.join(ROOT, "CHANGELOG.md"))
    a = ap.parse_args(argv)
    with open(a.changelog, encoding="utf-8") as f:
        text = f.read()
    try:
        name, notes = release(a.version, text)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    if a.title:
        print(name)
    elif a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(notes)
        print(name)
    else:
        print(name)
        print()
        print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
