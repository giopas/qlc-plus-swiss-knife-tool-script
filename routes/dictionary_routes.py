"""routes/dictionary_routes.py — Dictionary Manager API (fully implemented)."""

from flask import Blueprint, jsonify, request
from core import workspace as ws

bp = Blueprint('dictionary', __name__, url_prefix='/api/dictionary')


@bp.route('/')
def get_dictionary():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_dictionary())


@bp.route('/<fid>', methods=['PATCH'])
def update_entry(fid):
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    ws.update_description(fid, data.get('desc', ''))
    return jsonify({'ok': True})


@bp.route('/load', methods=['POST'])
def load_dict():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        count = ws.load_dictionary(path)
        return jsonify({'ok': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/save', methods=['POST'])
def save_dict():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        ws.save_dictionary(path)
        return jsonify({'ok': True, 'path': path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
