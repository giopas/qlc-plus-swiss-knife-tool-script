"""
routes/brightness_routes.py
============================
Flask routes for the Brightness tab.

  GET  /api/brightness/fixtures        — fixture list with channel info
  POST /api/brightness/preview         — count scenes/values that would change
  POST /api/brightness/apply           — generate scaled QXW and stream to browser
  POST /api/brightness/upload-qxf      — accept a QXF file and rebuild channel cache
"""

import os
import tempfile

from flask import Blueprint, Response, jsonify, request
from werkzeug.utils import secure_filename

import core.brightness as br
import core.workspace  as ws

bp = Blueprint('brightness', __name__, url_prefix='/api/brightness')


def _safe_err(exc: Exception) -> str:
    return str(exc)[:300]


@bp.route('/fixtures')
def fixtures():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(br.get_fixture_info())


@bp.route('/preview', methods=['POST'])
def preview():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    raw_scales = data.get('scales', {})
    try:
        scales = {str(k): float(v) for k, v in raw_scales.items()}
        stats  = br.preview_scales(scales)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/apply', methods=['POST'])
def apply_brightness():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    raw_scales  = data.get('scales', {})
    raw_manual  = data.get('manual_dimmer_offsets', {})
    try:
        scales  = {str(k): float(v)  for k, v  in raw_scales.items()}
        manual  = {str(k): int(v)    for k, v  in raw_manual.items()}
        fname, xml_bytes, stats = br.apply_brightness_scales(scales, manual or None)
        resp = Response(
            xml_bytes,
            mimetype='application/octet-stream',
            headers={
                'Content-Disposition':           f'attachment; filename="{fname}"',
                'X-Suggested-Filename':          fname,
                'X-Scenes-Modified':             str(stats['scenes_modified']),
                'X-Values-Changed':              str(stats['values_changed']),
                'Access-Control-Expose-Headers': (
                    'X-Suggested-Filename,X-Scenes-Modified,X-Values-Changed'
                ),
            },
        )
        return resp
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/upload-qxf', methods=['POST'])
def upload_qxf():
    """
    Accept an uploaded QXF file, save it to a temp location beside the
    workspace, and refresh the channel-map cache.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400

    f = request.files['file']
    safe_name = secure_filename(f.filename or '')
    if not safe_name.lower().endswith('.qxf'):
        return jsonify({'error': 'Only .qxf files are accepted.'}), 400

    ws_path = ws.get_state().get('path') or ''
    if ws_path:
        dest_dir = os.path.dirname(ws_path)
    else:
        dest_dir = tempfile.gettempdir()

    dest = os.path.join(dest_dir, safe_name)
    f.save(dest)
    br.invalidate_cache()   # force re-parse on next fixtures request
    return jsonify({'saved': safe_name, 'message': f'{safe_name} saved — reloading fixtures.'})
