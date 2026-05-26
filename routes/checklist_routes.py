"""routes/checklist_routes.py — Setup Checklist API (fully implemented)."""

from flask import Blueprint, jsonify, Response
from core import workspace as ws

bp = Blueprint('checklist', __name__, url_prefix='/api/checklist')


@bp.route('/fixtures')
def fixtures():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_fixtures())


@bp.route('/export-txt', methods=['POST'])
def export_txt():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    rows = ws.get_fixtures()
    lines = [
        'QLC+ Swiss Knife — Setup Checklist\n',
        '=' * 64 + '\n',
        f'{"ID":<6} {"Name":<32} {"Uni":>4} {"Addr":>5}  {"Groups"}\n',
        '-' * 64 + '\n',
    ]
    for r in rows:
        lines.append(
            f'{r["id"]:<6} {r["name"][:32]:<32} {r["universe"]:>4} '
            f'{r["address"]:>5}  {r["groups"]}\n'
        )
    txt = ''.join(lines)
    return Response(
        txt,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename=checklist.txt'},
    )
