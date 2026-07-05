"""
routes/id_browser_routes.py
===========================
  GET  /api/functions              → all Engine functions
  GET  /api/vc-widgets             → all VC widgets (flat list)
  GET  /api/vc/tree                → full nested VC widget tree with positions + colours
  POST /api/vc/patch               → apply position/appearance changes (in-memory XML)
  POST /api/vc/export-qxw         → save patched workspace as new .qxw file
  POST /api/functions/export-pdf  → PDF download
  POST /api/vc-widgets/export-pdf → PDF download
"""

import os
from flask import Blueprint, jsonify, request, Response
from core import workspace as ws
from core import pdf as pdf_mod

bp = Blueprint('id_browser', __name__, url_prefix='/api')


@bp.route('/functions')
def functions():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_functions())


@bp.route('/vc-widgets')
def vc_widgets():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_vc_widgets())


# ── VC Editor endpoints ───────────────────────────────────────────────────────

@bp.route('/vc/tree')
def vc_tree():
    """Return the full nested VC widget tree with positions and colours."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    tree = ws.get_vc_tree()
    if tree is None:
        return jsonify({'error': 'No VirtualConsole found in workspace.'}), 404
    return jsonify(tree)


@bp.route('/vc/patch', methods=['POST'])
def vc_patch():
    """
    Apply position/appearance changes to VC widgets in the in-memory XML.

    Body: { "changes": [ {id, x?, y?, w?, h?, bg_color?, fg_color?,
                           font_size?, font_bold?}, ... ] }
    Returns: { "patched": int, "errors": [str] }
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data    = request.get_json(force=True) or {}
    changes = data.get('changes') or []
    if not isinstance(changes, list):
        return jsonify({'error': "'changes' must be a list"}), 400

    try:
        result = ws.patch_vc_widgets(changes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify(result)


@bp.route('/vc/export-qxw', methods=['POST'])
def vc_export_qxw():
    """
    Write the current (patched) workspace to a new .qxw file.

    Body: { "path": "/absolute/path/to/output.qxw" }
         or use the native picker by omitting/leaving path empty (falls back to
         /api/picker/save-name on the client side).
    Returns: { "ok": true, "path": "..." } or { "error": "..." }
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()

    if not path:
        return jsonify({'error': 'No output path provided.'}), 400

    # Safety: must end in .qxw
    if not path.lower().endswith('.qxw'):
        path += '.qxw'

    try:
        ws.export_qxw(path)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'ok': True, 'path': path})


# ── PDF exports ───────────────────────────────────────────────────────────────

@bp.route('/functions/export-pdf', methods=['POST'])
def functions_pdf():
    """Return the Functions table as a PDF download."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data  = request.get_json(force=True) or {}
    paper = data.get('paper', 'A4 Landscape')
    fsize = int(data.get('fsize', 8))
    W, H  = _paper_size(paper)

    rows_raw = ws.get_functions()
    headers  = ['ID', 'Name', 'Type', 'Contains']
    rows     = [[r['id'], r['name'], r['type'], r['contains']] for r in rows_raw]

    state = ws.get_state()
    title = f"Functions — {os.path.basename(state.get('path') or 'workspace')}"

    pdf_bytes = pdf_mod.build_table_pdf(rows, headers, title=title, W=W, H=H, fsize=fsize)
    filename  = 'functions.pdf'
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


@bp.route('/vc-widgets/export-pdf', methods=['POST'])
def vc_widgets_pdf():
    """Return the VC Widgets table as a PDF download (ID, Type, Caption, Func, Frame)."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data  = request.get_json(force=True) or {}
    paper = data.get('paper', 'A4 Landscape')
    fsize = int(data.get('fsize', 8))
    W, H  = _paper_size(paper)

    rows_raw = ws.get_vc_widgets()
    # X/Y/W/H are now managed in the VC Editor, not in the PDF table
    headers  = ['Widget ID', 'Type', 'Caption', 'Func ID', 'Function', 'Frame Path']
    rows     = [[r['widget_id'], r['type'], r['caption'],
                 r['func_id'], r['func_name'], r['frame_path']]
                for r in rows_raw]

    state = ws.get_state()
    title = f"VC Widgets — {os.path.basename(state.get('path') or 'workspace')}"

    pdf_bytes = pdf_mod.build_table_pdf(rows, headers, title=title, W=W, H=H, fsize=fsize)
    filename  = 'vc_widgets.pdf'
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _paper_size(name: str):
    sizes = {
        'A4 Portrait':         (595.0, 842.0),
        'A4 Landscape':        (842.0, 595.0),
        'US Letter Portrait':  (612.0, 792.0),
        'US Letter Landscape': (792.0, 612.0),
    }
    return sizes.get(name, (842.0, 595.0))
