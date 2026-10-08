"""routes/dictionary_routes.py — Dictionary Manager API (fully implemented)."""

import os
import re
from flask import Blueprint, jsonify, request, Response
from core import workspace as ws
import core.session as sess


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))

bp = Blueprint('dictionary', __name__, url_prefix='/api/dictionary')


@bp.route('/')
def get_dictionary():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_dictionary())


@bp.route('/<fid>', methods=['PATCH'])
def update_entry(fid):
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    ws.update_description(fid, data.get('desc', ''))
    return jsonify({'ok': True})


@bp.route('/bulk-update', methods=['POST'])
def bulk_update():
    """Sync a batch of {id, desc} entries to shared_descriptions (used after Browse TXT import)."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    entries = data.get('entries', [])
    count = 0
    for e in entries:
        fid = str(e.get('id', '')).strip()
        desc = e.get('desc', '')
        if fid:
            ws.update_description(fid, desc)
            count += 1
    return jsonify({'ok': True, 'count': count})


@bp.route('/draft', methods=['POST'])
def draft():
    """Fill the functions that have no description with a first one drawn
    from the show (structure, names, colours).  overwrite=true redraws all."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    from core import dictionary_draft as dd
    data = request.get_json(silent=True) or {}
    rows = ws.get_dictionary()
    texts = dd.draft_all(rows, dd.current_facts(), overwrite=bool(data.get('overwrite')))
    for fid, text in texts.items():
        ws.update_description(fid, text)
    return jsonify({'ok': True, 'drafted': len(texts), 'total': len(rows),
                    'described': sum(1 for r in ws.get_dictionary() if (r.get('desc') or '').strip())})


def new_dictionary_path(folder: str, stem: str) -> str:
    """<stem>_dictionary.txt in *folder*, or _v2, _v3 … when taken (never overwrites)."""
    base = os.path.join(folder, f'{stem}_dictionary')
    path, n = base + '.txt', 2
    while os.path.exists(path):
        path, n = f'{base}_v{n}.txt', n + 1
    return path


@bp.route('/save-new', methods=['POST'])
def save_new():
    """Save the dictionary as a NEW file next to the show (or next to the
    dictionary that was loaded): <show>_dictionary.txt, _v2 … if taken."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(silent=True) or {}
    st = ws.get_state()
    show_path = st.get('path') or ''
    loaded = (data.get('near') or '').strip()
    folder = os.path.dirname(loaded or show_path)
    if not folder or not os.path.isdir(folder):
        return jsonify({'error': 'No folder to save into: open the show from a file first.'}), 400
    stem = os.path.splitext(st.get('original_name') or os.path.basename(show_path) or 'Show.qxw')[0]
    path = new_dictionary_path(folder, stem)
    try:
        ws.save_dictionary(path)
        sess.set_dictionary(path)
        return jsonify({'ok': True, 'path': path})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/load', methods=['POST'])
def load_dict():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        count = ws.load_dictionary(path)
        sess.set_dictionary(path)
        return jsonify({'ok': True, 'count': count})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/save', methods=['POST'])
def save_dict():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    try:
        ws.save_dictionary(path)
        return jsonify({'ok': True, 'path': path})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/export-txt', methods=['POST'])
def export_txt():
    """Download the full dictionary (all functions) as ID|Name|Description TXT."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    rows = ws.get_dictionary()
    lines = ['ID|Name|Type|Description\n']
    for r in sorted(rows, key=lambda x: int(x['id']) if str(x['id']).isdigit() else 0):
        desc = (r.get('desc') or '').replace('\n', '\\n')
        lines.append(f"{r['id']}|{r['name']}|{r.get('type','')}|{desc}\n")
    import os
    state = ws.get_state()
    _src = state.get('original_name') or state.get('path') or 'workspace'
    bn   = os.path.splitext(os.path.basename(_src))[0]
    filename = f'{bn}_ID_dictionary.txt'
    return Response(
        ''.join(lines),
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )
