"""
routes/showpic_routes.py
========================
A read-only picture of a Show (3.10.0).  Nothing here changes the show in progress.

  GET /api/showpic/list        — the Shows of the open file: [{id, name}]
  GET /api/showpic/<id>        — the tracks and items of one Show
"""

import os

from flask import Blueprint, jsonify

import core.workspace as ws
from core import show_picture

bp = Blueprint('showpic', __name__, url_prefix='/api/showpic')


def _engine():
    st = ws._state
    if not st.get('loaded') or st.get('qxw_root') is None:
        raise ValueError('No workspace loaded.')
    eng = st['qxw_root'].find('q:Engine', ws.NS)
    if eng is None:
        raise ValueError('The workspace has no <Engine> element.')
    return eng


@bp.route('/list')
def pic_list():
    try:
        return jsonify(show_picture.shows(_engine()))
    except ValueError as e:
        return jsonify({'error': str(e)[:300]}), 400


@bp.route('/<show_id>')
def pic_show(show_id):
    try:
        path = ws._state.get('path') or ''
        base = '' if ws._state.get('original_name') else (os.path.dirname(os.path.abspath(path)) if path else '')
        return jsonify(show_picture.picture(_engine(), show_id[:20], base))
    except ValueError as e:
        return jsonify({'error': str(e)[:300]}), 400
