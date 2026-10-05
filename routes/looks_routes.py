"""routes/looks_routes.py — Look and Chaser Builder tab (WORKPLAN Phase 2.3).

Works on the open workspace; the built copy is returned for a Save dialog
and the report is written next to wherever it is saved."""

import os
import re
import xml.etree.ElementTree as ET

from flask import Blueprint, Response, jsonify, request

from core import look_builder as lb
from core import qxw_io
from core.quick_start import nomenclature as nom
from routes.doctor_routes import _defs, _open_workspace

bp = Blueprint('looks', __name__, url_prefix='/api/looks')
_last: dict = {}


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def _nom(ref):
    try:
        return nom.load_profile(os.path.basename(ref or 'plain'))
    except ValueError:
        return nom.load_profile('plain')


def _plan() -> dict:
    d = request.get_json(force=True) or {}
    looks = [{'group': str(x.get('group')), 'colours': list(x.get('colours') or []),
              'level': x.get('level'), 'position': x.get('position')}
             for x in (d.get('looks') or []) if isinstance(x, dict)]
    matrices = [dict(x) for x in (d.get('matrices') or []) if isinstance(x, dict)]
    chasers = [dict(x) for x in (d.get('chasers') or []) if isinstance(x, dict)]
    vc = (d.get('vc_page') or '').strip() if isinstance(d.get('vc_page'), str) else ''
    return {'looks': looks, 'chasers': chasers, 'matrices': matrices, 'folder': (d.get('folder') or '').strip(),
            'vc_page': vc or None, 'nomenclature': d.get('nomenclature') or 'plain'}


def _need_ws():
    root, path, name = _open_workspace()
    if root is None:
        return None, None, None, (jsonify({'error': 'No workspace open.'}), 400)
    return root, path, name, None


@bp.route('/options')
def options():
    root, path, name, err = _need_ws()
    if err:
        return err
    return jsonify({'source': name, 'groups': lb.groups(root, _defs(path)),
                    'palettes': lb.palettes(), 'palette_order': list(lb.palettes()), 'presets': lb.presets(),
                    'patterns': [{'id': p, 'label': lb.PATTERN_LABELS[p]} for p in lb.PATTERNS],
                    'notes': list(lb.NOTES), 'nomenclature': nom.list_profiles(),
                    'positions': [{'name': k, 'pan': v[0], 'tilt': v[1]} for k, v in lb.POSITIONS.items()],
                    'pixel_bars': lb.pixel_bars(root, _defs(path)),
                    'matrix_patterns': [{'name': k, 'colours': v[1], 'duration': v[2]}
                                        for k, v in lb.MATRIX_PATTERNS.items()]})


@bp.route('/preview-chaser', methods=['POST'])
def preview_chaser():
    root, path, _n, err = _need_ws()
    if err:
        return err
    try:
        return jsonify(lb.preview_chaser(root, _defs(path), request.get_json(force=True) or {}))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/preview-look', methods=['POST'])
def preview_look():
    root, path, _n, err = _need_ws()
    if err:
        return err
    d = request.get_json(force=True) or {}
    try:
        return jsonify(lb.preview_look(root, _defs(path), str(d.get('group', 'all')),
                                       d.get('colours') or [], float(d.get('level') or 1.0), d.get('position')))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


def _run(root, path, name, out_name=''):
    p = _plan()
    if not p['looks'] and not p['chasers'] and not p['matrices']:
        raise ValueError('Add at least one look, chaser or matrix pattern.')
    return lb.run(root, _defs(path), p, _nom(p['nomenclature']), name, out_name)


@bp.route('/check', methods=['POST'])
def check():
    root, path, name, err = _need_ws()
    if err:
        return err
    try:
        res = _run(root, path, name)
        return jsonify({'created': res['created'], 'log': res['log'], 'notes': res['notes'],
                        'functions': res['functions'], 'doctor': res['doctor'], 'blocked': res['blocked']})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/build', methods=['POST'])
def build():
    global _last
    root, path, name, err = _need_ws()
    if err:
        return err
    try:
        out_name = os.path.basename(qxw_io.next_version_name(name))
        res = _run(root, path, name, out_name)
        if res['blocked']:
            return jsonify({'error': 'Doctor found new errors in the result; not exported.',
                            'findings': res['doctor']['new_errors']}), 422
        ET.indent(res['root'], space=' ')
        _last = {'report': res['report'], 'created': res['created'], 'doctor': res['doctor'],
                 'filename': out_name}
        return Response(
            qxw_io.qxw_bytes(res['root']), mimetype='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename="{out_name}"',
                     'X-Suggested-Filename': out_name,
                     'Access-Control-Expose-Headers': 'X-Suggested-Filename'})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/apply', methods=['POST'])
def apply():
    """Add the looks and chasers to the show in progress (a step in its history)."""
    global _last
    root, path, name, err = _need_ws()
    if err:
        return err
    try:
        from routes.show_routes import applied
        res = _run(root, path, name, '')
        if res['blocked']:
            return jsonify({'error': 'Doctor found new errors in the result; not applied.',
                            'findings': res['doctor']['new_errors']}), 422
        _last = {'report': res['report'], 'created': res['created'], 'doctor': res['doctor'],
                 'filename': ''}
        c = res['created']
        title = f'{c.get("looks", 0)} looks, {c.get("chasers", 0)} chasers' + \
            (f', {c["matrices"]} matrices' if c.get('matrices') else '')
        detail = f'{c.get("buttons", 0)} buttons' if c.get('buttons') else ''
        return applied('looks', title, res['root'], res['report'], detail)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
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
    rp = lb.report_path(os.path.abspath(qxw))
    with open(rp, 'w', encoding='utf-8') as fh:
        fh.write(_last['report'])
    return jsonify({'ok': True, 'path': rp, 'name': os.path.basename(rp)})


@bp.route('/presets', methods=['GET'])
def presets():
    return jsonify({'presets': lb.presets()})


@bp.route('/presets', methods=['POST'])
def save_preset():
    try:
        p = lb.save_preset(request.get_json(force=True) or {})
        return jsonify({'ok': True, 'preset': p, 'presets': lb.presets()})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except OSError as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/presets/delete', methods=['POST'])
def delete_preset():
    name = ((request.get_json(force=True) or {}).get('name') or '').strip()
    if not lb.delete_preset(name):
        return jsonify({'error': 'Not one of your presets.'}), 404
    return jsonify({'ok': True, 'presets': lb.presets()})


@bp.route('/palettes', methods=['POST'])
def save_palette():
    d = request.get_json(force=True) or {}
    try:
        p = lb.save_palette(str(d.get('name') or ''), d.get('colours') or [])
        return jsonify({'ok': True, 'palette': p, 'palettes': lb.palettes(), 'palette_order': list(lb.palettes())})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except OSError as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/palettes/delete', methods=['POST'])
def delete_palette():
    name = ((request.get_json(force=True) or {}).get('name') or '').strip()
    if not lb.delete_palette(name):
        return jsonify({'error': 'Not one of your palettes.'}), 404
    return jsonify({'ok': True, 'palettes': lb.palettes(), 'palette_order': list(lb.palettes())})
