"""routes/fixture_routes.py — Fixture Configurator API (read-only rig view).

Full configurator (canvas, QXF loading, auto-DMX, QXW generation) is a
future enhancement.  This endpoint surfaces the workspace fixture list so
the Fixture tab can display it immediately.
"""

from flask import Blueprint, jsonify
from core import workspace as ws

bp = Blueprint('fixture', __name__, url_prefix='/api/fixture')


@bp.route('/rig')
def rig():
    """Return the list of fixtures parsed from the loaded workspace."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_fixtures())
