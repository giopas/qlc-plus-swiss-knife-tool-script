"""
routes/id_browser_routes.py
===========================
  GET  /api/functions            → all Engine functions
  GET  /api/vc-widgets           → all VC widgets
  POST /api/functions/export-pdf → PDF download
  POST /api/vc-widgets/export-pdf
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
    """Return the VC Widgets table as a PDF download."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data  = request.get_json(force=True) or {}
    paper = data.get('paper', 'A4 Landscape')
    fsize = int(data.get('fsize', 8))
    W, H  = _paper_size(paper)

    rows_raw = ws.get_vc_widgets()
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
