"""routes/colours_routes.py — Copy Colours (3.23.0).

  GET  /api/colours/fixtures — the show's fixtures, what they can do, how many looks set them
  POST /api/colours/preview  — what a copy would change (nothing is changed)
  POST /api/colours/apply    — copy in the show in progress (a step in its History)

Body of preview and apply: ``{"pairs": [{"target": id, "source": id}, …],
"brightness": "keep" | "source", "add": bool}``."""

import copy

from flask import Blueprint, jsonify, request

from core import colour_copy, qxw_io
from routes.doctor_routes import _defs, _open_workspace

bp = Blueprint('colours', __name__, url_prefix='/api/colours')


def _root():
    root, path, _name = _open_workspace()
    if root is None:
        return None, None
    return qxw_io.strip_ns(copy.deepcopy(root)), path


def _body():
    d = request.get_json(force=True) or {}
    plan = {}
    for p in d.get('pairs') or []:
        if isinstance(p, dict) and p.get('target') not in (None, '') and p.get('source') not in (None, ''):
            plan[str(p['target'])] = str(p['source'])
    brightness = d.get('brightness') or 'keep'
    if brightness not in colour_copy.BRIGHTNESS:
        raise ValueError('brightness must be "keep" or "source"')
    return plan, brightness, bool(d.get('add'))


@bp.route('/fixtures')
def fixtures():
    root, path = _root()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    return jsonify({'fixtures': colour_copy.fixtures(root, _defs(path))})


def _run():
    root, path = _root()
    if root is None:
        return None, (jsonify({'error': 'No workspace open.'}), 400)
    try:
        plan, brightness, add = _body()
    except ValueError as e:
        return None, (jsonify({'error': str(e)}), 400)
    if not plan:
        return None, (jsonify({'error': 'Choose at least one fixture and the fixture it takes its colours from.'}), 400)
    return (colour_copy.run(root, plan, _defs(path), brightness, add), plan), None


def _public(res):
    rep = res['report']
    return {'pairs': rep['pairs'], 'problems': rep['problems'], 'total': rep['total'],
            'lines': res['lines'], 'doctor': res['doctor'], 'blocked': res['blocked']}


@bp.route('/preview', methods=['POST'])
def preview():
    got, err = _run()
    if err:
        return err
    return jsonify(_public(got[0]))


@bp.route('/apply', methods=['POST'])
def apply():
    got, err = _run()
    if err:
        return err
    res, plan = got
    if res['blocked']:
        return jsonify({'error': 'Doctor found new errors in the result; not applied.',
                        'findings': res['doctor']['new_errors']}), 422
    if not res['report']['total']:
        return jsonify({'error': 'Nothing to change: ' + ' '.join(res['lines'])[:400]}), 400
    from routes.show_routes import applied
    rep = res['report']
    names = {f['id']: f['name'] for f in colour_copy.fixtures(res['root'], {})}
    if len(rep['pairs']) == 1:
        t, st = next(iter(rep['pairs'].items()))
        title = f"'{names.get(t, t)}' takes the colours of '{names.get(st['source'], st['source'])}'"
    else:
        title = f"{len(rep['pairs'])} fixtures take the colours of others"
    out = applied('colours', title, res['root'], '\n'.join(res['lines']) + '\n',
                  f"{rep['total']} look(s) changed")
    body = out.get_json()
    body.update(_public(res))
    return jsonify(body)
