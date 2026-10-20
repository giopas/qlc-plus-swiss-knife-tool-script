"""routes/show_routes.py — the show in progress (WORKPLAN Phase 2.6).

    GET  /api/show/status    name, steps, unsaved, changed tools, Doctor counts
    GET  /api/show/history   the steps
    POST /api/show/undo      {n}: back to before step n (default: the last one)
    GET  /api/show/file      the show as a .qxw (for the Save dialog)
    POST /api/show/saved     {qxw_path}: the file was saved there → report + mark saved
    POST /api/show/save      {path}: write the show there (server side) + report
    GET  /api/show/definitions  where each fixture definition was found, and which travel
    GET  /api/show/travel    the "take the show elsewhere" zip (for the Save dialog)
    POST /api/show/travel    {path}: write that zip there (a new file, never over one)
"""

import os
import re

from flask import Blueprint, Response, jsonify, request

from core import show, workspace

bp = Blueprint('show', __name__, url_prefix='/api/show')

_doctor_cache: dict = {}


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def doctor_counts() -> dict:
    """Errors / warnings / infos of the show as it is now (cached per change)."""
    v = show.version()
    if _doctor_cache.get('version') == v and _doctor_cache.get('path') == workspace._state.get('path'):
        return _doctor_cache['counts']
    from core.doctor import check
    from routes.doctor_routes import _defs
    st = workspace._state
    rep = check(st['qxw_root'], _defs(st.get('path') or ''))
    counts = rep.severity_counts()
    _doctor_cache.update({'version': v, 'path': st.get('path'), 'counts': counts})
    return counts


def applied(tool: str, title: str, new_root, report: str = '', detail: str = ''):
    """Adopt a tool's result as the show; JSON for the client."""
    res = show.apply_result(tool, title, new_root, report, detail, doctor=doctor_counts)
    res['show']['doctor'] = doctor_counts()
    return jsonify(res)


def touched_ok(payload: dict | None = None) -> dict:
    """Attach the show status to a live-edit response."""
    out = dict(payload or {})
    out['show'] = show.status()
    return out


@bp.route('/status')
def status():
    st = show.status()
    if st.get('active') and request.args.get('doctor', '1') != '0':
        try:
            st['doctor'] = doctor_counts()
        except Exception:  # noqa: BLE001
            st['doctor'] = None
    return jsonify(st)


@bp.route('/history')
def history():
    return jsonify({'show': show.status(), 'steps': show.history()})


@bp.route('/undo', methods=['POST'])
def undo():
    if not show.active():
        return jsonify({'error': 'No show open.'}), 400
    n = (request.get_json(silent=True) or {}).get('n')
    try:
        st = show.undo_to(int(n)) if n else show.undo_last()
        return jsonify({'ok': True, 'show': st})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/redo', methods=['POST'])
def redo():
    if not show.active():
        return jsonify({'error': 'No show open.'}), 400
    try:
        return jsonify({'ok': True, 'show': show.redo()})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/file')
def file():
    if not show.active():
        return jsonify({'error': 'No show open.'}), 400
    name = show.suggested_name()
    return Response(show.show_bytes(), mimetype='application/octet-stream',
                    headers={'Content-Disposition': f'attachment; filename="{name}"',
                             'X-Suggested-Filename': name,
                             'Access-Control-Expose-Headers': 'X-Suggested-Filename'})


def _fixture_files(qxw: str) -> dict:
    """A show started from a profile's rig: write the fixture definitions QLC+
    lacks next to the saved file (as Quick Start does)."""
    if not (qxw and show._show.get('qxf_pending')):
        return {}
    folder = os.path.dirname(os.path.abspath(qxw))
    if not os.path.isdir(folder):
        return {}
    try:
        from routes import quick_start_routes as qs
        r = qs.write_qxf(folder)
        return {'fixture_files': r['files'], 'fixture_warnings': r['warnings']}
    except Exception:  # noqa: BLE001 — never block a save
        return {}


@bp.route('/saved', methods=['POST'])
def saved():
    """The client saved /file with the Save dialog.  qxw_path is known when the
    native dialog wrote it (the report goes next to it); a browser download
    only gives the name."""
    body = request.get_json(silent=True) or {}
    qxw = (body.get('qxw_path') or '').strip()
    name = (body.get('name') or '').strip()
    try:
        if qxw and qxw.lower().endswith('.qxw') and os.path.isdir(os.path.dirname(os.path.abspath(qxw))):
            out = show.mark_saved(os.path.abspath(qxw))
        else:
            out = show.mark_saved('')
            show._show['saved_name'] = os.path.basename(name) if name else show._show['saved_name']
        return jsonify({'ok': True, **out, **_fixture_files(qxw), 'show': show.status()})
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/save', methods=['POST'])
def save():
    path = ((request.get_json(silent=True) or {}).get('path') or '').strip()
    if not show.active():
        return jsonify({'error': 'No show open.'}), 400
    if not path.lower().endswith('.qxw'):
        return jsonify({'error': 'Choose a .qxw file name.'}), 400
    try:
        # cue notes follow the show: a button added or renamed since the notes
        # were written is named in them (only when something changed, so a
        # save without changes stays an identical copy)
        if show.status().get('steps'):
            from core import workspace as _ws
            if _ws.cue_notes_missing():
                _ws.fill_cue_notes()
                show.close_step()
        out = show.save(os.path.abspath(path))
        return jsonify({'ok': True, **out, **_fixture_files(path), 'show': show.status()})
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 400


@bp.route('/report')
def report_text():
    return Response(show.report(), mimetype='text/plain; charset=utf-8')


# ── Take the show elsewhere (3.7.0) ──────────────────────────────────────────

def _definition_rows():
    from core import definitions
    from routes.doctor_routes import _defs
    path = workspace._state.get('path') or ''
    return definitions.describe(workspace._state['qxw_root'], _defs(path), path), path


def _travel_name() -> str:
    st = show.status()
    if st.get('unsaved') == 0 and st.get('saved_name'):
        return st['saved_name']
    return st['source_name'] if not st.get('steps') else st['suggested_name']


@bp.route('/definitions')
def definitions_info():
    """Where each fixture definition of the show was found (QLC+ library, user
    folder, show folder) and which have to travel with it."""
    if not show.active():
        return jsonify({'error': 'No show open.'}), 400
    rows, _path = _definition_rows()
    return jsonify({'definitions': rows, 'travelling': sum(1 for r in rows if r['travels']),
                    'missing': sum(1 for r in rows if not r['found'])})


def _travel_zip():
    from core import definitions
    rows, path = _definition_rows()
    name = _travel_name()
    return name, definitions.build_zip(name, show.show_bytes(), rows, path)


@bp.route('/travel', methods=['GET', 'POST'])
def travel():
    if not show.active():
        return jsonify({'error': 'No show open.'}), 400
    try:
        name, data = _travel_zip()
        from core import definitions
        zname = definitions.zip_name(name)
        if request.method == 'GET':
            return Response(data, mimetype='application/zip',
                            headers={'Content-Disposition': f'attachment; filename="{zname}"',
                                     'X-Suggested-Filename': zname,
                                     'Access-Control-Expose-Headers': 'X-Suggested-Filename'})
        path = ((request.get_json(silent=True) or {}).get('path') or '').strip()
        if not path.lower().endswith('.zip'):
            return jsonify({'error': 'Choose a .zip file name.'}), 400
        path = os.path.abspath(path)
        if os.path.exists(path):
            return jsonify({'error': 'That file exists already; choose another name.'}), 400
        if not os.path.isdir(os.path.dirname(path)):
            return jsonify({'error': 'That folder does not exist.'}), 400
        with open(path, 'xb') as fh:
            fh.write(data)
        return jsonify({'ok': True, 'path': path, 'name': os.path.basename(path)})
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': _safe_err(e)}), 400
