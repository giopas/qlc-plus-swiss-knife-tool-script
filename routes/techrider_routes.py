"""routes/techrider_routes.py — Tech Rider API."""

import os
from flask import Blueprint, jsonify, Response, request
from core import workspace as ws
from core import pdf as pdf_mod

bp = Blueprint('techrider', __name__, url_prefix='/api/techrider')


def _build_summary():
    """Group fixtures by (manufacturer, model, mode) and return summary data."""
    fixtures = ws.get_fixtures()
    if not fixtures:
        return None

    # Group by (manufacturer, model, mode)
    groups = {}
    for f in fixtures:
        key = (f.get('manufacturer', ''), f.get('model', ''), f.get('mode', ''))
        if key not in groups:
            groups[key] = []
        groups[key].append(f)

    type_rows = []
    all_universes = set()

    for (mfg, model, mode), fxs in sorted(groups.items()):
        qty = len(fxs)
        universes = sorted(set(f.get('universe', 0) for f in fxs))
        all_universes.update(universes)

        patches = []
        for f in fxs:
            patches.append(
                f.get('patch', f"U{f.get('universe', 0)}.{f.get('address', 0):03d}"))
        patches.sort()
        first_patch = patches[0] if patches else ''
        last_patch = patches[-1] if patches else ''
        patch_range = first_patch if first_patch == last_patch else f"{first_patch} - {last_patch}"

        colors = list(set(f.get('color', '') for f in fxs if f.get('color')))
        color = colors[0] if len(colors) == 1 else ''

        type_rows.append({
            'manufacturer': mfg,
            'model': model,
            'mode': mode,
            'quantity': qty,
            'dmx_channels': 'N/A',
            'first_patch': first_patch,
            'last_patch': last_patch,
            'patch_range': patch_range,
            'color': color,
            'universes': universes,
        })

    # Fixture groups: group name -> list of fixture names
    fixture_groups = {}
    for f in fixtures:
        grp_str = f.get('groups', '')
        if not grp_str:
            continue
        for g in grp_str.split(', '):
            g = g.strip()
            if g:
                fixture_groups.setdefault(g, []).append(f.get('name', ''))

    return {
        'types': type_rows,
        'total_fixtures': len(fixtures),
        'universes_used': sorted(all_universes),
        'total_groups': len(type_rows),
        'fixture_groups': fixture_groups,
    }


@bp.route('/summary')
def summary():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = _build_summary()
    if data is None:
        return jsonify({'error': 'No fixtures found.'}), 400
    return jsonify(data)


@bp.route('/export-pdf', methods=['POST'])
def export_pdf():
    """Return a Tech Rider table PDF as application/pdf."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data = _build_summary()
    if data is None:
        return jsonify({'error': 'No fixtures to export.'}), 400

    req_data  = request.get_json(force=True) or {}
    show_name = (req_data.get('show_name') or 'Untitled Show').strip()
    doc_date  = (req_data.get('doc_date') or '').strip() or None
    paper     = req_data.get('paper', 'A3 Landscape')

    paper_sizes = {
        'A3 Landscape':        (1190.0, 841.0),
        'A4 Portrait':         (595.0,  842.0),
        'A4 Landscape':        (842.0,  595.0),
        'US Letter Portrait':  (612.0,  792.0),
        'US Letter Landscape': (792.0,  612.0),
    }
    W, H = paper_sizes.get(paper, (1190.0, 841.0))

    headers = ['Type', 'Model', 'Mode', 'Qty', 'Patch Range', 'Universe(s)']
    rows = []
    for t in data['types']:
        uni_str = ', '.join(str(u) for u in t['universes'])
        rows.append([
            t['manufacturer'],
            t['model'],
            t['mode'],
            str(t['quantity']),
            t['patch_range'],
            uni_str,
        ])

    if not rows:
        return jsonify({'error': 'No fixtures to export.'}), 400

    title = f"TECH RIDER: {show_name}"
    if doc_date:
        title += f"  —  {doc_date}"

    pdf_bytes = pdf_mod.build_table_pdf(rows, headers, title=title, W=W, H=H)

    filename = 'TechRider.pdf'
    state = ws.get_state()
    _src = state.get('original_name') or state.get('path')
    if _src:
        filename = os.path.splitext(os.path.basename(_src))[0] + '_TechRider.pdf'

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )
