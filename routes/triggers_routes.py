"""routes/triggers_routes.py — Trigger Manager API (fully implemented)."""

import re
from flask import Blueprint, jsonify, request
from core import workspace as ws


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))

bp = Blueprint('triggers', __name__, url_prefix='/api/triggers')


@bp.route('/')
def triggers():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    assigned_only = request.args.get('assigned_only', 'false').lower() == 'true'
    return jsonify(ws.get_triggers(assigned_only=assigned_only))


@bp.route('/duplicates')
def duplicates():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    km = {}
    for d in ws.get_triggers():
        if d['key']:
            km.setdefault(d['key'], []).append(f"{d['caption']} ({d['type']})")
    return jsonify({k: v for k, v in km.items() if len(v) > 1})


@bp.route('/<uid>', methods=['PATCH'])
def update_trigger(uid):
    data = request.get_json(force=True) or {}
    ok = ws.update_trigger(
        uid,
        key      = data.get('key', '').strip(),
        universe = data.get('uni', '').strip(),
        channel  = data.get('ch',  '').strip(),
    )
    if not ok:
        return jsonify({'error': f'Trigger {uid!r} not found.'}), 404
    return jsonify({'ok': True})


@bp.route('/save', methods=['POST'])
def save():
    try:
        path = ws.save_triggers()
        return jsonify({'ok': True, 'path': path})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500
