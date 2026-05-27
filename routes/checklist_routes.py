"""routes/checklist_routes.py — Setup Checklist API."""

import os
from flask import Blueprint, jsonify, Response, request
from core import workspace as ws
from core import pdf as pdf_mod

bp = Blueprint('checklist', __name__, url_prefix='/api/checklist')


@bp.route('/fixtures')
def fixtures():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_fixtures())


@bp.route('/export-txt', methods=['POST'])
def export_txt():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    rows = ws.get_fixtures()
    rows.sort(key=lambda r: r['universe'] * 1000 + r['address'])
    lines = [
        'QLC+ Swiss Knife — Setup Checklist\n',
        '=' * 80 + '\n',
        f'{"ID":<6} {"Name":<32} {"Patch":<10} {"Groups"}\n',
        '-' * 80 + '\n',
    ]
    for r in rows:
        patch = r.get('patch', f"U{r['universe']}.{r['address']:03d}")
        lines.append(
            f'{"☐":<3} {r["id"]:<5} {r["name"][:30]:<30} {patch:<10} {r["groups"]}\n'
        )
    txt = ''.join(lines)
    return Response(
        txt,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename=checklist.txt'},
    )


@bp.route('/export-pdf', methods=['POST'])
def export_pdf():
    """Return a Blueprint PDF (top-view + front-view) as application/pdf."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data      = request.get_json(force=True) or {}
    show_name = (data.get('show_name') or 'Untitled Show').strip()
    doc_date  = (data.get('doc_date')  or '').strip() or None
    paper     = data.get('paper', 'A3 Landscape')

    paper_sizes = {
        'A3 Landscape':        (1190.0, 841.0),
        'A4 Portrait':         (595.0,  842.0),
        'A4 Landscape':        (842.0,  595.0),
        'US Letter Portrait':  (612.0,  792.0),
        'US Letter Landscape': (792.0,  612.0),
    }
    W, H = paper_sizes.get(paper, (1190.0, 841.0))

    # Build fixture_data for the blueprint (same shape as original script)
    fixture_data = []
    for r in ws.get_fixtures():
        fixture_data.append({
            'name':   r['name'],
            'patch':  r.get('patch', f"U{r['universe']}.{r['address']:03d}"),
            'color':  r.get('color', '#888888'),
            'x':      r.get('x_mm', 0),
            'y':      r.get('y_mm', 0),
            'z':      r.get('z_mm', 0),
            'in_3d':  r.get('in_3d', False),
        })

    pdf_bytes = pdf_mod.build_blueprint_pdf(
        fixture_data, show_name=show_name, doc_date=doc_date, W=W, H=H)

    if pdf_bytes is None:
        return jsonify({'error': 'No fixtures have 3D position data. '
                                 'Add fixtures to the Monitor 3D view in QLC+ first.'}), 400

    filename = 'blueprint.pdf'
    state = ws.get_state()
    # Use original_name (upload mode) or path (path mode) to derive filename
    _src = state.get('original_name') or state.get('path')
    if _src:
        filename = os.path.splitext(os.path.basename(_src))[0] + '_Blueprint.pdf'

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )
