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
build_fixture_map(src_fixtures, tgt_fixtures)  → compatibility info
validate(plan)              → ValidationResult dict
execute(plan)               → bytes (new QXW)
clear()
"""

from __future__ import annotations

import copy
import os
import re
from collections import defaultdict
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
_SCRIPT_FUNC_RE = re.compile(r'(?:start|stop)function:(\d+)')


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

    # Ordered: seeds first, then dependencies
    ordered = []
    seen = set()
    for fid in seed_ids:
        if fid in visited and fid not in seen:
            ordered.append(fid)
            seen.add(fid)
    for fid in visited:
        if fid not in seen:
            ordered.append(fid)
            seen.add(fid)

    all_fixture_ids = set()
    for fids in fixture_refs.values():
        all_fixture_ids.update(fids)

    return {
        "function_ids": ordered,
        "fixture_ids":  sorted(all_fixture_ids),
        "dep_map":      dict(dep_map),
        "fixture_map":  {k: sorted(v) for k, v in fixture_refs.items()},
        "cycles":       cycles,
        "unresolved":   unresolved,
        "seed_ids":     list(seed_ids),
    }


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

    # ── EFX fixtures ──────────────────────────────────────────────────────
    for efx_fix in fn_el.findall("EFXFixture"):
        eid = efx_fix.findtext("ID", "")
        if eid and eid.isdigit():
            fix_ids.add(eid)

    # ── Script commands ───────────────────────────────────────────────────
    if fn_type == "Script":
        for cmd in fn_el.findall("Command"):
            text = cmd.text or ""
            for m in _SCRIPT_FUNC_RE.finditer(text):
                func_ids.append(m.group(1))

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


def auto_map(closure_fixture_ids: list[str]) -> dict:
    """
    Auto-generate a fixture mapping: each source fixture → all tier-1
    target fixtures of the same model+mode.

    Returns dict: src_fixture_id → [tgt_fixture_id, ...]
    """
    info = build_fixture_candidates(closure_fixture_ids)
    mapping = {}
    for src_id, cands in info["candidates"].items():
        mapping[src_id] = [t["id"] for t in cands["tier1"]]
    return mapping


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
        fanout_mode      — str
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

    func_ids    = closure.get("function_ids", [])
    fix_ids     = closure.get("fixture_ids", [])
    cycles      = closure.get("cycles", [])
    unresolved  = closure.get("unresolved", [])
    seed_ids    = closure.get("seed_ids", [])

    # ── Errors ────────────────────────────────────────────────────────────
    if not func_ids:
        errors.append("No functions selected.")

    for fid in unresolved:
        errors.append(f"Function ID {fid} is referenced but not found in source file.")

    # Check that every source fixture has at least one target
    for src_id in fix_ids:
        targets = fixture_mapping.get(src_id, [])
        if not targets:
            errors.append(
                f"Source fixture ID {src_id} has no target fixture assigned.")

    # Check for double-assignment within the same function (ambiguous values)
    fanout = compute_fanout(
        fix_ids, fixture_mapping, fanout_mode)
    tgt_to_src = defaultdict(set)
    for tgt_id, src_id in fanout.items():
        tgt_to_src[tgt_id].add(src_id)
    for tgt_id, src_ids in tgt_to_src.items():
        if len(src_ids) > 1:
            errors.append(
                f"Target fixture {tgt_id} is assigned to multiple source "
                f"fixtures ({', '.join(sorted(src_ids))}) — values would conflict.")

    # ── Warnings ──────────────────────────────────────────────────────────
    if cycles:
        for c in cycles:
            warnings.append(f"Reference cycle detected: {c}")

    # Check name collisions with target
    if _tgt["loaded"]:
        tgt_engine = _engine(_tgt["root"])
        if tgt_engine is not None:
            tgt_fn_names = {fn.get("Name", "") for fn in tgt_engine.findall("Function")}
            src_engine = _engine(_src["root"])
            if src_engine is not None:
                for fid in func_ids:
                    for fn in src_engine.findall("Function"):
                        if fn.get("ID") == fid:
                            name = fn.get("Name", "")
                            if name in tgt_fn_names:
                                warnings.append(
                                    f'Function name "{name}" already exists in target '
                                    f'(will be prefixed).')
                            break

    # Version mismatch
    src_summary = _make_summary(_src["root"])
    tgt_summary = _make_summary(_tgt["root"])
    src_ver = src_summary.get("creator_version", "")
    tgt_ver = tgt_summary.get("creator_version", "")
    if src_ver and tgt_ver:
        src_major = src_ver.split(".")[0] if src_ver else ""
        tgt_major = tgt_ver.split(".")[0] if tgt_ver else ""
        if src_major != tgt_major:
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
            f"{fanout_mode} fan-out: IDs {', '.join(sorted(unassigned))}.")

    # ── Info ──────────────────────────────────────────────────────────────
    n_seed = len(seed_ids)
    n_dep  = len(func_ids) - n_seed
    n_tgt_fix = len(assigned_tgt_ids)
    info.append(
        f"{n_seed} selected + {n_dep} dependencies = "
        f"{len(func_ids)} functions to import.")
    info.append(f"{n_tgt_fix} target fixtures affected.")
    info.append(f"Fan-out mode: {fanout_mode}.")

    return {
        "errors":   errors,
        "warnings": warnings,
        "info":     info,
        "ok":       len(errors) == 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Execute — the main import
# ═══════════════════════════════════════════════════════════════════════════════

def execute(plan: dict) -> tuple[str, bytes]:
    """
    Execute the import: copy functions from source into a deep copy of the
    target, rebasing IDs, remapping fixtures, applying fan-out and mirror.

    Parameters
    ----------
    plan : dict (same shape as validate())

    Returns
    -------
    (suggested_filename, xml_bytes)
    """
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

    src_engine = _engine(_src["root"])
    tgt_root   = copy.deepcopy(_tgt["root"])
    tgt_engine = _engine(tgt_root)

    # ── 1. Compute fan-out assignment ─────────────────────────────────────
    fanout = compute_fanout(fix_ids, fixture_mapping, fanout_mode)
    # fanout: tgt_fixture_id → src_fixture_id

    # Invert: src_fixture_id → [tgt_fixture_id, ...]
    src_to_tgt: dict[str, list[str]] = defaultdict(list)
    for tgt_id, src_id in fanout.items():
        src_to_tgt[src_id].append(tgt_id)

    # ── 2. Allocate new function IDs in the target ────────────────────────
    max_id = _max_id_in(tgt_root)
    func_id_map: dict[str, str] = {}  # src_func_id → new_tgt_func_id
    for fid in func_ids:
        max_id += 1
        func_id_map[fid] = str(max_id)

    # ── 3. Build name conflict set ────────────────────────────────────────
    tgt_fn_names = {fn.get("Name", "") for fn in tgt_engine.findall("Function")}

    # ── 4. Index source functions ─────────────────────────────────────────
    src_func_by_id: dict[str, ET.Element] = {}
    for fn in src_engine.findall("Function"):
        src_func_by_id[fn.get("ID", "")] = fn

    # ── 5. Copy and transform each function ───────────────────────────────
    for src_fid in func_ids:
        src_fn = src_func_by_id.get(src_fid)
        if src_fn is None:
            continue

        new_fn = copy.deepcopy(src_fn)

        # Set new ID
        new_fn.set("ID", func_id_map[src_fid])

        # Prefix name if collision
        name = new_fn.get("Name", "")
        if name_prefix:
            name = f"{name_prefix}{name}"
            new_fn.set("Name", name)
        if name in tgt_fn_names:
            name = f"[imported] {name}"
            new_fn.set("Name", name)
        tgt_fn_names.add(name)

        # Set Path for QLC+ folder grouping
        if import_path:
            new_fn.set("Path", import_path)

        # Remap function ID references within (Step text, BoundScene, etc.)
        _remap_func_refs(new_fn, func_id_map)

        # Remap fixture references (fan-out)
        _remap_fixture_refs(new_fn, src_to_tgt, mirror_fixtures,
                            pan_channel_map)

        tgt_engine.append(new_fn)

    # ── 6. Serialize ──────────────────────────────────────────────────────
    xml_bytes = qxw_io.qxw_bytes(tgt_root)

    name = _tgt["name"] or "workspace"
    suggested = qxw_io.next_version_name(f"{name}.qxw")

    return suggested, xml_bytes


def _max_id_in(root: ET.Element) -> int:
    """Find the highest numeric ID used in the Engine block."""
    engine = _engine(root)
    if engine is None:
        return 0
    hi = 0
    for el in engine.iter():
        for attr in ("ID",):
            val = el.get(attr, "")
            if val.isdigit():
                hi = max(hi, int(val))
        # Also check text content that might be an ID
        if el.text and el.text.strip().isdigit():
            hi = max(hi, int(el.text.strip()))
    return hi


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
                lambda m: (m.group(0).split(":")[0] + ":" + id_map[m.group(1)]
                           if m.group(1) in id_map else m.group(0)),
                child.text)

        # Generic attribute refs
        for attr in _FUNC_REF_ATTRS:
            val = child.get(attr, "")
            if val in id_map:
                child.set(attr, id_map[val])

        # Recurse into grandchildren (e.g. ShowFunction inside Track)
        _remap_func_refs(child, id_map)


def _remap_fixture_refs(fn_el: ET.Element,
                        src_to_tgt: dict[str, list[str]],
                        mirror_fixtures: set[str],
                        pan_channel_map: dict):
    """
    Remap fixture IDs in function elements, applying fan-out.

    For Scene FixtureVal: duplicate the block for each target fixture.
    For EFXFixture: duplicate for each target.
    """
    fn_type = fn_el.get("Type", "")

    # ── Scene / Sequence FixtureVal ───────────────────────────────────────
    if fn_type in ("Scene", "Sequence"):
        old_fvals = fn_el.findall("FixtureVal")
        for fv in old_fvals:
            fn_el.remove(fv)

        for fv in old_fvals:
            src_fix_id = fv.get("ID", "")
            tgt_ids = src_to_tgt.get(src_fix_id, [])

            if not tgt_ids:
                # Fixture not in mapping — keep as-is (it might be a target
                # fixture that was already in both files)
                fn_el.append(fv)
                continue

            for tgt_id in tgt_ids:
                new_fv = copy.deepcopy(fv)
                new_fv.set("ID", tgt_id)

                # Apply mirror if this target is flagged
                if tgt_id in mirror_fixtures and src_fix_id in pan_channel_map:
                    pan_info = pan_channel_map[src_fix_id]
                    val_text = new_fv.text or ""
                    if val_text.strip():
                        new_fv.text = mirror_pan_values(
                            val_text.strip(),
                            pan_info["coarse"],
                            pan_info.get("fine"),
                        )

                fn_el.append(new_fv)

    # ── EFX ───────────────────────────────────────────────────────────────
    elif fn_type == "EFX":
        old_efx_fixes = fn_el.findall("EFXFixture")
        for ef in old_efx_fixes:
            fn_el.remove(ef)

        for ef in old_efx_fixes:
            id_el = ef.find("ID")
            src_fix_id = (id_el.text or "").strip() if id_el is not None else ""
            tgt_ids = src_to_tgt.get(src_fix_id, [])

            if not tgt_ids:
                fn_el.append(ef)
                continue

            for tgt_id in tgt_ids:
                new_ef = copy.deepcopy(ef)
                new_id_el = new_ef.find("ID")
                if new_id_el is not None:
                    new_id_el.text = tgt_id
                fn_el.append(new_ef)

    # ── Recurse into children for nested refs ─────────────────────────────
    for child in fn_el:
        if child.tag in ("Track",):
            _remap_fixture_refs(child, src_to_tgt, mirror_fixtures,
                                pan_channel_map)


# ═══════════════════════════════════════════════════════════════════════════════
# Generate import report (plain text, for forum/clipboard)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_report(plan: dict, validation: dict) -> str:
    """Generate a plain-text import report."""
    lines = [
        "═══ Function Porter — Import Report ═══",
        "",
        f"Source:  {_src['name']}  ({_src['path']})",
        f"Target:  {_tgt['name']}  ({_tgt['path']})",
        "",
    ]

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

    lines.append("═══════════════════════════════════════")
    return "\n".join(lines)
