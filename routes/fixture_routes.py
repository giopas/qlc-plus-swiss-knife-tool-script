"""
routes/fixture_routes.py
========================
Fixture Configurator API — porting in progress.

PORTING GUIDE
-------------
Source class: FixtureConfiguratorTab  (qlc_swiss_knife_0.7.3.py)
Key methods to port:
  - add_fixture() / remove_fixture()  → rig table management
  - _parse_qxf()                      → load a .qxf fixture definition
  - auto_dmx()                        → auto-assign DMX addresses
  - generate_qxw()                    → produce a new .qxw from template

Canvas (the 2D drag-and-drop stage view):
  The tkinter Canvas → HTML5 <canvas> with mouse drag events in JS.
  Position data flows: JS canvas drag → PATCH /api/fixture/<id>/position
  → ws._state['fixture_map'][id]['canvas_x/y'] → picked up by generate_qxw.

Planned endpoints:
  GET  /api/fixture/rig           → current rig (fixture instances)
  POST /api/fixture/rig           → add a fixture instance
  DELETE /api/fixture/rig/<id>    → remove a fixture instance
  PATCH /api/fixture/rig/<id>     → update position / DMX / name
  POST /api/fixture/load-qxf      → parse a .qxf file, return definition
  POST /api/fixture/auto-dmx      → auto-assign DMX to all rig fixtures
  POST /api/fixture/generate-qxw  → produce a new .qxw workspace file
"""

from flask import Blueprint, jsonify
from core import workspace as ws

bp = Blueprint('fixture', __name__, url_prefix='/api/fixture')


@bp.route('/rig')
def rig():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify({'status': 'not_implemented',
                    'message': 'Fixture Configurator porting in progress.'})
