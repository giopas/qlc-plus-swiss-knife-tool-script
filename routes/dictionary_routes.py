"""routes/dictionary_routes.py — Dictionary Manager API (fully implemented)."""

from flask import Blueprint, jsonify, request, Response
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


@bp.route('/export-txt', methods=['POST'])
def export_txt():
    """Download the full dictionary (all functions) as ID|Name|Description TXT."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    rows = ws.get_dictionary()
    lines = ['ID|Name|Type|Description\n']
    for r in sorted(rows, key=lambda x: int(x['id']) if str(x['id']).isdigit() else 0):
        desc = (r.get('desc') or '').replace('\n', '\\n')
        lines.append(f"{r['id']}|{r['name']}|{r.get('type','')}|{desc}\n")
    import os
    state = ws.get_state()
    _src = state.get('original_name') or state.get('path') or 'workspace'
    bn   = os.path.splitext(os.path.basename(_src))[0]
    filename = f'{bn}_ID_dictionary.txt'
    return Response(
        ''.join(lines),
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )
