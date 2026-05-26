"""
routes/triggers_routes.py
=========================
Trigger Manager API — porting in progress.

PORTING GUIDE
-------------
Source class: TriggerManagerTab  (qlc_swiss_knife_0.7.3.py)
Key methods to port:
  - on_qxw_loaded()       → populate table with all VC keyboard/MIDI bindings
  - save_qxw()            → write trigger changes back to the XML tree + file
  - _find_duplicates()    → highlight conflicting key/MIDI assignments

Planned endpoints:
  GET  /api/triggers            → all trigger bindings (from vc_widgets)
  PATCH /api/triggers/<id>      → update key/MIDI/function for one widget
  POST /api/triggers/save       → write changes back to the .qxw file
  GET  /api/triggers/duplicates → list conflicting key assignments

Note: vc_widgets already contains widget_id, caption, func_id, frame_path.
The trigger tab additionally needs KeySequence and Input (MIDI) nodes from
the raw XML — those need to be parsed in _parse_vc_node or a separate pass.
"""

from flask import Blueprint, jsonify
from core import workspace as ws

bp = Blueprint('triggers', __name__, url_prefix='/api/triggers')


@bp.route('/')
def triggers():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify({'status': 'not_implemented',
                    'message': 'Trigger Manager porting in progress.'})
