"""routes/reducer_routes.py — Rig Reducer tab (WORKPLAN Phase 2.2).

Works on the open workspace; the reduced copy is returned for a Save dialog
and the report is written next to wherever it is saved."""

import os
import re
import xml.etree.ElementTree as ET

from flask import Blueprint, Response, jsonify, request

from core import qxw_io, rig_reducer
from routes.doctor_routes import _defs, _open_workspace

bp = Blueprint('reducer', __name__, url_prefix='/api/reducer')
_last: dict = {}


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def _plan():
    d = request.get_json(force=True) or {}
    keep = [str(k) for k in (d.get('keep') or [])]
    rp = {}
    for k, v in (d.get('repatch') or {}).items():
        if isinstance(v, dict):
            rp[str(k)] = {x: v.get(x) for x in ('name', 'universe', 'address')
                          if v.get(x) not in (None, '')}
    return keep, rp


@bp.route('/fixtures')
def fixtures():
    root, _path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    return jsonify({'source': name, 'fixtures': rig_reducer.fixtures(root)})


@bp.route('/preview', methods=['POST'])
def preview():
    root, path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    keep, rp = _plan()
    if not keep:
        return jsonify({'error': 'Keep at least one fixture.'}), 400
    try:
        res = rig_reducer.run(root, keep, rp, _defs(path), name)
        return jsonify({'removed': res['removed'], 'log': res['log'][:400],
                        'more': max(0, len(res['log']) - 400),
                        'doctor': res['doctor'], 'blocked': res['blocked']})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/reduce', methods=['POST'])
def run_reduce():
    global _last
    root, path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    keep, rp = _plan()
    if not keep:
        return jsonify({'error': 'Keep at least one fixture.'}), 400
    try:
        out_name = os.path.basename(qxw_io.next_version_name(name))
        res = rig_reducer.run(root, keep, rp, _defs(path), name, out_name)
        if res['blocked']:
            return jsonify({'error': 'Doctor found new errors in the result; not exported.',
                            'findings': res['doctor']['new_errors']}), 422
        ET.indent(res['root'], space=' ')
        _last = {'report': res['report'], 'removed': res['removed'],
                 'doctor': res['doctor'], 'filename': out_name}
        return Response(
            qxw_io.qxw_bytes(res['root']), mimetype='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename="{out_name}"',
                     'X-Suggested-Filename': out_name,
                     'Access-Control-Expose-Headers': 'X-Suggested-Filename'})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/apply', methods=['POST'])
def run_apply():
    """Reduce the show in progress (a step in its history)."""
    global _last
    root, path, name = _open_workspace()
    if root is None:
        return jsonify({'error': 'No workspace open.'}), 400
    keep, rp = _plan()
    if not keep:
        return jsonify({'error': 'Keep at least one fixture.'}), 400
    try:
        from routes.show_routes import applied
        res = rig_reducer.run(root, keep, rp, _defs(path), name, '')
        if res['blocked']:
            return jsonify({'error': 'Doctor found new errors in the result; not applied.',
                            'findings': res['doctor']['new_errors']}), 422
        _last = {'report': res['report'], 'removed': res['removed'],
                 'doctor': res['doctor'], 'filename': ''}
        rem = ', '.join(f'{v} {k}' for k, v in (res['removed'] or {}).items() if v)
        ren = sum(1 for e in rp.values() if 'name' in e)
        pat = sum(1 for e in rp.values() if 'universe' in e or 'address' in e)
        return applied('reducer', f'kept {len(keep)} fixtures'
                       + (f', renamed {ren}' if ren else '')
                       + (f', re-patched {pat}' if pat else ''), res['root'],
                       res['report'], f'removed: {rem}' if rem else '')
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/last-result')
def last_result():
    return jsonify(_last)


@bp.route('/save-report', methods=['POST'])
def save_report():
    qxw = ((request.get_json(force=True) or {}).get('qxw_path') or '').strip()
    if not _last.get('report'):
        return jsonify({'error': 'No report yet.'}), 400
    folder = os.path.dirname(os.path.abspath(qxw)) if qxw else ''
    if not qxw.lower().endswith('.qxw') or not os.path.isdir(folder):
        return jsonify({'error': 'Workspace folder not found.'}), 400
    rp = rig_reducer.report_path(os.path.abspath(qxw))
    with open(rp, 'w', encoding='utf-8') as fh:
        fh.write(_last['report'])
    return jsonify({'ok': True, 'path': rp, 'name': os.path.basename(rp)})
