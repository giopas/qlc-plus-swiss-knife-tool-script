"""routes/merger_routes.py — QXW Merger API."""

import re
from flask import Blueprint, jsonify, request, Response
from core import merger as mg

bp = Blueprint('merger', __name__, url_prefix='/api/merger')


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


# ── State ─────────────────────────────────────────────────────────────────────

@bp.route('/state')
def state():
    return jsonify(mg.get_state())


# ── Load source / destination ─────────────────────────────────────────────────

@bp.route('/src/load', methods=['POST'])
def load_src():
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        summary = mg.load_src(path)
        return jsonify({'ok': True, 'summary': summary, 'name': mg.get_state()['src_name']})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/dst/load', methods=['POST'])
def load_dst():
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        summary = mg.load_dst(path)
        return jsonify({'ok': True, 'summary': summary, 'name': mg.get_state()['dst_name']})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/src/clear', methods=['POST'])
def clear_src():
    mg.clear_src()
    return jsonify({'ok': True})


@bp.route('/dst/clear', methods=['POST'])
def clear_dst():
    mg.clear_dst()
    return jsonify({'ok': True})


# ── List elements ─────────────────────────────────────────────────────────────

@bp.route('/src/fixtures')
def src_fixtures():
    return jsonify(mg.list_src_fixtures())


@bp.route('/src/groups')
def src_groups():
    return jsonify(mg.list_src_groups())


@bp.route('/src/functions')
def src_functions():
    return jsonify(mg.list_src_functions())


@bp.route('/dst/fixtures')
def dst_fixtures():
    return jsonify(mg.list_dst_fixtures())


@bp.route('/dst/functions')
def dst_functions():
    return jsonify(mg.list_dst_functions())


# ── Copy ──────────────────────────────────────────────────────────────────────

@bp.route('/copy', methods=['POST'])
def copy_elements():
    """
    Copy selected elements from source into destination.
    Body: {fixture_ids: [str], group_ids: [str], function_ids: [str]}
    """
    data         = request.get_json(force=True) or {}
    fixture_ids  = [str(x) for x in (data.get('fixture_ids')  or [])]
    group_ids    = [str(x) for x in (data.get('group_ids')    or [])]
    function_ids = [str(x) for x in (data.get('function_ids') or [])]

    if not (fixture_ids or group_ids or function_ids):
        return jsonify({'error': 'Nothing selected to copy.'}), 400

    try:
        result = mg.copy_elements(fixture_ids, group_ids, function_ids)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Export merged destination ─────────────────────────────────────────────────

@bp.route('/export', methods=['POST'])
def export():
    """Return the merged destination QXW as a download."""
    try:
        fname, xml_bytes = mg.export_dst()
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
