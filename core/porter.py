"""
core/porter.py — Function Porter engine
========================================
Cross-workspace function import with dependency resolution, ID rebasing,
fixture remapping and fan-out.

Pure logic — no Flask, no UI.  Fully testable from a script.

Public API
----------
load_source(path)           → dict summary
load_target(path)           → dict summary
get_state()                 → dict
list_source_functions()     → list[dict]
list_source_fixtures()      → list[dict]
list_target_fixtures()      → list[dict]
resolve_closure(seed_ids)   → ClosureResult dict
build_fixture_candidates(ids) → compatibility tiers
auto_map(ids, strategy)     → src → [tgt] ("all" | "same_id" | "fan_in")
compute_blocks(...)         → tgt → [src, ...] (who feeds each target)
validate(plan)              → ValidationResult dict
execute(plan)               → (suggested name, bytes)
port(plan)                  → PortResult (bytes + Doctor gate + report)
seeds_from_widgets(ids)     → function IDs used by source VC widgets
clear()

Fan-in (many source fixtures → fewer targets)
---------------------------------------------
``fanout_mode="fan_in"``: several source fixtures may feed one target.  The
sources of a target form its *block* (in stage order, left → right).  For
every scene the target takes the values of the first source in its block
that is **lit** in that scene (an intensity/colour channel above 0), else of
the first source the scene declares.  So a chase that runs across 8 PARs
still lights one of 4 targets on every step, and colours are never mixed.
``auto_map(ids, "fan_in")`` proposes the blocks: per fixture type, sources
and targets in stage order, split into equal contiguous blocks.

Source fixtures with no target are an error unless ``drop_unmapped`` is set
(then their values are left out, e.g. the ceiling spots when porting into a
floor-only rig).  Scenes, matrices and EFX left with no fixture are removed
from the port, with every step and VC button that used them (reported).
"""

from __future__ import annotations

import copy
import os
import re
from collections import defaultdict
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from core import qxw_io

# ═══════════════════════════════════════════════════════════════════════════════
# Module state
# ═══════════════════════════════════════════════════════════════════════════════

_src: dict = {"loaded": False, "path": None, "name": None, "tree": None, "root": None}
_tgt: dict = {"loaded": False, "path": None, "name": None, "tree": None, "root": None}


def _short_name(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _engine(root: ET.Element) -> ET.Element | None:
    return root.find("Engine")


def _parse_qxw(path: str) -> tuple[ET.ElementTree, ET.Element]:
    # Strip the QLC+ namespace so plain tag names ("Engine") work.
    tree = qxw_io.load_qxw(path, strip_namespace=True)
    root = tree.getroot()
    return tree, root


# ═══════════════════════════════════════════════════════════════════════════════
# Load / clear
# ═══════════════════════════════════════════════════════════════════════════════

def load_source(path: str, name: str = None) -> dict:
    global _src
    tree, root = _parse_qxw(path)
    _src = {"loaded": True, "path": path, "name": name or _short_name(path),
            "tree": tree, "root": root}
    return _make_summary(root)


def load_target(path: str, name: str = None) -> dict:
    global _tgt
    tree, root = _parse_qxw(path)
    _tgt = {"loaded": True, "path": path, "name": name or _short_name(path),
            "tree": tree, "root": root}
    return _make_summary(root)


def clear():
    global _src, _tgt
    _src = {"loaded": False, "path": None, "name": None, "tree": None, "root": None}
    _tgt = {"loaded": False, "path": None, "name": None, "tree": None, "root": None}


def source_root() -> ET.Element | None:
    return _src["root"]


def target_root() -> ET.Element | None:
    return _tgt["root"]


def get_state() -> dict:
    return {
        "src_loaded": _src["loaded"],
        "tgt_loaded": _tgt["loaded"],
        "src_name":   _src["name"],
        "tgt_name":   _tgt["name"],
        "src_path":   _src["path"],
        "tgt_path":   _tgt["path"],
    }


def _make_summary(root: ET.Element) -> dict:
    engine = _engine(root)
    if engine is None:
        return {"fixtures": 0, "functions": 0, "creator_version": ""}
    creator = root.find("Creator")
    version = ""
    if creator is not None:
        v_el = creator.find("Version")
        if v_el is not None and v_el.text:
            version = v_el.text.strip()
    return {
        "fixtures":  len(engine.findall("Fixture")),
        "functions": len(engine.findall("Function")),
        "creator_version": version,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# List helpers
# ═══════════════════════════════════════════════════════════════════════════════

def list_source_functions() -> list[dict]:
    if not _src["loaded"]:
        return []
    engine = _engine(_src["root"])
    if engine is None:
        return []
    result = []
    for fn in engine.findall("Function"):
        result.append({
            "id":   fn.get("ID", ""),
            "name": fn.get("Name", ""),
            "type": fn.get("Type", ""),
            "path": fn.get("Path", ""),
        })
    return result


def list_source_fixtures() -> list[dict]:
    if not _src["loaded"]:
        return []
    engine = _engine(_src["root"])
    if engine is None:
        return []
    return [_fixture_info(f) for f in engine.findall("Fixture")]


def list_target_fixtures() -> list[dict]:
    if not _tgt["loaded"]:
        return []
    engine = _engine(_tgt["root"])
    if engine is None:
        return []
    return [_fixture_info(f) for f in engine.findall("Fixture")]


def _fixture_info(el: ET.Element) -> dict:
    """Extract fixture metadata from a <Fixture> element."""
    def _child_text(tag: str, default: str = "") -> str:
        ch = el.find(tag)
        return (ch.text or default).strip() if ch is not None else default

    return {
        "id":           _child_text("ID", el.get("ID", "")),
        "name":         _child_text("Name", el.get("Name", "")),
        "manufacturer": _child_text("Manufacturer", el.get("Manufacturer", "")),
        "model":        _child_text("Model", el.get("Model", "")),
        "mode":         _child_text("Mode", el.get("Mode", "")),
        "universe":     _child_text("Universe", el.get("Universe", "0")),
        "address":      _child_text("Address", el.get("Address", "0")),
        "channels":     _child_text("Channels", el.get("Channels", "0")),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Dependency resolution
# ═══════════════════════════════════════════════════════════════════════════════

# Every place a function ID can appear as a reference
_FUNC_REF_ATTRS = {"Function", "FunctionID", "SceneID", "ChaserID"}
_FIX_REF_ATTRS  = {"Fixture", "FixtureID"}

# Script command patterns that embed function IDs
# QLC+ saves script commands percent-encoded ("stopfunction%3A12")
_SCRIPT_FUNC_RE = re.compile(r'((?:start|stop)function(?::|%3A))(\d+)', re.IGNORECASE)


def resolve_closure(seed_ids: list[str]) -> dict:
    """
    Walk all reference sites from the seed function IDs to a fixed point.

    Returns
    -------
    dict with:
        function_ids   list[str] — all function IDs in the closure (seeds + deps)
        fixture_ids    list[str] — all fixture IDs referenced by the closure
        dep_map        dict[str, list[str]] — func_id → [func_ids it depends on]
        fixture_map    dict[str, list[str]] — func_id → [fixture_ids it references]
        lit_fixture_map dict[str, list[str]] — func_id → fixtures it lights (> 0)
        cycles         list[str] — cycle descriptions (if any)
        unresolved     list[str] — IDs referenced but not found in source
        seed_ids       list[str] — the original seeds (for UI distinction)
    """
    if not _src["loaded"]:
        raise RuntimeError("Source QXW not loaded.")

    engine = _engine(_src["root"])
    if engine is None:
        raise RuntimeError("Source has no Engine block.")

    # Index all functions by ID
    func_by_id: dict[str, ET.Element] = {}
    for fn in engine.findall("Function"):
        func_by_id[fn.get("ID", "")] = fn

    # BFS/DFS to closure
    visited: set[str] = set()
    queue = list(seed_ids)
    dep_map: dict[str, list[str]] = defaultdict(list)
    fixture_refs: dict[str, set[str]] = defaultdict(set)
    cycles: list[str] = []
    unresolved: list[str] = []
    in_stack: set[str] = set()  # for cycle detection
    discovery: list[str] = []   # visit order (deterministic)

    def _walk(fid: str, path: list[str]):
        if fid in visited:
            return
        if fid in in_stack:
            cycle_start = path.index(fid)
            cycles.append(" → ".join(path[cycle_start:] + [fid]))
            return
        if fid not in func_by_id:
            unresolved.append(fid)
            return

        in_stack.add(fid)
        path.append(fid)
        visited.add(fid)
        discovery.append(fid)

        fn_el = func_by_id[fid]
        fn_type = fn_el.get("Type", "")

        # Collect all child function refs and fixture refs
        child_func_ids: list[str] = []
        _collect_refs(fn_el, fn_type, child_func_ids, fixture_refs[fid])

        dep_map[fid] = child_func_ids
        for child_id in child_func_ids:
            _walk(child_id, path)

        path.pop()
        in_stack.discard(fid)

    for sid in seed_ids:
        _walk(sid, [])

    # Ordered (deterministic): seeds first, then dependencies in discovery
    # order.  ``visited`` is a set, so never iterate it for ordering.
    ordered = []
    seen = set()
    for fid in seed_ids:
        if fid in visited and fid not in seen:
            ordered.append(fid)
            seen.add(fid)
    for fid in discovery:
        if fid not in seen:
            ordered.append(fid)
            seen.add(fid)

    # RGB matrices use a fixture group: its fixtures are part of the closure
    group_ids: list[str] = []
    groups = {g.get("ID", ""): g for g in engine.findall("FixtureGroup")}
    for fid in ordered:
        fn = func_by_id.get(fid)
        if fn is not None and fn.get("Type") == "RGBMatrix":
            gid = (fn.findtext("FixtureGroup") or "").strip()
            if gid and gid not in group_ids:
                group_ids.append(gid)
                g = groups.get(gid)
                if g is not None:
                    for head in g.findall("Head"):
                        fx = head.get("Fixture", "")
                        if fx:
                            fixture_refs[fid].add(fx)
                else:
                    unresolved.append(f"group {gid}")

    all_fixture_ids = set()
    for fids in fixture_refs.values():
        all_fixture_ids.update(fids)

    # Fixtures a function actually lights (a scene declaring a fixture at 0
    # does not use it) — the Porter UI uses it to untick functions that only
    # light fixtures the user chose not to port.
    lit_map: dict[str, list[str]] = {}
    for fid in ordered:
        fn = func_by_id.get(fid)
        if fn is None:
            continue
        if fn.get("Type") in ("Scene", "Sequence"):
            lit_map[fid] = _id_sorted({fv.get("ID", "") for fv in fn.findall("FixtureVal")
                                       if any(v > 0 for v in _pairs(fv.text).values())})
        else:
            lit_map[fid] = _id_sorted(fixture_refs.get(fid, set()))

    return {
        "function_ids": ordered,
        "fixture_ids":  _id_sorted(all_fixture_ids),
        "lit_fixture_map": lit_map,
        "group_ids":    group_ids,
        "dep_map":      dict(dep_map),
        "fixture_map":  {k: _id_sorted(v) for k, v in fixture_refs.items()},
        "cycles":       cycles,
        "unresolved":   unresolved,
        "seed_ids":     list(seed_ids),
    }


def _id_sorted(ids) -> list[str]:
    """Sort IDs numerically (``"2"`` before ``"10"``), non-numeric last."""
    return sorted(ids, key=lambda i: (0, int(i), "") if str(i).isdigit() else (1, 0, str(i)))


def _efx_fixtures(fn_el: ET.Element) -> list[ET.Element]:
    return [c for c in fn_el if c.tag in ("Fixture", "EFXFixture")]


def _collect_refs(fn_el: ET.Element, fn_type: str,
                  func_ids: list[str], fix_ids: set[str]):
    """Collect function and fixture ID references from a function element."""

    # ── FixtureVal (Scene, Sequence) ──────────────────────────────────────
    for fv in fn_el.findall("FixtureVal"):
        fid = fv.get("ID", "")
        if fid:
            fix_ids.add(fid)

    # ── Step (Chaser, Collection) — text is function ID ───────────────────
    for step in fn_el.findall("Step"):
        text = (step.text or "").strip()
        if text and text.isdigit():
            func_ids.append(text)

    # ── BoundScene (Sequence) ─────────────────────────────────────────────
    bound = fn_el.get("BoundScene", "")
    if bound and bound.isdigit():
        func_ids.append(bound)

    # ── Show tracks ───────────────────────────────────────────────────────
    for track in fn_el.findall("Track"):
        scene_id = track.get("SceneID", "")
        if scene_id and scene_id.isdigit():
            func_ids.append(scene_id)
        for sf in track.findall("ShowFunction"):
            sf_id = sf.get("ID", "")
            if sf_id and sf_id.isdigit():
                func_ids.append(sf_id)

    # ── EFX fixtures (QLC+ saves <Fixture><ID>; <EFXFixture> is legacy) ───
    if fn_type == "EFX":
        for efx_fix in _efx_fixtures(fn_el):
            eid = (efx_fix.findtext("ID", "") or "").strip()
            if eid and eid.isdigit():
                fix_ids.add(eid)

    # ── Script commands ───────────────────────────────────────────────────
    if fn_type == "Script":
        for cmd in fn_el.findall("Command"):
            text = cmd.text or ""
            for m in _SCRIPT_FUNC_RE.finditer(text):
                func_ids.append(m.group(2))

    # ── Generic: walk child attributes for any remaining refs ─────────────
    for child in fn_el:
        for attr in _FUNC_REF_ATTRS:
            val = child.get(attr, "")
            if val and val.isdigit() and val not in func_ids:
                # Avoid adding the element's own ID
                if attr != "ID" or child.tag != "Function":
                    func_ids.append(val)
        for attr in _FIX_REF_ATTRS:
            val = child.get(attr, "")
            if val and val.isdigit():
                fix_ids.add(val)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixture compatibility
# ═══════════════════════════════════════════════════════════════════════════════

def build_fixture_candidates(closure_fixture_ids: list[str]) -> dict:
    """
    For each source fixture referenced by the closure, find compatible
    target fixtures grouped by tier.

    Returns
    -------
    dict with:
        source_fixtures  list[dict] — fixture info for each src fixture in closure
        candidates       dict[str, dict] — src_fixture_id → {
            tier1: [tgt fixtures],  # exact model+mode
            tier2: [tgt fixtures],  # same model, different mode
            tier3: [tgt fixtures],  # different model (best-effort)
        }
    """
    if not _src["loaded"] or not _tgt["loaded"]:
        raise RuntimeError("Both source and target must be loaded.")

    src_engine = _engine(_src["root"])
    tgt_engine = _engine(_tgt["root"])

    # Index source fixtures
    src_fixtures = {}
    for f in src_engine.findall("Fixture"):
        info = _fixture_info(f)
        if info["id"] in closure_fixture_ids:
            src_fixtures[info["id"]] = info

    # All target fixtures
    tgt_list = [_fixture_info(f) for f in tgt_engine.findall("Fixture")]

    candidates = {}
    for src_id, src_info in src_fixtures.items():
        tier1, tier2, tier3 = [], [], []
        for tgt in tgt_list:
            if (tgt["manufacturer"] == src_info["manufacturer"] and
                    tgt["model"] == src_info["model"]):
                if tgt["mode"] == src_info["mode"]:
                    tier1.append(tgt)
                else:
                    tier2.append(tgt)
            else:
                tier3.append(tgt)
        candidates[src_id] = {"tier1": tier1, "tier2": tier2, "tier3": tier3}

    return {
        "source_fixtures": list(src_fixtures.values()),
        "candidates": candidates,
    }


def auto_map(closure_fixture_ids: list[str], strategy: str = "all") -> dict:
    """
    Propose a fixture mapping ``src_id → [tgt_id, ...]``.

    strategy
        ``"all"``      every tier-1 target (same model + mode) — for fan-out.
        ``"same_id"``  the target fixture with the same ID and model + mode
                       (a rig reduced from the source, e.g. Pub from Festival).
        ``"fan_in"``   per fixture type, sources and targets in stage order
                       split into equal contiguous blocks (14 → 6: each target
                       gets 2–3 neighbouring sources).  Use with
                       ``fanout_mode="fan_in"``.
    Sources with no suitable target map to ``[]``.
    """
    if strategy == "same_id":
        return _map_same_id(closure_fixture_ids)
    if strategy == "fan_in":
        return _map_fan_in(closure_fixture_ids)
    info = build_fixture_candidates(closure_fixture_ids)
    mapping = {}
    for src_id, cands in info["candidates"].items():
        mapping[src_id] = [t["id"] for t in cands["tier1"]]
    return mapping


def _type_key(info: dict) -> tuple:
    return (info["manufacturer"], info["model"], info["mode"])


def _fixture_infos(root: ET.Element) -> dict[str, dict]:
    engine = _engine(root)
    if engine is None:
        return {}
    return {i["id"]: i for i in (_fixture_info(f) for f in engine.findall("Fixture"))}


def _positions(root: ET.Element) -> dict[str, tuple]:
    """3D monitor positions ``fixture_id → (x, y, z)`` (mm), if saved."""
    pos = {}
    for mon in root.iter("Monitor"):
        for it in mon.findall("FxItem"):
            try:
                pos[it.get("ID", "")] = (float(it.get("XPos", 0)), float(it.get("YPos", 0)),
                                         float(it.get("ZPos", 0)))
            except ValueError:
                continue
    return pos


def stage_order(root: ET.Element, ids) -> list[str]:
    """Fixture IDs in stage order: left → right by 3D X position (then depth),
    when every fixture has a position; otherwise by universe and DMX address."""
    ids = list(dict.fromkeys(str(i) for i in ids))
    infos = _fixture_infos(root)
    pos = _positions(root)

    def num(v, d=0):
        try:
            return int(v)
        except (TypeError, ValueError):
            return d

    def addr_key(i):
        inf = infos.get(i, {})
        return (num(inf.get("universe")), num(inf.get("address")), num(i, 1 << 30), i)

    if ids and all(i in pos for i in ids):
        return sorted(ids, key=lambda i: (pos[i][0], pos[i][2]) + addr_key(i))
    return sorted(ids, key=addr_key)


def _map_same_id(ids: list[str]) -> dict:
    if not _src["loaded"] or not _tgt["loaded"]:
        raise RuntimeError("Both source and target must be loaded.")
    src, tgt = _fixture_infos(_src["root"]), _fixture_infos(_tgt["root"])
    out = {}
    for s in _id_sorted(ids):
        t = tgt.get(s)
        out[s] = [s] if (s in src and t is not None and _type_key(t) == _type_key(src[s])) else []
    return out


def _map_fan_in(ids: list[str]) -> dict:
    if not _src["loaded"] or not _tgt["loaded"]:
        raise RuntimeError("Both source and target must be loaded.")
    src, tgt = _fixture_infos(_src["root"]), _fixture_infos(_tgt["root"])
    out: dict[str, list[str]] = {s: [] for s in _id_sorted(ids)}
    by_type: dict[tuple, list[str]] = defaultdict(list)
    for s in out:
        if s in src:
            by_type[_type_key(src[s])].append(s)
    for key in sorted(by_type):
        S = stage_order(_src["root"], by_type[key])
        T = stage_order(_tgt["root"], [t for t, i in tgt.items() if _type_key(i) == key])
        m, n = len(S), len(T)
        for k, t in enumerate(T):
            a = k * m // n
            b = max(a + 1, (k + 1) * m // n)
            for s in S[a:b]:
                out[s].append(t)
    return out


def compute_blocks(src_fixture_ids: list[str], fixture_mapping: dict[str, list[str]],
                   mode: str = "pattern_repeat") -> dict[str, list[str]]:
    """Who feeds each target: ``tgt_id → [src_id, ...]`` (in the order of
    *src_fixture_ids*, which should be stage order).  One source per target,
    except in ``fan_in`` mode where every source mapped to a target joins
    its block."""
    if mode == "fan_in":
        blocks: dict[str, list[str]] = defaultdict(list)
        for s in src_fixture_ids:
            for t in fixture_mapping.get(s, []):
                if s not in blocks[t]:
                    blocks[t].append(s)
        return dict(blocks)
    return {t: [s] for t, s in compute_fanout(src_fixture_ids, fixture_mapping, mode).items()}


def _intensity_channels(infos: dict[str, dict], defs: dict) -> dict[str, set]:
    """``fixture_id → {channel indices in the Intensity group}`` (dimmer and
    colour), for fixtures whose definition is known."""
    out = {}
    for fid, inf in infos.items():
        d = defs.get((inf["manufacturer"].strip().lower(), inf["model"].strip().lower()))
        names = (d or {}).get("mode_channels", {}).get(inf["mode"]) if d else None
        if not names:
            continue
        cdefs = d.get("channel_defs", {})
        idx = {i for i, n in enumerate(names) if (cdefs.get(n) or {}).get("group") == "Intensity"}
        if idx:
            out[fid] = idx
    return out


def _neutral_maps(infos: dict[str, dict], defs: dict) -> dict[str, dict[int, int]]:
    """``fixture_id → {channel index: neutral value}`` for every channel of
    the fixture's mode (Quick Start's capability-aware neutral values), for
    fixtures whose definition is known."""
    from core.quick_start.channel_model import neutral_map
    out = {}
    for fid, inf in infos.items():
        d = defs.get((inf["manufacturer"].strip().lower(), inf["model"].strip().lower()))
        if not d or inf["mode"] not in (d.get("mode_channels") or {}):
            continue
        try:
            n = int(inf.get("channels") or 0)
        except ValueError:
            n = 0
        out[fid] = neutral_map({"mode": inf["mode"], "ch_count": n}, d)
    return out


def _complete(text: str, neutral: dict[int, int]) -> str:
    """Declare every channel: keep the scene's values, add the missing
    channels at their neutral value, drop indices the fixture doesn't have."""
    vals = {c: v for c, v in _pairs(text).items() if c in neutral}
    for c, v in neutral.items():
        vals.setdefault(c, v)
    return ",".join(f"{c},{vals[c]}" for c in sorted(vals))


def _pairs(text: str) -> dict[int, int]:
    parts = (text or "").strip().split(",")
    out = {}
    for i in range(0, len(parts) - 1, 2):
        try:
            out[int(parts[i])] = int(parts[i + 1])
        except ValueError:
            continue
    return out


def _is_lit(text: str, intensity: set | None) -> bool:
    """A fixture is lit in a scene if an intensity/colour channel is above 0
    (any channel, when the definition is unknown)."""
    vals = _pairs(text)
    if intensity:
        return any(v > 0 for c, v in vals.items() if c in intensity)
    return any(v > 0 for v in vals.values())


# ═══════════════════════════════════════════════════════════════════════════════
# Fan-out engine
# ═══════════════════════════════════════════════════════════════════════════════

def compute_fanout(src_fixture_ids: list[str],
                   fixture_mapping: dict[str, list[str]],
                   mode: str = "pattern_repeat") -> dict[str, str]:
    """
    Compute which target fixture inherits from which source fixture.

    Parameters
    ----------
    src_fixture_ids : list[str]
        Source fixture IDs in the order they appear in the functions.
    fixture_mapping : dict
        src_id → [tgt_id, ...] — all target fixtures mapped to each source.
    mode : str
        "pattern_repeat" | "clone" | "block" | "manual"

    Returns
    -------
    dict: tgt_fixture_id → src_fixture_id
    """
    M = len(src_fixture_ids)
    if M == 0:
        return {}

    # Collect all unique target IDs across all source mappings, preserving order
    all_targets = []
    seen = set()
    for src_id in src_fixture_ids:
        for tgt_id in fixture_mapping.get(src_id, []):
            if tgt_id not in seen:
                all_targets.append(tgt_id)
                seen.add(tgt_id)

    N = len(all_targets)
    if N == 0:
        return {}

    result: dict[str, str] = {}

    if mode == "pattern_repeat":
        # Target fixture i inherits from source fixture (i % M)
        for i, tgt_id in enumerate(all_targets):
            result[tgt_id] = src_fixture_ids[i % M]

    elif mode == "clone":
        # Every target mapped to src_id gets src_id's values
        for src_id in src_fixture_ids:
            for tgt_id in fixture_mapping.get(src_id, []):
                result[tgt_id] = src_id

    elif mode == "block":
        # Contiguous blocks: first N/M targets → src[0], next N/M → src[1], etc.
        block_size = max(1, N // M)
        for i, tgt_id in enumerate(all_targets):
            src_idx = min(i // block_size, M - 1)
            result[tgt_id] = src_fixture_ids[src_idx]

    elif mode == "manual":
        # Manual mode: expect fixture_mapping to already be 1:1
        for src_id in src_fixture_ids:
            for tgt_id in fixture_mapping.get(src_id, []):
                result[tgt_id] = src_id

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Mirror helper
# ═══════════════════════════════════════════════════════════════════════════════

def mirror_pan_values(ch_values: str, pan_ch_index: int,
                      pan_fine_ch_index: int | None = None) -> str:
    """
    Invert Pan channel value(s) in a FixtureVal text string.

    FixtureVal text format: "ch_idx,value,ch_idx,value,..."

    For 16-bit: combine coarse+fine into 16-bit, invert against 65535,
    then re-split.  NOT byte-independent inversion.

    Returns the modified channel-value string.
    """
    parts = ch_values.split(",")
    # Build a mutable dict: ch_index → value
    pairs: dict[int, int] = {}
    for i in range(0, len(parts) - 1, 2):
        try:
            ch_idx = int(parts[i])
            val    = int(parts[i + 1])
            pairs[ch_idx] = val
        except (ValueError, IndexError):
            continue

    if pan_ch_index in pairs:
        if pan_fine_ch_index is not None and pan_fine_ch_index in pairs:
            # 16-bit inversion
            coarse = pairs[pan_ch_index]
            fine   = pairs[pan_fine_ch_index]
            combined = (coarse << 8) | fine
            inverted = 65535 - combined
            pairs[pan_ch_index]      = (inverted >> 8) & 0xFF
            pairs[pan_fine_ch_index] = inverted & 0xFF
        else:
            # 8-bit inversion
            pairs[pan_ch_index] = 255 - pairs[pan_ch_index]

    # Rebuild the string
    result_parts = []
    for ch_idx in sorted(pairs.keys()):
        result_parts.append(str(ch_idx))
        result_parts.append(str(pairs[ch_idx]))
    return ",".join(result_parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════════

def validate(plan: dict) -> dict:
    """
    Pre-flight validation of an import plan.

    Parameters
    ----------
    plan : dict with:
        closure          — result of resolve_closure()
        fixture_mapping  — src_id → [tgt_id, ...]
        fanout_mode      — "pattern_repeat" | "clone" | "block" | "manual" | "fan_in"
        drop_unmapped    — bool: leave out values of unmapped source fixtures
        complete_channels — bool (default True): declare every channel of
                           each target fixture (missing ones at neutral)
        qxf_paths        — extra .qxf files/folders (definitions)
        vc               — VC porting options (core.porter_vc.port_vc)
        mirror_fixtures  — list[str] of tgt fixture IDs to mirror
        pan_channel_map  — dict[src_fixture_id, {coarse: int, fine: int|None}]
                           (channel indices for Pan in each source fixture)

    Returns
    -------
    dict with:
        errors    list[str] — block export
        warnings  list[str] — informational
        info      list[str] — summary lines
        ok        bool      — True if no errors
    """
    errors:   list[str] = []
    warnings: list[str] = []
    info:     list[str] = []

    closure         = plan.get("closure", {})
    fixture_mapping = plan.get("fixture_mapping", {})
    fanout_mode     = plan.get("fanout_mode", "pattern_repeat")
    mirror_fixtures = set(plan.get("mirror_fixtures", []))
    drop_unmapped   = bool(plan.get("drop_unmapped", False))

    func_ids    = closure.get("function_ids", [])
    fix_ids     = closure.get("fixture_ids", [])
    cycles      = closure.get("cycles", [])
    unresolved  = closure.get("unresolved", [])
    seed_ids    = closure.get("seed_ids", [])

    src_infos = _fixture_infos(_src["root"]) if _src["loaded"] else {}
    tgt_infos = _fixture_infos(_tgt["root"]) if _tgt["loaded"] else {}

    def fx_label(infos, i):
        inf = infos.get(i)
        return f"{i} '{inf['name']}'" if inf else i

    # ── Errors ────────────────────────────────────────────────────────────
    if not func_ids:
        errors.append("No functions selected.")

    for fid in unresolved:
        errors.append(f"Function ID {fid} is referenced but not found in source file.")

    # Every source fixture needs a target, unless the user drops it
    unmapped = [s for s in fix_ids if not fixture_mapping.get(s)]
    if unmapped and not drop_unmapped:
        for src_id in unmapped:
            errors.append(
                f"Source fixture ID {src_id} has no target fixture assigned.")
    elif unmapped:
        warnings.append(
            f"{len(unmapped)} source fixture(s) have no target; their values are left out: "
            + ", ".join(fx_label(src_infos, s) for s in unmapped) + ".")

    for s, targets in fixture_mapping.items():
        for t in targets:
            if tgt_infos and t not in tgt_infos:
                errors.append(f"Target fixture ID {t} does not exist in the target.")

    order = stage_order(_src["root"], fix_ids) if _src["loaded"] else list(fix_ids)
    blocks = compute_blocks(order, fixture_mapping, fanout_mode)
    fanout = compute_fanout(fix_ids, fixture_mapping, fanout_mode) \
        if fanout_mode != "fan_in" else {t: b[0] for t, b in blocks.items()}

    # Double assignment (ambiguous values) — expected, and resolved, in fan-in
    if fanout_mode != "fan_in":
        tgt_to_src = defaultdict(set)
        for s in fix_ids:
            for t in fixture_mapping.get(s, []):
                tgt_to_src[t].add(s)
        for tgt_id, src_ids in sorted(tgt_to_src.items()):
            if len(src_ids) > 1 and fanout_mode in ("manual", "clone"):
                errors.append(
                    f"Target fixture {tgt_id} is assigned to multiple source "
                    f"fixtures ({', '.join(_id_sorted(src_ids))}) — values would conflict. "
                    f"Use the fan-in mode to merge several sources into one target.")

    # ── Warnings ──────────────────────────────────────────────────────────
    if cycles:
        for c in cycles:
            warnings.append(f"Reference cycle detected: {c}")

    for t, block in sorted(blocks.items(), key=lambda kv: _id_sorted([kv[0]])[0]):
        for s in block:
            si, ti = src_infos.get(s), tgt_infos.get(t)
            if si and ti and _type_key(si) != _type_key(ti):
                warnings.append(
                    f"Source fixture {fx_label(src_infos, s)} ({si['model']}, {si['mode']}) → "
                    f"target {fx_label(tgt_infos, t)} ({ti['model']}, {ti['mode']}): "
                    f"different fixture type, values are copied channel by channel.")

    # Check name collisions with target
    if _tgt["loaded"] and _src["loaded"]:
        tgt_engine = _engine(_tgt["root"])
        src_engine = _engine(_src["root"])
        if tgt_engine is not None and src_engine is not None:
            tgt_fn_names = {fn.get("Name", "") for fn in tgt_engine.findall("Function")}
            src_by_id = {fn.get("ID"): fn for fn in src_engine.findall("Function")}
            for fid in func_ids:
                fn = src_by_id.get(fid)
                if fn is not None and fn.get("Name", "") in tgt_fn_names:
                    warnings.append(
                        f'Function name "{fn.get("Name", "")}" already exists in target '
                        f'(will be prefixed).')

    # Version mismatch
    if _src["loaded"] and _tgt["loaded"]:
        src_ver = _make_summary(_src["root"]).get("creator_version", "")
        tgt_ver = _make_summary(_tgt["root"]).get("creator_version", "")
        if src_ver and tgt_ver and src_ver.split(".")[0] != tgt_ver.split(".")[0]:
            warnings.append(
                f"Source is QLC+ {src_ver}, target is QLC+ {tgt_ver}. "
                f"Palette and Sequence handling may differ.")

    # Mirror without Pan channel info
    if mirror_fixtures:
        pan_map = plan.get("pan_channel_map", {})
        for src_id in fix_ids:
            if src_id not in pan_map:
                warnings.append(
                    f"Mirror requested but Pan channel index not identified "
                    f"for source fixture {src_id}. Mirror will be skipped "
                    f"for those fixtures.")
                break

    # Unassigned target fixtures
    all_tgt_ids = set()
    for targets in fixture_mapping.values():
        all_tgt_ids.update(targets)
    assigned_tgt_ids = set(fanout.keys())
    unassigned = all_tgt_ids - assigned_tgt_ids
    if unassigned:
        warnings.append(
            f"{len(unassigned)} target fixture(s) left unassigned by "
            f"{fanout_mode} fan-out: IDs {', '.join(_id_sorted(unassigned))}.")

    # ── Info ──────────────────────────────────────────────────────────────
    n_seed = len(seed_ids)
    n_dep  = len(func_ids) - n_seed
    info.append(
        f"{n_seed} selected + {n_dep} dependencies = "
        f"{len(func_ids)} functions to import.")
    info.append(f"{len(assigned_tgt_ids)} target fixtures affected.")
    info.append(f"Fan-out mode: {fanout_mode}.")
    if fanout_mode == "fan_in":
        for t in _id_sorted(blocks):
            info.append(f"Target {fx_label(tgt_infos, t)} ← "
                        + ", ".join(fx_label(src_infos, s) for s in blocks[t]))

    return {
        "errors":   errors,
        "warnings": warnings,
        "info":     info,
        "ok":       len(errors) == 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Execute — the main import
# ═══════════════════════════════════════════════════════════════════════════════

class PorterBlocked(RuntimeError):
    """The port would add Doctor errors to the target; nothing is written."""

    def __init__(self, message: str, result: dict):
        super().__init__(message)
        self.result = result


def _load_defs(plan: dict) -> dict:
    """Fixture definitions for "lit" detection and Doctor: folders of the
    source and target files, plus ``plan["qxf_paths"]``."""
    from core.doctor import load_qxf_defs
    paths = list(plan.get("qxf_paths") or [])
    for side in (_src, _tgt):
        if side.get("path"):
            paths.append(os.path.dirname(os.path.abspath(side["path"])))
    defs = load_qxf_defs(dict.fromkeys(paths))
    try:                                  # stock definitions from the installed QLC+
        from core.quick_start import qlc_library
        extra = []
        for side in (_src, _tgt):
            if side.get("loaded"):
                for inf in _fixture_infos(side["root"]).values():
                    key = (inf["manufacturer"].strip().lower(), inf["model"].strip().lower())
                    if key not in defs:
                        f = qlc_library.find(inf["manufacturer"], inf["model"])
                        if f:
                            extra.append(f)
        if extra:
            for k, v in load_qxf_defs(dict.fromkeys(extra)).items():
                defs.setdefault(k, v)
    except Exception:  # noqa: BLE001 — definitions only improve the result
        pass
    return defs


def execute(plan: dict) -> tuple[str, bytes]:
    """
    Execute the import: copy functions from source into a deep copy of the
    target, rebasing IDs, remapping fixtures, applying fan-out/fan-in and
    mirror.  With ``plan["vc"]`` the Virtual Console widgets come too
    (see :mod:`core.porter_vc`).  No Doctor gate — use :func:`port`.

    Returns
    -------
    (suggested_filename, xml_bytes)
    """
    res = _build(plan)
    return res["filename"], res["bytes"]


def port(plan: dict) -> dict:
    """Validate, build, port the VC, run Doctor and write the report text.

    Doctor gates the result: errors that the target did not already have
    raise :class:`PorterBlocked` (its ``result`` carries the report).

    Returns dict: ``filename``, ``bytes``, ``report`` (text), ``doctor``
    (``errors``/``warnings`` lists of new findings, ``ok``), ``pruned``,
    ``groups``, ``vc`` (VC port summary or None), ``validation``.
    """
    validation = validate(plan)
    if not validation["ok"]:
        raise PorterBlocked("Validation failed.", {"validation": validation})
    res = _build(plan)
    res["validation"] = validation

    from core.doctor import check
    defs = res.pop("_defs")
    before = check(_tgt["root"], list(defs.values()))
    after = check(qxw_io.loads_qxw(res["bytes"]), list(defs.values()))

    def key(f):
        return (f.code, f.location, f.message)
    old = {key(f) for f in before.findings}
    new = [f for f in after.findings if key(f) not in old and f.severity != "info"]
    res["doctor"] = {
        "errors": [f"{f.code} {f.location}: {f.message}" for f in new if f.severity == "error"],
        "warnings": [f"{f.code} {f.location}: {f.message}" for f in new if f.severity == "warning"],
        "total_errors": len(after.errors), "total_warnings": len(after.warnings),
    }
    res["doctor"]["ok"] = not res["doctor"]["errors"]
    res["report"] = generate_report(plan, validation, res)
    if not res["doctor"]["ok"]:
        raise PorterBlocked("Doctor found new errors in the result; not exported.", res)
    return res


def _build(plan: dict) -> dict:
    if not _src["loaded"] or not _tgt["loaded"]:
        raise RuntimeError("Both source and target must be loaded.")

    closure         = plan["closure"]
    fixture_mapping = plan["fixture_mapping"]
    fanout_mode     = plan.get("fanout_mode", "pattern_repeat")
    mirror_fixtures = set(plan.get("mirror_fixtures", []))
    pan_channel_map = plan.get("pan_channel_map", {})
    name_prefix     = plan.get("name_prefix", "")
    import_path     = plan.get("import_path", "")  # QLC+ Path for grouping

    func_ids = closure["function_ids"]
    fix_ids  = closure["fixture_ids"]

    src_root   = _src["root"]
    src_engine = _engine(src_root)
    tgt_root   = copy.deepcopy(_tgt["root"])
    tgt_engine = _engine(tgt_root)

    defs = _load_defs(plan)
    intensity = _intensity_channels(_fixture_infos(src_root), defs)
    neutral = (_neutral_maps(_fixture_infos(_tgt["root"]), defs)
               if plan.get("complete_channels", True) else {})

    # ── 1. Who feeds which target ─────────────────────────────────────────
    order = stage_order(src_root, fix_ids)
    blocks = compute_blocks(order, fixture_mapping, fanout_mode)

    # ── 2. Allocate new function IDs in the target (max + 1) ──────────────
    max_id = _max_id_in(tgt_root)
    func_id_map: dict[str, str] = {}  # src_func_id → new_tgt_func_id
    for fid in func_ids:
        max_id += 1
        func_id_map[fid] = str(max_id)

    tgt_fn_names = {fn.get("Name", "") for fn in tgt_engine.findall("Function")}
    src_func_by_id = {fn.get("ID", ""): fn for fn in src_engine.findall("Function")}
    src_groups = {g.get("ID", ""): g for g in src_engine.findall("FixtureGroup")}

    # ── 3. Copy and transform each function ───────────────────────────────
    new_fns: dict[str, ET.Element] = {}
    pruned: list[dict] = []
    group_map: dict[str, str | None] = {}
    new_groups: list[ET.Element] = []
    for src_fid in func_ids:
        src_fn = src_func_by_id.get(src_fid)
        if src_fn is None:
            continue
        new_fn = copy.deepcopy(src_fn)
        new_fn.set("ID", func_id_map[src_fid])

        name = new_fn.get("Name", "")
        if name_prefix:
            name = f"{name_prefix}{name}"
            new_fn.set("Name", name)
        if name in tgt_fn_names:
            name = f"[imported] {name}"
            new_fn.set("Name", name)
        tgt_fn_names.add(name)
        if import_path:
            new_fn.set("Path", import_path)

        _remap_func_refs(new_fn, func_id_map)
        before, after = _remap_fixture_refs(new_fn, blocks, mirror_fixtures,
                                            pan_channel_map, intensity, neutral)
        if new_fn.get("Type") == "RGBMatrix":
            gid = (new_fn.findtext("FixtureGroup") or "").strip()
            if gid not in group_map:
                group_map[gid] = _port_group(src_groups.get(gid), tgt_engine, blocks,
                                             new_groups)
            new_gid = group_map[gid]
            if new_gid is None:
                pruned.append({"id": src_fid, "name": src_fn.get("Name", ""),
                               "reason": "no fixture of its matrix group is ported"})
            else:
                new_fn.find("FixtureGroup").text = new_gid
        elif before and not after:
            pruned.append({"id": src_fid, "name": src_fn.get("Name", ""),
                           "reason": "none of its fixtures is ported"})
        new_fns[src_fid] = new_fn

    # ── 4. Cascade: drop steps / commands that use removed functions ──────
    pruned += _cascade_prune(new_fns, func_id_map, {p["id"] for p in pruned})
    removed = {p["id"] for p in pruned}

    # ── 5. Insert groups (after fixtures/groups) and functions ────────────
    _insert_groups(tgt_engine, new_groups)
    for src_fid, el in new_fns.items():
        if src_fid not in removed:
            tgt_engine.append(el)
    kept_map = {s: n for s, n in func_id_map.items() if s in new_fns and s not in removed}
    panic = []
    if plan.get("extend_panic", True):
        panic = _extend_panic_reset(tgt_engine, [kept_map[s] for s in func_ids if s in kept_map])

    # ── 6. Virtual Console ────────────────────────────────────────────────
    vc_result = None
    vc_opts = plan.get("vc") or {}
    removed_vc: list[str] = []
    if vc_opts.get("remove"):
        # Target items the user chose to drop — before placement, so their
        # space is reused.  Keys index the target as loaded (same order).
        from core import porter_vc
        removed_vc = porter_vc.remove_widgets(tgt_root, vc_opts["remove"])
    if vc_opts.get("enabled"):
        from core import porter_vc
        vc_result = porter_vc.port_vc(src_root, tgt_root, kept_map, blocks, vc_opts,
                                      src_name=_src["name"] or "source")

    # ── 7. Serialize (indented like QLC+'s own files) ─────────────────────
    ET.indent(tgt_root, space=" ")
    xml_bytes = qxw_io.qxw_bytes(tgt_root)
    name = _tgt["name"] or "workspace"
    return {
        "filename": qxw_io.next_version_name(f"{name}.qxw"),
        "bytes": xml_bytes,
        "func_id_map": kept_map,
        "blocks": blocks,
        "pruned": pruned,
        "groups": [{"id": g.get("ID"), "name": g.findtext("Name", "")} for g in new_groups],
        "vc": vc_result,
        "panic": panic,
        "removed_vc": removed_vc,
        "_defs": defs,
    }


def _max_id_in(root: ET.Element) -> int:
    """Highest function ID in the Engine block (new IDs start above it)."""
    engine = _engine(root)
    if engine is None:
        return 0
    ids = [int(f.get("ID")) for f in engine.findall("Function")
           if (f.get("ID") or "").isdigit()]
    return max(ids, default=-1)


def _cascade_prune(new_fns: dict[str, ET.Element], id_map: dict[str, str],
                   removed_src: set[str]) -> list[dict]:
    """Remove steps and script commands that point at removed functions;
    functions left with no step are removed too (repeated to a fixed point)."""
    out: list[dict] = []
    removed = set(removed_src)
    changed = True
    while changed:
        changed = False
        gone = {id_map[s] for s in removed if s in id_map}
        for sfid, el in new_fns.items():
            if sfid in removed:
                continue
            steps = el.findall("Step")
            dead = [st for st in steps if (st.text or "").strip() in gone]
            for st in dead:
                el.remove(st)
            if dead:
                for n, st in enumerate(el.findall("Step")):
                    if st.get("Number") is not None:
                        st.set("Number", str(n))
            for cmd in el.findall("Command"):
                ids = {m.group(2) for m in _SCRIPT_FUNC_RE.finditer(unquote(cmd.text or ""))}
                if ids & gone:
                    el.remove(cmd)
            reason = ""
            if steps and not el.findall("Step"):
                reason = "all its steps use functions that were removed"
            if (el.get("BoundScene") or "") in gone:
                reason = "its bound scene was removed"
            if reason:
                removed.add(sfid)
                out.append({"id": sfid, "name": el.get("Name", ""), "reason": reason})
                changed = True
    return out


_PANIC_RE = re.compile(r"panic\s*reset", re.IGNORECASE)


def _extend_panic_reset(engine: ET.Element, new_ids: list[str]) -> list[str]:
    """Make the target's PANIC RESET script stop the ported functions too.

    A Quick Start PANIC RESET is a Script that stops every function it knows
    and then starts the neutral scene; ported functions are unknown to it, so
    a ported look would survive the reset.  The stop commands are inserted
    before the first ``startfunction`` (same encoding as the script uses).
    Returns the names of the scripts changed."""
    changed = []
    for fn in engine.findall("Function"):
        if fn.get("Type") != "Script" or not _PANIC_RE.search(fn.get("Name", "")):
            continue
        cmds = fn.findall("Command")
        start = next((c for c in cmds if re.match(r"\s*startfunction", unquote(c.text or ""))), None)
        if start is None or not new_ids:
            continue
        sep = "%3A" if "%3A" in (start.text or "") else ":"
        have = {m.group(2) for c in cmds for m in _SCRIPT_FUNC_RE.finditer(c.text or "")}
        pos = list(fn).index(start)
        added = 0
        for fid in new_ids:
            if fid in have:
                continue
            cmd = ET.Element("Command")
            cmd.text = f"stopfunction{sep}{fid}"
            fn.insert(pos + added, cmd)
            added += 1
        if added:
            changed.append(f"{fn.get('Name', '')} ({added} stop commands added)")
    return changed


def _insert_groups(engine: ET.Element, groups: list[ET.Element]) -> None:
    if not groups:
        return
    last = -1
    for i, c in enumerate(list(engine)):
        if c.tag in ("Fixture", "FixtureGroup"):
            last = i
    for n, g in enumerate(groups):
        engine.insert(last + 1 + n, g)


def _port_group(src_group: ET.Element | None, tgt_engine: ET.Element,
                blocks: dict[str, list[str]], new_groups: list[ET.Element]) -> str | None:
    """Build (or reuse) the target fixture group for an RGB matrix.

    Each target takes the grid cell of the first source in its block that
    is in the group; empty rows/columns are closed up.  An existing target
    group with exactly the same heads is reused.  Returns the group ID, or
    None when no fixture of the group is ported.
    """
    if src_group is None:
        return None
    heads = defaultdict(list)                  # src fixture → [(x, y, head)]
    for h in src_group.findall("Head"):
        try:
            heads[h.get("Fixture", "")].append((int(h.get("X", 0)), int(h.get("Y", 0)),
                                                (h.text or "0").strip()))
        except ValueError:
            continue
    placed = []
    for t in _id_sorted(blocks):
        rep = next((s for s in blocks[t] if s in heads), None)
        if rep is not None:
            for x, y, head in heads[rep]:
                placed.append((x, y, t, head))
    if not placed:
        return None
    xs = {x: i for i, x in enumerate(sorted({p[0] for p in placed}))}
    ys = {y: i for i, y in enumerate(sorted({p[1] for p in placed}))}
    cells = sorted(((ys[y], xs[x], t, head) for x, y, t, head in placed))
    wanted = {(t, head) for _, _, t, head in cells}

    existing = tgt_engine.findall("FixtureGroup") + new_groups
    for g in existing:
        have = {(h.get("Fixture", ""), (h.text or "0").strip()) for h in g.findall("Head")}
        if have == wanted:
            return g.get("ID")
    gid = str(max([int(g.get("ID")) for g in existing if (g.get("ID") or "").isdigit()],
                  default=-1) + 1)
    names = {g.findtext("Name", "") for g in existing}
    name = src_group.findtext("Name", "") or f"Group {gid}"
    if name in names:
        name = f"{name} (ported)"
    g = ET.Element("FixtureGroup", {"ID": gid})
    ET.SubElement(g, "Name").text = name
    ET.SubElement(g, "Size", {"X": str(len(xs)), "Y": str(len(ys))})
    seen = set()
    for y, x, t, head in cells:
        if (x, y) in seen:
            continue
        seen.add((x, y))
        ET.SubElement(g, "Head", {"X": str(x), "Y": str(y), "Fixture": t}).text = head
    new_groups.append(g)
    return gid


def _remap_func_refs(fn_el: ET.Element, id_map: dict[str, str]):
    """Rewrite all function ID references within a function element."""
    # BoundScene attribute
    bound = fn_el.get("BoundScene", "")
    if bound in id_map:
        fn_el.set("BoundScene", id_map[bound])

    for child in fn_el:
        tag = child.tag

        # Step text (Chaser, Collection)
        if tag == "Step":
            text = (child.text or "").strip()
            if text in id_map:
                child.text = id_map[text]

        # Show tracks
        if tag == "Track":
            scene_id = child.get("SceneID", "")
            if scene_id in id_map:
                child.set("SceneID", id_map[scene_id])
            for sf in child.findall("ShowFunction"):
                sf_id = sf.get("ID", "")
                if sf_id in id_map:
                    sf.set("ID", id_map[sf_id])

        # Script commands
        if tag == "Command" and child.text:
            child.text = _SCRIPT_FUNC_RE.sub(
                lambda m: (m.group(1) + id_map[m.group(2)]
                           if m.group(2) in id_map else m.group(0)),
                child.text)

        # Generic attribute refs
        for attr in _FUNC_REF_ATTRS:
            val = child.get(attr, "")
            if val in id_map:
                child.set(attr, id_map[val])

        # Recurse into grandchildren (e.g. ShowFunction inside Track)
        _remap_func_refs(child, id_map)


def _remap_fixture_refs(fn_el: ET.Element,
                        blocks: dict[str, list[str]],
                        mirror_fixtures: set[str],
                        pan_channel_map: dict,
                        intensity: dict[str, set] | None = None,
                        neutral: dict[str, dict[int, int]] | None = None) -> tuple[int, int]:
    """
    Remap fixture IDs in a Scene (``FixtureVal``) or EFX (``Fixture``).

    Each target gets the values of one source of its block: the first one
    that is lit in this scene, else the first one the scene declares.
    Values of sources that feed no target are left out.  Output order
    follows the source order.  With *neutral* (target fixture → neutral
    values) scene values are completed so every channel is declared
    (no LTP bleed, WORKPLAN principle 5).

    Returns ``(fixtures before, fixtures after)``.
    """
    intensity = intensity or {}
    fn_type = fn_el.get("Type", "")

    if fn_type in ("Scene", "Sequence"):
        old = fn_el.findall("FixtureVal")
    elif fn_type == "EFX":
        old = _efx_fixtures(fn_el)
    else:
        return 0, 0
    if not old:
        return 0, 0

    def src_of(el):
        if fn_type == "EFX":
            return (el.findtext("ID") or "").strip()
        return el.get("ID", "")

    by_src = {}
    for el in old:
        by_src.setdefault(src_of(el), el)

    feeds: dict[str, list[str]] = defaultdict(list)   # rep src → [targets]
    for t in _id_sorted(blocks):
        declared = [s for s in blocks[t] if s in by_src]
        if not declared:
            continue
        rep = declared[0]
        if fn_type != "EFX":
            rep = next((s for s in declared
                        if _is_lit(by_src[s].text, intensity.get(s))), declared[0])
        feeds[rep].append(t)

    # position of the first old element, so the new ones land in the same place
    first = list(fn_el).index(old[0])
    for el in old:
        fn_el.remove(el)
    new = []
    done = set()
    for el in old:
        s = src_of(el)
        if s in done:
            continue
        done.add(s)
        for t in feeds.get(s, []):
            dup = copy.deepcopy(el)
            if fn_type == "EFX":
                dup.find("ID").text = t
            else:
                dup.set("ID", t)
                if t in mirror_fixtures and s in pan_channel_map and (dup.text or "").strip():
                    pan = pan_channel_map[s]
                    dup.text = mirror_pan_values(dup.text.strip(), pan["coarse"], pan.get("fine"))
                if neutral and t in neutral and fn_type == "Scene":
                    dup.text = _complete(dup.text or "", neutral[t])
            new.append(dup)
    for n, el in enumerate(new):
        fn_el.insert(first + n, el)
    return len(by_src), len(new)


# ═══════════════════════════════════════════════════════════════════════════════
# Generate import report (plain text, saved next to the output file)
# ═══════════════════════════════════════════════════════════════════════════════

def report_path(qxw_path: str) -> str:
    """``show_v2.qxw`` → ``show_v2_port_report.txt`` (same folder)."""
    stem, _ = os.path.splitext(qxw_path)
    return f"{stem}_port_report.txt"


def generate_report(plan: dict, validation: dict, result: dict | None = None) -> str:
    """Plain-text import report.  With *result* (from :func:`port`) it also
    lists the fixture blocks, removed functions, VC widgets and Doctor."""
    lines = [
        "═══ Function Porter — Import Report ═══",
        "",
        f"Source:  {_src['name']}",
        f"Target:  {_tgt['name']}",
    ]
    if result and result.get("filename"):
        lines.append(f"Output:  {result['filename']}")
    lines.append("")

    closure = plan.get("closure", {})
    seed_ids = closure.get("seed_ids", [])
    func_ids = closure.get("function_ids", [])
    fix_ids  = closure.get("fixture_ids", [])

    lines.append(f"Selected: {len(seed_ids)} function(s)")
    lines.append(f"Dependencies pulled in: {len(func_ids) - len(seed_ids)}")
    lines.append(f"Total functions: {len(func_ids)}")
    lines.append(f"Source fixtures referenced: {len(fix_ids)}")
    lines.append(f"Fan-out mode: {plan.get('fanout_mode', 'pattern_repeat')}")
    lines.append("")

    if validation.get("errors"):
        lines.append("── ERRORS (blocking) ──")
        for e in validation["errors"]:
            lines.append(f"  ✗ {e}")
        lines.append("")

    if validation.get("warnings"):
        lines.append("── WARNINGS ──")
        for w in validation["warnings"]:
            lines.append(f"  ⚠ {w}")
        lines.append("")

    if validation.get("info"):
        lines.append("── SUMMARY ──")
        for i in validation["info"]:
            lines.append(f"  • {i}")
        lines.append("")

    if result:
        fmap = result.get("func_id_map", {})
        lines.append(f"── FUNCTIONS ({len(fmap)} ported) ──")
        src_fn = {fn.get("ID"): fn for fn in _engine(_src["root"]).findall("Function")}
        for s, n in fmap.items():
            fn = src_fn.get(s)
            lines.append(f"  {s:>5} → {n:<5} {fn.get('Type', '') if fn is not None else ''}"
                         f"  {fn.get('Name', '') if fn is not None else ''}")
        lines.append("")
        if result.get("pruned"):
            lines.append(f"── REMOVED FROM THE PORT ({len(result['pruned'])}) ──")
            for p in result["pruned"]:
                lines.append(f"  - {p['id']} '{p['name']}': {p['reason']}")
            lines.append("")
        if result.get("panic"):
            lines.append("── PANIC RESET ──")
            for p in result["panic"]:
                lines.append(f"  • {p}: it now stops the ported functions too")
            lines.append("")
        if result.get("groups"):
            lines.append("── FIXTURE GROUPS CREATED ──")
            for g in result["groups"]:
                lines.append(f"  + {g['id']} '{g['name']}'")
            lines.append("")
        if result.get("removed_vc"):
            lines.append(f"── REMOVED FROM THE TARGET VC ({len(result['removed_vc'])}) ──")
            for r in result["removed_vc"]:
                lines.append(f"  - {r}")
            lines.append("")
        vc = result.get("vc")
        if vc:
            lines.append("── VIRTUAL CONSOLE ──")
            for ln in vc.get("summary", []):
                lines.append(f"  • {ln}")
            for d in vc.get("dropped", []):
                lines.append(f"  - dropped {d}")
            lines.append("")
        doc = result.get("doctor")
        if doc:
            lines.append("── DOCTOR (new findings only) ──")
            lines.append(f"  {len(doc['errors'])} new error(s), {len(doc['warnings'])} new warning(s); "
                         f"file total: {doc['total_errors']} error(s), "
                         f"{doc['total_warnings']} warning(s)")
            for e in doc["errors"]:
                lines.append(f"  ✗ {e}")
            for w in doc["warnings"][:50]:
                lines.append(f"  ⚠ {w}")
            if len(doc["warnings"]) > 50:
                lines.append(f"  … {len(doc['warnings']) - 50} more warnings")
            lines.append("")

    lines.append("═══════════════════════════════════════")
    return "\n".join(lines) + "\n"
