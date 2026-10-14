"""routes/wizard_routes.py — Wizard Repair (3.1.0).

Finishes a show made by the QLC+ 5.3 Show Wizard, in the show in progress.

    GET  /api/wizard/analyse   what each repair step would do
    POST /api/wizard/repair    {steps: [...]}: apply them (a step in the history)
"""

import re

from flask import Blueprint, jsonify, request

from core import wizard_repair
from routes.doctor_routes import _defs, _open_workspace

bp = Blueprint('wizard', __name__, url_prefix='/api/wizard')


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def report(actions: list, source: str = '') -> str:
    """The repair report, one line per action, grouped by step."""
    lines = ['═══ Wizard Repair — Report ═══', '']
    if source:
        lines += [f'Show:  {source}', '']
    for step in wizard_repair.STEPS:
        acts = [a['action'] for a in actions if a['step'] == step]
        if acts:
            lines.append(f'── {step} ──')
            lines += [f'  {a}' for a in acts]
            lines.append('')
    if not actions:
        lines.append('Nothing to repair.')
    return '\n'.join(lines) + '\n'


@bp.route('/analyse')
def analyse():
    root, path, _name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    try:
        return jsonify(wizard_repair.analyse(root, _defs(path)))
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/repair', methods=['POST'])
def repair():
    root, path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    body = request.get_json(silent=True) or {}
    steps = [s for s in (body.get('steps') or []) if s in wizard_repair.STEPS]
    if not steps:
        return jsonify({'error': 'Tick at least one repair.'}), 400
    try:
        from routes.show_routes import applied
        new_root, actions = wizard_repair.repair(root, _defs(path), steps)
        if not actions:
            return jsonify({'error': 'Nothing to repair for the steps you ticked.'}), 400
        done = sorted({a['step'] for a in actions}, key=wizard_repair.STEPS.index)
        return applied('wizard', f'{len(actions)} change(s): ' + ', '.join(done), new_root,
                       report(actions, name), '; '.join(a['action'] for a in actions[:3])
                       + (' …' if len(actions) > 3 else ''))
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 500
