"""
routes/checklist_routes.py
==========================
Setup Checklist API — porting in progress.

PORTING GUIDE
-------------
Source class: SetupChecklistTab  (qlc_swiss_knife_0.7.3.py)
Key methods to port:
  - on_qxw_loaded()       → build fixture/group/patch table from workspace
  - export_pdf()          → blueprint PDF with fixture patches
  - export_txt()          → plain-text checklist file

Planned endpoints:
  GET  /api/checklist/fixtures   → fixture list (name, uni, addr, groups, pos)
  POST /api/checklist/export-pdf → return PDF blob
  POST /api/checklist/export-txt → return plain-text file

Note: fixture data is already available via ws.get_fixtures() — the
checklist route mainly needs to format it differently and add the
blueprint/PDF rendering layer.
"""

from flask import Blueprint, jsonify
from core import workspace as ws

bp = Blueprint('checklist', __name__, url_prefix='/api/checklist')


@bp.route('/fixtures')
def fixtures():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_fixtures())   # already implemented in workspace.py
