"""routes/setlist_routes.py — Setlist Manager API."""

import os
import re
from flask import Blueprint, jsonify, request, Response
from core import workspace as ws
from core import pdf as pdf_mod


def _safe_err(exc: Exception) -> str:
    """Strip filesystem paths from exception messages before sending to client."""
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))

bp = Blueprint('setlist', __name__, url_prefix='/api/setlist')

# ── Slots ──────────────────────────────────────────────────────────────────────

@bp.route('/slots')
def slots():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_cuelist_slots())


@bp.route('/chasers')
def chasers():
    """Return available Chaser functions for the target selector."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_available_chasers())


# ── Song lists (simple strings — for TXT load/save) ───────────────────────────

@bp.route('/<slot_id>/songs')
def get_songs(slot_id):
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_slot_songs(slot_id))


@bp.route('/<slot_id>/songs', methods=['POST'])
def set_songs(slot_id):
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data  = request.get_json(force=True) or {}
    songs = data.get('songs', [])
    if not isinstance(songs, list):
        return jsonify({'error': 'songs must be a list.'}), 400
    ws.set_slot_songs(slot_id, songs)
    return jsonify({'ok': True, 'count': len(songs)})


# ── Detailed song rows (with func assignment + timing) ────────────────────────

@bp.route('/<slot_id>/details')
def get_details(slot_id):
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_slot_details(slot_id))


@bp.route('/<slot_id>/details', methods=['POST'])
def set_details(slot_id):
    """Replace the full detailed song list for a slot."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    rows = data.get('rows', [])
    if not isinstance(rows, list):
        return jsonify({'error': 'rows must be a list.'}), 400
    ws.set_slot_details(slot_id, rows)
    return jsonify({'ok': True, 'count': len(rows)})


@bp.route('/<slot_id>/details/<int:row_idx>', methods=['PATCH'])
def patch_detail(slot_id, row_idx):
    """Patch a single song row."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    ws.update_song_detail(slot_id, row_idx, data)
    return jsonify({'ok': True})


# ── TXT load/save ─────────────────────────────────────────────────────────────

@bp.route('/load', methods=['POST'])
def load_setlist():
    """Load a setlist TXT file. Format: slot_id|song1|song2|..."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        count = 0
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if len(parts) >= 2:
                    slot_id = parts[0].strip()
                    songs   = [s.strip() for s in parts[1:] if s.strip()]
                    ws.set_slot_songs(slot_id, songs)
                    count += 1
        return jsonify({'ok': True, 'count': count})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/save', methods=['POST'])
def save_setlist():
    """Save all slot song lists to a pipe-delimited TXT file."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        slots  = ws.get_cuelist_slots()
        lines  = [
            '# QLC+ Swiss Knife — Setlist\n',
            '# Format: slot_id|song1|song2|...\n',
        ]
        for slot in slots:
            sid   = slot['id']
            songs = ws.get_slot_songs(sid)
            if songs:
                lines.append(f'{sid}|' + '|'.join(songs) + '\n')
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return jsonify({'ok': True, 'path': path})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Purge (Setlist) clones from workspace ─────────────────────────────────────

@bp.route('/purge-workspace-clones', methods=['POST'])
def purge_workspace_clones():
    """
    Delete all (Setlist) clone functions from the in-memory workspace XML and
    state maps, and unassign them from every slot's song list.
    Returns {ok, removed, unassigned}.
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    try:
        result = ws.purge_workspace_clones()
        return jsonify({'ok': True, **result})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Auto-match song names to QLC+ functions ──────────────────────────────────

@bp.route('/auto-match', methods=['POST'])
def auto_match():
    """
    Auto-match a list of song name strings to QLC+ function IDs.
    Uses the 4-stage find_best_match algorithm (exact→substring→token→fuzzy).
    Body : {songs: [str]}
    Returns: [{txt_name, matched_id, matched_name}]
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data  = request.get_json(force=True) or {}
    songs = data.get('songs', [])
    if not isinstance(songs, list):
        return jsonify({'error': 'songs must be a list.'}), 400
    results = []
    for s in songs:
        matched_name, matched_id = ws.find_best_match(str(s))
        results.append({
            'txt_name':     s,
            'matched_id':   matched_id,
            'matched_name': matched_name,
        })
    return jsonify(results)


# ── Chaser / QXW generation ───────────────────────────────────────────────────

@bp.route('/<slot_id>/generate-qxw', methods=['POST'])
def generate_qxw(slot_id):
    """
    Clone base functions → build/update a Chaser → stream QXW bytes to browser.
    The browser's showSaveFilePicker (or <a> fallback) lets the user choose
    where to save without any server-side path configuration.
    Body: {target_chaser_id: str|"__new__"}
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data             = request.get_json(force=True) or {}
    target_chaser_id = (data.get('target_chaser_id') or '').strip() or None
    try:
        fname, xml_bytes = ws.generate_slot_qxw_content(slot_id, target_chaser_id)
        return Response(
            xml_bytes,
            mimetype='application/octet-stream',
            headers={
                'Content-Disposition':           f'attachment; filename="{fname}"',
                'X-Suggested-Filename':          fname,
                'Access-Control-Expose-Headers': 'X-Suggested-Filename',
            },
        )
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── PDF export ────────────────────────────────────────────────────────────────

@bp.route('/<slot_id>/export-pdf', methods=['POST'])
def export_pdf(slot_id):
    """Return a setlist PDF as application/pdf."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data      = request.get_json(force=True) or {}
    show_name = (data.get('show_name') or 'Untitled').strip()
    paper     = data.get('paper', 'A4 Landscape')
    inc_notes = bool(data.get('include_notes', False))

    paper_sizes = {
        'A4 Portrait':         (595.0,  842.0),
        'A4 Landscape':        (842.0,  595.0),
        'US Letter Portrait':  (612.0,  792.0),
        'US Letter Landscape': (792.0,  612.0),
    }
    W, H = paper_sizes.get(paper, (842.0, 595.0))

    # Prefer detailed rows; fall back to simple string list
    songs = ws.get_slot_details(slot_id)
    if not songs:
        plain = ws.get_slot_songs(slot_id)
        songs = [{'txt_name': s, 'qxw_name': '', 'qxw_id': '',
                  'in': '0', 'hold': '4294967294', 'out': '0'}
                 for s in plain]

    slot_info = next((s for s in ws.get_cuelist_slots() if s['id'] == slot_id), None)
    slot_label = slot_info['caption'] if slot_info else f'Slot {slot_id}'

    selected_cols = [
        ('num',      '#'),
        ('song',     'Song'),
        ('cue',      'Cue'),
        ('fade_in',  'Fade In'),
        ('hold',     'Hold'),
        ('fade_out', 'Fade Out'),
    ]
    for col_key in (data.get('columns') or []):
        pass  # future: allow caller to restrict columns

    pdf_bytes = pdf_mod.build_setlist_pdf(
        songs, slot_label=slot_label, show_name=show_name,
        selected_cols=selected_cols, include_notes=inc_notes,
        W=W, H=H,
    )
    if pdf_bytes is None:
        return jsonify({'error': 'No songs to export.'}), 400

    filename = f'setlist_{slot_id}.pdf'
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )
