"""
routes/session_routes.py
========================
API for the .qsk session / project file feature.

  GET  /api/session/current        — current session state + dirty flag
  GET  /api/session/export         — session as JSON (download as .qsk)
  POST /api/session/update-field   — update one field (workspace, dictionary,
                                     setlist_backup, brightness_forced)
  POST /api/session/apply          — apply a full imported session dict:
                                     loads workspace, dictionary, QXF overrides
  POST /api/session/mark-saved     — mark current state as saved (clear dirty)
"""

import os

from flask import Blueprint, jsonify, request

import core.brightness as br
import core.session    as sess
import core.workspace  as ws

bp = Blueprint('session', __name__, url_prefix='/api/session')


def _safe_err(exc: Exception) -> str:
    return str(exc)[:300]


# ── Current state ─────────────────────────────────────────────────────────────

@bp.route('/current')
def current():
    """Return in-memory session state (safe for direct JSON render)."""
    state = sess.get_session()
    # Always reflect the current workspace path from workspace state
    ws_path = ws.get_state().get('path')
    if ws_path and not ws_path.startswith('/tmp') and not ws_path.startswith(
        os.path.join(os.sep, 'var', 'folders')
    ):
        state['workspace'] = ws_path
    return jsonify(state)


# ── Export ────────────────────────────────────────────────────────────────────

@bp.route('/export')
def export():
    """Return the session as a JSON object (client downloads this as .qsk).

    Also includes extra display fields (not saved to .qsk):
      ws_loaded        — bool, whether a workspace is currently loaded
      ws_original_name — filename as uploaded (upload mode only)
      ws_upload_mode   — True when workspace came from a file upload, not a path
      brightness_count — number of forced QXF assignments
    """
    # Sync forced assignments from brightness module before export
    forced = br.get_forced_assignments()
    sess.set_brightness_forced(forced)

    # Sync workspace path (path mode only; upload mode has no usable path)
    ws_state = ws.get_state()
    ws_path  = ws_state.get('path') or ''
    upload_mode = bool(ws_state.get('original_name'))
    if ws_path and not _is_temp(ws_path) and not upload_mode:
        sess.set_workspace(ws_path)

    data = sess.to_export()

    # Attach display-only metadata for the modal
    data['ws_loaded']        = ws_state.get('loaded', False)
    data['ws_original_name'] = ws_state.get('original_name')   # non-None in upload mode
    data['ws_upload_mode']   = upload_mode
    data['brightness_count'] = len(forced)
    data['slot_paths_count'] = len(data.get('slot_paths') or {})
    data['show_name']        = sess.get_show_name()
    data['event_date']       = sess.get_event_date()
    return jsonify(data)


# ── Update one field ──────────────────────────────────────────────────────────

@bp.route('/update-field', methods=['POST'])
def update_field():
    """
    Update a single session field.  Body: {"field": "...", "value": ...}

    Accepted fields: workspace, dictionary, setlist_backup, brightness_forced
    """
    data  = request.get_json(force=True) or {}
    field = (data.get('field') or '').strip()
    value = data.get('value')

    if field == 'workspace':
        sess.set_workspace(value)
    elif field == 'dictionary':
        sess.set_dictionary(value)
    elif field == 'setlist_backup':
        sess.set_setlist_backup(value)
    elif field == 'brightness_forced':
        sess.set_brightness_forced(value or {})
    elif field == 'show_name':
        sess.set_show_name(value or '')
    elif field == 'event_date':
        sess.set_event_date(value or '')
    else:
        return jsonify({'error': f'Unknown field: {field!r}'}), 400

    return jsonify({'ok': True, 'dirty': sess.get_session()['dirty']})


# ── Apply a full imported session ─────────────────────────────────────────────

@bp.route('/apply', methods=['POST'])
def apply_session():
    """
    Apply a complete session dict — typically the parsed content of a .qsk file.

    Body: { "session": { ... session dict ... } }

    Steps (best-effort; errors are reported but do not abort):
      1. Load workspace from path
      2. Load dictionary from path
      3. Restore brightness forced QXF assignments
      4. Record setlist_backup path (client is responsible for loading it)

    Returns:
      {
        "ok": bool,
        "results": { field: "ok" | "skipped" | "error: …" },
        "session": { updated session state }
      }
    """
    data         = request.get_json(force=True) or {}
    session_data = data.get('session') or {}
    results      = {}

    # ── 1. Workspace ──────────────────────────────────────────────────────────
    ws_path = (session_data.get('workspace') or '').strip()
    if ws_path:
        if not os.path.isfile(ws_path):
            results['workspace'] = f'error: file not found — {ws_path}'
        else:
            try:
                ws.load_qxw(ws_path)
                sess.set_workspace(ws_path)
                results['workspace'] = 'ok'
            except Exception as e:
                results['workspace'] = f'error: {_safe_err(e)}'
    else:
        results['workspace'] = 'skipped'

    # ── 2. Dictionary ─────────────────────────────────────────────────────────
    dict_path = (session_data.get('dictionary') or '').strip()
    if dict_path:
        if not os.path.isfile(dict_path):
            results['dictionary'] = f'error: file not found — {dict_path}'
        elif not ws.get_state()['loaded']:
            results['dictionary'] = 'skipped (no workspace loaded)'
        else:
            try:
                count = ws.load_dictionary(dict_path)
                sess.set_dictionary(dict_path)
                results['dictionary'] = f'ok ({count} entries)'
            except Exception as e:
                results['dictionary'] = f'error: {_safe_err(e)}'
    else:
        results['dictionary'] = 'skipped'

    # ── 3. Brightness forced QXF assignments ──────────────────────────────────
    forced = session_data.get('brightness_forced') or {}
    if forced:
        try:
            br.restore_forced_assignments(forced)
            restored = br.get_forced_assignments()
            sess.set_brightness_forced(restored)
            results['brightness_forced'] = f'ok ({len(restored)} assignments)'
        except Exception as e:
            results['brightness_forced'] = f'error: {_safe_err(e)}'
    else:
        results['brightness_forced'] = 'skipped'

    # ── 4. Per-slot file paths — restore slot details from saved paths ───────────
    slot_paths = session_data.get('slot_paths') or {}
    if slot_paths:
        loaded_slots, failed_slots = 0, 0
        for slot_id, path in slot_paths.items():
            path = (path or '').strip()
            if not path or not os.path.isfile(path):
                failed_slots += 1
                continue
            try:
                rows = []
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = line.split('|')
                        if len(parts) >= 6:
                            rows.append({
                                'txt_name': parts[0].strip(),
                                'qxw_id':   parts[1].strip(),
                                'qxw_name': parts[2].strip(),
                                'in':       parts[3].strip() or '0',
                                'hold':     parts[4].strip() or '4294967294',
                                'out':      parts[5].strip() or '0',
                            })
                        else:
                            name = parts[0].strip()
                            if name:
                                rows.append({
                                    'txt_name': name, 'qxw_id': '', 'qxw_name': '',
                                    'in': '0', 'hold': '4294967294', 'out': '0',
                                })
                if ws.get_state()['loaded']:
                    ws.set_slot_details(slot_id, rows)
                    sess.set_slot_path(slot_id, path)
                    loaded_slots += 1
            except Exception:
                failed_slots += 1
        parts = [f'{loaded_slots} slot(s) restored']
        if failed_slots:
            parts.append(f'{failed_slots} missing/failed')
        results['slot_paths'] = 'ok (' + ', '.join(parts) + ')'
    else:
        results['slot_paths'] = 'skipped'

    # ── 5. Auto-match unassigned songs across all restored slots ─────────────────
    # Runs after both workspace and slot files are loaded so find_best_match()
    # can resolve against the live function table.
    if slot_paths and ws.get_state()['loaded']:
        total_matched = 0
        for slot_id in slot_paths:
            rows = ws.get_slot_details(slot_id)
            if not rows:
                continue
            changed = False
            for row in rows:
                if row.get('qxw_id'):        # already assigned — keep it
                    continue
                name = (row.get('txt_name') or '').strip()
                if not name:
                    continue
                matched_name, matched_id = ws.find_best_match(name)
                if matched_id:
                    row['qxw_id']   = matched_id
                    row['qxw_name'] = matched_name
                    total_matched  += 1
                    changed         = True
            if changed:
                ws.set_slot_details(slot_id, rows)
        results['auto_match'] = f'ok ({total_matched} song(s) matched)'
    else:
        results['auto_match'] = 'skipped'

    # Stamp the session as clean after a full apply
    sess.clear_dirty()

    ok = all('error' not in v for v in results.values())
    return jsonify({'ok': ok, 'results': results, 'session': sess.get_session()})


# ── Mark saved ────────────────────────────────────────────────────────────────

@bp.route('/load-from-path', methods=['POST'])
def load_from_path():
    """
    Read a .qsk file from disk and apply it (load workspace, dictionary, etc.).
    Body: { "path": "/abs/path/to/session.qsk" }
    """
    import json as _json

    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    if not os.path.isfile(path):
        return jsonify({'error': f'File not found: {path}'}), 404

    try:
        with open(path, 'r', encoding='utf-8') as f:
            session_data = _json.load(f)
    except Exception as e:
        return jsonify({'error': f'Could not parse .qsk: {_safe_err(e)}'}), 400

    # Apply session (reuse apply logic inline)
    results = {}

    # 1. Workspace
    ws_path = (session_data.get('workspace') or '').strip()
    if ws_path:
        if not os.path.isfile(ws_path):
            results['workspace'] = f'error: file not found'
        else:
            try:
                ws.load_qxw(ws_path)
                sess.set_workspace(ws_path)
                results['workspace'] = 'ok'
            except Exception as e:
                results['workspace'] = f'error: {_safe_err(e)}'
    else:
        results['workspace'] = 'skipped'

    # 2. Dictionary
    dict_path = (session_data.get('dictionary') or '').strip()
    if dict_path and os.path.isfile(dict_path) and ws.get_state()['loaded']:
        try:
            count = ws.load_dictionary(dict_path)
            sess.set_dictionary(dict_path)
            results['dictionary'] = f'ok ({count} entries)'
        except Exception as e:
            results['dictionary'] = f'error: {_safe_err(e)}'
    else:
        results['dictionary'] = 'skipped'

    # 3. Brightness forced QXF assignments
    forced = session_data.get('brightness_forced') or {}
    if forced:
        try:
            br.restore_forced_assignments(forced)
            sess.set_brightness_forced(br.get_forced_assignments())
            results['brightness_forced'] = 'ok'
        except Exception as e:
            results['brightness_forced'] = f'error: {_safe_err(e)}'

    # 4. Per-slot file paths
    slot_paths = session_data.get('slot_paths') or {}
    if slot_paths and ws.get_state()['loaded']:
        loaded_slots = 0
        for slot_id, sp in slot_paths.items():
            sp = (sp or '').strip()
            if not sp or not os.path.isfile(sp):
                continue
            try:
                rows = []
                with open(sp, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = line.split('|')
                        if len(parts) >= 6:
                            rows.append({
                                'txt_name': parts[0].strip(),
                                'qxw_id':   parts[1].strip(),
                                'qxw_name': parts[2].strip(),
                                'in':       parts[3].strip() or '0',
                                'hold':     parts[4].strip() or '4294967294',
                                'out':      parts[5].strip() or '0',
                            })
                        else:
                            name = parts[0].strip()
                            if name:
                                rows.append({'txt_name': name, 'qxw_id': '', 'qxw_name': '',
                                             'in': '0', 'hold': '4294967294', 'out': '0'})
                ws.set_slot_details(slot_id, rows)
                sess.set_slot_path(slot_id, sp)
                loaded_slots += 1
            except Exception:
                pass
        results['slot_paths'] = f'ok ({loaded_slots} slot(s))'

    # 5. Auto-match unassigned songs
    if slot_paths and ws.get_state()['loaded']:
        for slot_id in slot_paths:
            rows = ws.get_slot_details(slot_id)
            if not rows:
                continue
            changed = False
            for row in rows:
                if row.get('qxw_id'):
                    continue
                name = (row.get('txt_name') or '').strip()
                if not name:
                    continue
                matched_name, matched_id = ws.find_best_match(name)
                if matched_id:
                    row['qxw_id']   = matched_id
                    row['qxw_name'] = matched_name
                    changed = True
            if changed:
                ws.set_slot_details(slot_id, rows)

    filename = os.path.basename(path)
    sess.set_session_file(filename)
    sess.clear_dirty()

    ok = all('error' not in v for v in results.values())
    return jsonify({'ok': ok, 'results': results, 'session_file': filename,
                    'session_path': path, 'session': sess.get_session()})


@bp.route('/show-info', methods=['GET'])
def show_info():
    """Return the current show name and event date."""
    return jsonify({
        'show_name':  sess.get_show_name(),
        'event_date': sess.get_event_date(),
    })


@bp.route('/show-info', methods=['POST'])
def update_show_info():
    """Update show name and/or event date."""
    data = request.get_json(force=True) or {}
    if 'show_name' in data:
        sess.set_show_name(data['show_name'] or '')
    if 'event_date' in data:
        sess.set_event_date(data['event_date'] or '')
    return jsonify({
        'ok': True,
        'show_name':  sess.get_show_name(),
        'event_date': sess.get_event_date(),
    })


@bp.route('/new', methods=['POST'])
def new_session():
    """Clear the current session state to start fresh."""
    sess.clear_session()
    return jsonify({'ok': True, 'session': sess.get_session()})


@bp.route('/mark-saved', methods=['POST'])
def mark_saved():
    """Called by the client after successfully downloading the .qsk export."""
    data = request.get_json(force=True) or {}
    path = (data.get('session_file') or '').strip() or None
    sess.set_session_file(path)
    return jsonify({'ok': True})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_temp(path: str) -> bool:
    """Return True if path looks like a temporary file (upload mode)."""
    import tempfile
    tmp = tempfile.gettempdir()
    return path.startswith(tmp) or path.startswith('/var/folders')
