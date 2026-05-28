"""
core/fixture.py — Fixture Configurator state & QXW generation

Public API
----------
State access
  get_rig()               → list[dict]
  get_qxf_defs()          → dict
  get_stage_dims()        → dict  {w_mm, d_mm, h_mm}
  set_stage_dims(w, d, h)

QXF loading
  load_qxf(path)          → dict  (the parsed definition)

Rig management
  add_fixture(entry)      → int   (new index)
  update_fixture(idx, patch)
  remove_fixture(idx)
  move_fixture(idx, direction)   direction = -1 or +1
  clear_rig()

Workspace import
  import_from_qxw(qxw_root)     populates rig from an existing workspace

DMX
  auto_assign_dmx()

QXW generation
  build_qxw(template_path=None, qxw_root=None) → bytes  (XML content)

Helpers
  mm_to_grid(x_mm, z_mm, cols, rows, stage_w_mm, stage_d_mm) → str
  snap_to_grid(x_mm, z_mm, cols, rows, stage_w_mm, stage_d_mm) → (x, z)
"""

import copy
import datetime
import xml.etree.ElementTree as ET

QLC_NS_URI = "http://www.qlcplus.org/Workspace"
QXF_NS_URI = "http://www.qlcplus.org/FixtureDefinition"
NS  = {"q": QLC_NS_URI}

COLOR_PALETTE = [
    "#00e5ff", "#ff007f", "#39ff14", "#ffff00",
    "#ff8c00", "#b026ff", "#ff3333",
]

HEIGHT_ROLE_NAMES = ["Floor", "Low-Mid", "Mid", "Top-Mid", "Top"]

# ── Module-level state ────────────────────────────────────────────────────────

_rig: list = []          # list of rig entry dicts
_qxf_defs: dict = {}     # "Manufacturer::Model" → parsed definition dict
_model_colors: dict = {} # "Manufacturer::Model" → hex color

_stage_w_mm: int = 8000
_stage_d_mm: int = 6000
_stage_h_mm: int = 4000
_grid_cols:  int = 8
_grid_rows:  int = 6

# Stored template XML root (ET.Element) – set when a QXW is loaded
_template_root: "ET.Element | None" = None


# ── Stage / grid helpers ──────────────────────────────────────────────────────

def get_stage_dims() -> dict:
    return {"w_mm": _stage_w_mm, "d_mm": _stage_d_mm, "h_mm": _stage_h_mm,
            "cols": _grid_cols, "rows": _grid_rows}


def set_stage_dims(w_mm: int, d_mm: int, h_mm: int,
                   cols: int = 8, rows: int = 6):
    global _stage_w_mm, _stage_d_mm, _stage_h_mm, _grid_cols, _grid_rows
    _stage_w_mm = max(500, int(w_mm))
    _stage_d_mm = max(500, int(d_mm))
    _stage_h_mm = max(200, int(h_mm))
    _grid_cols  = max(2, int(cols))
    _grid_rows  = max(2, int(rows))


def _height_tiers() -> list:
    """Five evenly-spaced Y tiers from 0 to stage_h_mm."""
    n = len(HEIGHT_ROLE_NAMES)
    return [int(_stage_h_mm * i / (n - 1)) for i in range(n)]


def mm_to_grid(x_mm: float, z_mm: float,
               cols: int = None, rows: int = None,
               stage_w_mm: int = None, stage_d_mm: int = None) -> str:
    """Return grid intersection label e.g. 'C3' for the given mm position."""
    c  = cols       if cols       is not None else _grid_cols
    r  = rows       if rows       is not None else _grid_rows
    sw = stage_w_mm if stage_w_mm is not None else _stage_w_mm
    sd = stage_d_mm if stage_d_mm is not None else _stage_d_mm
    col_idx = round(x_mm / sw * c) if sw > 0 else 0
    row_idx = round(z_mm / sd * r) if sd > 0 else 0
    col_idx = max(0, min(c, col_idx))
    row_idx = max(0, min(r, row_idx))
    col_lbl = chr(ord("A") + col_idx)
    row_lbl = str(r - row_idx + 1)   # row 1 = downstage (high Z), row N = upstage
    return f"{col_lbl}{row_lbl}"


def snap_to_grid(x_mm: float, z_mm: float,
                 cols: int = None, rows: int = None,
                 stage_w_mm: int = None, stage_d_mm: int = None):
    """Snap mm position to the nearest grid intersection."""
    c  = cols       if cols       is not None else _grid_cols
    r  = rows       if rows       is not None else _grid_rows
    sw = stage_w_mm if stage_w_mm is not None else _stage_w_mm
    sd = stage_d_mm if stage_d_mm is not None else _stage_d_mm
    if sw > 0 and c > 0:
        cell_w = sw / c
        x_mm = round(x_mm / cell_w) * cell_w
    if sd > 0 and r > 0:
        cell_d = sd / r
        z_mm = round(z_mm / cell_d) * cell_d
    return int(max(0, min(sw, x_mm))), int(max(0, min(sd, z_mm)))


def mm_to_height_role(y_mm: float) -> str:
    tiers = _height_tiers()
    min_d = float("inf")
    best  = HEIGHT_ROLE_NAMES[0]
    for i, t in enumerate(tiers):
        d = abs(y_mm - t)
        if d < min_d:
            min_d = d
            best  = HEIGHT_ROLE_NAMES[i]
    return best


# ── Role helpers ─────────────────────────────────────────────────────────────

_ROLE_KEYS = [
    "Front Left", "Front Center", "Front Right",
    "Back Left",  "Back Center",  "Back Right",
    "Side Left",  "Side Right",   "Center",
    "Wing Left",  "Wing Right",
    "Ceiling",    "Floor",
    "Wash",       "Spot",         "Strobe",
    "Fill",       "Key",          "Backlight",
]


def _extract_role_from_name(name: str) -> str:
    """
    Try to derive a meaningful role string from the fixture name.
    Returns the matched role keyword or 'Custom' if none found.
    """
    nu = name.upper()
    for rk in _ROLE_KEYS:
        if rk.upper() in nu:
            return rk
    return "Custom"


# ── Color assignment ──────────────────────────────────────────────────────────

def _get_model_color(key: str) -> str:
    if key not in _model_colors:
        _model_colors[key] = COLOR_PALETTE[len(_model_colors) % len(COLOR_PALETTE)]
    return _model_colors[key]


# ── Rig access ────────────────────────────────────────────────────────────────

def get_rig() -> list:
    return list(_rig)


def get_qxf_defs() -> dict:
    return dict(_qxf_defs)


def clear_rig():
    global _rig, _qxf_defs, _model_colors
    _rig = []
    _qxf_defs = {}
    _model_colors = {}


# ── QXF parsing ───────────────────────────────────────────────────────────────

def load_qxf(path: str) -> dict:
    """
    Parse a .qxf fixture definition file and store its definition.

    Returns the parsed definition dict.
    Raises ValueError if the file is not a valid QXF.
    """
    ns = {"f": QXF_NS_URI}
    tree = ET.parse(path)
    root = tree.getroot()

    if QXF_NS_URI not in (root.tag or ""):
        raise ValueError(
            f"Not a valid QXF file. Expected namespace '{QXF_NS_URI}', "
            f"got: '{root.tag}'"
        )

    mfg   = root.findtext("f:Manufacturer", default="Unknown", namespaces=ns)
    model = root.findtext("f:Model",        default="Unknown", namespaces=ns)
    ftype = root.findtext("f:Type",         default="Color Changer", namespaces=ns)

    modes = {}
    for mode_el in root.findall("f:Mode", ns):
        mname    = mode_el.get("Name", "Default")
        ch_count = len(mode_el.findall("f:Channel", ns))
        modes[mname] = ch_count

    channels = [ch.get("Name", "?") for ch in root.findall("f:Channel", ns)]

    key = f"{mfg}::{model}"
    _qxf_defs[key] = {
        "manufacturer": mfg,
        "model":        model,
        "type":         ftype,
        "modes":        modes,
        "channels":     channels,
        "path":         path,
    }
    _get_model_color(key)
    return _qxf_defs[key]


# ── Rig management ────────────────────────────────────────────────────────────

def add_fixture(entry: dict) -> int:
    """
    Add a fixture entry to the rig. Returns the new index.

    Required keys: manufacturer, model, mode, ch_count, name,
                   universe (0-indexed), address (0-indexed),
                   x_mm, z_mm, y_mm
    Optional keys: role (defaults to "Custom")
    """
    e = dict(entry)
    e.setdefault("role", "Custom")
    key = f"{e.get('manufacturer','Unknown')}::{e.get('model','Unknown')}"
    e["key"]   = key
    e["color"] = _get_model_color(key)
    # Register in qxf_defs if unknown
    if key not in _qxf_defs:
        _qxf_defs[key] = {
            "manufacturer": e.get("manufacturer", "Unknown"),
            "model":        e.get("model", "Unknown"),
            "type":         "Color Changer",
            "modes":        {e.get("mode", "Default"): e.get("ch_count", 1)},
            "channels":     [],
            "path":         "",
        }
    _rig.append(e)
    return len(_rig) - 1


def update_fixture(idx: int, patch: dict):
    """Merge patch into rig[idx]."""
    if 0 <= idx < len(_rig):
        _rig[idx].update(patch)


def remove_fixture(idx: int):
    if 0 <= idx < len(_rig):
        _rig.pop(idx)


def move_fixture(idx: int, direction: int):
    new_idx = idx + direction
    if 0 <= idx < len(_rig) and 0 <= new_idx < len(_rig):
        _rig[idx], _rig[new_idx] = _rig[new_idx], _rig[idx]


# ── Import from QXW ───────────────────────────────────────────────────────────

def import_from_qxw(qxw_root: "ET.Element"):
    """
    Read Fixture elements from a QXW root and populate the rig.
    Merges — won't duplicate fixtures already present (matched by name+address+universe).
    Also reads stage dimensions from Monitor/Grid.
    """
    global _stage_w_mm, _stage_d_mm, _stage_h_mm, _template_root

    if qxw_root is None:
        return

    _template_root = qxw_root

    # Stage dims from Monitor/Grid
    grid = qxw_root.find('.//q:Monitor/q:Grid', NS)
    if grid is not None:
        units = int(grid.get('Units', '0'))
        try:
            w = float(grid.get('Width',  str(_stage_w_mm // 1000)))
            d = float(grid.get('Depth',  str(_stage_d_mm // 1000)))
            h = float(grid.get('Height', str(_stage_h_mm // 1000)))
            if units == 1:  # feet
                _stage_w_mm = int(w * 304.8)
                _stage_d_mm = int(d * 304.8)
                _stage_h_mm = int(h * 304.8)
            else:           # metres
                _stage_w_mm = int(w * 1000)
                _stage_d_mm = int(d * 1000)
                _stage_h_mm = int(h * 1000)
        except (ValueError, TypeError):
            pass

    # 3-D positions from Monitor/FxItem
    monitor_pos = {}
    for fxi in qxw_root.findall(".//q:Monitor/q:FxItem", NS):
        fid = fxi.get("ID")
        monitor_pos[fid] = {
            "x": float(fxi.get("XPos", "0")),
            "y": float(fxi.get("YPos", "0")),
            "z": float(fxi.get("ZPos", "0")),
        }

    existing_keys = {(e["name"], e["address"], e["universe"]) for e in _rig}

    for fix in qxw_root.findall("q:Engine/q:Fixture", NS):
        id_node  = fix.find("q:ID",           NS)
        fid      = id_node.text if id_node is not None else None
        name_n   = fix.find("q:Name",         NS)
        name     = (name_n.text or "").strip() if name_n is not None else f"Fixture {fid}"
        mfg_n    = fix.find("q:Manufacturer", NS)
        mfg      = mfg_n.text if mfg_n is not None else "Unknown"
        model_n  = fix.find("q:Model",        NS)
        model    = model_n.text if model_n is not None else "Unknown"
        mode_n   = fix.find("q:Mode",         NS)
        mode     = mode_n.text if mode_n is not None else "Default"
        uni_n    = fix.find("q:Universe",      NS)
        universe = max(0, min(255, int(uni_n.text))) if uni_n is not None else 0
        addr_n   = fix.find("q:Address",      NS)
        address  = max(0, min(511, int(addr_n.text))) if addr_n is not None else 0
        ch_n     = fix.find("q:Channels",     NS)
        ch_count = max(1, min(512, int(ch_n.text))) if ch_n is not None else 7

        if (name, address, universe) in existing_keys:
            continue

        pos = monitor_pos.get(fid, {"x": 0.0, "y": 0.0, "z": 0.0})
        key = f"{mfg}::{model}"

        if key not in _qxf_defs:
            _qxf_defs[key] = {
                "manufacturer": mfg,
                "model":        model,
                "type":         "Color Changer",
                "modes":        {mode: ch_count},
                "channels":     [],
                "path":         "",
            }
        else:
            if mode not in _qxf_defs[key]["modes"]:
                _qxf_defs[key]["modes"][mode] = ch_count

        entry = {
            "key":          key,
            "manufacturer": mfg,
            "model":        model,
            "mode":         mode,
            "ch_count":     ch_count,
            "name":         name,
            "role":         _extract_role_from_name(name),
            "universe":     universe,
            "address":      address,
            "x_mm":         int(pos["x"]),
            "z_mm":         int(pos["z"]),
            "y_mm":         int(pos["y"]),
            "color":        _get_model_color(key),
        }
        _rig.append(entry)
        existing_keys.add((name, address, universe))


# ── Auto-DMX ──────────────────────────────────────────────────────────────────

def auto_assign_dmx():
    """Re-assign DMX addresses sequentially within each universe."""
    by_uni: dict = {}
    for e in _rig:
        by_uni.setdefault(e["universe"], []).append(e)
    for entries in by_uni.values():
        addr = 0
        for e in entries:
            e["address"] = addr
            addr += e["ch_count"]


# ── Function assignment (default) ─────────────────────────────────────────────

def _build_default_assignments(template_root: "ET.Element") -> dict:
    """
    Build a map: func_id → list of rig indices (ordered by slot, extras appended).
    Mirrors the logic in FixtureConfiguratorTab._build_default_assignments.
    """
    if not _rig or template_root is None:
        return {}

    # Template fixture info map: id → {name, x, z}
    tmpl_info = {}
    for fix in template_root.findall('q:Engine/q:Fixture', NS):
        fid_n = fix.find('q:ID', NS)
        fid   = fid_n.text if fid_n is not None else fix.get('ID')
        name_n = fix.find('q:Name', NS)
        name   = (name_n.text or '').strip() if name_n is not None else ''
        tmpl_info[fid] = {'name': name, 'x': 0.0, 'z': 0.0}
    for fxi in template_root.findall('.//q:Monitor/q:FxItem', NS):
        fid = fxi.get('ID')
        if fid in tmpl_info:
            tmpl_info[fid]['x'] = float(fxi.get('XPos', 0))
            tmpl_info[fid]['z'] = float(fxi.get('ZPos', 0))

    rig_by_name = {e['name']: i for i, e in enumerate(_rig)}
    rig_by_role: dict = {}
    for i, e in enumerate(_rig):
        rig_by_role.setdefault(e.get('role', 'Custom'), []).append(i)

    def _closest_unused(tx, tz, used):
        best_i, best_d = -1, float('inf')
        for i, e in enumerate(_rig):
            if i in used:
                continue
            d = ((e['x_mm'] - tx) ** 2 + (e['z_mm'] - tz) ** 2) ** 0.5
            if d < best_d:
                best_d, best_i = d, i
        if best_i == -1:
            for i, e in enumerate(_rig):
                d = ((e['x_mm'] - tx) ** 2 + (e['z_mm'] - tz) ** 2) ** 0.5
                if d < best_d:
                    best_d, best_i = d, i
        return best_i

    assignments = {}
    n_rig = len(_rig)

    for func in template_root.findall('q:Engine/q:Function', NS):
        fid   = func.get('ID')
        ftype = func.get('Type', '')

        slots = []
        if ftype == 'Scene':
            for fv in func.findall('q:FixtureVal', NS):
                sid = fv.get('ID')
                if sid and sid not in slots:
                    slots.append(sid)
        elif ftype == 'RGBMatrix':
            fg = func.find('q:FixtureGroup', NS)
            if fg is not None:
                fg_id = fg.get('ID')
                group_el = template_root.find(
                    f'q:Engine/q:FixtureGroup[@ID="{fg_id}"]', NS)
                if group_el is not None:
                    for head in group_el.findall('q:Head', NS):
                        fid_h = head.get('Fixture')
                        if fid_h and fid_h not in slots:
                            slots.append(fid_h)

        if not slots:
            assignments[fid] = list(range(n_rig))
            continue

        assigned, used = [], set()
        for slot_id in slots:
            info = tmpl_info.get(slot_id, {'name': '', 'x': 0.0, 'z': 0.0})
            t_name, t_x, t_z = info['name'], info['x'], info['z']
            ri = -1

            if t_name and t_name in rig_by_name:
                c = rig_by_name[t_name]
                if c not in used:
                    ri = c

            if ri == -1:
                role = _extract_role_from_name(t_name)
                if role:
                    for c in rig_by_role.get(role, []):
                        if c not in used:
                            ri = c; break

            if ri == -1:
                ri = _closest_unused(t_x, t_z, used)

            if ri == -1:
                ri = len(assigned) % n_rig

            assigned.append(ri)
            used.add(ri)

        for i in range(n_rig):
            if i not in used:
                assigned.append(i)

        assignments[fid] = assigned

    return assignments


# ── QXW generation ────────────────────────────────────────────────────────────

def build_qxw(template_root: "ET.Element" = None,
              func_assignments: dict = None) -> bytes:
    """
    Rebuild the Engine's Fixture / FixtureGroup blocks from the current rig
    and adapt all Function FixtureVal entries.

    Parameters
    ----------
    template_root : ET.Element | None
        Deep-copied XML root to modify. Falls back to the stored _template_root.
    func_assignments : dict | None
        {func_id: [rig_indices…]}. If None, default assignments are computed.

    Returns
    -------
    bytes
        UTF-8 encoded QXW XML content.
    """
    root = copy.deepcopy(template_root) if template_root is not None else (
           copy.deepcopy(_template_root) if _template_root is not None else None)
    if root is None:
        raise ValueError("No template QXW loaded. Load a workspace first.")
    if not _rig:
        raise ValueError("Rig is empty. Add at least one fixture.")

    if func_assignments is None:
        func_assignments = _build_default_assignments(root)

    engine = root.find("q:Engine", NS)
    if engine is None:
        raise ValueError("Template has no <Engine> element.")

    new_count = len(_rig)
    QWS = QLC_NS_URI

    # 1. Remove old Fixture elements
    for fx in engine.findall("q:Fixture", NS):
        engine.remove(fx)

    # 2. Remove old FixtureGroup elements
    for fg in engine.findall("q:FixtureGroup", NS):
        engine.remove(fg)

    # 3. Insert new Fixture elements
    iom = engine.find("q:InputOutputMap", NS)
    insert_after = (list(engine).index(iom) + 1) if iom is not None else 0

    def _sub(parent, tag, text):
        el = ET.SubElement(parent, f"{{{QWS}}}{tag}")
        el.text = str(text)
        return el

    for i, e in enumerate(_rig):
        fx_el = ET.Element(f"{{{QWS}}}Fixture")
        _sub(fx_el, "Manufacturer", e["manufacturer"])
        _sub(fx_el, "Model",        e["model"])
        _sub(fx_el, "Mode",         e["mode"])
        _sub(fx_el, "ID",           str(i))
        _sub(fx_el, "Name",         e["name"])
        _sub(fx_el, "Universe",     str(e["universe"]))
        _sub(fx_el, "Address",      str(e["address"]))
        _sub(fx_el, "Channels",     str(e["ch_count"]))
        engine.insert(insert_after + i, fx_el)

    # 4. Build FixtureGroup
    fg_el = ET.SubElement(engine, f"{{{QWS}}}FixtureGroup")
    fg_el.set("ID", "0")
    _sub(fg_el, "Name", "")
    size_el = ET.SubElement(fg_el, f"{{{QWS}}}Size")
    size_el.set("X", str(new_count))
    size_el.set("Y", "1")
    for i in range(new_count):
        head_el = ET.SubElement(fg_el, f"{{{QWS}}}Head")
        head_el.set("X", str(i))
        head_el.set("Y", "0")
        head_el.set("Fixture", str(i))
        head_el.text = "0"

    # 5. Adapt Function FixtureVal entries
    for func in engine.findall("q:Function", NS):
        func_id  = func.get("ID")
        old_vals = func.findall("q:FixtureVal", NS)
        if not old_vals:
            continue

        old_slot_vals = []
        for fv in old_vals:
            old_slot_vals.append((int(fv.get("ID", "0")), fv.text or ""))
            func.remove(fv)

        n_slots    = len(old_slot_vals)
        assignment = func_assignments.get(func_id, list(range(new_count)))

        for rig_pos, rig_idx in enumerate(assignment):
            if not (0 <= rig_idx < new_count):
                continue
            tmpl_slot = rig_pos % n_slots if n_slots > 0 else 0
            _, val_text = old_slot_vals[tmpl_slot] if tmpl_slot < len(old_slot_vals) else (0, "")
            fv_new = ET.SubElement(func, f"{{{QWS}}}FixtureVal")
            fv_new.set("ID", str(rig_idx))
            fv_new.text = val_text

    # 6. Update Monitor FxItem positions + stage grid
    monitor = root.find(".//q:Monitor", NS)
    if monitor is not None:
        grid_el = monitor.find(f"{{{QWS}}}Grid")
        if grid_el is None:
            grid_el = ET.SubElement(monitor, f"{{{QWS}}}Grid")
        grid_el.set("Width",  str(int(_stage_w_mm / 1000)))
        grid_el.set("Height", str(int(_stage_h_mm / 1000)))
        grid_el.set("Depth",  str(int(_stage_d_mm / 1000)))
        grid_el.set("Units",  "0")

        for fxi in monitor.findall(f"{{{QWS}}}FxItem"):
            monitor.remove(fxi)
        for i, e in enumerate(_rig):
            fxi = ET.SubElement(monitor, f"{{{QWS}}}FxItem")
            fxi.set("ID",   str(i))
            fxi.set("XPos", str(int(e["x_mm"])))
            fxi.set("YPos", str(int(e.get("y_mm", 0))))
            fxi.set("ZPos", str(int(e["z_mm"])))
            fxi.set("XRot", "65")
            fxi.set("YRot", "0")
            fxi.set("ZRot", "0")

    # 7. Update VC Sliders
    vc = root.find("q:VirtualConsole", NS)
    if vc is not None:
        _update_vc_sliders(vc, new_count)

    xml_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE Workspace>\n' + xml_str).encode("utf-8")


def _update_vc_sliders(vc_node: "ET.Element", new_count: int):
    """Rebuild Level/Channel entries in all VC Sliders to cover new_count fixtures."""
    QWS = QLC_NS_URI
    for slider in vc_node.iter(f"{{{QWS}}}Slider"):
        level_el = slider.find(f"{{{QWS}}}Level")
        if level_el is None:
            continue
        old_channels = level_el.findall(f"{{{QWS}}}Channel")
        if not old_channels:
            continue
        ch_nums = list(dict.fromkeys(
            max(0, min(511, int(ch.get("Channel", ch.text or "0"))))
            for ch in old_channels
        ))
        for ch in old_channels:
            level_el.remove(ch)
        for fix_i in range(new_count):
            for ch_num in ch_nums:
                ch_el = ET.SubElement(level_el, f"{{{QWS}}}Channel")
                ch_el.set("Fixture", str(fix_i))
                ch_el.text = str(ch_num)


# ── Serialise rig to API-friendly dicts ───────────────────────────────────────

def rig_to_api(rig: list = None) -> list:
    """Return rig as list of dicts suitable for JSON serialisation."""
    entries = rig if rig is not None else _rig
    result  = []
    for i, e in enumerate(_rig if rig is None else rig):
        grid = mm_to_grid(e["x_mm"], e["z_mm"])
        result.append({
            "idx":          i,
            "key":          e.get("key", ""),
            "manufacturer": e.get("manufacturer", ""),
            "model":        e.get("model", ""),
            "mode":         e.get("mode", ""),
            "ch_count":     e.get("ch_count", 1),
            "name":         e.get("name", ""),
            "role":         e.get("role", "Custom"),
            "universe":     e.get("universe", 0) + 1,  # 1-indexed for display
            "address":      e.get("address", 0) + 1,   # 1-indexed for display
            "x_mm":         e.get("x_mm", 0),
            "z_mm":         e.get("z_mm", 0),
            "y_mm":         e.get("y_mm", 0),
            "h_role":       mm_to_height_role(e.get("y_mm", 0)),
            "grid":         grid,
            "color":        e.get("color", "#888888"),
        })
    return result
