"""routes/porter_routes.py — Function Porter API."""

import os
import re
import tempfile
from flask import Blueprint, jsonify, request, Response
from core import porter, porter_vc

bp = Blueprint('porter', __name__, url_prefix='/api/porter')


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


# ── State ────────────────────────────────────────────────────────────────────

@bp.route('/state')
def state():
    return jsonify(porter.get_state())


# ── Load source / target ────────────────────────────────────────────────────

def _load_side(load_fn, name_key):
    """Shared loader for source/target — supports JSON path or file upload."""
    tmp = None
    name = None          # uploads: keep the real file name, not the temp name
    try:
        if request.is_json:
            data = request.get_json(force=True) or {}
            path = (data.get('path') or '').strip()
            if not path:
                return jsonify({'error': 'No path provided.'}), 400
            if not os.path.isfile(path):
                return jsonify({'error': 'File not found.'}), 404
        else:
            f = request.files.get('file')
            if not f:
                return jsonify({'error': 'No file uploaded.'}), 400
            suffix = os.path.splitext(f.filename or '')[-1].lower()
            if suffix != '.qxw':
                return jsonify({'error': f'Only .qxw files are accepted (got: {suffix or "no extension"}).'}), 400
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.qxw')
            f.save(tmp.name)
            tmp.close()
            path = tmp.name
            name = os.path.splitext(os.path.basename(f.filename))[0]

        summary = load_fn(path, name)
        return jsonify({'ok': True, 'summary': summary,
                        'name': porter.get_state()[name_key]})

    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500

    finally:
        if tmp:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


@bp.route('/source/load', methods=['POST'])
def load_source():
    return _load_side(porter.load_source, 'src_name')


@bp.route('/target/load', methods=['POST'])
def load_target():
    return _load_side(porter.load_target, 'tgt_name')


@bp.route('/clear', methods=['POST'])
def clear():
    global _last_result
    porter.clear()
    _last_result = {}
    return jsonify({'ok': True})


# ── List helpers ─────────────────────────────────────────────────────────────

@bp.route('/source/functions')
def source_functions():
    return jsonify(porter.list_source_functions())


@bp.route('/source/fixtures')
def source_fixtures():
    return jsonify(porter.list_source_fixtures())


@bp.route('/target/fixtures')
def target_fixtures():
    return jsonify(porter.list_target_fixtures())


# ── Dependency resolution ────────────────────────────────────────────────────

@bp.route('/resolve', methods=['POST'])
def resolve_closure():
    """
    Resolve the full dependency closure for selected function IDs.
    Body: { seed_ids: ["0", "1", ...] }
    """
    data = request.get_json(force=True) or {}
    seed_ids = [str(x) for x in (data.get('seed_ids') or [])]
    if not seed_ids:
        return jsonify({'error': 'No function IDs provided.'}), 400

    try:
        result = porter.resolve_closure(seed_ids)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Fixture compatibility ────────────────────────────────────────────────────

@bp.route('/fixture-candidates', methods=['POST'])
def fixture_candidates():
    """
    Get compatibility tiers for source fixtures referenced by the closure.
    Body: { fixture_ids: ["0", "1", ...] }
    """
    data = request.get_json(force=True) or {}
    fixture_ids = [str(x) for x in (data.get('fixture_ids') or [])]
    if not fixture_ids:
        return jsonify({'error': 'No fixture IDs provided.'}), 400

    try:
        result = porter.build_fixture_candidates(fixture_ids)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/auto-map', methods=['POST'])
def auto_map():
    """
    Auto-generate a fixture mapping.
    Body: { fixture_ids: ["0", "1", ...], strategy: "all" | "same_id" | "fan_in" }
    """
    data = request.get_json(force=True) or {}
    fixture_ids = [str(x) for x in (data.get('fixture_ids') or [])]
    if not fixture_ids:
        return jsonify({'error': 'No fixture IDs provided.'}), 400
    strategy = data.get('strategy') or 'all'
    if strategy not in ('all', 'same_id', 'fan_in'):
        return jsonify({'error': f'Unknown strategy {strategy!r}.'}), 400

    try:
        result = porter.auto_map(fixture_ids, strategy)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Virtual Console ──────────────────────────────────────────────────────────

@bp.route('/source/vc')
def source_vc():
    """Source VC pages/frames/widgets as a flat tree (keys, captions, depth)."""
    if not porter.get_state()['src_loaded']:
        return jsonify([])
    return jsonify(porter_vc.list_source_vc(porter.source_root()))


@bp.route('/target/pages')
def target_pages():
    if not porter.get_state()['tgt_loaded']:
        return jsonify([])
    return jsonify(porter_vc.list_target_pages(porter.target_root()))


@bp.route('/vc/seeds', methods=['POST'])
def vc_seeds():
    """Function IDs used by the chosen source widgets. Body: { keys: ["w12", ...] }"""
    data = request.get_json(force=True) or {}
    keys = [str(k) for k in (data.get('keys') or [])]
    if not porter.get_state()['src_loaded']:
        return jsonify({'error': 'Source QXW not loaded.'}), 400
    return jsonify({'seed_ids': porter_vc.seeds_from_widgets(porter.source_root(), keys)})


# ── Validate ─────────────────────────────────────────────────────────────────

@bp.route('/validate', methods=['POST'])
def validate():
    """
    Validate an import plan before executing.
    Body: full plan dict (closure, fixture_mapping, fanout_mode, etc.)
    """
    data = request.get_json(force=True) or {}
    plan = _normalize_plan(data)

    try:
        result = porter.validate(plan)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Execute ──────────────────────────────────────────────────────────────────

@bp.route('/execute', methods=['POST'])
def execute():
    """
    Execute the import and return the modified QXW as a download.
    Body: full plan dict.
    """
    data = request.get_json(force=True) or {}
    plan = _normalize_plan(data)

    global _last_result
    try:
        # Validate, build, port the VC, Doctor gate (new errors block)
        try:
            res = porter.port(plan)
        except porter.PorterBlocked as b:
            if 'validation' in b.result and 'bytes' not in b.result:
                return jsonify({'error': 'Validation failed.',
                                'validation': b.result['validation']}), 400
            return jsonify({'error': str(b),
                            'findings': b.result['doctor']['errors'],
                            'report': b.result.get('report', '')}), 422

        _last_result = {k: v for k, v in res.items() if k != 'bytes'}
        fname, xml_bytes = res['filename'], res['bytes']
        return Response(
            xml_bytes,
            mimetype='application/octet-stream',
            headers={
                'Content-Disposition':           f'attachment; filename="{fname}"',
                'X-Suggested-Filename':          fname,
                'Access-Control-Expose-Headers': 'X-Suggested-Filename',
            },
        )
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


_last_result: dict = {}


@bp.route('/last-result')
def last_result():
    """Summary of the last export (Doctor, VC, removed functions)."""
    r = _last_result
    if not r:
        return jsonify({})
    return jsonify({'filename': r.get('filename'), 'doctor': r.get('doctor'),
                    'vc': r.get('vc'), 'pruned': r.get('pruned', []),
                    'groups': r.get('groups', []), 'panic': r.get('panic', []),
                    'functions': len(r.get('func_id_map', {}))})


@bp.route('/save-report', methods=['POST'])
def save_report():
    """Write the last import report next to the saved workspace:
    ``<name>_port_report.txt``.  Body: { qxw_path }"""
    data = request.get_json(force=True) or {}
    qxw = (data.get('qxw_path') or '').strip()
    if not _last_result.get('report'):
        return jsonify({'error': 'No import report yet.'}), 400
    folder = os.path.dirname(os.path.abspath(qxw)) if qxw else ''
    if not qxw.lower().endswith('.qxw') or not os.path.isdir(folder):
        return jsonify({'error': 'Workspace folder not found.'}), 400
    path = porter.report_path(os.path.abspath(qxw))
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(_last_result['report'])
    return jsonify({'ok': True, 'path': path, 'name': os.path.basename(path)})


# ── Report ───────────────────────────────────────────────────────────────────

@bp.route('/report', methods=['POST'])
def report():
    """
    Generate a plain-text import report (for clipboard / forum).
    Body: { plan: {...}, validation: {...} }
    """
    data = request.get_json(force=True) or {}
    plan = _normalize_plan(data.get('plan') or data)
    validation = data.get('validation')

    try:
        if validation is None:
            validation = porter.validate(plan)
        if _last_result.get('report'):
            text = _last_result['report']
        else:
            text = porter.generate_report(plan, validation)
        return jsonify({'ok': True, 'report': text})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_plan(data: dict) -> dict:
    """
    Normalize a plan dict from the frontend, ensuring all keys exist
    and types are correct.
    """
    closure = data.get('closure', {})
    fixture_mapping = data.get('fixture_mapping', {})
    # Ensure fixture_mapping values are lists of strings
    normalized_mapping = {}
    for k, v in fixture_mapping.items():
        if isinstance(v, list):
            normalized_mapping[str(k)] = [str(x) for x in v]
        elif isinstance(v, str):
            normalized_mapping[str(k)] = [v]
        else:
            normalized_mapping[str(k)] = []

    pan_channel_map = data.get('pan_channel_map', {})
    # Ensure pan_channel_map keys are strings and values have int indices
    normalized_pan = {}
    for k, v in pan_channel_map.items():
        if isinstance(v, dict):
            entry = {'coarse': int(v.get('coarse', 0))}
            if v.get('fine') is not None:
                entry['fine'] = int(v['fine'])
            normalized_pan[str(k)] = entry

    vc = data.get('vc') or {}
    return {
        'drop_unmapped':     bool(data.get('drop_unmapped', False)),
        'complete_channels': bool(data.get('complete_channels', True)),
        'extend_panic':      bool(data.get('extend_panic', True)),
        'vc': {
            'enabled':      bool(vc.get('enabled', False)),
            'scope':        [str(k) for k in (vc.get('scope') or [])],
            'target_page':  str(vc.get('target_page') or ''),
            'page_caption': str(vc.get('page_caption') or ''),
            'bindings':     vc.get('bindings') if vc.get('bindings') in ('keep_free', 'keep', 'drop') else 'keep_free',
        },
        'closure':         closure,
        'fixture_mapping': normalized_mapping,
        'fanout_mode':     data.get('fanout_mode', 'pattern_repeat'),
        'mirror_fixtures': [str(x) for x in (data.get('mirror_fixtures') or [])],
        'pan_channel_map': normalized_pan,
        'name_prefix':     data.get('name_prefix', ''),
        'import_path':     data.get('import_path', ''),
    }
