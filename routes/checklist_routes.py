"""routes/checklist_routes.py — the Setup Checklist API, kept for old links and
scripts (v2.3: thin wrappers over core.showbook — the app itself uses Show
Paperwork, ``/api/showbook/*``, with the *Crew checklist* preset)."""

import os
import re

from flask import Blueprint, Response, jsonify, request

from core import showbook
from core import workspace as ws

bp = Blueprint('checklist', __name__, url_prefix='/api/checklist')


def _loaded():
    return None if ws.get_state()['loaded'] else (jsonify({'error': 'No workspace loaded.'}), 400)


def _doc(sections=None, presets=None, data=None):
    d = data or {}
    return showbook.generate(sections=sections, presets=presets,
                             show_name=(d.get('show_name') or 'Untitled Show').strip(),
                             date=(d.get('doc_date') or '').strip() or None)


def _name(suffix: str, ext: str) -> str:
    st = ws.get_state()
    src = st.get('original_name') or st.get('path')
    return (os.path.splitext(os.path.basename(src))[0] + '_' if src else '') + suffix + '.' + ext


def _paper(data: dict) -> str:
    return data.get('paper') if data.get('paper') in showbook.PAPERS else 'A3 Landscape'


@bp.route('/fixtures')
def fixtures():
    return _loaded() or jsonify(ws.get_fixtures())


@bp.route('/export-txt', methods=['POST'])
def export_txt():
    bad = _loaded()
    if bad:
        return bad
    rows = _doc(['checklist'])['sections']['checklist']
    lines = ['QLC+ Swiss Knife — Setup Checklist\n', '=' * 80 + '\n',
             f'{"ID":<6} {"Name":<32} {"Patch":<10} {"Groups"}\n', '-' * 80 + '\n']
    for r in rows:
        lines.append(f'{"☐":<3} {r["id"]:<5} {r["name"][:30]:<30} {r["patch"]:<10} {r["groups"]}\n')
    return Response(''.join(lines), mimetype='text/plain',
                    headers={'Content-Disposition': 'attachment; filename=checklist.txt'})


def _pdf(sections, presets, suffix):
    bad = _loaded()
    if bad:
        return bad
    data = request.get_json(force=True, silent=True) or {}
    try:
        doc = _doc(sections, presets, data)
        if sections == ['stage_plan'] and not doc['sections']['stage_plan']['placed']:
            return jsonify({'error': 'No fixtures have 3D position data. '
                                     'Add fixtures to the Monitor 3D view in QLC+ first.'}), 400
        out = showbook.export_pdf(doc, _paper(data))
    except (RuntimeError, ValueError) as e:
        return jsonify({'error': str(e)}), 400
    return Response(out, mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment; filename=' + re.sub(r'\s+', '_', _name(suffix, 'pdf'))})


@bp.route('/export-pdf', methods=['POST'])
def export_pdf():
    """The *Crew checklist* paperwork (checklist + stage plot) as a PDF."""
    return _pdf(None, ['checklist'], 'Checklist')


@bp.route('/export-blueprint-pdf', methods=['POST'])
def export_blueprint_pdf():
    """The stage plot alone."""
    return _pdf(['stage_plan'], None, 'Blueprint')
