"""
routes/brightness_routes.py
============================
Flask routes for the Brightness tab.

  GET  /api/brightness/fixtures        — fixture list with channel info
  POST /api/brightness/preview         — count scenes/values that would change
  POST /api/brightness/apply           — generate scaled QXW and stream to browser
  POST /api/brightness/upload-qxf      — accept one or more QXF files and rebuild cache
  GET  /api/brightness/scan-local      — scan standard QLC+ fixture dirs, report matches
  POST /api/brightness/fetch-github    — download missing QXFs from GitHub (internet!)
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


# ── Fixture info ──────────────────────────────────────────────────────────────

@bp.route('/fixtures')
def fixtures():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(br.get_fixture_info())


# ── Preview ───────────────────────────────────────────────────────────────────

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


# ── Apply / generate QXW ──────────────────────────────────────────────────────

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


# ── Upload QXF (one or many) ──────────────────────────────────────────────────

@bp.route('/upload-qxf', methods=['POST'])
def upload_qxf():
    """
    Accept one or more QXF files, save them next to the loaded workspace,
    and refresh the channel-map cache.
    """
    files = request.files.getlist('file')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No file(s) uploaded.'}), 400

    ws_path = ws.get_state().get('path') or ''
    dest_dir = os.path.dirname(ws_path) if ws_path else tempfile.gettempdir()

    saved  = []
    errors = []
    for f in files:
        safe_name = secure_filename(f.filename or '')
        if not safe_name.lower().endswith('.qxf'):
            errors.append(f'{f.filename}: not a .qxf file, skipped.')
            continue
        dest = os.path.join(dest_dir, safe_name)
        try:
            f.save(dest)
            saved.append(safe_name)
        except Exception as e:
            errors.append(f'{safe_name}: save failed — {e}')

    if saved:
        br.invalidate_cache()

    return jsonify({
        'saved':   saved,
        'errors':  errors,
        'message': (
            f'{len(saved)} QXF file(s) saved — reloading fixtures.'
            if saved else 'No files were saved.'
        ),
    })


# ── Scan local QLC+ fixture directories ──────────────────────────────────────

@bp.route('/scan-local')
def scan_local():
    """
    Scan all standard QLC+ fixture directories on this machine and report
    which workspace fixtures are now matched (source: local filesystem).
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    try:
        result = br.scan_local_fixtures()
        result['source'] = 'local'
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Fetch from GitHub (internet) ──────────────────────────────────────────────

@bp.route('/fetch-github', methods=['POST'])
def fetch_github():
    """
    Download missing QXF definitions from the official QLC+ GitHub repository.

    ⚠  This endpoint makes outbound HTTP requests to github.com and
       raw.githubusercontent.com.  The caller must have informed the user
       before triggering this endpoint.

    Body: { "fixtures": [{"manufacturer": str, "model": str, "fixture_name": str}] }
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data     = request.get_json(force=True) or {}
    fixtures = data.get('fixtures', [])
    if not fixtures:
        return jsonify({'error': 'No fixtures listed.'}), 400

    ws_path  = ws.get_state().get('path') or ''
    save_dir = os.path.dirname(ws_path) if ws_path else tempfile.gettempdir()

    try:
        result = br.fetch_fixtures_from_github(fixtures, save_dir)
        result['source_type'] = 'internet'   # always flag for the UI
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Assign QXF to a specific fixture group (manual override) ─────────────────

@bp.route('/assign-qxf', methods=['POST'])
def assign_qxf():
    """
    Explicitly assign a QXF file to a fixture group, bypassing all
    automatic name-matching.  The file is saved next to the workspace and
    force-mapped to the given manufacturer/model for the rest of the session.

    Form fields:
      file         — the .qxf file
      manufacturer — fixture manufacturer string (as stored in the workspace)
      model        — fixture model string (as stored in the workspace)
    """
    manufacturer = request.form.get('manufacturer', '').strip()
    model        = request.form.get('model', '').strip()
    if not manufacturer or not model:
        return jsonify({'error': 'manufacturer and model are required.'}), 400
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400

    f         = request.files['file']
    safe_name = secure_filename(f.filename or '')
    if not safe_name.lower().endswith('.qxf'):
        return jsonify({'error': 'Only .qxf files are accepted.'}), 400

    ws_path  = ws.get_state().get('path') or ''
    dest_dir = os.path.dirname(ws_path) if ws_path else tempfile.gettempdir()
    dest     = os.path.join(dest_dir, safe_name)
    try:
        f.save(dest)
    except Exception as e:
        return jsonify({'error': f'Could not save file: {_safe_err(e)}'}), 500

    br.force_qxf_for_fixture(manufacturer, model, dest)
    return jsonify({
        'saved':   safe_name,
        'message': f'QXF "{safe_name}" assigned to {manufacturer} {model}.',
    })
