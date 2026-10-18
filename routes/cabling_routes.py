"""routes/cabling_routes.py — Cabling (3.6.0).

Plans the DMX cabling of the show in progress with your kit.  The show is
only read; the plan lives in ``<show>.cabling.json`` next to it and your kit
in settings.

    GET  /api/cabling/state        rig, tonight's plan, evaluation, found in the show
    POST /api/cabling/plan         {plan}: keep tonight's plan (<show>.cabling.json)
    POST /api/cabling/evaluate     {plan}: check a plan without keeping it
    GET  /api/cabling/kit          your kit and the presets
    POST /api/cabling/kit          {kit}: keep your kit (settings)
    POST /api/cabling/kit/item     {item}: check one kit item (the clean item or the error)
"""

import copy
import os
import re

from flask import Blueprint, jsonify, request

from core import qxw_io, workspace
from core.cabling import kit as kit_mod
from core.cabling import plan as plan_mod
from core.cabling import rig as rig_mod
from routes.doctor_routes import _defs, _open_workspace

bp = Blueprint('cabling', __name__, url_prefix='/api/cabling')

_mem = {'for': None, 'plan': None}   # when the show has no folder of its own


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def _real_path() -> str:
    p = workspace.get_state().get('path') or ''
    return p if p and os.path.isfile(p) else ''


def _sidecar() -> str:
    p = _real_path()
    return plan_mod.sidecar_path(p) if p else ''


def _rig():
    """The show in progress as the planner sees it, read fresh each time (a
    fixture moved on the stage moves its cable)."""
    root, path, name = _open_workspace()
    if root is None:
        return None
    if _mem['for'] != (path, name):           # another show: its own plan
        _mem.update({'for': (path, name), 'plan': None})
    stripped = qxw_io.strip_ns(copy.deepcopy(root))
    return rig_mod.read_rig(stripped, _defs(path), path or '')


def _current_plan() -> tuple:
    side = _sidecar()
    saved = plan_mod.load_plan(side) if side else None
    return (saved or _mem['plan'] or plan_mod.new_plan()), bool(saved)


@bp.route('/state')
def state():
    r = _rig()
    if r is None:
        return jsonify({'error': 'No workspace open.'}), 400
    p, saved = _current_plan()
    return jsonify({'rig': r, 'plan': p, 'saved': saved,
                    'sidecar': os.path.basename(_sidecar()) if _sidecar() else '',
                    'evaluation': plan_mod.evaluate(p, r),
                    'found': plan_mod.not_in_inventory(p, r)})


@bp.route('/evaluate', methods=['POST'])
def evaluate():
    r = _rig()
    if r is None:
        return jsonify({'error': 'No workspace open.'}), 400
    p = plan_mod.clean_plan((request.get_json(silent=True) or {}).get('plan'))
    return jsonify({'plan': p, 'evaluation': plan_mod.evaluate(p, r),
                    'found': plan_mod.not_in_inventory(p, r)})


@bp.route('/plan', methods=['POST'])
def save_plan():
    r = _rig()
    if r is None:
        return jsonify({'error': 'No workspace open.'}), 400
    p = plan_mod.clean_plan((request.get_json(silent=True) or {}).get('plan'))
    side = _sidecar()
    if not side:
        _mem['plan'] = p
        return jsonify({'ok': True, 'saved': False, 'plan': p})
    try:
        plan_mod.save_plan(p, side)
    except OSError as e:
        return jsonify({'error': _safe_err(e)}), 500
    return jsonify({'ok': True, 'saved': True, 'sidecar': os.path.basename(side), 'plan': p})


@bp.route('/kit', methods=['GET'])
def get_kit():
    return jsonify({'kit': kit_mod.load_base(), 'presets': kit_mod.presets(),
                    'connectors': list(kit_mod.CONNECTORS), 'kinds': list(kit_mod.KINDS)})


@bp.route('/kit', methods=['POST'])
def save_kit():
    data = (request.get_json(silent=True) or {}).get('kit')
    inv = kit_mod.clean_inventory(data)
    if inv.get('dropped'):
        return jsonify({'error': 'Some items cannot be used.', 'dropped': inv['dropped']}), 400
    try:
        kit_mod.save_base(inv)
    except OSError as e:
        return jsonify({'error': _safe_err(e)}), 500
    return jsonify({'ok': True, 'kit': kit_mod.load_base()})


@bp.route('/kit/item', methods=['POST'])
def check_item():
    try:
        return jsonify({'item': kit_mod.clean_item((request.get_json(silent=True) or {}).get('item'))})
    except kit_mod.KitError as e:
        return jsonify({'error': str(e)}), 400
