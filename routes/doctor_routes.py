"""routes/doctor_routes.py — Workspace Doctor tab (WORKPLAN Phase 2.1).

Works on the open workspace (as loaded in memory).  Fixes never touch it:
the fixed copy is returned for a Save dialog and the fix report is written
next to wherever it is saved.
"""

import os
import re

from flask import Blueprint, Response, jsonify, request

from core import qxw_io, workspace
from core.doctor import TITLES, check, load_qxf_defs
from core.doctor import fixes

bp = Blueprint('doctor', __name__, url_prefix='/api/doctor')

_last: dict = {}


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def _open_workspace():
    st = workspace._state
    if not st.get('loaded'):
        return None, None, None
    path = st.get('path') or ''
    name = st.get('original_name') or os.path.basename(path) or 'workspace.qxw'
    return st['qxw_root'], path, name


def _defs(path: str) -> dict:
    """Definitions next to the workspace, then the installed QLC+ library."""
    folder = os.path.dirname(os.path.abspath(path)) if path else ''
    defs = load_qxf_defs([folder] if folder and os.path.isdir(folder) else [])
    try:
        from core.quick_start import qlc_library
        root = workspace._state.get('qxw_root')
        extra = []
        for el in root.iter():
            if el.tag.endswith('Fixture') and el.find('./*') is not None:
                mfg = next((c.text for c in el if c.tag.endswith('Manufacturer')), None)
                model = next((c.text for c in el if c.tag.endswith('Model')), None)
                if mfg and model and (mfg.strip().lower(), model.strip().lower()) not in defs:
                    f = qlc_library.find(mfg, model)
                    if f:
                        extra.append(f)
        if extra:
            for k, v in load_qxf_defs(dict.fromkeys(extra)).items():
                defs.setdefault(k, v)
    except Exception:  # noqa: BLE001 — definitions only improve the result
        pass
    return defs


def _finding(f):
    ok = fixes.fixable(f)
    return {
        'key': fixes.finding_key(f), 'code': f.code, 'severity': f.severity,
        'location': f.location, 'message': f.message, 'fixable': ok,
        'hint': fixes.fix_hint(f),
        'removing': f.code in fixes.REMOVING,
        'default': ok and f.code in fixes.DEFAULT_CODES,
    }


@bp.route('/check')
def run_check():
    root, path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    try:
        rep = check(root, _defs(path), source=name)
        return jsonify({
            'source': name, 'stats': rep.stats, 'summary': rep.severity_counts(),
            'counts': rep.counts(), 'titles': TITLES,
            'findings': [_finding(f) for f in rep.findings],
        })
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/fix', methods=['POST'])
def run_fix():
    """Body: { keys: [finding keys] } → the fixed workspace (download)."""
    global _last
    root, path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    keys = [str(k) for k in ((request.get_json(force=True) or {}).get('keys') or [])]
    if not keys:
        return jsonify({'error': 'Tick at least one finding to fix.'}), 400
    try:
        res = fixes.fix(root, _defs(path), keys=keys)
        import xml.etree.ElementTree as ET
        ET.indent(res.root, space=' ')
        out_name = os.path.basename(qxw_io.next_version_name(name))
        _last = {
            'report': fixes.format_report(res, name, out_name),
            'before': res.before.severity_counts(), 'after': res.after.severity_counts(),
            'actions': len(res.actions), 'skipped': len(res.skipped), 'filename': out_name,
        }
        return Response(
            qxw_io.qxw_bytes(res.root), mimetype='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename="{out_name}"',
                     'X-Suggested-Filename': out_name,
                     'Access-Control-Expose-Headers': 'X-Suggested-Filename'})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/apply', methods=['POST'])
def run_apply():
    """Body: { keys } → fix the show in progress (a step in its history)."""
    global _last
    root, path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    keys = [str(k) for k in ((request.get_json(force=True) or {}).get('keys') or [])]
    if not keys:
        return jsonify({'error': 'Tick at least one finding to fix.'}), 400
    try:
        from routes.show_routes import applied
        res = fixes.fix(root, _defs(path), keys=keys)
        rep = fixes.format_report(res, name, '')
        _last = {'report': rep, 'before': res.before.severity_counts(),
                 'after': res.after.severity_counts(), 'actions': len(res.actions),
                 'skipped': len(res.skipped), 'filename': ''}
        a = len(res.actions)
        return applied('doctor', f'{a} fix{"es" if a != 1 else ""}', res.root, rep,
                       f'errors {_last["before"].get("error", 0)} → {_last["after"].get("error", 0)}, '
                       f'warnings {_last["before"].get("warning", 0)} → {_last["after"].get("warning", 0)}')
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/last-result')
def last_result():
    return jsonify(_last)


@bp.route('/save-report', methods=['POST'])
def save_report():
    """Write the last fix report next to the saved workspace:
    ``<name>_fix_report.txt``.  Body: { qxw_path }"""
    qxw = ((request.get_json(force=True) or {}).get('qxw_path') or '').strip()
    if not _last.get('report'):
        return jsonify({'error': 'No fix report yet.'}), 400
    folder = os.path.dirname(os.path.abspath(qxw)) if qxw else ''
    if not qxw.lower().endswith('.qxw') or not os.path.isdir(folder):
        return jsonify({'error': 'Workspace folder not found.'}), 400
    rp = fixes.report_path(os.path.abspath(qxw))
    with open(rp, 'w', encoding='utf-8') as fh:
        fh.write(_last['report'])
    return jsonify({'ok': True, 'path': rp, 'name': os.path.basename(rp)})
