"""
routes/id_browser_routes.py
===========================
  GET /api/functions   → all Engine functions (ID Browser — Functions sub-tab)
  GET /api/vc-widgets  → all VC widgets      (ID Browser — VC Widgets sub-tab)

Both endpoints return JSON arrays ready for Grid.js consumption.
CSV export is handled entirely client-side (no server round-trip needed).
PDF export posts to the respective /pdf endpoint and receives a PDF blob.
"""

from flask import Blueprint, jsonify, request, Response
from core import workspace as ws

bp = Blueprint('id_browser', __name__, url_prefix='/api')


@bp.route('/functions')
def functions():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_functions())


@bp.route('/vc-widgets')
def vc_widgets():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_vc_widgets())
