"""
routes/dictionary_routes.py
===========================
Dictionary Manager API — porting in progress.

PORTING GUIDE
-------------
Source class: DictionaryManagerTab  (qlc_swiss_knife_0.7.3.py)
Key methods to port:
  - load_txt() / save_txt()    → read/write ID→description .txt files
  - update_inspector()         → merge descriptions with func_detailed
  - on_qxw_loaded()            → re-populate after workspace load

Planned endpoints:
  GET  /api/dictionary          → all ID→description entries
  POST /api/dictionary          → create or update an entry
  DELETE /api/dictionary/<id>   → remove an entry
  POST /api/dictionary/load     → load a .txt dictionary file
  POST /api/dictionary/save     → save current dictionary to .txt
"""

from flask import Blueprint, jsonify
from core import workspace as ws

bp = Blueprint('dictionary', __name__, url_prefix='/api/dictionary')


@bp.route('/')
def get_dictionary():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    # shared_descriptions lives in ws._state but is populated by the dict tab
    return jsonify({'status': 'not_implemented',
                    'message': 'Dictionary Manager porting in progress.'})
