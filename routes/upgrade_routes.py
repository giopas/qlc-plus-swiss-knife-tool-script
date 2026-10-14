"""routes/upgrade_routes.py — Upgrade to QLC+ 5.3 (3.2.0).

Gives a show made with QLC+ 5.0 to 5.2 what QLC+ 5.3 offers, in the show in
progress.

    GET  /api/upgrade/analyse?target=5.3   what each step would do
    POST /api/upgrade/apply                {steps: [...], target}: apply them
                                           (a step in the history)
"""

import re

from flask import Blueprint, jsonify, request

from core import upgrade53
from routes.doctor_routes import _defs, _open_workspace

bp = Blueprint('upgrade', __name__, url_prefix='/api/upgrade')


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def report(actions: list, source: str = '', target: str = '5.3') -> str:
    """The upgrade report, one line per action, grouped by step."""
    lines = ['═══ Upgrade to QLC+ 5.3 — Report ═══', '']
    if source:
        lines += [f'Show:    {source}']
    lines += [f'Target:  QLC+ {target}', '']
    for step in upgrade53.STEPS:
        acts = [a['action'] for a in actions if a['step'] == step]
        if acts:
            lines.append(f'── {step} ──')
            lines += [f'  {a}' for a in acts]
            lines.append('')
    if not actions:
        lines.append('Nothing to add.')
    return '\n'.join(lines) + '\n'


@bp.route('/analyse')
def analyse():
    root, path, _name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    try:
        return jsonify(upgrade53.analyse(root, _defs(path), request.args.get('target', '5.3')))
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/apply', methods=['POST'])
def apply():
    root, path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    body = request.get_json(silent=True) or {}
    target = body.get('target') if body.get('target') in upgrade53.TARGETS else '5.3'
    steps = [s for s in (body.get('steps') or []) if s in upgrade53.STEPS]
    if not steps:
        return jsonify({'error': 'Tick at least one step.'}), 400
    try:
        from routes.show_routes import applied
        new_root, actions = upgrade53.upgrade(root, _defs(path), steps, target)
        if not actions:
            return jsonify({'error': 'Nothing to add for the steps you ticked.'}), 400
        done = sorted({a['step'] for a in actions}, key=upgrade53.STEPS.index)
        return applied('upgrade', f'{len(actions)} change(s): ' + ', '.join(done), new_root,
                       report(actions, name, target), '; '.join(a['action'] for a in actions[:3])
                       + (' …' if len(actions) > 3 else ''))
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 500
