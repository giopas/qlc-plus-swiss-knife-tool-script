"""
core/showbook.py — Show Book document generator
=================================================
Reads the loaded workspace (via core.workspace) and QXF fixture
definitions (via core.fixture / core.qxf_parser) to produce structured
show documentation: patch lists, function details with decoded DMX
values, chaser timings, VC layout, and summary statistics.

Pure data module — no Flask, no UI.  Returns Python dicts/lists that
routes and exporters consume.

Public API
----------
generate(sections, qxf_dir=None)  → document dict
export_csv(document)              → bytes (ZIP)
export_pdf(document)              → bytes (PDF)
"""

from __future__ import annotations

import copy
import csv
import datetime
import io
import os
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from typing import Optional

from core import workspace
from core import fixture as fixture_mod
from core.qxf_parser import parse_qxf, decode_value

# ── Constants ─────────────────────────────────────────────────────────────────

QLC_NS_URI = workspace.QLC_NS_URI
NS = workspace.NS

ALL_SECTIONS = [
    "rider",
    "stage_plan",
    "checklist",
    "summary",
    "patch",
    "functions",
    "scenes",
    "chasers",
    "collections",
    "efx",
    "shows",
    "scripts",
    "vc_layout",
    "doctor",
]

# ── Show Paperwork (WORKPLAN 2.6): presets by reader ────────────────────────
# The Show Book, the Checklist and the Tech Rider are one tool now; what
# differs is who reads the paper.
PRESETS = {
    "rider":     {"label": "Tech rider", "reader": "for the venue",
                  "title": "Tech Rider", "sections": ["rider", "stage_plan"]},
    "checklist": {"label": "Crew checklist", "reader": "for load-in",
                  "title": "Crew Checklist", "sections": ["checklist", "stage_plan"]},
    "operator":  {"label": "Operator show book", "reader": "for you at the desk",
                  "title": "Show Book",
                  "sections": ["summary", "patch", "functions", "scenes", "chasers",
                               "collections", "efx", "shows", "scripts", "vc_layout",
                               "doctor"]},
}
# What may leave your hands: a document made only of the venue / crew presets
# never carries function names, key / MIDI maps, the Virtual Console or the
# Doctor — a rule, not a tick box.
VENUE_SAFE = {"rider", "stage_plan", "checklist", "patch"}


def resolve_sections(presets: list[str] | None, sections: list[str] | None) -> tuple[list[str], str]:
    """Sections to build and the document title.  *sections* (what is ticked)
    wins over the presets' own lists; with only venue presets (rider, crew
    checklist) only VENUE_SAFE sections are ever built."""
    presets = [p for p in (presets or []) if p in PRESETS]
    from_presets = [x for p in presets for x in PRESETS[p]["sections"]]
    chosen = [x for x in (sections or []) if x in ALL_SECTIONS] or from_presets \
        or list(PRESETS["operator"]["sections"])
    if presets and all(p in ("rider", "checklist") for p in presets):
        chosen = [x for x in chosen if x in VENUE_SAFE] or from_presets
    order = [x for x in ALL_SECTIONS if x in set(chosen)]
    title = " + ".join(PRESETS[p]["title"] for p in presets) if presets else "Show Paperwork"
    return order, title


# Buttons without a function
_ACTION_LABELS = {"StopAll": "(stop all functions)", "Blackout": "(blackout)"}

# Binding-slot names shown in the VC layout (CueList / Frame sub-controls)
_SLOT_LABELS = {"Next": "Next", "Previous": "Prev", "Stop": "Stop", "Playback": "Play",
                "CrossFade": "Xfade", "Enable": "Enable", "NextPage": "Next page",
                "PreviousPage": "Prev page"}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate(sections: list[str] | None = None,
             qxf_dir: str | None = None,
             date: str | None = None,
             presets: list[str] | None = None,
             show_name: str | None = None) -> dict:
    """Build a structured document from the loaded workspace.

    Parameters
    ----------
    sections : list[str] or None
        Which sections to include.  None or empty means all.
    qxf_dir : str or None
        Optional directory to scan for .qxf files (for value decoding).
        If None, uses whatever QXF defs are already loaded.  Definitions
        next to the workspace and, for fixtures still missing, the installed
        QLC+ library are always added.
    date : str or None
        Date printed in the book (default: today) — pass one for
        reproducible output.

    Returns
    -------
    dict with keys:
        show_name   str
        date        str
        sections    dict[str, any]  — keyed by section name
    """
    state = workspace._state
    if not state.get("loaded"):
        raise RuntimeError("No workspace loaded")

    root = state["qxw_root"]
    title = "Show Book"
    if presets:
        sections, title = resolve_sections(presets, sections)
    elif sections is None or len(sections) == 0:
        sections = [x for x in ALL_SECTIONS if x in PRESETS["operator"]["sections"]]

    # Load QXF definitions if a directory is provided
    if qxf_dir and os.path.isdir(qxf_dir):
        _load_qxf_dir(qxf_dir)

    _load_workspace_qxfs(state)

    # Build QXF lookup for value decoding
    qxf_lookup = _build_qxf_lookup()

    # Derive show name from filename
    if not show_name:
        show_name = state.get("original_name") or os.path.basename(state.get("path", "Untitled"))
        if show_name.endswith(".qxw"):
            show_name = show_name[:-4]

    doc = {
        "show_name": show_name,
        "date": date or datetime.date.today().isoformat(),
        "title": title,
        "presets": [p for p in (presets or []) if p in PRESETS],
        "sections": {},
    }

    if "rider" in sections:
        doc["sections"]["rider"] = _build_rider(state, root)

    if "stage_plan" in sections:
        doc["sections"]["stage_plan"] = _build_stage_plan(state)

    if "checklist" in sections:
        doc["sections"]["checklist"] = _build_checklist(state)

    if "summary" in sections:
        doc["sections"]["summary"] = _build_summary(state, root)

    if "patch" in sections:
        doc["sections"]["patch"] = _build_patch(state)

    if "functions" in sections:
        doc["sections"]["functions"] = _build_function_index(state)

    if "scenes" in sections:
        doc["sections"]["scenes"] = _build_scenes(root, state, qxf_lookup)

    if "chasers" in sections:
        doc["sections"]["chasers"] = _build_chasers(root, state)

    if "collections" in sections:
        doc["sections"]["collections"] = _build_collections(root, state)

    if "efx" in sections:
        doc["sections"]["efx"] = _build_efx(root, state)

    if "shows" in sections:
        doc["sections"]["shows"] = _build_shows(root, state)

    if "scripts" in sections:
        doc["sections"]["scripts"] = _build_scripts(root, state)

    if "vc_layout" in sections:
        doc["sections"]["vc_layout"] = _build_vc_layout(root, state)

    if "doctor" in sections:
        doc["sections"]["doctor"] = _build_doctor(root, qxf_lookup)

    return doc


# ═══════════════════════════════════════════════════════════════════════════════
# QXF HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _load_qxf_dir(qxf_dir: str):
    """Scan a directory for .qxf files and load them."""
    for fname in os.listdir(qxf_dir):
        if fname.lower().endswith(".qxf"):
            path = os.path.join(qxf_dir, fname)
            try:
                fixture_mod.load_qxf(path)
            except Exception:
                pass  # skip broken files


def _load_workspace_qxfs(state: dict):
    """Add the definitions QLC+ itself would use: ``.qxf`` files next to the
    workspace, then the installed QLC+ library for models still missing."""
    path = state.get("path") or ""
    folder = os.path.dirname(os.path.abspath(path)) if path else ""
    if folder and os.path.isdir(folder):
        _load_qxf_dir(folder)
    have = {(d.get("manufacturer", "").lower(), d.get("model", "").lower())
            for d in fixture_mod.get_qxf_defs().values()}
    try:
        from core.quick_start import qlc_library
    except Exception:  # noqa: BLE001
        return
    for info in state.get("fixture_map", {}).values():
        mfg = info.get("manufacturer", "")
        model = _model_only(info)
        if (mfg.lower(), model.lower()) in have:
            continue
        try:
            found = qlc_library.find(mfg, model)
            if found:
                fixture_mod.load_qxf(found)
                have.add((mfg.lower(), model.lower()))
        except Exception:  # noqa: BLE001 — decoding just stays raw
            pass


def _model_only(info: dict) -> str:
    """Workspace fixture model without the manufacturer prefix
    (``fixture_map`` stores "Manufacturer Model")."""
    mfg = info.get("manufacturer", "")
    model = info.get("model", "")
    if mfg and model.startswith(mfg + " "):
        return model[len(mfg) + 1:]
    return model


def _build_qxf_lookup() -> dict:
    """Build a lookup: 'Manufacturer Model' → qxf_def with channel_defs.

    Returns dict keyed by 'Mfg Model' string.
    """
    defs = fixture_mod.get_qxf_defs()
    lookup = {}
    for key, defn in defs.items():
        # key is "Manufacturer::Model"
        mfg = defn.get("manufacturer", "")
        model = defn.get("model", "")
        lookup_key = f"{mfg} {model}"
        lookup[lookup_key] = defn
    return lookup


def _get_fixture_qxf(fixture_info: dict, qxf_lookup: dict) -> dict | None:
    """Find the QXF definition for a workspace fixture."""
    model_str = fixture_info.get("model", "")  # "Manufacturer Model"
    return qxf_lookup.get(model_str)


def _get_mode_channels(qxf_def: dict, mode_name: str) -> list[str]:
    """Get ordered channel names for a mode, with fallback."""
    mode_channels = qxf_def.get("mode_channels", {})
    if mode_name in mode_channels:
        return mode_channels[mode_name]
    # Try partial match
    for mname, channels in mode_channels.items():
        if mname.lower() == mode_name.lower():
            return channels
    # Fallback: first mode or flat channel list
    if mode_channels:
        return next(iter(mode_channels.values()))
    return qxf_def.get("channels", [])


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def _build_summary(state: dict, root: ET.Element) -> dict:
    """Overview statistics."""
    fixture_count = len(state.get("fixture_map", {}))
    func_count = len(state.get("func_detailed", {}))
    layout = _build_vc_layout(root, state)
    vc_count = layout["widget_count"]

    # Count by function type
    type_counts = {}
    for fid, info in state.get("func_detailed", {}).items():
        ftype = info.get("type", "Unknown")
        type_counts[ftype] = type_counts.get(ftype, 0) + 1

    # Count universes
    universes = set()
    for fid, info in state.get("fixture_map", {}).items():
        universes.add(info.get("universe", 0))

    return {
        "fixture_count": fixture_count,
        "function_count": func_count,
        "vc_widget_count": vc_count,
        "vc_page_count": len(layout["pages"]),
        "universe_count": len(universes),
        "universes": sorted(universes),
        "function_types": type_counts,
    }


def _build_patch(state: dict) -> list[dict]:
    """Fixture patch list, sorted by universe then address."""
    rows = []
    for fid, info in state.get("fixture_map", {}).items():
        rows.append({
            "id": fid,
            "name": info.get("name", ""),
            "manufacturer": info.get("manufacturer", "Unknown"),
            "model": _model_only(info) or "Unknown",
            "mode": info.get("mode", "Default"),
            "universe": info.get("universe", 0),
            "address": info.get("address", 0),
            "patch": info.get("patch", ""),
            "groups": info.get("groups", ""),
        })
    rows.sort(key=lambda r: (r["universe"], r["address"]))
    return rows


def _fixture_channels(root: ET.Element) -> dict:
    """fixture id → number of DMX channels (from the workspace)."""
    out = {}
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.endswith("Fixture") and el.find("./*") is not None:
            fid = next((c.text for c in el if c.tag.endswith("ID")), None)
            ch = next((c.text for c in el if c.tag.endswith("Channels")), None)
            if fid is not None:
                try:
                    out[fid.strip()] = int(ch or 0)
                except ValueError:
                    out[fid.strip()] = 0
    return out


def _build_rider(state: dict, root: ET.Element) -> dict:
    """Fixture types for the venue: make, model, mode, how many, channels,
    patch range, universes; totals.  No function, VC or binding data."""
    chans = _fixture_channels(root)
    groups: dict = {}
    for fid, info in state.get("fixture_map", {}).items():
        key = (info.get("manufacturer", "") or "Unknown", _model_only(info) or "Unknown",
               info.get("mode", "") or "Default")
        groups.setdefault(key, []).append((fid, info))
    types, total_ch, unis = [], 0, set()
    for (mfg, model, mode), fxs in sorted(groups.items()):
        patches = sorted(f[1].get("patch", "") for f in fxs)
        u = sorted({f[1].get("universe", 0) for f in fxs})
        unis.update(u)
        ch = max((chans.get(f[0], 0) for f in fxs), default=0)
        total_ch += sum(chans.get(f[0], 0) for f in fxs)
        types.append({"manufacturer": mfg, "model": model, "mode": mode, "quantity": len(fxs),
                      "channels": ch,
                      "patch_range": patches[0] if len(set(patches)) == 1 else f"{patches[0]} - {patches[-1]}",
                      "universes": u})
    return {"types": types, "total_fixtures": sum(t["quantity"] for t in types),
            "total_channels": total_ch, "universes": sorted(unis)}


def _build_stage_plan(state: dict) -> dict:
    """3D positions for the stage plot (top and front view)."""
    fx = []
    for fid, info in state.get("fixture_map", {}).items():
        fx.append({"id": fid, "name": info.get("name", ""), "patch": info.get("patch", ""),
                   "color": info.get("color", "#888888"), "x": info.get("x_mm", 0),
                   "y": info.get("y_mm", 0), "z": info.get("z_mm", 0),
                   "in_3d": bool(info.get("in_3d"))})
    fx.sort(key=lambda f: int(f["id"]) if str(f["id"]).isdigit() else 0)
    return {"fixtures": fx, "placed": sum(1 for f in fx if f["in_3d"])}


def _build_checklist(state: dict) -> list[dict]:
    """Load-in checklist: every fixture with its patch, groups and 3D place,
    a box to tick.  Sorted by universe and address."""
    rows = []
    for p in _build_patch(state):
        info = state["fixture_map"].get(p["id"], {})
        pos = (f"{info.get('x_mm', 0) / 1000:.2f} / {info.get('y_mm', 0) / 1000:.2f} / "
               f"{info.get('z_mm', 0) / 1000:.2f} m") if info.get("in_3d") else ""
        rows.append({**p, "position": pos})
    return rows


def _build_function_index(state: dict) -> list[dict]:
    """Function summary table, sorted by ID.  Includes dictionary description
    when available (from shared_descriptions)."""
    descs = state.get("shared_descriptions", {})
    rows = []
    for fid, info in state.get("func_detailed", {}).items():
        rows.append({
            "id": fid,
            "name": info.get("name", ""),
            "type": info.get("type", ""),
            "description": descs.get(fid, ""),
        })
    rows.sort(key=lambda r: int(r["id"]) if r["id"].isdigit() else 0)
    return rows


def _build_scenes(root: ET.Element, state: dict,
                  qxf_lookup: dict) -> list[dict]:
    """Detailed scene breakdown with decoded DMX values."""
    descs = state.get("shared_descriptions", {})
    scenes = []
    fixture_map = state.get("fixture_map", {})

    for func in root.findall("q:Engine/q:Function[@Type='Scene']", NS):
        fid = func.get("ID", "")
        fname = func.get("Name", "")

        channels = []
        for fval in func.findall("q:FixtureVal", NS):
            fix_id = fval.get("ID", "")
            fix_info = fixture_map.get(fix_id, {})
            fix_name = fix_info.get("name", f"Fixture {fix_id}")
            fix_model = fix_info.get("model", "")
            fix_mode = fix_info.get("mode", "Default")

            # Parse "ch_idx,value,ch_idx,value,..." pairs
            raw_text = (fval.text or "").strip()
            if not raw_text:
                continue

            parts = raw_text.split(",")
            ch_values = []
            for i in range(0, len(parts) - 1, 2):
                try:
                    ch_idx = int(parts[i])
                    value = int(parts[i + 1])
                    ch_values.append((ch_idx, value))
                except (ValueError, IndexError):
                    continue

            # Decode using QXF if available
            qxf_def = _get_fixture_qxf(fix_info, qxf_lookup)
            mode_ch_names = []
            channel_defs = {}
            fine_pairs = {}
            physical = {}
            if qxf_def:
                mode_ch_names = _get_mode_channels(qxf_def, fix_mode)
                channel_defs = qxf_def.get("channel_defs", {})
                physical = qxf_def.get("physical", {})
                fp_by_mode = qxf_def.get("fine_pairs", {})
                fine_pairs = fp_by_mode.get(fix_mode, {})
                if not fine_pairs:
                    # Try first mode
                    for fp in fp_by_mode.values():
                        fine_pairs = fp
                        break

            # Build a map of ch_idx → value for fine pair lookup
            value_by_idx = {idx: val for idx, val in ch_values}

            decoded_channels = []
            for ch_idx, value in ch_values:
                ch_name = ""
                decoded_label = str(value)

                if ch_idx < len(mode_ch_names):
                    ch_name = mode_ch_names[ch_idx]
                    ch_def = channel_defs.get(ch_name)
                    if ch_def:
                        # Check for fine pair
                        fine_name = fine_pairs.get(ch_name)
                        fine_raw = None
                        if fine_name and fine_name in mode_ch_names:
                            fine_idx = mode_ch_names.index(fine_name)
                            fine_raw = value_by_idx.get(fine_idx)

                        result = decode_value(ch_def, value, fine_raw, physical)
                        decoded_label = result.get("label", str(value))

                decoded_channels.append({
                    "channel_index": ch_idx,
                    "channel_name": ch_name or f"Ch {ch_idx + 1}",
                    "raw_value": value,
                    "decoded": decoded_label,
                })

            channels.append({
                "fixture_id": fix_id,
                "fixture_name": fix_name,
                "fixture_model": fix_model,
                "channels": decoded_channels,
            })

        scenes.append({
            "id": fid,
            "name": fname,
            "description": descs.get(fid, ""),
            "fixtures": channels,
        })

    scenes.sort(key=lambda s: int(s["id"]) if s["id"].isdigit() else 0)
    return scenes


def _build_chasers(root: ET.Element, state: dict) -> list[dict]:
    """Chaser details with steps and timing."""
    descs = state.get("shared_descriptions", {})
    func_by_id = state.get("func_by_id", {})
    chasers = []

    for func in root.findall("q:Engine/q:Function[@Type='Chaser']", NS):
        fid = func.get("ID", "")
        fname = func.get("Name", "")

        # Read speed modes
        speed_node = func.find("q:Speed", NS)
        fade_in = speed_node.get("FadeIn", "0") if speed_node is not None else "0"
        fade_out = speed_node.get("FadeOut", "0") if speed_node is not None else "0"
        duration = speed_node.get("Duration", "0") if speed_node is not None else "0"

        direction_node = func.find("q:Direction", NS)
        direction = (direction_node.text or "Forward") if direction_node is not None else "Forward"

        run_order_node = func.find("q:RunOrder", NS)
        run_order = (run_order_node.text or "Loop") if run_order_node is not None else "Loop"

        steps = []
        for step in func.findall("q:Step", NS):
            step_num = step.get("Number", "?")
            step_func_id = (step.text or "").strip()
            step_func_name = func_by_id.get(step_func_id, f"[ID {step_func_id}]")

            step_fi = step.get("FadeIn", fade_in)
            step_fo = step.get("FadeOut", fade_out)
            step_dur = step.get("Duration", duration)
            step_hold = step.get("Hold", "0")

            steps.append({
                "number": step_num,
                "function_id": step_func_id,
                "function_name": step_func_name,
                "fade_in": _format_time_ms(step_fi),
                "fade_out": _format_time_ms(step_fo),
                "duration": _format_time_ms(step_dur),
                "hold": _format_time_ms(step_hold),
            })

        chasers.append({
            "id": fid,
            "name": fname,
            "description": descs.get(fid, ""),
            "direction": direction,
            "run_order": run_order,
            "speed": {
                "fade_in": _format_time_ms(fade_in),
                "fade_out": _format_time_ms(fade_out),
                "duration": _format_time_ms(duration),
            },
            "steps": steps,
        })

    chasers.sort(key=lambda c: int(c["id"]) if c["id"].isdigit() else 0)
    return chasers


def _build_collections(root: ET.Element, state: dict) -> list[dict]:
    """Collection details with member functions."""
    descs = state.get("shared_descriptions", {})
    func_by_id = state.get("func_by_id", {})
    collections = []

    for func in root.findall("q:Engine/q:Function[@Type='Collection']", NS):
        fid = func.get("ID", "")
        fname = func.get("Name", "")

        members = []
        for step in func.findall("q:Step", NS):
            member_id = (step.text or "").strip()
            member_name = func_by_id.get(member_id, f"[ID {member_id}]")
            members.append({
                "function_id": member_id,
                "function_name": member_name,
            })

        collections.append({
            "id": fid,
            "name": fname,
            "description": descs.get(fid, ""),
            "members": members,
        })

    collections.sort(key=lambda c: int(c["id"]) if c["id"].isdigit() else 0)
    return collections


def _build_efx(root: ET.Element, state: dict) -> list[dict]:
    """EFX details."""
    fixture_map = state.get("fixture_map", {})
    efx_list = []

    for func in root.findall("q:Engine/q:Function[@Type='EFX']", NS):
        fid = func.get("ID", "")
        fname = func.get("Name", "")

        algorithm_node = func.find("q:Algorithm", NS)
        algorithm = (algorithm_node.text or "Circle") if algorithm_node is not None else "Circle"

        fixtures = []
        for efx_fx in func.findall("q:EFXFixture", NS):
            fx_id_node = efx_fx.find("q:ID", NS)
            fx_id = (fx_id_node.text or "").strip() if fx_id_node is not None else ""
            fx_info = fixture_map.get(fx_id, {})
            fx_name = fx_info.get("name", f"Fixture {fx_id}")
            fixtures.append({
                "fixture_id": fx_id,
                "fixture_name": fx_name,
            })

        efx_list.append({
            "id": fid,
            "name": fname,
            "algorithm": algorithm,
            "fixtures": fixtures,
        })

    efx_list.sort(key=lambda e: int(e["id"]) if e["id"].isdigit() else 0)
    return efx_list


def _build_shows(root: ET.Element, state: dict) -> list[dict]:
    """Show function details."""
    func_by_id = state.get("func_by_id", {})
    shows = []

    for func in root.findall("q:Engine/q:Function[@Type='Show']", NS):
        fid = func.get("ID", "")
        fname = func.get("Name", "")

        tracks = []
        for track in func.findall("q:Track", NS):
            track_name = track.get("Name", "")
            track_func_id = track.get("SceneID", "")
            track_func_name = func_by_id.get(track_func_id, "")

            show_funcs = []
            for sf in track.findall("q:ShowFunction", NS):
                sf_id = sf.get("ID", "")
                sf_name = func_by_id.get(sf_id, f"[ID {sf_id}]")
                sf_start = sf.get("StartTime", "0")
                sf_dur = sf.get("Duration", "0")
                show_funcs.append({
                    "function_id": sf_id,
                    "function_name": sf_name,
                    "start_time": _format_time_ms(sf_start),
                    "duration": _format_time_ms(sf_dur),
                })

            tracks.append({
                "name": track_name,
                "scene_id": track_func_id,
                "scene_name": track_func_name,
                "show_functions": show_funcs,
            })

        shows.append({
            "id": fid,
            "name": fname,
            "tracks": tracks,
        })

    shows.sort(key=lambda s: int(s["id"]) if s["id"].isdigit() else 0)
    return shows


def _build_scripts(root: ET.Element, state: dict) -> list[dict]:
    """Script function details."""
    scripts = []

    for func in root.findall("q:Engine/q:Function[@Type='Script']", NS):
        fid = func.get("ID", "")
        fname = func.get("Name", "")

        commands = []
        for cmd in func.findall("q:Command", NS):
            commands.append((cmd.text or "").strip())

        scripts.append({
            "id": fid,
            "name": fname,
            "commands": commands,
        })

    scripts.sort(key=lambda s: int(s["id"]) if s["id"].isdigit() else 0)
    return scripts


def _vc_bindings(w: ET.Element) -> str:
    """Key / MIDI bindings of widget *w* itself, e.g. ``"Next: key Space,
    MIDI U2 ch 20"``."""
    parts = []

    def walk(el, slot):
        for c in el:
            tag = c.tag.replace(f"{{{QLC_NS_URI}}}", "")
            if tag in workspace._WIDGET_TYPES:
                continue
            label = (_SLOT_LABELS.get(slot, slot) + ": ") if slot else ""
            if tag == "Key" and (c.text or "").strip():
                parts.append(f"{label}key {(c.text or '').strip()}")
            elif tag == "Input" and c.get("Channel") is not None:
                u = c.get("Universe", "")
                u = int(u) + 1 if u.isdigit() else u
                parts.append(f"{label}MIDI U{u} ch {c.get('Channel')}")
            elif len(c):
                walk(c, tag if not slot else slot)
    walk(w, "")
    return ", ".join(parts)


def _build_vc_layout(root: ET.Element, state: dict) -> dict:
    """Virtual Console by page: every page (top-level frame), its frames and
    widgets in document order, with position, size, function and key/MIDI
    bindings.

    Returns ``{"pages": [{id, type, caption, size, widgets: [row]}],
    "widget_count"}``; a row is ``{id, type, caption, frame (path inside the
    page), depth, x, y, w, h, function_id, function_name, bindings}``.
    """
    func_by_id = state.get("func_by_id", {})
    vc = root.find("q:VirtualConsole", NS)
    pages = []
    count = 0
    if vc is None:
        return {"pages": pages, "widget_count": 0}

    def tag_of(el):
        return el.tag.replace(f"{{{QLC_NS_URI}}}", "")

    def geom(el):
        ws = el.find("q:WindowState", NS)
        if ws is None:
            return "", "", "", ""
        return ws.get("X", ""), ws.get("Y", ""), ws.get("Width", ""), ws.get("Height", "")

    def func_of(el):
        t = tag_of(el)
        if t == "CueList":
            fid = (el.findtext("q:Chaser", default="", namespaces=NS) or "").strip()
        else:
            fe = el.find("q:Function", NS)
            fid = fe.get("ID", "") if fe is not None else ""
        return "" if fid in ("", "4294967295", "-1") else fid

    def walk(el, path, depth, rows):
        nonlocal count
        for c in el:
            t = tag_of(c)
            if t not in workspace._WIDGET_TYPES:
                continue
            x, y, w, h = geom(c)
            fid = func_of(c)
            cap = (c.get("Caption", "") or "").replace("\n", " ").strip()
            rows.append({
                "id": c.get("ID", ""), "type": t, "caption": cap,
                "frame": " › ".join(path), "depth": depth,
                "x": x, "y": y, "w": w, "h": h,
                "function_id": fid,
                "function_name": (func_by_id.get(fid, "") if fid else
                                  _ACTION_LABELS.get((c.findtext("q:Action", default="",
                                                                 namespaces=NS) or "").strip(), "")),
                "bindings": _vc_bindings(c),
            })
            count += 1
            if t in ("Frame", "SoloFrame"):
                walk(c, path + [cap or "(frame)"], depth + 1, rows)

    for pg in vc:
        t = tag_of(pg)
        if t not in ("Frame", "SoloFrame"):
            continue
        _x, _y, w, h = geom(pg)
        rows: list[dict] = []
        walk(pg, [], 0, rows)
        pages.append({"id": pg.get("ID", ""), "type": t,
                      "caption": (pg.get("Caption", "") or "").replace("\n", " ").strip(),
                      "size": f"{w}×{h}" if w and h else "", "widgets": rows})
    return {"pages": pages, "widget_count": count}


def _build_doctor(root: ET.Element, qxf_lookup: dict) -> dict:
    """Workspace Doctor summary (read-only): counts and every error and
    warning (info findings counted only)."""
    from core import qxw_io
    from core.doctor import check
    plain = qxw_io.strip_ns(copy.deepcopy(root))
    report = check(plain, list(qxf_lookup.values()))
    findings = [{"code": f.code, "severity": f.severity, "location": f.location,
                 "message": f.message}
                for f in report.findings if f.severity in ("error", "warning")]
    return {
        "errors": len(report.errors),
        "warnings": len(report.warnings),
        "info": len([f for f in report.findings if f.severity == "info"]),
        "findings": findings,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TIME FORMATTER
# ═══════════════════════════════════════════════════════════════════════════════

def _format_time_ms(val) -> str:
    """Format a millisecond value as a human-readable time string."""
    try:
        ms = int(val)
    except (ValueError, TypeError):
        return str(val)

    if ms == 0:
        return "0s"
    if ms < 1000:
        return f"{ms}ms"
    secs = ms / 1000
    if secs < 60:
        return f"{secs:.1f}s"
    mins = int(secs // 60)
    secs_rem = secs % 60
    return f"{mins}m {secs_rem:.0f}s"


# ═══════════════════════════════════════════════════════════════════════════════
# CSV EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def export_csv(document: dict) -> bytes:
    """Export the document as a ZIP of CSV files.

    Returns bytes of a ZIP archive containing one CSV per section.
    """
    buf = io.BytesIO()
    sections = document.get("sections", {})

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr = _fixed_time_writestr(zf)       # same input → same bytes
        if "rider" in sections:
            zf.writestr("rider.csv", _csv_write(
                [[t["manufacturer"], t["model"], t["mode"], t["quantity"], t["channels"],
                  t["patch_range"], " ".join(str(u) for u in t["universes"])]
                 for t in sections["rider"]["types"]],
                ["Manufacturer", "Model", "Mode", "Qty", "Channels", "Patch range", "Universes"]))
        if "stage_plan" in sections:
            zf.writestr("stage_plan.csv", _csv_write(
                [[f["id"], f["name"], f["patch"], f["x"], f["y"], f["z"]]
                 for f in sections["stage_plan"]["fixtures"] if f["in_3d"]],
                ["ID", "Name", "Patch", "X mm", "Y mm", "Z mm"]))
        if "checklist" in sections:
            zf.writestr("checklist.csv", _csv_write(
                [["", c["id"], c["name"], c["model"], c["mode"], c["patch"], c["groups"],
                  c["position"]] for c in sections["checklist"]],
                ["Done", "ID", "Name", "Model", "Mode", "Patch", "Groups", "3D position"]))
        if "patch" in sections:
            zf.writestr("patch.csv", _csv_patch(sections["patch"]))

        if "functions" in sections:
            zf.writestr("functions.csv", _csv_functions(sections["functions"]))

        if "scenes" in sections:
            zf.writestr("scenes.csv", _csv_scenes(sections["scenes"]))

        if "chasers" in sections:
            zf.writestr("chasers.csv", _csv_chasers(sections["chasers"]))

        if "collections" in sections:
            zf.writestr("collections.csv", _csv_collections(sections["collections"]))

        if "efx" in sections:
            zf.writestr("efx.csv", _csv_efx(sections["efx"]))

        if "shows" in sections:
            zf.writestr("shows.csv", _csv_shows(sections["shows"]))

        if "scripts" in sections:
            zf.writestr("scripts.csv", _csv_scripts(sections["scripts"]))

        if "vc_layout" in sections:
            zf.writestr("vc_layout.csv", _csv_vc(sections["vc_layout"]))

        if "doctor" in sections:
            zf.writestr("doctor.csv", _csv_doctor(sections["doctor"]))

        # Summary as a simple text file
        if "summary" in sections:
            zf.writestr("summary.txt", _txt_summary(document))

    return buf.getvalue()


def _fixed_time_writestr(zf: zipfile.ZipFile):
    """``zf.writestr`` with a fixed timestamp (1980-01-01), so the ZIP is
    byte-identical run to run (WORKPLAN principle 3)."""
    orig = zf.writestr

    def w(name, data):
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        return orig(info, data)
    return w


def _csv_write(rows: list[list], headers: list[str]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    return buf.getvalue()


def _csv_patch(patch: list[dict]) -> str:
    headers = ["ID", "Name", "Manufacturer", "Model", "Mode",
               "Universe", "Address", "Patch", "Groups"]
    rows = [[p["id"], p["name"], p["manufacturer"], p["model"],
             p["mode"], p["universe"], p["address"], p["patch"],
             p["groups"]] for p in patch]
    return _csv_write(rows, headers)


def _csv_functions(functions: list[dict]) -> str:
    headers = ["ID", "Name", "Type", "Description"]
    rows = [[f["id"], f["name"], f["type"], f.get("description", "")] for f in functions]
    return _csv_write(rows, headers)


def _csv_scenes(scenes: list[dict]) -> str:
    headers = ["Scene ID", "Scene Name", "Fixture ID", "Fixture Name",
               "Channel Index", "Channel Name", "Raw Value", "Decoded"]
    rows = []
    for s in scenes:
        for fx in s.get("fixtures", []):
            for ch in fx.get("channels", []):
                rows.append([
                    s["id"], s["name"], fx["fixture_id"], fx["fixture_name"],
                    ch["channel_index"], ch["channel_name"],
                    ch["raw_value"], ch["decoded"],
                ])
    return _csv_write(rows, headers)


def _csv_chasers(chasers: list[dict]) -> str:
    headers = ["Chaser ID", "Chaser Name", "Direction", "Run Order",
               "Step #", "Function ID", "Function Name",
               "Fade In", "Hold", "Fade Out", "Duration"]
    rows = []
    for c in chasers:
        for step in c.get("steps", []):
            rows.append([
                c["id"], c["name"], c["direction"], c["run_order"],
                step["number"], step["function_id"], step["function_name"],
                step["fade_in"], step["hold"], step["fade_out"],
                step["duration"],
            ])
    return _csv_write(rows, headers)


def _csv_collections(collections: list[dict]) -> str:
    headers = ["Collection ID", "Collection Name",
               "Member Function ID", "Member Function Name"]
    rows = []
    for c in collections:
        for m in c.get("members", []):
            rows.append([c["id"], c["name"],
                         m["function_id"], m["function_name"]])
    return _csv_write(rows, headers)


def _csv_efx(efx_list: list[dict]) -> str:
    headers = ["EFX ID", "EFX Name", "Algorithm",
               "Fixture ID", "Fixture Name"]
    rows = []
    for e in efx_list:
        for fx in e.get("fixtures", []):
            rows.append([e["id"], e["name"], e["algorithm"],
                         fx["fixture_id"], fx["fixture_name"]])
    return _csv_write(rows, headers)


def _csv_vc(layout: dict) -> str:
    headers = ["Page", "Frame Path", "Widget ID", "Type", "Caption", "X", "Y",
               "Width", "Height", "Function ID", "Function Name", "Key / MIDI"]
    rows = []
    for pg in layout.get("pages", []):
        rows.append([pg["caption"], "", pg["id"], pg["type"] + " (page)", pg["caption"],
                     "", "", *(pg["size"].split("×") if pg["size"] else ["", ""]), "", "", ""])
        for w in pg["widgets"]:
            rows.append([pg["caption"], w["frame"], w["id"], w["type"], w["caption"],
                         w["x"], w["y"], w["w"], w["h"],
                         w["function_id"], w["function_name"], w["bindings"]])
    return _csv_write(rows, headers)


def _csv_shows(shows: list[dict]) -> str:
    headers = ["Show ID", "Show Name", "Track", "Function ID", "Function Name",
               "Start", "Duration"]
    rows = []
    for sh in shows:
        for tr in sh["tracks"]:
            for sf in tr["show_functions"] or [{}]:
                rows.append([sh["id"], sh["name"], tr["name"], sf.get("function_id", ""),
                             sf.get("function_name", ""), sf.get("start_time", ""),
                             sf.get("duration", "")])
    return _csv_write(rows, headers)


def _csv_scripts(scripts: list[dict]) -> str:
    headers = ["Script ID", "Script Name", "Line", "Command"]
    rows = [[sc["id"], sc["name"], i + 1, cmd]
            for sc in scripts for i, cmd in enumerate(sc["commands"])]
    return _csv_write(rows, headers)


def _csv_doctor(doc: dict) -> str:
    headers = ["Code", "Severity", "Location", "Message"]
    rows = [[f["code"], f["severity"], f["location"], f["message"]] for f in doc["findings"]]
    return _csv_write(rows, headers)


def _txt_summary(document: dict) -> str:
    s = document["sections"].get("summary", {})
    lines = [
        f"Show Book: {document['show_name']}",
        f"Date: {document['date']}",
        "",
        f"Fixtures: {s.get('fixture_count', 0)}",
        f"Functions: {s.get('function_count', 0)}",
        f"VC Widgets: {s.get('vc_widget_count', 0)} on {s.get('vc_page_count', 0)} page(s)",
        f"Universes: {s.get('universe_count', 0)} ({', '.join(str(u) for u in s.get('universes', []))})",
        "",
        "Functions by type:",
    ]
    for ftype, count in sorted(s.get("function_types", {}).items()):
        lines.append(f"  {ftype}: {count}")
    d = document["sections"].get("doctor")
    if d:
        lines += ["", f"Doctor: {d['errors']} error(s), {d['warnings']} warning(s), "
                      f"{d['info']} info"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

# Re-use the raw PDF primitives from core.pdf
from core.pdf import assemble_pdf, _pdf_str

# Page dimensions (points)
_W = 842.0  # page width  (A4 landscape by default; export_pdf(paper=…) sets it)
_H = 595.0  # page height

# Paper sizes in PDF points (the old Checklist / Tech Rider choices, 1.9)
PAPERS = {
    "A4 Landscape":        (842.0, 595.0),
    "A4 Portrait":         (595.0, 842.0),
    "A3 Landscape":        (1190.0, 842.0),
    "A3 Portrait":         (842.0, 1190.0),
    "US Letter Landscape": (792.0, 612.0),
    "US Letter Portrait":  (612.0, 792.0),
}
DEFAULT_PAPER = "A4 Landscape"
_PAD = 14
_TITLE_H = 34
_ROW_H = 14
_HDR_H = 16
_FSIZE = 8

# Colours
_COL_DARK     = (0.12, 0.12, 0.18)
_COL_HDR      = (0.22, 0.30, 0.45)
_COL_ALT      = (0.93, 0.95, 1.00)
_COL_WHITE    = (1.0, 1.0, 1.0)
_COL_BORDER   = (0.80, 0.84, 0.92)
_COL_ACCENT   = (0.20, 0.45, 0.75)
_COL_SECTION  = (0.15, 0.18, 0.28)


def _pdf_clean(s) -> str:
    """Text the built-in PDF fonts can show: typographic characters mapped to
    Latin-1 look-alikes, emoji and other symbols dropped (not printed as ?)."""
    s = str(s)
    for a, b in (("›", ">"), ("→", "->"), ("—", "-"), ("–", "-"), ("…", "..."),
                 ("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"), ("×", "x"), ("\n", " ")):
        s = s.replace(a, b)
    s = "".join(ch for ch in s if ord(ch) < 256)
    return re.sub(r"\s{2,}", " ", s).strip()


class _PdfBuilder:
    """Low-level PDF page builder using raw PDF streams."""

    def __init__(self, title: str, show_name: str, date: str):
        self.title = title
        self.show_name = show_name
        self.date = date
        self.pages: list[bytes] = []
        self.ops: list[str] = []
        self.page_num = 0
        self.cy = _H  # current y cursor

    def _emit(self, s: str):
        self.ops.append(s)

    def fc(self, r, g, b):
        self._emit(f"{r:.4f} {g:.4f} {b:.4f} rg")

    def sc(self, r, g, b):
        self._emit(f"{r:.4f} {g:.4f} {b:.4f} RG")

    def lw(self, w):
        self._emit(f"{w} w")

    def rfill(self, x, y, w, h, col):
        self.fc(*col)
        self._emit(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def rbox(self, x, y, w, h, fcol, scol, wd=0.3):
        self.fc(*fcol)
        self.sc(*scol)
        self.lw(wd)
        self._emit(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re B")

    def txt(self, x, y, s, sz=8, bold=False):
        s = _pdf_str(_pdf_clean(s))
        f = "/F2" if bold else "/F1"
        self._emit(f"BT {f} {sz} Tf {x:.2f} {y:.2f} Td ({s}) Tj ET")

    def txt_trunc(self, x, y, s, sz, max_w):
        """Write text, truncating if wider than max_w."""
        s = _pdf_clean(s) if s is not None else ""
        max_chars = max(4, int(max_w / (sz * 0.52)))
        if len(s) > max_chars:
            s = s[:max_chars - 1] + "~"
        self.txt(x, y, s, sz)

    def finish_page(self):
        if self.ops:
            self.pages.append(
                zlib.compress("\n".join(self.ops).encode("latin-1", "replace"))
            )
            self.ops.clear()

    def new_page(self):
        if self.ops:
            self.finish_page()
        self.page_num += 1
        self.cy = _H
        self._draw_page_header()

    def _draw_page_header(self):
        """Draw the page header bar."""
        self.rfill(0, _H - _TITLE_H, _W, _TITLE_H, _COL_DARK)
        self.fc(1, 1, 1)
        self.txt(_PAD, _H - _TITLE_H + 12, self.show_name, sz=11, bold=True)
        tx = max(_PAD + 160, _W / 2 - 40)            # never over the date (portrait pages)
        self.fc(1, 1, 1)
        self.txt_trunc(tx, _H - _TITLE_H + 12, self.title, 9, (_W - 190) - tx)
        self.txt(_W - 180, _H - _TITLE_H + 18, f"Date: {self.date}", sz=8)
        self.txt(_W - 180, _H - _TITLE_H + 8, f"Page {self.page_num}", sz=8)
        self.cy = _H - _TITLE_H - 6

    def ensure_space(self, needed: float):
        """Start a new page if less than `needed` points remain."""
        if self.cy - needed < _PAD + _ROW_H:
            self.new_page()

    def section_heading(self, text: str):
        """Draw a section heading bar."""
        self.ensure_space(30)
        self.cy -= 6
        h = 20
        self.rfill(_PAD, self.cy - h, _W - 2 * _PAD, h, _COL_SECTION)
        self.fc(1, 1, 1)
        self.txt(_PAD + 6, self.cy - h + 6, text, sz=10, bold=True)
        self.cy -= h + 4

    def table_header(self, headers: list[str], col_w: list[float]):
        """Draw a table header row."""
        self.ensure_space(_HDR_H + _ROW_H)
        col_x = _col_positions(col_w)
        for xi, wi, hdr in zip(col_x, col_w, headers):
            self.rbox(xi, self.cy - _HDR_H, wi, _HDR_H, _COL_HDR,
                      (0.1, 0.2, 0.35), 0.2)
        self.fc(1, 1, 1)
        for xi, hdr in zip(col_x, headers):
            self.txt(xi + 3, self.cy - _HDR_H + 4, hdr, sz=_FSIZE, bold=True)
        self.cy -= _HDR_H

    def table_row(self, cells: list[str], col_w: list[float], row_idx: int):
        """Draw a table data row."""
        self.ensure_space(_ROW_H)
        col_x = _col_positions(col_w)
        rc = _COL_ALT if row_idx % 2 == 0 else _COL_WHITE
        for xi, wi in zip(col_x, col_w):
            self.rbox(xi, self.cy - _ROW_H, wi, _ROW_H, rc, _COL_BORDER, 0.2)
        self.fc(0, 0, 0)
        for cell, xi, wi in zip(cells, col_x, col_w):
            self.txt_trunc(xi + 3, self.cy - _ROW_H + 3, cell, _FSIZE, wi - 6)
        self.cy -= _ROW_H

    def spacer(self, h: float = 8):
        self.cy -= h

    def build(self) -> bytes:
        self.finish_page()
        return assemble_pdf(self.pages, _W, _H)


def _col_positions(widths: list[float]) -> list[float]:
    positions = []
    x = _PAD
    for w in widths:
        positions.append(x)
        x += w
    return positions


def _auto_col_widths(headers: list[str], fixed: dict[str, float] = None) -> list[float]:
    """Compute column widths that fill the usable page width."""
    fixed = fixed or {}
    usable = _W - 2 * _PAD
    fixed_w = sum(fixed.get(h, 0) for h in headers)
    flex_headers = [h for h in headers if h not in fixed]
    flex_each = max(50, (usable - fixed_w) / max(1, len(flex_headers)))
    widths = [fixed.get(h, flex_each) for h in headers]
    total = sum(widths)
    if total > usable:
        scale = usable / total
        widths = [w * scale for w in widths]
    return widths


def export_pdf(document: dict, paper: str = DEFAULT_PAPER) -> bytes:
    """Export the document as a multi-page PDF on *paper* (see PAPERS;
    unknown names fall back to A4 landscape).  Returns raw PDF bytes."""
    global _W, _H
    saved = (_W, _H)
    _W, _H = PAPERS.get(paper or DEFAULT_PAPER, PAPERS[DEFAULT_PAPER])
    try:
        return _export_pdf(document)
    finally:
        _W, _H = saved


def _export_pdf(document: dict) -> bytes:
    show_name = document.get("show_name", "Untitled")
    date = document.get("date", "")
    sections = document.get("sections", {})

    pdf = _PdfBuilder(document.get("title") or "Show Book", show_name, date)
    pdf.new_page()

    # ── Tech rider / stage plot / crew checklist (Show Paperwork) ─────────
    if "rider" in sections:
        _pdf_rider(pdf, sections["rider"], show_name, date)
    if "checklist" in sections:
        _pdf_checklist(pdf, sections["checklist"])
    if "stage_plan" in sections:
        _pdf_stage_plan(pdf, sections["stage_plan"], show_name, date)

    # ── Cover / Summary ───────────────────────────────────────────────────
    if "summary" in sections:
        _pdf_summary(pdf, sections["summary"], show_name, date)

    # ── Patch List ────────────────────────────────────────────────────────
    if "patch" in sections:
        _pdf_patch(pdf, sections["patch"])

    # ── Function Index ────────────────────────────────────────────────────
    if "functions" in sections:
        _pdf_functions(pdf, sections["functions"])

    # ── Scenes ────────────────────────────────────────────────────────────
    if sections.get("scenes"):
        _pdf_scenes(pdf, sections["scenes"])

    # ── Chasers ───────────────────────────────────────────────────────────
    if sections.get("chasers"):
        _pdf_chasers(pdf, sections["chasers"])

    # ── Collections ───────────────────────────────────────────────────────
    if sections.get("collections"):
        _pdf_collections(pdf, sections["collections"])

    # ── EFX ───────────────────────────────────────────────────────────────
    if sections.get("efx"):
        _pdf_efx(pdf, sections["efx"])

    # ── Shows / Scripts ───────────────────────────────────────────────────
    if "shows" in sections and sections["shows"]:
        _pdf_shows(pdf, sections["shows"])
    if "scripts" in sections and sections["scripts"]:
        _pdf_scripts(pdf, sections["scripts"])

    # ── VC Layout ─────────────────────────────────────────────────────────
    if "vc_layout" in sections:
        _pdf_vc(pdf, sections["vc_layout"])

    # ── Doctor ────────────────────────────────────────────────────────────
    if "doctor" in sections:
        _pdf_doctor(pdf, sections["doctor"])

    return pdf.build()


def _pdf_rider(pdf: _PdfBuilder, rider: dict, show_name: str, date: str):
    """Tech rider: fixture types and totals (nothing about the show itself)."""
    pdf.section_heading("Lighting - fixtures we bring / need")
    headers = ["Manufacturer", "Model", "Mode", "Qty", "Ch", "Patch range", "Universe(s)"]
    col_w = _auto_col_widths(headers, {"Qty": 35, "Ch": 35, "Universe(s)": 70, "Patch range": 110})
    pdf.table_header(headers, col_w)
    for i, t in enumerate(rider["types"]):
        pdf.table_row([t["manufacturer"], t["model"], t["mode"], t["quantity"], t["channels"] or "",
                       t["patch_range"], ", ".join(str(u) for u in t["universes"])], col_w, i)
    pdf.spacer(10)
    pdf.ensure_space(20)
    pdf.fc(*_COL_DARK)
    pdf.txt(_PAD, pdf.cy - 10,
            f"Total: {rider['total_fixtures']} fixture(s), {rider['total_channels']} DMX channel(s), "
            f"{len(rider['universes'])} universe(s).", sz=9, bold=True)
    pdf.cy -= 20


def _pdf_checklist(pdf: _PdfBuilder, rows: list[dict]):
    """Crew checklist: a box to tick per fixture."""
    pdf.section_heading("Load-in checklist")
    headers = ["Done", "ID", "Name", "Model", "Mode", "Patch", "Groups", "3D position"]
    col_w = _auto_col_widths(headers, {"Done": 34, "ID": 30, "Patch": 55, "Mode": 70,
                                       "3D position": 110})
    pdf.table_header(headers, col_w)
    for i, c in enumerate(rows):
        pdf.table_row(["[ ]", c["id"], c["name"], c["model"], c["mode"], c["patch"],
                       c["groups"], c["position"]], col_w, i)


def _pdf_stage_plan(pdf: _PdfBuilder, plan: dict, show_name: str, date: str):
    """Stage plot on a page of its own (top and front view)."""
    from core.pdf import blueprint_stream
    stream = blueprint_stream(plan["fixtures"], show_name=show_name, doc_date=date, W=_W, H=_H)
    if stream is None:
        pdf.section_heading("Stage plot")
        pdf.fc(*_COL_DARK)
        pdf.txt(_PAD, pdf.cy - 12, "No fixture has a 3D position in this show - place them in "
                "QLC+'s 3D view or in Stage & Meshes.", sz=9)
        pdf.cy -= 20
        return
    if pdf.cy >= _H - _TITLE_H - 6:          # only the header on this page: drop it
        pdf.ops.clear()
        pdf.page_num -= 1
    pdf.finish_page()
    pdf.pages.append(stream)
    pdf.page_num += 1
    pdf.cy = 0                               # whatever follows starts a new page


def _pdf_summary(pdf: _PdfBuilder, summary: dict, show_name: str, date: str):
    """Render the cover / summary section."""
    # Big title
    pdf.spacer(40)
    pdf.fc(*_COL_ACCENT)
    pdf.txt(_PAD + 20, pdf.cy, show_name, sz=22, bold=True)
    pdf.cy -= 30
    pdf.fc(0.4, 0.4, 0.4)
    pdf.txt(_PAD + 20, pdf.cy, f"Show Book  |  {date}", sz=12)
    pdf.cy -= 40

    # Stats
    stats = [
        ("Fixtures", summary.get("fixture_count", 0)),
        ("Functions", summary.get("function_count", 0)),
        ("VC Widgets", f"{summary.get('vc_widget_count', 0)} on "
                       f"{summary.get('vc_page_count', 0)} page(s)"),
        ("Universes", summary.get("universe_count", 0)),
    ]
    pdf.fc(0, 0, 0)
    for label, value in stats:
        pdf.txt(_PAD + 30, pdf.cy, f"{label}:", sz=10, bold=True)
        pdf.txt(_PAD + 140, pdf.cy, str(value), sz=10)
        pdf.cy -= 18

    # Function type breakdown
    pdf.spacer(10)
    pdf.txt(_PAD + 30, pdf.cy, "Functions by type:", sz=10, bold=True)
    pdf.cy -= 16
    for ftype, count in sorted(summary.get("function_types", {}).items()):
        pdf.fc(0.3, 0.3, 0.3)
        pdf.txt(_PAD + 50, pdf.cy, f"{ftype}: {count}", sz=9)
        pdf.cy -= 14


def _pdf_patch(pdf: _PdfBuilder, patch: list[dict]):
    """Render the fixture patch list."""
    pdf.section_heading("Fixture Patch List")
    headers = ["ID", "Name", "Model", "Mode", "Patch", "Groups"]
    fixed = {"ID": 35, "Patch": 60, "Mode": 80}
    col_w = _auto_col_widths(headers, fixed)
    pdf.table_header(headers, col_w)
    for i, p in enumerate(patch):
        pdf.table_row([p["id"], p["name"], p["model"], p["mode"],
                       p["patch"], p["groups"]], col_w, i)


def _pdf_functions(pdf: _PdfBuilder, functions: list[dict]):
    """Render the function index (with dictionary description when available)."""
    pdf.section_heading("Function Index")
    has_desc = any(f.get("description") for f in functions)
    if has_desc:
        headers = ["ID", "Name", "Type", "Description"]
        fixed = {"ID": 40, "Type": 90}
    else:
        headers = ["ID", "Name", "Type"]
        fixed = {"ID": 40, "Type": 90}
    col_w = _auto_col_widths(headers, fixed)
    pdf.table_header(headers, col_w)
    for i, f in enumerate(functions):
        row = [f["id"], f["name"], f["type"]]
        if has_desc:
            row.append(f.get("description", ""))
        pdf.table_row(row, col_w, i)


def _pdf_scenes(pdf: _PdfBuilder, scenes: list[dict]):
    """Render scene details with decoded DMX values."""
    pdf.section_heading("Scene Details")

    for scene in scenes:
        pdf.ensure_space(40)
        pdf.fc(*_COL_ACCENT)
        label = f"Scene #{scene['id']}: {scene['name']}"
        if scene.get("description"):
            label += f"  — {scene['description']}"
        pdf.txt(_PAD + 4, pdf.cy - 11, label, sz=9, bold=True)
        pdf.cy -= 16

        for fx_group in scene.get("fixtures", []):
            pdf.ensure_space(30)
            pdf.fc(0.3, 0.3, 0.3)
            pdf.txt(_PAD + 10, pdf.cy - 10,
                    f"{fx_group['fixture_name']} ({fx_group['fixture_model']})",
                    sz=8, bold=True)
            pdf.cy -= 13

            headers = ["Ch#", "Channel", "Raw", "Decoded"]
            fixed = {"Ch#": 30, "Raw": 35}
            col_w = _auto_col_widths(headers, fixed)
            pdf.table_header(headers, col_w)

            for ci, ch in enumerate(fx_group.get("channels", [])):
                pdf.table_row([
                    str(ch["channel_index"]),
                    ch["channel_name"],
                    str(ch["raw_value"]),
                    ch["decoded"],
                ], col_w, ci)

            pdf.spacer(6)

        pdf.spacer(4)


def _pdf_chasers(pdf: _PdfBuilder, chasers: list[dict]):
    """Render chaser details."""
    pdf.section_heading("Chaser Details")

    for chaser in chasers:
        pdf.ensure_space(40)
        pdf.fc(*_COL_ACCENT)
        pdf.txt(_PAD + 4, pdf.cy - 11,
                f"Chaser #{chaser['id']}: {chaser['name']}  "
                f"[{chaser['direction']} / {chaser['run_order']}]",
                sz=9, bold=True)
        pdf.cy -= 16

        headers = ["Step", "Function", "Fade In", "Hold", "Fade Out", "Duration"]
        fixed = {"Step": 35, "Fade In": 60, "Hold": 55, "Fade Out": 60, "Duration": 60}
        col_w = _auto_col_widths(headers, fixed)
        pdf.table_header(headers, col_w)

        for si, step in enumerate(chaser.get("steps", [])):
            pdf.table_row([
                step["number"],
                step["function_name"],
                step["fade_in"],
                step["hold"],
                step["fade_out"],
                step["duration"],
            ], col_w, si)

        pdf.spacer(6)


def _pdf_collections(pdf: _PdfBuilder, collections: list[dict]):
    """Render collection details."""
    pdf.section_heading("Collection Details")

    for coll in collections:
        pdf.ensure_space(30)
        pdf.fc(*_COL_ACCENT)
        pdf.txt(_PAD + 4, pdf.cy - 11,
                f"Collection #{coll['id']}: {coll['name']}",
                sz=9, bold=True)
        pdf.cy -= 16

        headers = ["#", "Function ID", "Function Name"]
        fixed = {"#": 30, "Function ID": 60}
        col_w = _auto_col_widths(headers, fixed)
        pdf.table_header(headers, col_w)

        for mi, member in enumerate(coll.get("members", [])):
            pdf.table_row([
                str(mi + 1),
                member["function_id"],
                member["function_name"],
            ], col_w, mi)

        pdf.spacer(4)


def _pdf_efx(pdf: _PdfBuilder, efx_list: list[dict]):
    """Render EFX details."""
    pdf.section_heading("EFX Details")

    for efx in efx_list:
        pdf.ensure_space(30)
        pdf.fc(*_COL_ACCENT)
        pdf.txt(_PAD + 4, pdf.cy - 11,
                f"EFX #{efx['id']}: {efx['name']}  [{efx['algorithm']}]",
                sz=9, bold=True)
        pdf.cy -= 16

        headers = ["Fixture ID", "Fixture Name"]
        fixed = {"Fixture ID": 60}
        col_w = _auto_col_widths(headers, fixed)
        pdf.table_header(headers, col_w)

        for fi, fx in enumerate(efx.get("fixtures", [])):
            pdf.table_row([fx["fixture_id"], fx["fixture_name"]], col_w, fi)

        pdf.spacer(4)


def _pdf_vc(pdf: _PdfBuilder, layout: dict):
    """VC layout: one sub-table per page, frames indented."""
    pdf.section_heading("Virtual Console Layout")
    headers = ["ID", "Type", "Caption", "Position / size", "Function", "Key / MIDI"]
    fixed = {"ID": 35, "Type": 60, "Position / size": 105}
    col_w = _auto_col_widths(headers, fixed)
    for pg in layout.get("pages", []):
        pdf.ensure_space(40)
        pdf.fc(*_COL_ACCENT)
        pdf.txt(_PAD, pdf.cy - 12, f"Page: {pg['caption']}"
                + (f"   ({pg['size']} px, {len(pg['widgets'])} widgets)" if pg["size"] else ""),
                sz=10, bold=True)
        pdf.cy -= 18
        pdf.table_header(headers, col_w)
        for wi, w in enumerate(pg["widgets"]):
            pos = f"{w['x']},{w['y']}  {w['w']}x{w['h']}" if w["w"] else ""
            fn = f"{w['function_id']} {w['function_name']}".strip()
            pdf.table_row([w["id"], w["type"], "» " * w["depth"] + w["caption"], pos, fn,
                           w["bindings"]], col_w, wi)
        pdf.spacer(8)


def _pdf_shows(pdf: _PdfBuilder, shows: list[dict]):
    pdf.section_heading("Shows")
    headers = ["Show", "Track", "Function", "Start", "Duration"]
    col_w = _auto_col_widths(headers, {"Start": 70, "Duration": 70})
    pdf.table_header(headers, col_w)
    i = 0
    for sh in shows:
        for tr in sh["tracks"]:
            for sf in tr["show_functions"]:
                pdf.table_row([f"{sh['id']} {sh['name']}", tr["name"],
                               f"{sf['function_id']} {sf['function_name']}",
                               sf["start_time"], sf["duration"]], col_w, i)
                i += 1


def _pdf_scripts(pdf: _PdfBuilder, scripts: list[dict]):
    pdf.section_heading("Scripts")
    headers = ["Script", "Line", "Command"]
    col_w = _auto_col_widths(headers, {"Line": 35})
    pdf.table_header(headers, col_w)
    i = 0
    for sc in scripts:
        for n, cmd in enumerate(sc["commands"]):
            pdf.table_row([f"{sc['id']} {sc['name']}", str(n + 1), cmd], col_w, i)
            i += 1


def _pdf_doctor(pdf: _PdfBuilder, doc: dict):
    pdf.section_heading("Workspace Doctor")
    pdf.fc(0, 0, 0)
    pdf.txt(_PAD + 6, pdf.cy - 12, f"{doc['errors']} error(s), {doc['warnings']} warning(s), "
            f"{doc['info']} info finding(s).", sz=9, bold=True)
    pdf.cy -= 20
    if not doc["findings"]:
        return
    headers = ["Code", "Severity", "Location", "Message"]
    col_w = _auto_col_widths(headers, {"Code": 40, "Severity": 55})
    pdf.table_header(headers, col_w)
    for i, f in enumerate(doc["findings"]):
        pdf.table_row([f["code"], f["severity"], f["location"], f["message"]], col_w, i)
