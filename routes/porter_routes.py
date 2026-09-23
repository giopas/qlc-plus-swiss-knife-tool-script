"""routes/porter_routes.py — Function Porter API."""

import os
import re
import tempfile
from flask import Blueprint, jsonify, request, Response
from core import porter

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
    porter.clear()
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
    Auto-generate a fixture mapping (tier-1 only).
    Body: { fixture_ids: ["0", "1", ...] }
    """
    data = request.get_json(force=True) or {}
    fixture_ids = [str(x) for x in (data.get('fixture_ids') or [])]
    if not fixture_ids:
        return jsonify({'error': 'No fixture IDs provided.'}), 400

    try:
        result = porter.auto_map(fixture_ids)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


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

    try:
        # Validate first
        validation = porter.validate(plan)
        if not validation['ok']:
            return jsonify({'error': 'Validation failed.',
                            'validation': validation}), 400

        fname, xml_bytes = porter.execute(plan)
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

    return {
        'closure':         closure,
        'fixture_mapping': normalized_mapping,
        'fanout_mode':     data.get('fanout_mode', 'pattern_repeat'),
        'mirror_fixtures': [str(x) for x in (data.get('mirror_fixtures') or [])],
        'pan_channel_map': normalized_pan,
        'name_prefix':     data.get('name_prefix', ''),
        'import_path':     data.get('import_path', ''),
    }
