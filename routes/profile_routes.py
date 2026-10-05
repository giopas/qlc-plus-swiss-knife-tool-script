"""routes/profile_routes.py — Show Profiles and the recipe from the History
(WORKPLAN 3.1, v2.1.0).

    GET  /api/profile/recipe   the recipe of the show in progress, as it is now
    GET  /api/profile/list     the saved profiles
    POST /api/profile/save     {name, description}: the show's changes as a profile
    POST /api/profile/apply    {name | path, params}: apply a profile to the open show
    POST /api/profile/start    {name | path, params}: a profile with its own rig builds a show from
                               nothing (replaces the open show), then applies its steps
    POST /api/profile/save     also {include_rig, steps:false, stage, project_name}: keep the Quick Start
                               rig inside (steps:false = the rig alone, without the show's changes)
    GET  /api/profile/<name>   the steps (for the step editor)
    POST /api/profile/edit     {name, steps: [indices in the new order], title?, description?}
    POST /api/profile/delete   {name}

None of these calls is recorded in the recipe (the calls a profile makes are).
"""

import json
import os
import re

from flask import Blueprint, Response, current_app, jsonify, request

from core import profile as prof
from core import recipe, show, workspace

bp = Blueprint('profile', __name__, url_prefix='/api/profile')


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def _loaded():
    return workspace._state.get('loaded')


@bp.route('/recipe')
def get_recipe():
    """The recipe so far, without saving the show (History › Save the recipe)."""
    if not _loaded() or not recipe.active():
        return jsonify({'error': 'No show open.'}), 400
    data = recipe.snapshot()
    stem = os.path.splitext(workspace._state.get('original_name')
                            or os.path.basename(workspace._state.get('path') or 'show'))[0]
    name = f'{stem}.recipe.json'
    return Response(json.dumps(data, indent=1, ensure_ascii=False), mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename="{name}"',
                             'X-Suggested-Filename': name,
                             'X-Calls': str(len(data.get('calls', []))),
                             'Access-Control-Expose-Headers': 'X-Suggested-Filename, X-Calls'})


@bp.route('/list')
def list_():
    return jsonify({'profiles': prof.list_profiles(), 'folder': prof.profiles_dir(),
                    'changes': len(recipe.snapshot().get('calls', [])) if recipe.active() else 0})


@bp.route('/save', methods=['POST'])
def save():
    d = request.get_json(force=True) or {}
    start = None
    if d.get('include_rig'):
        from routes import quick_start_routes as qs
        start = qs.snapshot(d.get('stage'), str(d.get('project_name') or ''))
        if not start:
            return jsonify({'error': 'The Quick Start rig is empty — build the rig in Quick Start first.'}), 400
    # rig only (Quick Start: "Save the rig as a profile"): the show's changes are left out
    keep_steps = d.get('steps', True) is not False
    snap = recipe.snapshot() if (keep_steps and _loaded() and recipe.active()) else {}
    has_calls = bool(snap.get('calls'))
    if not start and not (_loaded() and recipe.active()):
        return jsonify({'error': 'No show open.'}), 400
    if not start and not has_calls:
        return jsonify({'error': 'No changes yet — a profile keeps the changes you make to the show.'}), 400
    try:
        p = prof.make(snap if has_calls else None, str(d.get('name') or ''), str(d.get('description') or ''), start)
        path = prof.save(p)
    except prof.ProfileError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True, 'name': p['name'], 'steps': len(p['steps']), 'params': list(p['params']),
                    'rig': bool(p.get('start')), 'file': os.path.basename(path), 'path': path})


@bp.route('/start', methods=['POST'])
def start():
    """A profile with its own rig builds a show from nothing and applies its
    steps; the open show is replaced (the client has asked about unsaved changes)."""
    d = request.get_json(force=True) or {}
    p: dict = {}
    try:
        p = prof.load(str(d.get('path') or d.get('name') or ''))
        params = {str(k): str(v) for k, v in (d.get('params') or {}).items() if v}
        prof.resolve_params(p, params)                       # fail before replacing the show
        began = prof.start_show(current_app.test_client(), p)
        res = prof.apply_live(current_app.test_client(), p, params, show_path='')
    except prof.ProfileError as e:
        return jsonify({'error': str(e), 'params': list(p.get('params') or {})}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 500
    return jsonify({'ok': True, 'name': p['name'], 'started': began, **res, 'show': show.status()})


@bp.route('/apply', methods=['POST'])
def apply():
    """Apply a profile to the show in progress: each step becomes a step of
    its History (undo works); what the show doesn't have is left out."""
    if not _loaded():
        return jsonify({'error': 'Open a show first.'}), 400
    d = request.get_json(force=True) or {}
    p: dict = {}
    try:
        p = prof.load(str(d.get('path') or d.get('name') or ''))
        params = {str(k): str(v) for k, v in (d.get('params') or {}).items() if v}
        res = prof.apply_live(current_app.test_client(), p, params,
                              show_path=workspace._state.get('path') or '')
    except prof.ProfileError as e:
        return jsonify({'error': str(e), 'params': list(p.get('params') or {})}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 500
    return jsonify({'ok': True, 'name': p['name'], **res, 'show': show.status()})


@bp.route('/delete', methods=['POST'])
def delete():
    d = request.get_json(force=True) or {}
    try:
        ok = prof.delete(str(d.get('name') or ''))
    except prof.ProfileError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': ok, 'profiles': prof.list_profiles()})


# ── step editor (v2.3) ───────────────────────────────────────────────────────

@bp.route('/steps')
def steps():
    """A saved profile's steps, for the editor."""
    try:
        p = prof.load(request.args.get('name', ''))
    except prof.ProfileError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'name': p['name'], 'description': p.get('description', ''),
                    'rig': bool(p.get('start')),
                    'steps': [{'n': i, 'title': s.get('title') or s['path'], 'path': s['path']}
                              for i, s in enumerate(p.get('steps', []))]})


@bp.route('/edit', methods=['POST'])
def edit():
    """Rename a profile's steps, drop some, change their order.
    ``order``: the old step numbers to keep, in the new order;
    ``titles``: {old number: new title}."""
    d = request.get_json(force=True) or {}
    try:
        p = prof.load(str(d.get('name') or ''))
        p = prof.edit(p, d.get('order'), d.get('titles') or {}, d.get('description'))
        path = prof.save(p)
    except prof.ProfileError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True, 'name': p['name'], 'steps': len(p['steps']), 'path': path})
