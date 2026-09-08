"""
routes/quick_start_routes.py — Quick Start QXW API
===================================================
  GET  /api/quickstart/status         → current wizard state
  POST /api/quickstart/add-fixture    → add fixture(s) to the quick-start rig
  POST /api/quickstart/remove-fixture → remove fixture from the quick-start rig
  POST /api/quickstart/clear          → clear the quick-start rig
  POST /api/quickstart/load-qxf       → load a .qxf file by path
  POST /api/quickstart/upload-qxf     → upload a .qxf file (multipart)
  GET  /api/quickstart/analyse        → run capability analysis
  GET  /api/quickstart/preview        → preview VC layout (JSON)
  POST /api/quickstart/generate       → generate and download .qxw
  POST /api/quickstart/update-placement → update fixture canvas position
  POST /api/quickstart/auto-dmx       → auto-assign DMX addresses
  GET  /api/quickstart/gh/manufacturers → list manufacturers from QLC+ GitHub
  GET  /api/quickstart/gh/fixtures      → list fixtures for a manufacturer
  POST /api/quickstart/gh/load          → load a fixture definition from GitHub
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

try:
    import requests as _requests
except ImportError:
    _requests = None


QXF_NS_URI = "http://www.qlcplus.org/FixtureDefinition"

_GH_FIXTURES_BASE = (
    "https://api.github.com/repos/mcallegari/qlcplus/contents/"
    "resources/fixtures"
)
_GH_RAW_BASE = (
    "https://raw.githubusercontent.com/mcallegari/qlcplus/master/"
    "resources/fixtures"
)


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


bp = Blueprint('quickstart', __name__, url_prefix='/api/quickstart')


# ── Module-level wizard state ────────────────────────────────────────────────

_qs_rig: list = []          # list of fixture entry dicts
_qs_qxf_defs: dict = {}     # "Manufacturer::Model" → parsed definition dict
_qs_next_id: int = 0

# GitHub fixture cache (avoid repeated API calls)
_gh_manufacturer_cache: list = []
_gh_fixture_cache: dict = {}  # manufacturer → list of fixture files


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
        raise ValueError("Not a valid QXF file")

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


def _parse_qxf_bytes(data: bytes, filename: str = 'fixture.qxf') -> dict:
    """Parse QXF from raw bytes (upload or GitHub fetch)."""
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


# ── API-friendly serialisation ───────────────────────────────────────────────

def _defn_to_api(key: str, defn: dict) -> dict:
    """Serialise a fixture definition for the frontend."""
    return {
        "key":          key,
        "manufacturer": defn["manufacturer"],
        "model":        defn["model"],
        "type":         defn["type"],
        "channels":     len(defn.get("channels", [])),
        "channel_names": defn.get("channels", []),
        "modes":        [{"name": n, "channels": c}
                         for n, c in defn["modes"].items()],
    }


def _rig_to_api() -> list:
    result = []
    for i, e in enumerate(_qs_rig):
        result.append({
            "idx":          i,
            "key":          e.get("key", ""),
            "manufacturer": e.get("manufacturer", ""),
            "model":        e.get("model", ""),
            "mode":         e.get("mode", "Default"),
            "channels":     e.get("ch_count", 1),
            "name":         e.get("name", ""),
            "universe":     e.get("universe", 0),
            "address":      e.get("address", 0),
            "x":            e.get("x_mm", 0),
            "z":            e.get("z_mm", 0),
            "y":            e.get("y_mm", 0),
            "x_rot":        e.get("x_rot"),
            "y_rot":        e.get("y_rot"),
            "z_rot":        e.get("z_rot"),
        })
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Routes — Core wizard
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
        "loaded_defs":     [_defn_to_api(k, d) for k, d in _qs_qxf_defs.items()],
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
        return jsonify({'error': 'File not found.'}), 404
    try:
        defn = _parse_qxf(path)
        key = f"{defn['manufacturer']}::{defn['model']}"
        return jsonify({
            'ok': True,
            'definition': _defn_to_api(key, defn),
        })
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
        key = f"{defn['manufacturer']}::{defn['model']}"
        return jsonify({
            'ok': True,
            'definition': _defn_to_api(key, defn),
        })
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 400


@bp.route('/add-fixture', methods=['POST'])
def add_fixture():
    """Add fixture instance(s) to the quick-start rig."""
    global _qs_next_id
    data = request.get_json(force=True) or {}
    key  = (data.get('key') or '').strip()

    if not key or key not in _qs_qxf_defs:
        return jsonify({'error': f'Unknown fixture type: {key}. Load a QXF first.'}), 400

    defn     = _qs_qxf_defs[key]
    mode     = data.get('mode', next(iter(defn['modes']), 'Default'))
    quantity = max(1, min(100, int(data.get('quantity', 1))))
    ch_count = defn['modes'].get(mode, 1)
    name_tpl = data.get('name') or defn['model']

    for i in range(quantity):
        name = f"{name_tpl} {len(_qs_rig) + 1}"
        entry = {
            "key":          key,
            "manufacturer": defn["manufacturer"],
            "model":        defn["model"],
            "mode":         mode,
            "ch_count":     ch_count,
            "name":         name,
            "quantity":     1,
            "universe":     0,
            "address":      0,
            "x_mm":         0,
            "z_mm":         0,
            "y_mm":         0,
            "x_rot":        None,
            "y_rot":        None,
            "z_rot":        None,
        }
        _qs_rig.append(entry)
        _qs_next_id += 1

    _auto_assign_dmx()
    return jsonify({'ok': True, 'rig': _rig_to_api()})


@bp.route('/remove-fixture', methods=['POST'])
def remove_fixture():
    """Remove a fixture by index."""
    data = request.get_json(force=True) or {}
    idx  = int(data.get('idx', data.get('index', -1)))
    if not (0 <= idx < len(_qs_rig)):
        return jsonify({'error': 'Invalid index.'}), 400
    _qs_rig.pop(idx)
    _auto_assign_dmx()
    return jsonify({'ok': True, 'rig': _rig_to_api()})


@bp.route('/remove-def', methods=['POST'])
def remove_def():
    """Remove a loaded fixture definition (and optionally its rig entries)."""
    data = request.get_json(force=True) or {}
    key = (data.get('key') or '').strip()
    if not key or key not in _qs_qxf_defs:
        return jsonify({'error': f'Unknown definition: {key}'}), 400
    del _qs_qxf_defs[key]
    # Optionally remove rig entries using this def
    if data.get('remove_fixtures', False):
        global _qs_rig
        _qs_rig = [e for e in _qs_rig if e.get('key') != key]
        _auto_assign_dmx()
    return jsonify({
        'ok': True,
        'loaded_defs': [_defn_to_api(k, d) for k, d in _qs_qxf_defs.items()],
        'rig': _rig_to_api(),
    })


@bp.route('/clear', methods=['POST'])
def clear():
    """Clear the entire quick-start rig."""
    _reset_qs()
    return jsonify({'ok': True, 'rig': []})


@bp.route('/update-placement', methods=['POST'])
def update_placement():
    """Update fixture canvas position."""
    data = request.get_json(force=True) or {}
    idx  = int(data.get('idx', data.get('index', -1)))
    if not (0 <= idx < len(_qs_rig)):
        return jsonify({'error': 'Invalid index.'}), 400
    for axis in ('x', 'z', 'y'):
        k_mm = f'{axis}_mm'
        if axis in data:
            _qs_rig[idx][k_mm] = int(data[axis])
        elif k_mm in data:
            _qs_rig[idx][k_mm] = int(data[k_mm])
    # Orientation overrides
    for rot_axis in ('x_rot', 'y_rot', 'z_rot'):
        if rot_axis in data:
            val = data[rot_axis]
            _qs_rig[idx][rot_axis] = int(val) if val is not None else None
    return jsonify({'ok': True, 'rig': _rig_to_api()})


@bp.route('/auto-dmx', methods=['POST'])
def auto_dmx():
    """Auto-assign DMX addresses."""
    _auto_assign_dmx()
    universes = set(e.get("universe", 0) for e in _qs_rig) if _qs_rig else set()
    return jsonify({
        'ok': True,
        'rig': _rig_to_api(),
        'universes': len(universes),
    })


@bp.route('/analyse')
def analyse():
    """Run capability analysis on the current rig."""
    if not _qs_rig:
        return jsonify({'error': 'Rig is empty.'}), 400
    analysis = RigCapabilityAnalysis(_qs_rig, _qs_qxf_defs)
    groups   = analysis.group_by_type()
    return jsonify({
        'summary':         analysis.summary(),
        'groups':          {k: len(v) for k, v in groups.items()},
        'has_any_rgb':     analysis.summary().get('has_any_rgb', False),
        'has_any_strobe':  analysis.summary().get('has_any_strobe', False),
        'has_any_dimmer':  analysis.summary().get('has_any_dimmer', False),
        'has_any_pan_tilt': analysis.summary().get('has_any_pan_tilt', False),
    })


@bp.route('/preview')
def preview():
    """Preview the generated VC layout (JSON representation)."""
    if not _qs_rig:
        return jsonify({'error': 'Rig is empty.'}), 400

    analysis = RigCapabilityAnalysis(_qs_rig, _qs_qxf_defs)
    gen      = VCLayoutGenerator(_qs_rig, _qs_qxf_defs, analysis)
    funcs, vc_frame, _fg = gen.generate()
    stats    = gen.stats()

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


@bp.route('/generate', methods=['GET', 'POST'])
def generate():
    """Generate and download a complete .qxw file.

    Accepts GET (query params) or POST (JSON body or form data) so that
    both regular browsers (fetch + blob) and pywebview (form submit or
    direct navigation) can trigger the download.
    """
    if not _qs_rig:
        return jsonify({'error': 'Rig is empty.'}), 400

    # Collect parameters from whichever source is available
    if request.method == 'GET':
        data = request.args.to_dict()
    elif request.content_type and 'json' in request.content_type:
        data = request.get_json(force=True) or {}
    else:
        data = request.form.to_dict()

    try:
        analysis = RigCapabilityAnalysis(_qs_rig, _qs_qxf_defs)
        gen      = VCLayoutGenerator(_qs_rig, _qs_qxf_defs, analysis)
        funcs, vc_frame, fixture_groups = gen.generate()

        # Use QS-specific stage dims if provided, else fall back to global
        # Support both nested JSON {stage: {w_mm, d_mm, h_mm}} and flat
        # form fields (stage_w, stage_d, stage_h)
        qs_stage = data.get('stage', {})
        if isinstance(qs_stage, dict) and all(k in qs_stage for k in ('w_mm', 'd_mm', 'h_mm')):
            stage_w = int(qs_stage['w_mm'])
            stage_d = int(qs_stage['d_mm'])
            stage_h = int(qs_stage['h_mm'])
        elif all(k in data for k in ('stage_w', 'stage_d', 'stage_h')):
            stage_w = int(data['stage_w'])
            stage_d = int(data['stage_d'])
            stage_h = int(data['stage_h'])
        else:
            stage = fx.get_stage_dims()
            stage_w = stage['w_mm']
            stage_d = stage['d_mm']
            stage_h = stage['h_mm']

        qxw_bytes = build_qxw(
            rig=_qs_rig,
            functions=funcs,
            vc_frame=vc_frame,
            fixture_groups=fixture_groups,
            stage_w_mm=stage_w,
            stage_d_mm=stage_d,
            stage_h_mm=stage_h,
        )

        # Build filename: project_name_YYYYMMDD_HHMM.qxw
        proj = (data.get('project_name') or '').strip()
        now = datetime.datetime.now()
        ts = now.strftime('%Y%m%d_%H%M')
        if proj:
            slug = re.sub(r'[^a-zA-Z0-9_\- ]', '', proj).replace(' ', '_')
        else:
            slug = 'quick_start'
        filename = f'{slug}_{ts}.qxw'

        return Response(
            qxw_bytes,
            mimetype='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename={filename}'},
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': _safe_err(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# Routes — QLC+ GitHub fixture repository browser
# ═════════════════════════════════════════════════════════════════════════════

def _gh_get(url: str) -> list:
    """Fetch JSON from the GitHub API. Uses requests if available, else urllib."""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'SwissKnife-QLC-QuickStart',
    }
    if _requests:
        resp = _requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    else:
        import urllib.request
        import json
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())


def _gh_get_raw(url: str) -> bytes:
    """Fetch raw file content from GitHub."""
    headers = {'User-Agent': 'SwissKnife-QLC-QuickStart'}
    if _requests:
        resp = _requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.content
    else:
        import urllib.request
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()


@bp.route('/gh/manufacturers')
def gh_manufacturers():
    """List fixture manufacturers from the QLC+ GitHub repo."""
    global _gh_manufacturer_cache
    if _gh_manufacturer_cache:
        return jsonify({'ok': True, 'manufacturers': _gh_manufacturer_cache})
    try:
        data = _gh_get(_GH_FIXTURES_BASE)
        dirs = sorted(
            [d['name'] for d in data if d.get('type') == 'dir'],
            key=str.lower,
        )
        _gh_manufacturer_cache = dirs
        return jsonify({'ok': True, 'manufacturers': dirs})
    except Exception as e:
        return jsonify({'error': f'GitHub API error: {_safe_err(e)}'}), 502


@bp.route('/gh/fixtures')
def gh_fixtures():
    """List .qxf fixture files for a given manufacturer."""
    mfg = request.args.get('manufacturer', '').strip()
    if not mfg:
        return jsonify({'error': 'No manufacturer specified.'}), 400
    # Sanitise: only allow safe chars
    if not re.match(r'^[\w\s\-\.&]+$', mfg):
        return jsonify({'error': 'Invalid manufacturer name.'}), 400

    if mfg in _gh_fixture_cache:
        return jsonify({'ok': True, 'fixtures': _gh_fixture_cache[mfg]})

    try:
        url = f"{_GH_FIXTURES_BASE}/{mfg.replace(' ', '%20')}"
        data = _gh_get(url)
        files = sorted([
            {
                'name': d['name'],
                'display': d['name'].replace('.qxf', '').replace('-', ' '),
            }
            for d in data
            if d.get('type') == 'file' and d['name'].lower().endswith('.qxf')
        ], key=lambda x: x['display'].lower())
        _gh_fixture_cache[mfg] = files
        return jsonify({'ok': True, 'fixtures': files})
    except Exception as e:
        return jsonify({'error': f'GitHub API error: {_safe_err(e)}'}), 502


@bp.route('/gh/load', methods=['POST'])
def gh_load():
    """Download and parse a fixture QXF from the QLC+ GitHub repo."""
    data = request.get_json(force=True) or {}
    mfg      = (data.get('manufacturer') or '').strip()
    filename = (data.get('filename') or '').strip()
    if not mfg or not filename:
        return jsonify({'error': 'manufacturer and filename required.'}), 400
    if not re.match(r'^[\w\s\-\.&]+$', mfg):
        return jsonify({'error': 'Invalid manufacturer name.'}), 400
    if not filename.lower().endswith('.qxf'):
        return jsonify({'error': 'Only .qxf files.'}), 400

    try:
        url = (f"{_GH_RAW_BASE}/"
               f"{mfg.replace(' ', '%20')}/"
               f"{filename.replace(' ', '%20')}")
        raw = _gh_get_raw(url)
        defn = _parse_qxf_bytes(raw, filename)
        key = f"{defn['manufacturer']}::{defn['model']}"
        return jsonify({
            'ok': True,
            'definition': _defn_to_api(key, defn),
        })
    except Exception as e:
        return jsonify({'error': f'Failed to load from GitHub: {_safe_err(e)}'}), 502
