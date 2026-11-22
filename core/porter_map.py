"""core/porter_map.py — the Function Porter's fixture mapping as a file (3.21.0).

Step 3 of the Porter sends each source fixture to one or more target
fixtures.  Saved as a small JSON file, the same mapping can be loaded again
for the next show between the same two rigs (festival → pub, say).  QLC+'s
own Fixture Remap cannot reopen a mapping once it is made.

A fixture is written by what it is, not only by its ID, because the next
show may number its fixtures differently:

    {"id": "7", "name": "FLS", "manufacturer": "Eurolite",
     "model": "LED PAR-56", "mode": "4 channels", "universe": "0", "address": "12"}

Loading matches each saved fixture to a fixture of the show in this order:

1. same ID **and** same name;
2. same name (the first with the same model and mode when names repeat);
3. same ID and same model and mode.

Anything else is reported as not found and left for Auto-Map.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

FORMAT = "swissknife-porter-map"
VERSION = 1
KEYS = ("id", "name", "manufacturer", "model", "mode", "universe", "address")
OPTIONS = ("fanout", "strategy", "drop_unmapped", "complete_channels", "convert_panic", "mirror", "skip")


class MapError(ValueError):
    """The file is not a Porter mapping."""


def _ident(info: dict) -> dict:
    return {k: str(info.get(k, "")) for k in KEYS}


def export_map(mapping: Dict[str, Iterable[str]], src_fixtures: List[dict],
               tgt_fixtures: List[dict], options: Optional[dict] = None,
               src_name: str = "", tgt_name: str = "") -> dict:
    """The mapping ``{src id: [tgt ids]}`` as a file's content."""
    src = {str(f.get("id")): f for f in src_fixtures}
    tgt = {str(f.get("id")): f for f in tgt_fixtures}
    rows = []
    for sid, tids in mapping.items():
        s = src.get(str(sid))
        if s is None:
            continue
        rows.append({"source": _ident(s),
                     "targets": [_ident(tgt[str(t)]) for t in (tids or []) if str(t) in tgt]})
    opts = {k: v for k, v in (options or {}).items() if k in OPTIONS}
    return {"format": FORMAT, "version": VERSION, "source_show": src_name,
            "target_show": tgt_name, "rows": rows, "options": opts}


def _match(saved: dict, fixtures: List[dict], used: Optional[set] = None) -> Optional[str]:
    used = used if used is not None else set()

    def same(f, *keys):
        return all(str(f.get(k, "")) == str(saved.get(k, "")) for k in keys)

    free = [f for f in fixtures if str(f.get("id")) not in used]
    for keys in (("id", "name"), ("name", "model", "mode"), ("name",), ("id", "model", "mode")):
        if not all(saved.get(k) not in (None, "") for k in keys):
            continue
        hit = next((f for f in free if same(f, *keys)), None)
        if hit is not None:
            return str(hit.get("id"))
    return None


def import_map(data: dict, src_fixtures: List[dict], tgt_fixtures: List[dict]) -> dict:
    """Bind a saved mapping to the two shows loaded now.

    Returns ``{mapping: {src id: [tgt ids]}, options, found, not_found: [names],
    targets_not_found: [names]}``.  Source fixtures not in the file are left
    out of *mapping*, so the caller keeps (or auto-maps) them.
    """
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise MapError("This file is not a Function Porter mapping.")
    if int(data.get("version", 0) or 0) > VERSION:
        raise MapError("This mapping was saved by a newer Swiss Knife.")
    mapping: Dict[str, List[str]] = {}
    not_found: List[str] = []
    tgt_missing: List[str] = []
    used_src: set = set()
    for row in data.get("rows") or []:
        s = row.get("source") or {}
        sid = _match(s, src_fixtures, used_src)
        if sid is None:
            not_found.append(s.get("name") or s.get("id") or "?")
            continue
        used_src.add(sid)
        tids: List[str] = []
        for t in row.get("targets") or []:
            tid = _match(t, tgt_fixtures, set(tids))
            if tid is None:
                tgt_missing.append(t.get("name") or t.get("id") or "?")
            else:
                tids.append(tid)
        mapping[sid] = tids
    opts = {k: v for k, v in (data.get("options") or {}).items() if k in OPTIONS}
    # options that name source fixtures (mirror, skip) are bound the same way
    for key in ("mirror", "skip"):
        if key in opts:
            bound = []
            for s in opts[key] or []:
                sid = _match(s, src_fixtures) if isinstance(s, dict) else None
                if sid is not None:
                    bound.append(sid)
            opts[key] = bound
    return {"mapping": mapping, "options": opts, "found": len(mapping),
            "not_found": not_found, "targets_not_found": sorted(set(tgt_missing))}


def idents(ids: Iterable[str], fixtures: List[dict]) -> List[dict]:
    """The saved form of some source fixtures (for the mirror and skip options)."""
    by = {str(f.get("id")): f for f in fixtures}
    return [_ident(by[str(i)]) for i in ids if str(i) in by]
