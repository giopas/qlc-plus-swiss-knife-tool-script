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
]

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate(sections: list[str] | None = None,
             qxf_dir: str | None = None) -> dict:
    """Build a structured document from the loaded workspace.

    Parameters
    ----------
    sections : list[str] or None
        Which sections to include.  None or empty means all.
    qxf_dir : str or None
        Optional directory to scan for .qxf files (for value decoding).
        If None, uses whatever QXF defs are already loaded.

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
    if sections is None or len(sections) == 0:
        sections = list(ALL_SECTIONS)

    # Load QXF definitions if a directory is provided
    if qxf_dir and os.path.isdir(qxf_dir):
        _load_qxf_dir(qxf_dir)

    # Build QXF lookup for value decoding
    qxf_lookup = _build_qxf_lookup()

    # Derive show name from filename
    show_name = state.get("original_name") or os.path.basename(state.get("path", "Untitled"))
    if show_name.endswith(".qxw"):
        show_name = show_name[:-4]

    doc = {
        "show_name": show_name,
        "date": datetime.date.today().isoformat(),
        "sections": {},
    }

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
        doc["sections"]["vc_layout"] = _build_vc_layout(state)

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
    vc_count = len(state.get("vc_widgets", []))

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
            "model": info.get("model", "Unknown"),
            "mode": info.get("mode", "Default"),
            "universe": info.get("universe", 0),
            "address": info.get("address", 0),
            "patch": info.get("patch", ""),
            "groups": info.get("groups", ""),
        })
    rows.sort(key=lambda r: (r["universe"], r["address"]))
    return rows


def _build_function_index(state: dict) -> list[dict]:
    """Function summary table, sorted by ID."""
    rows = []
    for fid, info in state.get("func_detailed", {}).items():
        rows.append({
            "id": fid,
            "name": info.get("name", ""),
            "type": info.get("type", ""),
        })
    rows.sort(key=lambda r: int(r["id"]) if r["id"].isdigit() else 0)
    return rows


def _build_scenes(root: ET.Element, state: dict,
                  qxf_lookup: dict) -> list[dict]:
    """Detailed scene breakdown with decoded DMX values."""
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
            "fixtures": channels,
        })

    scenes.sort(key=lambda s: int(s["id"]) if s["id"].isdigit() else 0)
    return scenes


def _build_chasers(root: ET.Element, state: dict) -> list[dict]:
    """Chaser details with steps and timing."""
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


def _build_vc_layout(state: dict) -> list[dict]:
    """Virtual Console widget overview."""
    widgets = state.get("vc_widgets", [])
    rows = []
    for w in widgets:
        rows.append({
            "id": w.get("id", ""),
            "type": w.get("type", ""),
            "caption": w.get("caption", ""),
            "function_id": w.get("func_id", ""),
            "function_name": w.get("func_name", ""),
            "frame": w.get("frame_path", ""),
        })
    rows.sort(key=lambda r: int(r["id"]) if r["id"].isdigit() else 0)
    return rows


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

        if "vc_layout" in sections:
            zf.writestr("vc_layout.csv", _csv_vc(sections["vc_layout"]))

        # Summary as a simple text file
        if "summary" in sections:
            zf.writestr("summary.txt", _txt_summary(document))

    return buf.getvalue()


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
    headers = ["ID", "Name", "Type"]
    rows = [[f["id"], f["name"], f["type"]] for f in functions]
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


def _csv_vc(widgets: list[dict]) -> str:
    headers = ["Widget ID", "Type", "Caption",
               "Function ID", "Function Name", "Frame Path"]
    rows = [[w["id"], w["type"], w["caption"],
             w["function_id"], w["function_name"],
             w["frame"]] for w in widgets]
    return _csv_write(rows, headers)


def _txt_summary(document: dict) -> str:
    s = document["sections"].get("summary", {})
    lines = [
        f"Show Book: {document['show_name']}",
        f"Date: {document['date']}",
        "",
        f"Fixtures: {s.get('fixture_count', 0)}",
        f"Functions: {s.get('function_count', 0)}",
        f"VC Widgets: {s.get('vc_widget_count', 0)}",
        f"Universes: {s.get('universe_count', 0)} ({', '.join(str(u) for u in s.get('universes', []))})",
        "",
        "Functions by type:",
    ]
    for ftype, count in sorted(s.get("function_types", {}).items()):
        lines.append(f"  {ftype}: {count}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

# Re-use the raw PDF primitives from core.pdf
from core.pdf import assemble_pdf, _pdf_str

# Page dimensions (points)
_W = 842.0  # A4 landscape width
_H = 595.0  # A4 landscape height
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
        s = _pdf_str(str(s))
        f = "/F2" if bold else "/F1"
        self._emit(f"BT {f} {sz} Tf {x:.2f} {y:.2f} Td ({s}) Tj ET")

    def txt_trunc(self, x, y, s, sz, max_w):
        """Write text, truncating if wider than max_w."""
        s = str(s) if s is not None else ""
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
        self.txt(_W / 2 - 40, _H - _TITLE_H + 12, self.title, sz=9)
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


def export_pdf(document: dict) -> bytes:
    """Export the document as a multi-page PDF.

    Returns raw PDF bytes.
    """
    show_name = document.get("show_name", "Untitled")
    date = document.get("date", "")
    sections = document.get("sections", {})

    pdf = _PdfBuilder("Show Book", show_name, date)
    pdf.new_page()

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
    if "scenes" in sections:
        _pdf_scenes(pdf, sections["scenes"])

    # ── Chasers ───────────────────────────────────────────────────────────
    if "chasers" in sections:
        _pdf_chasers(pdf, sections["chasers"])

    # ── Collections ───────────────────────────────────────────────────────
    if "collections" in sections:
        _pdf_collections(pdf, sections["collections"])

    # ── EFX ───────────────────────────────────────────────────────────────
    if "efx" in sections:
        _pdf_efx(pdf, sections["efx"])

    # ── VC Layout ─────────────────────────────────────────────────────────
    if "vc_layout" in sections:
        _pdf_vc(pdf, sections["vc_layout"])

    return pdf.build()


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
        ("VC Widgets", summary.get("vc_widget_count", 0)),
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
    """Render the function index."""
    pdf.section_heading("Function Index")
    headers = ["ID", "Name", "Type"]
    fixed = {"ID": 40, "Type": 90}
    col_w = _auto_col_widths(headers, fixed)
    pdf.table_header(headers, col_w)
    for i, f in enumerate(functions):
        pdf.table_row([f["id"], f["name"], f["type"]], col_w, i)


def _pdf_scenes(pdf: _PdfBuilder, scenes: list[dict]):
    """Render scene details with decoded DMX values."""
    pdf.section_heading("Scene Details")

    for scene in scenes:
        pdf.ensure_space(40)
        pdf.fc(*_COL_ACCENT)
        pdf.txt(_PAD + 4, pdf.cy, f"Scene #{scene['id']}: {scene['name']}",
                sz=9, bold=True)
        pdf.cy -= 14

        for fx_group in scene.get("fixtures", []):
            pdf.ensure_space(30)
            pdf.fc(0.3, 0.3, 0.3)
            pdf.txt(_PAD + 10, pdf.cy,
                    f"{fx_group['fixture_name']} ({fx_group['fixture_model']})",
                    sz=8, bold=True)
            pdf.cy -= 12

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
        pdf.txt(_PAD + 4, pdf.cy,
                f"Chaser #{chaser['id']}: {chaser['name']}  "
                f"[{chaser['direction']} / {chaser['run_order']}]",
                sz=9, bold=True)
        pdf.cy -= 14

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
        pdf.txt(_PAD + 4, pdf.cy,
                f"Collection #{coll['id']}: {coll['name']}",
                sz=9, bold=True)
        pdf.cy -= 14

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
        pdf.txt(_PAD + 4, pdf.cy,
                f"EFX #{efx['id']}: {efx['name']}  [{efx['algorithm']}]",
                sz=9, bold=True)
        pdf.cy -= 14

        headers = ["Fixture ID", "Fixture Name"]
        fixed = {"Fixture ID": 60}
        col_w = _auto_col_widths(headers, fixed)
        pdf.table_header(headers, col_w)

        for fi, fx in enumerate(efx.get("fixtures", [])):
            pdf.table_row([fx["fixture_id"], fx["fixture_name"]], col_w, fi)

        pdf.spacer(4)


def _pdf_vc(pdf: _PdfBuilder, widgets: list[dict]):
    """Render VC layout table."""
    pdf.section_heading("Virtual Console Layout")

    headers = ["ID", "Type", "Caption", "Func ID", "Function", "Frame"]
    fixed = {"ID": 35, "Type": 65, "Func ID": 45}
    col_w = _auto_col_widths(headers, fixed)
    pdf.table_header(headers, col_w)

    for wi, w in enumerate(widgets):
        pdf.table_row([
            w["id"], w["type"], w["caption"],
            w["function_id"], w["function_name"], w["frame"],
        ], col_w, wi)
