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


@bp.route('/midi-shift', methods=['POST'])
def midi_shift():
    """Bulk-reassign MIDI channel. Body: {from_uni, from_ch, to_uni, to_ch}"""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data     = request.get_json(force=True) or {}
    from_uni = str(data.get('from_uni', '')).strip()
    from_ch  = str(data.get('from_ch',  '')).strip()
    to_uni   = str(data.get('to_uni',   '')).strip()
    to_ch    = str(data.get('to_ch',    '')).strip()
    if not (from_uni and from_ch and to_uni and to_ch):
        return jsonify({'error': 'All four fields (from_uni, from_ch, to_uni, to_ch) are required.'}), 400
    try:
        count = ws.bulk_shift_midi(from_uni, from_ch, to_uni, to_ch)
        return jsonify({'ok': True, 'updated': count})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/matrix')
def matrix():
    """Return data for the key-assignment matrix view."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_key_matrix())


@bp.route('/save', methods=['POST'])
def save():
    try:
        path = ws.save_triggers()
        return jsonify({'ok': True, 'path': path})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500
