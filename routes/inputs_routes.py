"""routes/inputs_routes.py — Inputs & MIDI panel of the Trigger Manager (v2.6.0).

Edits the show in progress: the universes' input patch and the Virtual
Console bindings (core.input_manager); every edit is a step of the show's
History."""

import copy
import re

from flask import Blueprint, jsonify, request

from core import input_manager as im, qxw_io, workspace
from routes.doctor_routes import _open_workspace

bp = Blueprint('inputs', __name__, url_prefix='/api/inputs')


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def _state(**extra):
    root, _path, name = _open_workspace()
    w = qxw_io.strip_ns(copy.deepcopy(root))
    return jsonify({'source': name, 'universes': im.universes(w), 'widgets': im.widgets_with_input(w),
                    'controllers': im.controllers(), 'profiles': im.profiles(),
                    'plugins': im.INPUT_PLUGINS,
                    'kinds': [{'id': k, 'label': l, 'count': n} for k, l, _o, n in im.KINDS], **extra})


def _put_back(live, edited, vc: bool) -> None:
    """Replace <InputOutputMap> (and the VC) of the live tree by the edited copy."""
    eng = next((c for c in live if c.tag.endswith('Engine')), None)
    src = edited.find('Engine')
    if eng is None or src is None:
        return
    for tag, parent, new_parent in [('InputOutputMap', eng, src)] + ([('VirtualConsole', live, edited)] if vc else []):
        new = new_parent.find(tag)
        old = next((c for c in parent if c.tag.endswith(tag)), None)
        idx = list(parent).index(old) if old is not None else len(parent)
        if old is not None:
            parent.remove(old)
        if new is not None:
            parent.insert(idx, qxw_io.qualify_ns(copy.deepcopy(new)))


@bp.route('/state')
def state():
    if _open_workspace()[0] is None:
        return jsonify({'error': 'No workspace open.'}), 400
    return _state()


@bp.route('/simulate', methods=['POST'])
def simulate():
    root, _p, _n = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    d = request.get_json(force=True) or {}
    try:
        if d.get('channel') not in (None, ''):
            ch = int(d['channel'])
        else:
            ch = im.encode(str(d.get('kind') or 'note'), int(d.get('number') or 0), d.get('midi_channel'))
        w = qxw_io.strip_ns(copy.deepcopy(root))
        return jsonify(im.simulate(w, str(d.get('universe') or '0'), ch))
    except (im.InputError, ValueError) as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/decode')
def decode():
    return jsonify(im.decode(request.args.get('channel', '')))


@bp.route('/op', methods=['POST'])
def op():
    live, _p, _n = _open_workspace()
    if live is None:
        return jsonify({'error': 'No workspace open.'}), 400
    d = request.get_json(force=True) or {}
    o = d.get('op')
    try:
        if o in ('remember', 'forget'):
            if o == 'remember':
                im.remember_controller(str(d.get('name', '')), plugin=str(d.get('plugin') or 'MIDI'),
                                       device=str(d.get('device', '')), line=d.get('line') or '0',
                                       profile=str(d.get('profile') or ''), feedback=bool(d.get('feedback', True)))
                return _state(message=f"Controller '{d.get('name')}' remembered.")
            im.forget_controller(str(d.get('name', '')))
            return _state(message='Controller forgotten.')
        w = qxw_io.strip_ns(copy.deepcopy(live))
        vc = False
        if o == 'set_input':
            res = im.set_input(w, str(d.get('universe', '')), plugin=str(d.get('plugin') or 'MIDI'),
                               device=str(d.get('device', '')), line=d.get('line') or '0',
                               profile=str(d.get('profile') or ''), feedback=bool(d.get('feedback')))
            msg, title = f"Universe {int(res['universe']) + 1}: input patched to {res['device']}.", 'input patch'
        elif o == 'apply_controller':
            c = next((x for x in im.controllers() if x['name'] == d.get('name')), None)
            if c is None:
                raise im.InputError('Controller not found.')
            im.set_input(w, str(d.get('universe', '')), plugin=c['plugin'], device=c['device'],
                         line=c['line'], profile=c['profile'], feedback=c['feedback'])
            msg, title = f"Universe {int(d.get('universe')) + 1}: '{c['name']}' patched.", 'input patch'
        elif o == 'clear_input':
            im.clear_input(w, str(d.get('universe', '')))
            msg, title = 'Input cleared.', 'input patch'
        elif o == 'move':
            res = im.move_bindings(w, str(d.get('src', '')), str(d.get('dst', '')), int(d.get('shift') or 0))
            vc = True
            msg, title = f"{res['moved']} binding(s) moved to universe {int(res['dst']) + 1}.", 'bindings moved'
        elif o == 'swap':
            res = im.swap_universes(w, str(d.get('a', '')), str(d.get('b', '')))
            vc = True
            msg, title = f"Universes {int(res['a']) + 1} and {int(res['b']) + 1} swapped.", 'bindings swapped'
        else:
            return jsonify({'error': f'Unknown operation: {o}'}), 400
        workspace._show_touch('inputs', title)
        _put_back(live, w, vc)
        workspace.reparse_after_vc_edit()
        return _state(message=msg)
    except (im.InputError, ValueError) as e:
        return jsonify({'error': _safe_err(e)}), 400
