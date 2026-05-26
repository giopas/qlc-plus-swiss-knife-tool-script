"""routes/setlist_routes.py — Setlist Manager API (fully implemented)."""

from flask import Blueprint, jsonify, request
from core import workspace as ws

bp = Blueprint('setlist', __name__, url_prefix='/api/setlist')


@bp.route('/slots')
def slots():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_cuelist_slots())


@bp.route('/<slot_id>/songs')
def get_songs(slot_id):
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_slot_songs(slot_id))


@bp.route('/<slot_id>/songs', methods=['POST'])
def set_songs(slot_id):
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    songs = data.get('songs', [])
    if not isinstance(songs, list):
        return jsonify({'error': 'songs must be a list.'}), 400
    ws.set_slot_songs(slot_id, songs)
    return jsonify({'ok': True, 'count': len(songs)})


@bp.route('/load', methods=['POST'])
def load_setlist():
    """Load a setlist TXT file. Format: slot_id|song1|song2|..."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        count = 0
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if len(parts) >= 2:
                    slot_id = parts[0].strip()
                    songs   = [s.strip() for s in parts[1:] if s.strip()]
                    ws.set_slot_songs(slot_id, songs)
                    count += 1
        return jsonify({'ok': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/save', methods=['POST'])
def save_setlist():
    """Save all slot song lists to a pipe-delimited TXT file."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        slots = ws.get_cuelist_slots()
        lines = [
            '# QLC+ Swiss Knife — Setlist\n',
            '# Format: slot_id|song1|song2|...\n',
        ]
        for slot in slots:
            sid   = slot['id']
            songs = ws.get_slot_songs(sid)
            if songs:
                lines.append(f'{sid}|' + '|'.join(songs) + '\n')
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return jsonify({'ok': True, 'path': path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
