"""
routes/quick_start_routes.py — Quick Start QXW API
===================================================
  GET  /api/quickstart/status         → current wizard state
  POST /api/quickstart/add-fixture    → add fixture(s) to the quick-start rig
  POST /api/quickstart/remove-fixture → remove fixture from the quick-start rig
  POST /api/quickstart/clear          → clear the quick-start rig
  POST /api/quickstart/load-qxf       → load a .qxf file
  POST /api/quickstart/upload-qxf     → upload a .qxf file (multipart)
  GET  /api/quickstart/analyse        → run capability analysis
  GET  /api/quickstart/preview        → preview VC layout (JSON)
  POST /api/quickstart/generate       → generate and download .qxw
  POST /api/quickstart/update-placement → update fixture canvas position
  POST /api/quickstart/auto-dmx       → auto-assign DMX addresses
"""

import os
import re
import datetime
import tempfile
import xml.etree.ElementTree as ET

from flask import Blueprint, jsonify, request, Response

from core import fixture as fx
from core.quick_start.fixture_analyzer import (
    FixtureCapabilities, RigCapabilityAnalysis,
)
from core.quick_start.vc_generator import VCLayoutGenerator
from core.quick_start.qxw_builder import build_qxw
from core.quick_start.template_library import list_templates


QXF_NS_URI = "http://www.qlcplus.org/FixtureDefinition"


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


bp = Blueprint('quickstart', __name__, url_prefix='/api/quickstart')


# ── Module-level wizard state ────────────────────────────────────────────────
# We reuse core.fixture's rig system but keep a separate "quick start" rig
# to avoid interfering with the main Fixture Configurator.

_qs_rig: list = []          # list of fixture entry dicts
_qs_qxf_defs: dict = {}     # "Manufacturer::Model" → parsed definition dict
_qs_next_id: int = 0


def _reset_qs():
    global _qs_rig, _qs_qxf_defs, _qs_next_id
    _qs_rig = []
    _qs_qxf_defs = {}
    _qs_next_id = 0


# ── QXF parsing (local to quick start) ───────────────────────────────────────

def _parse_qxf(path: str) -> dict:
    """Parse a .qxf fixture definition file. Returns definition dict."""
    ns = {"f": QXF_NS_URI}
    tree = ET.parse(path)
    root = tree.getroot()

    if QXF_NS_URI not in (root.tag or ""):
        raise ValueError(f"Not a valid QXF file: {path}")

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
    defn = {
        "manufacturer": mfg,
        "model":        model,
        "type":         ftype,
        "modes":        modes,
        "channels":     channels,
        "path":         path,
    }
    _qs_qxf_defs[key] = defn
    return defn


def _parse_qxf_bytes(data: bytes, filename: str) -> dict:
    """Parse QXF from raw bytes (upload)."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.qxf')
    try:
        tmp.write(data)
        tmp.close()
        return _parse_qxf(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ── DMX auto-assignment ──────────────────────────────────────────────────────

def _auto_assign_dmx():
    """Assign DMX addresses sequentially, rolling to next universe at 512."""
    current_channel = 0
    universe = 0
    for entry in _qs_rig:
        ch_count = entry.get("ch_count", 1)
        if current_channel + ch_count > 512:
            universe += 1
            current_channel = 0
        entry["universe"] = universe
        entry["address"]  = current_channel
        current_channel += ch_count


# ── API-friendly rig serialisation ───────────────────────────────────────────

def _rig_to_api() -> list:
    result = []
    for i, e in enumerate(_qs_rig):
        key = e.get("key", "")
        defn = _qs_qxf_defs.get(key, {})
        caps = FixtureCapabilities(defn.get("channels", []))
        result.append({
            "idx":          i,
            "key":          key,
            "manufacturer": e.get("manufacturer", ""),
            "model":        e.get("model", ""),
            "mode":         e.get("mode", "Default"),
            "ch_count":     e.get("ch_count", 1),
            "name":         e.get("name", ""),
            "quantity":     e.get("quantity", 1),
            "universe":     e.get("universe", 0) + 1,   # 1-indexed for display
            "address":      e.get("address", 0) + 1,
            "x_mm":         e.get("x_mm", 0),
            "z_mm":         e.get("z_mm", 0),
            "y_mm":         e.get("y_mm", 0),
            "capabilities": caps.summary(),
        })
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Routes
# ═════════════════════════════════════════════════════════════════════════════

@bp.route('/status')
def status():
    """Return current Quick Start wizard state."""
    total_ch = sum(e.get("ch_count", 0) for e in _qs_rig)
    universes = set(e.get("universe", 0) for e in _qs_rig) if _qs_rig else set()
    return jsonify({
        "fixture_count":   len(_qs_rig),
        "total_channels":  total_ch,
        "universes":       sorted(u + 1 for u in universes),
        "rig":             _rig_to_api(),
        "qxf_defs":        [
            {"key": k, "manufacturer": d["manufacturer"],
             "model": d["model"], "type": d["type"],
             "modes": [{"name": n, "channels": c} for n, c in d["modes"].items()]}
            for k, d in _qs_qxf_defs.items()
        ],
        "templates":       list_templates(),
    })


@bp.route('/load-qxf', methods=['POST'])
def load_qxf():
    """Load a .qxf fixture definition by path."""
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    if not os.path.exists(path):
        return jsonify({'error': f'File not found.'}), 404
    try:
        defn = _parse_qxf(path)
        return jsonify({'ok': True, 'definition': {
            'key':          f"{defn['manufacturer']}::{defn['model']}",
            'manufacturer': defn['manufacturer'],
            'model':        defn['model'],
            'type':         defn['type'],
            'modes':        [{'name': n, 'channels': c}
                             for n, c in defn['modes'].items()],
            'channels':     defn['channels'],
        }})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 400


@bp.route('/upload-qxf', methods=['POST'])
def upload_qxf():
    """Upload a .qxf file via multipart form."""
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No file uploaded.'}), 400
    filename = f.filename or 'fixture.qxf'
    if not filename.lower().endswith('.qxf'):
        return jsonify({'error': 'Only .qxf files accepted.'}), 400
    try:
        defn = _parse_qxf_bytes(f.read(), filename)
        return jsonify({'ok': True, 'definition': {
            'key':          f"{defn['manufacturer']}::{defn['model']}",
            'manufacturer': defn['manufacturer'],
            'model':        defn['model'],
            'type':         defn['type'],
            'modes':        [{'name': n, 'channels': c}
                             for n, c in defn['modes'].items()],
            'channels':     defn['channels'],
        }})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 400


@bp.route('/add-fixture', methods=['POST'])
def add_fixture():
    """Add fixture instance(s) to the quick-start rig."""
    global _qs_next_id
    data = request.get_json(force=True) or {}
    key  = (data.get('key') or '').strip()

    if not key or key not in _qs_qxf_defs:
        return jsonify({'error': f'Unknown fixture type: {key}'}), 400

    defn     = _qs_qxf_defs[key]
    mode     = data.get('mode', next(iter(defn['modes']), 'Default'))
    quantity = max(1, min(100, int(data.get('quantity', 1))))
    ch_count = defn['modes'].get(mode, 1)
    name_tpl = data.get('name', defn['model'])

    for i in range(quantity):
        name = f"{name_tpl} {len(_qs_rig) + 1}" if quantity > 1 else (
               f"{name_tpl} {len(_qs_rig) + 1}")
        entry = {
            "key":          key,
            "manufacturer": defn["manufacturer"],
            "model":        defn["model"],
            "mode":         mode,
            "ch_count":     ch_count,
            "name":         name,
            "quantity":     1,  # each entry is one instance
            "universe":     0,
            "address":      0,
            "x_mm":         0,
            "z_mm":         0,
            "y_mm":         0,
        }
        _qs_rig.append(entry)
        _qs_next_id += 1

    _auto_assign_dmx()
    return jsonify({'ok': True, 'rig': _rig_to_api()})


@bp.route('/remove-fixture', methods=['POST'])
def remove_fixture():
    """Remove a fixture by index."""
    data = request.get_json(force=True) or {}
    idx  = int(data.get('idx', -1))
    if not (0 <= idx < len(_qs_rig)):
        return jsonify({'error': 'Invalid index.'}), 400
    _qs_rig.pop(idx)
    _auto_assign_dmx()
    return jsonify({'ok': True, 'rig': _rig_to_api()})


@bp.route('/clear', methods=['POST'])
def clear():
    """Clear the entire quick-start rig."""
    _reset_qs()
    return jsonify({'ok': True})


@bp.route('/update-placement', methods=['POST'])
def update_placement():
    """Update fixture canvas position."""
    data = request.get_json(force=True) or {}
    idx  = int(data.get('idx', -1))
    if not (0 <= idx < len(_qs_rig)):
        return jsonify({'error': 'Invalid index.'}), 400
    if 'x_mm' in data:
        _qs_rig[idx]['x_mm'] = int(data['x_mm'])
    if 'z_mm' in data:
        _qs_rig[idx]['z_mm'] = int(data['z_mm'])
    if 'y_mm' in data:
        _qs_rig[idx]['y_mm'] = int(data['y_mm'])
    return jsonify({'ok': True, 'rig': _rig_to_api()})


@bp.route('/auto-dmx', methods=['POST'])
def auto_dmx():
    """Auto-assign DMX addresses."""
    _auto_assign_dmx()
    return jsonify({'ok': True, 'rig': _rig_to_api()})


@bp.route('/analyse')
def analyse():
    """Run capability analysis on the current rig."""
    if not _qs_rig:
        return jsonify({'error': 'Rig is empty.'}), 400
    analysis = RigCapabilityAnalysis(_qs_rig, _qs_qxf_defs)
    groups   = analysis.group_by_type()
    return jsonify({
        'summary':  analysis.summary(),
        'groups':   {k: len(v) for k, v in groups.items()},
        'fixtures': [
            {
                'idx':          idx,
                'name':         _qs_rig[idx].get('name', ''),
                'group':        next((g for g, idxs in groups.items() if idx in idxs), 'other'),
                'capabilities': analysis.fixture_caps[idx].summary(),
            }
            for idx in range(len(_qs_rig))
        ],
    })


@bp.route('/preview')
def preview():
    """Preview the generated VC layout (JSON representation)."""
    if not _qs_rig:
        return jsonify({'error': 'Rig is empty.'}), 400

    analysis = RigCapabilityAnalysis(_qs_rig, _qs_qxf_defs)
    gen      = VCLayoutGenerator(_qs_rig, _qs_qxf_defs, analysis)
    funcs, vc_frame = gen.generate()
    stats    = gen.stats()

    # Build a JSON-friendly tree from the VC XML
    def _vc_to_dict(el):
        tag = el.tag.replace(f'{{{fx.QLC_NS_URI}}}', '')
        d = {'type': tag, 'caption': el.get('Caption', ''), 'children': []}
        ws_el = el.find(f'{{{fx.QLC_NS_URI}}}WindowState')
        if ws_el is not None:
            d['x'] = ws_el.get('X', '0')
            d['y'] = ws_el.get('Y', '0')
            d['w'] = ws_el.get('Width', '0')
            d['h'] = ws_el.get('Height', '0')
        func_el = el.find(f'{{{fx.QLC_NS_URI}}}Function')
        if func_el is not None:
            d['function_id'] = func_el.get('ID', '')
        for child in el:
            child_tag = child.tag.replace(f'{{{fx.QLC_NS_URI}}}', '')
            if child_tag in ('Frame', 'Button', 'Slider', 'SoloFrame'):
                d['children'].append(_vc_to_dict(child))
        return d

    return jsonify({
        'vc_layout':  _vc_to_dict(vc_frame),
        'stats':      stats,
        'summary':    analysis.summary(),
    })


@bp.route('/generate', methods=['POST'])
def generate():
    """Generate and download a complete .qxw file."""
    if not _qs_rig:
        return jsonify({'error': 'Rig is empty.'}), 400

    try:
        analysis = RigCapabilityAnalysis(_qs_rig, _qs_qxf_defs)
        gen      = VCLayoutGenerator(_qs_rig, _qs_qxf_defs, analysis)
        funcs, vc_frame = gen.generate()

        stage = fx.get_stage_dims()
        qxw_bytes = build_qxw(
            rig=_qs_rig,
            functions=funcs,
            vc_frame=vc_frame,
            stage_w_mm=stage['w_mm'],
            stage_d_mm=stage['d_mm'],
            stage_h_mm=stage['h_mm'],
        )

        filename = ('quick_start_'
                    + datetime.date.today().strftime('%Y%m%d') + '.qxw')
        return Response(
            qxw_bytes,
            mimetype='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename={filename}'},
        )
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500
