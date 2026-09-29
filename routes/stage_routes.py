"""routes/stage_routes.py — Stage & Meshes tab (WORKPLAN Phase 2.5).

Edits a working copy of the open workspace's 3D stage (meshes, stage type
and size) with undo; 💾 returns a NEW workspace for a Save dialog and the
report is written next to wherever it is saved."""

import copy
import os
import re
import xml.etree.ElementTree as ET

from flask import Blueprint, Response, jsonify, request

from core import qxw_io, stage3d as s3
from routes.doctor_routes import _defs, _open_workspace

bp = Blueprint('stage', __name__, url_prefix='/api/stage')
_w: dict = {}            # {'key', 'root' (stripped copy), 'undo': [...], 'report'}
UNDO_LIMIT = 50


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def _work():
    root, path, name = _open_workspace()
    if root is None:
        return None
    key = (id(root), path)
    if _w.get('key') != key:
        _w.clear()
        _w.update({'key': key, 'orig': root, 'path': path, 'name': name,
                   'root': qxw_io.strip_ns(copy.deepcopy(root)), 'undo': []})
    return _w


def _dirs():
    return s3.library_dirs()


def _state(w, **extra):
    r = w['root']
    orig = qxw_io.strip_ns(copy.deepcopy(w['orig']))
    return jsonify({'source': w['name'], 'stage': s3.stage(r), 'types': s3.STAGE_TYPES,
                    'meshes': s3.meshes(r, w['path'], _dirs()), 'fixtures': s3.fixtures(r),
                    'undo': len(w['undo']),
                    'dirty': qxw_io.qxw_bytes(r) != qxw_io.qxw_bytes(orig), **extra})


@bp.route('/state')
def state():
    w = _work()
    if w is None:
        return jsonify({'error': 'No workspace open.'}), 400
    return _state(w)


def _num(v):
    return None if v in (None, '') else float(v)


@bp.route('/op', methods=['POST'])
def op():
    w = _work()
    if w is None:
        return jsonify({'error': 'No workspace open.'}), 400
    d = request.get_json(force=True) or {}
    o = d.get('op')
    r, kw = w['root'], {'qxw_path': w['path'], 'mesh_dirs': _dirs()}
    if o == 'undo':
        if not w['undo']:
            return jsonify({'error': 'Nothing to undo.'}), 400
        w['root'] = w['undo'].pop()
        return _state(w, message='Undone.')
    if o == 'reset':
        w['root'] = qxw_io.strip_ns(copy.deepcopy(w['orig']))
        w['undo'] = []
        return _state(w, message='All stage changes discarded.')
    snap = copy.deepcopy(r)
    try:
        mid = str(d.get('id', ''))
        if o == 'move':
            res = s3.move_to(r, mid, x=_num(d.get('x')), z=_num(d.get('z')), bottom=_num(d.get('bottom')), **kw)
            msg = f"Moved '{mid}'."
        elif o == 'floor':
            res = s3.on_floor(r, d.get('ids'), **kw)
            msg = f"{len(res['moved'])} mesh(es) put on the floor" + \
                  (f"; {len(res['skipped'])} skipped (model file not found)" if res['skipped'] else '') + '.'
        elif o == 'transform':
            res = s3.set_transform(r, mid, rot=d.get('rot'), scale=d.get('scale'), name=d.get('name'),
                                   res=d.get('res'), keep_floor=bool(d.get('keep_floor', True)), **kw)
            msg = 'Mesh updated.'
        elif o == 'add':
            res = s3.add_mesh(r, str(d.get('res', '')), name=str(d.get('name', '')),
                              x=_num(d.get('x')), z=_num(d.get('z')), **kw)
            msg = 'Mesh added on the floor.'
        elif o == 'arrange':
            res = s3.arrange(r, [str(i) for i in (d.get('ids') or [])], str(d.get('action', '')),
                             margin=_num(d.get('margin')) or 0, dx=_num(d.get('dx')) or 0,
                             dz=_num(d.get('dz')) or 0, dy=_num(d.get('dy')) or 0, **kw)
            msg = (f"{len(res['moved'])} mesh(es) placed" if res['moved'] else 'Already there')
            if res['skipped']:
                msg += f"; {len(res['skipped'])} skipped (model file not found)"
            if res['outside']:
                msg += f" — {len(res['outside'])} now reach(es) past the stage edge"
            msg += '.'
        elif o == 'duplicate':
            res = s3.duplicate_mesh(r, mid, **kw)
            msg = 'Mesh duplicated (0.5 m to the right).'
        elif o == 'remove':
            res = s3.remove_mesh(r, mid)
            msg = 'Mesh removed.'
        elif o == 'stage':
            t = d.get('type')
            res = s3.set_stage(r, type=None if t in (None, '') else int(t), w=_num(d.get('w')),
                               h=_num(d.get('h')), d=_num(d.get('d')),
                               keep_meshes=bool(d.get('keep_meshes', True)), **kw)
            msg = 'Stage updated' + (' — meshes kept in place.' if d.get('keep_meshes', True) else '.')
        else:
            return jsonify({'error': f'Unknown operation: {o}'}), 400
    except (s3.StageError, ValueError) as e:
        w['root'] = snap
        return jsonify({'error': str(e)}), 400
    w['undo'].append(snap)
    del w['undo'][:-UNDO_LIMIT]
    return _state(w, message=msg, result=res)


@bp.route('/library')
def library():
    return jsonify({'dirs': s3.library_dirs(), 'items': s3.library()[:2000]})


@bp.route('/library-dirs', methods=['POST'])
def library_dirs():
    try:
        dirs = s3.set_library_dirs((request.get_json(force=True) or {}).get('dirs') or [])
        return jsonify({'dirs': dirs, 'items': s3.library()[:2000]})
    except s3.StageError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/mesh-info', methods=['POST'])
def mesh_info():
    res = ((request.get_json(force=True) or {}).get('res') or '').strip()
    w = _work()
    info, path = s3.mesh_info(res, w['path'] if w else '', _dirs())
    if info is None:
        return jsonify({'error': 'Model file not found.'}), 404
    return jsonify({'size': [round(e * 1000) for e in info['ext']], 'vertices': info['count'],
                    'feet_at_zero': abs(info['min'][1]) < 1e-6})


@bp.route('/save', methods=['POST'])
def save():
    w = _work()
    if w is None:
        return jsonify({'error': 'No workspace open.'}), 400
    from core.doctor import check
    try:
        out_name = os.path.basename(qxw_io.next_version_name(w['name']))
        orig = qxw_io.strip_ns(copy.deepcopy(w['orig']))
        defs = _defs(w['path'])
        old = {(f.code, f.location, f.message) for f in check(orig, defs).errors}
        new = [f for f in check(w['root'], defs).errors if (f.code, f.location, f.message) not in old]
        if new:
            return jsonify({'error': 'Doctor found new errors in the result; not exported.',
                            'findings': [f"{f.code} {f.location}: {f.message}" for f in new]}), 422
        out = copy.deepcopy(w['root'])
        ET.indent(out, space=' ')
        w['report'] = s3.report(orig, w['root'], w['name'], out_name, w['path'], _dirs())
        return Response(qxw_io.qxw_bytes(out), mimetype='application/octet-stream',
                        headers={'Content-Disposition': f'attachment; filename="{out_name}"',
                                 'X-Suggested-Filename': out_name,
                                 'Access-Control-Expose-Headers': 'X-Suggested-Filename'})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/save-report', methods=['POST'])
def save_report():
    qxw = ((request.get_json(force=True) or {}).get('qxw_path') or '').strip()
    if not _w.get('report'):
        return jsonify({'error': 'No report yet.'}), 400
    folder = os.path.dirname(os.path.abspath(qxw)) if qxw else ''
    if not qxw.lower().endswith('.qxw') or not os.path.isdir(folder):
        return jsonify({'error': 'Workspace folder not found.'}), 400
    rp = s3.report_path(os.path.abspath(qxw))
    with open(rp, 'w', encoding='utf-8') as fh:
        fh.write(_w['report'])
    return jsonify({'ok': True, 'path': rp, 'name': os.path.basename(rp)})
