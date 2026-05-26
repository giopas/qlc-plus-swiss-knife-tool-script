"""
routes/setlist_routes.py
========================
Setlist Manager API — porting in progress.

PORTING GUIDE
-------------
Source class: SetlistManagerTab  (qlc_swiss_knife_0.7.3.py)
Key methods to port:
  - on_qxw_loaded()        → populate slot list from workspace cuelist IDs
  - load_txt() / save_txt() → read/write plain-text setlist files
  - _generate_chaser()     → clone a chaser for each slot
  - export_pdf()           → per-slot PDF output

Planned endpoints:
  GET  /api/setlist/slots          → list of CueList slots in the workspace
  GET  /api/setlist/<slot>/songs   → song list for a slot
  POST /api/setlist/<slot>/songs   → update song list
  POST /api/setlist/<slot>/generate → generate cloned chaser
  POST /api/setlist/<slot>/export-pdf
"""

from flask import Blueprint, jsonify
from core import workspace as ws

bp = Blueprint('setlist', __name__, url_prefix='/api/setlist')


@bp.route('/slots')
def slots():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    # TODO: return CueList-backed slots parsed from workspace
    return jsonify({'status': 'not_implemented',
                    'message': 'Setlist Manager porting in progress.'})
