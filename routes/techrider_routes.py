"""routes/techrider_routes.py — the Tech Rider API, kept for old links and
scripts (v2.3: thin wrappers over core.showbook — the app itself uses Show
Paperwork, ``/api/showbook/*``, with the *Tech rider* preset)."""

import os
import re

from flask import Blueprint, Response, jsonify, request

from core import showbook
from core import workspace as ws

bp = Blueprint('techrider', __name__, url_prefix='/api/techrider')


def _loaded():
    return None if ws.get_state()['loaded'] else (jsonify({'error': 'No workspace loaded.'}), 400)


def _rider(data=None):
    d = data or {}
    doc = showbook.generate(presets=['rider'], show_name=(d.get('show_name') or 'Untitled Show').strip(),
                            date=(d.get('doc_date') or '').strip() or None)
    return doc, doc['sections']['rider']


@bp.route('/summary')
def summary():
    bad = _loaded()
    if bad:
        return bad
    _, rider = _rider()
    if not rider['types']:
        return jsonify({'error': 'No fixtures found.'}), 400
    types = [{**t, 'dmx_channels': t['channels'], 'first_patch': t['patch_range'].split(' - ')[0],
              'last_patch': t['patch_range'].split(' - ')[-1]} for t in rider['types']]
    groups: dict = {}
    for f in ws.get_fixtures():
        for g in (x.strip() for x in (f.get('groups') or '').split(', ')):
            if g:
                groups.setdefault(g, []).append(f.get('name', ''))
    return jsonify({'types': types, 'total_fixtures': rider['total_fixtures'],
                    'universes_used': rider['universes'], 'total_groups': len(types),
                    'fixture_groups': groups})


@bp.route('/export-pdf', methods=['POST'])
def export_pdf():
    """The *Tech rider* paperwork (fixture types + stage plot) as a PDF."""
    bad = _loaded()
    if bad:
        return bad
    data = request.get_json(force=True, silent=True) or {}
    try:
        doc, rider = _rider(data)
        if not rider['types']:
            return jsonify({'error': 'No fixtures to export.'}), 400
        paper = data.get('paper') if data.get('paper') in showbook.PAPERS else 'A3 Landscape'
        out = showbook.export_pdf(doc, paper)
    except (RuntimeError, ValueError) as e:
        return jsonify({'error': str(e)}), 400
    st = ws.get_state()
    src = st.get('original_name') or st.get('path')
    name = (os.path.splitext(os.path.basename(src))[0] + '_' if src else '') + 'TechRider.pdf'
    return Response(out, mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment; filename=' + re.sub(r'\s+', '_', name)})
