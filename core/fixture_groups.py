"""
Fixture groups: create, edit and delete them (WORKPLAN 2.8 — the Pub test's
step 3 gap: no tool made groups for an existing show).

A QLC+ fixture group is a grid of heads:

    <FixtureGroup ID="10">
     <Name>Singer Pair</Name>
     <Size X="2" Y="1"/>
     <Head X="0" Y="0" Fixture="12">0</Head>
     …

RGB matrices run on a group (``<FixtureGroup>`` in the function), the Look
Builder makes looks per group, the VC can select groups.  Here a group is one
row of fixtures, ordered **left → right as seen from the audience** (3D X,
then depth) unless the caller keeps its own order; one head (head 0) per
fixture, as QLC+ does for single-head fixtures.  Pure functions on an
un-namespaced root.
"""
from __future__ import annotations

import re

import xml.etree.ElementTree as ET


class GroupError(ValueError):
    pass


def _eng(root):
    eng = root.find("Engine")
    if eng is None:
        raise GroupError("The workspace has no Engine.")
    return eng


def _fixtures(eng) -> dict[str, ET.Element]:
    return {(f.findtext("ID") or "").strip(): f for f in eng.findall("Fixture")}


def _positions(root) -> dict[str, tuple]:
    from core.porter import _positions as p
    return p(root)


def stage_order(root, ids) -> list[str]:
    """Fixture ids left → right as seen from the audience (3D X), then back
    → front; fixtures without a 3D position keep their order, at the end."""
    pos = _positions(root)
    ids = [str(i) for i in ids]
    placed = sorted([i for i in ids if i in pos], key=lambda i: (pos[i][0], pos[i][2], int(i) if i.isdigit() else 0))
    return placed + [i for i in ids if i not in pos]


def groups(root) -> list[dict]:
    """``[{id, name, size: [x, y], fixtures: [ids in grid order], heads: n,
    used_by: [matrix names]}]``."""
    eng = root.find("Engine")
    if eng is None:
        return []
    used: dict[str, list[str]] = {}
    for fn in eng.findall("Function"):
        if fn.get("Type") == "RGBMatrix":
            used.setdefault((fn.findtext("FixtureGroup") or "").strip(), []).append(fn.get("Name", ""))
    out = []
    for g in eng.findall("FixtureGroup"):
        sz = g.find("Size")
        hs = sorted(g.findall("Head"), key=lambda h: (int(h.get("Y", 0)), int(h.get("X", 0))))
        fids = []
        for h in hs:
            f = h.get("Fixture", "")
            if f not in fids:
                fids.append(f)
        out.append({"id": g.get("ID", ""), "name": g.findtext("Name") or "",
                    "size": [int(sz.get("X", 0)), int(sz.get("Y", 0))] if sz is not None else [0, 0],
                    "fixtures": fids, "heads": len(hs),
                    "used_by": sorted(used.get(g.get("ID", ""), []))})
    return out


def _group(eng, gid) -> ET.Element:
    for g in eng.findall("FixtureGroup"):
        if g.get("ID") == str(gid):
            return g
    raise GroupError(f"Fixture group {gid} not found.")


def _fill(g: ET.Element, fixtures: dict, ids: list[str]) -> None:
    """Replace the group's heads by *ids* (in this order), one row."""
    for el in list(g):
        if el.tag in ("Size", "Head"):
            g.remove(el)
    heads = [(f, 0) for f in ids]
    size = ET.SubElement(g, "Size", {"X": str(len(heads)), "Y": "1"})
    size.tail = None
    for x, (f, h) in enumerate(heads):
        el = ET.SubElement(g, "Head", {"X": str(x), "Y": "0", "Fixture": f})
        el.text = str(h)


def _check(eng, name: str, ids, gid=None) -> tuple[str, list[str], dict]:
    name = re.sub(r"\s+", " ", (name or "").strip().strip('"\'').rstrip(":;,.").strip())
    if not name:
        raise GroupError("Give the group a name.")
    if any((g.findtext("Name") or "").strip().lower() == name.lower() and g.get("ID") != str(gid)
           for g in eng.findall("FixtureGroup")):
        raise GroupError(f"A group called '{name}' already exists.")
    fx = _fixtures(eng)
    ids = [str(i) for i in ids]
    missing = [i for i in ids if i not in fx]
    if missing:
        raise GroupError(f"Fixture(s) not in the show: {', '.join(missing)}.")
    if not ids:
        raise GroupError("Pick at least one fixture.")
    seen, uniq = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return name, uniq, fx


def create(root, name: str, fixture_ids, order: str = "stage") -> dict:
    """New group (next free id) of *fixture_ids*; ``order="stage"`` sorts
    them left → right, ``"given"`` keeps the order given."""
    eng = _eng(root)
    name, ids, fx = _check(eng, name, fixture_ids)
    if order == "stage":
        ids = stage_order(root, ids)
    used = [int(g.get("ID")) for g in eng.findall("FixtureGroup") if (g.get("ID") or "").isdigit()]
    gid = str(max(used, default=-1) + 1)
    g = ET.Element("FixtureGroup", {"ID": gid})
    ET.SubElement(g, "Name").text = name
    _fill(g, fx, ids)
    last = -1
    for i, c in enumerate(list(eng)):
        if c.tag in ("Fixture", "FixtureGroup"):
            last = i
    eng.insert(last + 1, g)
    return {"id": gid, "name": name, "fixtures": ids}


def update(root, gid, *, name: str | None = None, fixture_ids=None, order: str = "stage") -> dict:
    """Rename and/or set the fixtures of a group (same id, so matrices and
    VC widgets that use it keep working)."""
    eng = _eng(root)
    g = _group(eng, gid)
    cur = next(x for x in groups(root) if x["id"] == str(gid))
    new_name, ids, fx = _check(eng, name if name is not None else cur["name"],
                               fixture_ids if fixture_ids is not None else cur["fixtures"], gid)
    g.find("Name").text = new_name
    if fixture_ids is not None:
        if order == "stage":
            ids = stage_order(root, ids)
        _fill(g, fx, ids)
    return {"id": str(gid), "name": new_name, "fixtures": ids if fixture_ids is not None else cur["fixtures"]}


def delete(root, gid) -> dict:
    """Delete a group; refused while an RGB matrix runs on it (say which)."""
    eng = _eng(root)
    g = _group(eng, gid)
    cur = next(x for x in groups(root) if x["id"] == str(gid))
    if cur["used_by"]:
        raise GroupError(f"'{cur['name']}' is used by {len(cur['used_by'])} RGB matrix(es): "
                         f"{', '.join(cur['used_by'][:5])}{'…' if len(cur['used_by']) > 5 else ''} — "
                         "change or delete those first.")
    eng.remove(g)
    return {"id": str(gid), "name": cur["name"]}
