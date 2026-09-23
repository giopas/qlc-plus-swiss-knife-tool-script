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
from core.quick_start.nomenclature import list_profiles, load_profile
from core.quick_start.vc_style import extract_style_file, list_styles, load_style
from core.quick_start.template_library import list_templates
from core.gh_fetch import gh_get as _gh_get_shared, gh_get_raw as _gh_get_raw_shared, GH_API_BASE, GH_RAW_BASE



QXF_NS_URI = "http://www.qlcplus.org/FixtureDefinition"

# GitHub base URLs now imported from core.gh_fetch
_GH_FIXTURES_BASE = GH_API_BASE
_GH_RAW_BASE = GH_RAW_BASE


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


bp = Blueprint('quickstart', __name__, url_prefix='/api/quickstart')


# ── Module-level wizard state ────────────────────────────────────────────────

_qs_rig: list = []          # list of fixture entry dicts
_qs_qxf_defs: dict = {}     # "Manufacturer::Model" → parsed definition dict
_qs_next_id: int = 0
# Generation options: naming profile id + VC style (dict)
_QS_DEFAULT_OPTIONS = {"nomenclature": "plain", "style": "default", "style_data": None}
_qs_options: dict = dict(_QS_DEFAULT_OPTIONS)
# Fixture groups [{name, fixtures:[rig index]}]; None = automatic (by fixture name)
_qs_groups = None
_qs_qxf_raw: dict = {}       # "Mfr::Model" → original .qxf bytes

# GitHub fixture cache (avoid repeated API calls)
_gh_manufacturer_cache: list = []
_gh_fixture_cache: dict = {}  # manufacturer → list of fixture files


def _reset_qs():
    global _qs_rig, _qs_qxf_defs, _qs_next_id, _qs_options, _qs_groups
    _qs_groups = None
    _qs_qxf_raw.clear()
    _qs_rig = []
    _qs_qxf_defs = {}
    _qs_next_id = 0
    _qs_options = dict(_QS_DEFAULT_OPTIONS)


def _style_ref(opts: dict):
    """What to hand VCLayoutGenerator as *style*."""
    return opts.get("style_data") or opts.get("style") or "default"


def _options_payload() -> dict:
    st = load_style(_style_ref(_qs_options))
    return {
        "nomenclature": _qs_options["nomenclature"],
        "style": _qs_options["style"],
        "style_data": st.to_dict(),
        "profiles": list_profiles(),
        "styles": list_styles(),
        "legend": load_profile(_qs_options["nomenclature"]).legend(),
    }


def _make_generator(opts: dict = None):
    o = {**_qs_options, **(opts or {})}
    analysis = RigCapabilityAnalysis(_qs_rig, _qs_qxf_defs)
    gen = VCLayoutGenerator(_qs_rig, _qs_qxf_defs, analysis,
                            nomenclature=o.get("nomenclature"),
                            style=_style_ref(o), groups=_qs_groups)
    return analysis, gen


# ── QXF parsing (local to quick start) ───────────────────────────────────────

def _parse_qxf(path: str) -> dict:
    """Parse a .qxf fixture definition file. Returns definition dict.

    Besides the flat ``channels``/``modes`` summary, the definition carries
    ``mode_channels`` (ordered channel names per mode) and ``channel_defs``
    (groups + capabilities) so the generator can address channels by their
    position *in the selected mode* and pick capability-aware neutral values.
    """
    from core.qxf_parser import parse_qxf
    rich = parse_qxf(path)
    key = f"{rich['manufacturer']}::{rich['model']}"
    defn = {
        "manufacturer":  rich["manufacturer"],
        "model":         rich["model"],
        "type":          rich["type"],
        "modes":         rich["modes"],
        "channels":      rich["channels"],
        "mode_channels": rich["mode_channels"],
        "channel_defs":  rich["channel_defs"],
        "path":          path,
    }
    # Keep the raw file: QLC+ needs it next to the saved workspace
    # (Fixture::loader falls back to "<workspace dir>/<Mfr>-<Model>.qxf").
    with open(path, "rb") as fh:
        _qs_qxf_raw[key] = fh.read()
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
            "y":            e.get("y_mm") if e.get("y_mm") is not None else 0,
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
            "y_mm":         None,
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
    _remap_groups_after_remove(idx)
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
        _reset_groups()
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


def _reset_groups() -> None:
    global _qs_groups
    _qs_groups = None


def _remap_groups_after_remove(idx: int) -> None:
    global _qs_groups
    if _qs_groups is None:
        return
    out = []
    for g in _qs_groups:
        fx = [i - 1 if i > idx else i for i in g["fixtures"] if i != idx]
        if fx:
            out.append({"name": g["name"], "fixtures": fx})
    _qs_groups = out


def _groups_payload() -> dict:
    _, gen = _make_generator()
    groups = _qs_groups if _qs_groups is not None else gen._default_groups()
    return {
        "auto": _qs_groups is None,
        "groups": groups,
        "fixtures": [{"idx": i, "name": e.get("name", f"#{i + 1}")} for i, e in enumerate(_qs_rig)],
    }


@bp.route('/groups', methods=['GET', 'POST'])
def groups():
    """Fixture groups used by Quick Start (VC group frames + matrix groups).

    GET → {auto, groups:[{name, fixtures:[idx]}], fixtures:[{idx, name}]}.
    POST {"groups": [...]} sets them; {"auto": true} goes back to the
    automatic grouping (one group per fixture name).
    """
    global _qs_groups
    if request.method == 'POST':
        data = request.get_json(force=True) or {}
        if data.get('auto'):
            _qs_groups = None
        else:
            clean, seen = [], set()
            for g in data.get('groups') or []:
                name = str(g.get('name', '')).strip()[:40]
                fx = sorted({int(i) for i in g.get('fixtures', []) if 0 <= int(i) < len(_qs_rig)})
                if not name or not fx:
                    continue
                if name.lower() in seen:
                    return jsonify({'error': f'Duplicate group name: {name}'}), 400
                seen.add(name.lower())
                clean.append({'name': name, 'fixtures': fx})
            _qs_groups = clean
    return jsonify(_groups_payload())


def qxf_filename(manufacturer: str, model: str) -> str:
    """File name QLC+ looks for next to a workspace (Fixture::loader)."""
    return f"{manufacturer}-{model}.qxf".replace(" ", "-").replace("/", "-")


@bp.route('/save-qxf', methods=['POST'])
def save_qxf():
    """Write the rig's fixture definitions next to a saved workspace.

    QLC+ looks for a definition it doesn't know in the workspace folder as
    ``<Manufacturer>-<Model>.qxf`` (spaces → dashes).  Without it the
    fixtures load as generic dimmers: no colour, RGB matrices do nothing.
    """
    data = request.get_json(force=True) or {}
    qxw = data.get('qxw_path') or ''
    folder = os.path.dirname(os.path.abspath(qxw)) if qxw else ''
    if not folder or not os.path.isdir(folder):
        return jsonify({'error': 'Workspace folder not found.'}), 400
    written = []
    for key in sorted({e.get('key') for e in _qs_rig}):
        raw, defn = _qs_qxf_raw.get(key), _qs_qxf_defs.get(key)
        if not raw or not defn:
            continue
        fname = qxf_filename(defn['manufacturer'], defn['model'])
        dest = os.path.join(folder, fname)
        try:
            with open(dest, 'rb') as fh:
                same = fh.read() == raw
        except OSError:
            same = False
        if not same:
            with open(dest, 'wb') as fh:
                fh.write(raw)
        written.append(fname)
    return jsonify({'ok': True, 'folder': folder, 'files': written})


@bp.route('/options', methods=['GET', 'POST'])
def options():
    """Get / set generation options: naming profile and VC style.

    POST JSON: ``{"nomenclature": "20minutes"}``, ``{"style": "compact"}``,
    ``{"style_path": "/path/reference.qxw"}`` (clone the style of a
    reference workspace) or ``{"style": {...}}`` (explicit style dict).
    POST multipart ``style_file``: clone the style of an uploaded .qxw.
    """
    global _qs_options
    if request.method == 'POST':
        upload = request.files.get('style_file')
        data = {} if upload else (request.get_json(force=True, silent=True) or {})
        try:
            if upload:
                from core.qxw_io import loads_qxw, strip_ns
                from core.quick_start.vc_style import extract_style
                st = extract_style(strip_ns(loads_qxw(upload.read())),
                                   source=upload.filename or 'reference.qxw')
                _qs_options['style'] = 'custom'
                _qs_options['style_data'] = st.to_dict()
            if 'nomenclature' in data:
                load_profile(data['nomenclature'])          # validate
                _qs_options['nomenclature'] = data['nomenclature'] or 'plain'
            if data.get('style_path'):
                st = extract_style_file(data['style_path'])
                _qs_options['style'] = 'custom'
                _qs_options['style_data'] = st.to_dict()
            elif isinstance(data.get('style'), dict):
                _qs_options['style'] = 'custom'
                _qs_options['style_data'] = load_style(data['style']).to_dict()
            elif 'style' in data:
                load_style(data['style'])                    # validate
                _qs_options['style'] = data['style'] or 'default'
                _qs_options['style_data'] = None
        except (ValueError, OSError) as e:
            return jsonify({'error': _safe_err(e)}), 400
        except Exception as e:  # malformed reference file
            return jsonify({'error': 'Could not read the reference workspace: ' + _safe_err(e)}), 400
    return jsonify(_options_payload())


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

    analysis, gen = _make_generator()
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
        app_el = el.find(f'{{{fx.QLC_NS_URI}}}Appearance')
        if app_el is not None:
            for k, tag in (('bg', 'BackgroundColor'), ('fg', 'ForegroundColor')):
                v = app_el.findtext(f'{{{fx.QLC_NS_URI}}}{tag}')
                if v and v.isdigit():
                    d[k] = '#%06x' % (int(v) & 0xFFFFFF)
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
        over = {k: data[k] for k in ("nomenclature", "style") if data.get(k)}
        if "style" in over:
            over["style_data"] = None if isinstance(over["style"], str) else over["style"]
        analysis, gen = _make_generator(over)
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
            vc_size=gen.page_size,
        )

        # Doctor gates every export (WORKPLAN principle 4): errors block it.
        from core.doctor import check
        from core.qxw_io import loads_qxw
        report = check(loads_qxw(qxw_bytes), list(_qs_qxf_defs.values()))
        if report.errors:
            return jsonify({
                'error': 'Doctor found errors in the generated workspace; not exported.',
                'findings': [f"{f.code} {f.location}: {f.message}" for f in report.errors],
            }), 422

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
    """Fetch JSON from the GitHub API.  Delegates to core.gh_fetch."""
    return _gh_get_shared(url)


def _gh_get_raw(url: str) -> bytes:
    """Fetch raw file content from GitHub.  Delegates to core.gh_fetch."""
    return _gh_get_raw_shared(url)


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
