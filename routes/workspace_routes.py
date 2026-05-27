"""
routes/workspace_routes.py
==========================
  GET  /               → serve the SPA
  POST /api/load       → load a .qxw file (JSON body: {"path": "..."})
                         or multipart/form-data file upload
  GET  /api/status     → current workspace status
  POST /api/reload     → reload the currently loaded file from disk
"""

import os
import tempfile
from flask import Blueprint, jsonify, render_template, request

from core import workspace as ws

bp = Blueprint('workspace', __name__)


@bp.route('/')
def index():
    return render_template('index.html', version=ws.VERSION)


@bp.route('/api/status')
def status():
    return jsonify(ws.get_state())


@bp.route('/api/load', methods=['POST'])
def load():
    """
    Two loading modes:

    1. Path mode (JSON):
       POST /api/load   Content-Type: application/json
       {"path": "/absolute/path/to/show.qxw"}

    2. Upload mode (form):
       POST /api/load   Content-Type: multipart/form-data
       file field: "file"

    Path mode is more convenient for repeat opens (user pastes the
    path once and reloads throughout the session).  Upload mode is
    the fallback for first-time use or cross-platform drag-and-drop.
    """
    path = None
    tmp  = None

    try:
        original_name = None   # only set in upload mode

        if request.is_json:
            data = request.get_json(force=True)
            path = (data or {}).get('path', '').strip()
            if not path:
                return jsonify({'error': 'No path provided.'}), 400
            if not os.path.isfile(path):
                return jsonify({'error': f'File not found: {path}'}), 404

        else:
            f = request.files.get('file')
            if not f:
                return jsonify({'error': 'No file uploaded.'}), 400
            original_name = f.filename or 'workspace.qxw'
            suffix = os.path.splitext(original_name)[-1] or '.qxw'
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            f.save(tmp.name)
            tmp.close()
            path = tmp.name

        state = ws.load_qxw(path)

        # For upload mode: record the original filename inside the workspace
        # state so output filenames and error messages are derived from it
        # (not from the temp path which is deleted after this request).
        if original_name:
            ws.set_original_name(original_name)
            state = ws.get_state()   # refresh to get the patched view

        return jsonify(state)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        if tmp and os.path.exists(tmp.name):
            # Only delete the temp file if we used upload mode
            if not request.is_json:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass


@bp.route('/api/reload', methods=['POST'])
def reload():
    """Re-parse the currently loaded file from disk (path mode only)."""
    state = ws.get_state()
    if not state['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    if state.get('original_name'):
        return jsonify({
            'error': (
                'Reload is only available when the workspace was loaded by path. '
                'Drag-and-drop or re-upload the file to refresh it.'
            )
        }), 400
    if not state['path']:
        return jsonify({'error': 'No workspace path available.'}), 400
    try:
        updated = ws.load_qxw(state['path'])
        return jsonify(updated)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
