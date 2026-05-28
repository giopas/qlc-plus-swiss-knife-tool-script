"""routes/fixture_routes.py — Fixture Configurator API (full implementation)."""

import os
import re
from flask import Blueprint, jsonify, request, Response
from core import workspace as ws
from core import fixture as fx
from core import pdf as pdf_mod


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))

bp = Blueprint('fixture', __name__, url_prefix='/api/fixture')


# ── Workspace rig view (read-only, from loaded QXW) ───────────────────────────

@bp.route('/rig')
def rig():
    """Return rig fixtures (from configurator state, or workspace if not configured)."""
    cfg_rig = fx.get_rig()
    if cfg_rig:
        return jsonify(fx.rig_to_api())
    # Fallback: workspace fixture list
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_fixtures())


# ── Configurator rig CRUD ─────────────────────────────────────────────────────

@bp.route('/configurator/rig')
def configurator_rig():
    """Return the full configurator rig with all fields."""
    return jsonify(fx.rig_to_api())


@bp.route('/configurator/qxf-defs')
def qxf_defs():
    """Return known fixture type definitions."""
    defs = fx.get_qxf_defs()
    result = []
    for key, d in defs.items():
        result.append({
            'key':          key,
            'manufacturer': d['manufacturer'],
            'model':        d['model'],
            'type':         d['type'],
            'modes':        [{'name': n, 'channels': c} for n, c in d['modes'].items()],
        })
    return jsonify(result)


@bp.route('/configurator/stage')
def stage_dims():
    return jsonify(fx.get_stage_dims())


@bp.route('/configurator/stage', methods=['POST'])
def set_stage():
    data = request.get_json(force=True) or {}
    try:
        fx.set_stage_dims(
            w_mm=int(data.get('w_mm', 8000)),
            d_mm=int(data.get('d_mm', 6000)),
            h_mm=int(data.get('h_mm', 4000)),
            cols=int(data.get('cols', 8)),
            rows=int(data.get('rows', 6)),
        )
        return jsonify({'ok': True, **fx.get_stage_dims()})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/configurator/add', methods=['POST'])
def add_fixture():
    data = request.get_json(force=True) or {}
    required = ('manufacturer', 'model', 'mode', 'ch_count', 'name', 'universe', 'address')
    missing  = [k for k in required if k not in data]
    if missing:
        return jsonify({'error': f'Missing fields: {missing}'}), 400
    try:
        entry = {
            'manufacturer': data['manufacturer'],
            'model':        data['model'],
            'mode':         data['mode'],
            'ch_count':     int(data['ch_count']),
            'name':         data['name'],
            'role':         data.get('role', 'Custom'),
            'universe':     int(data['universe']) - 1,  # UI sends 1-indexed
            'address':      int(data['address'])  - 1,
            'x_mm':         int(data.get('x_mm', 0)),
            'z_mm':         int(data.get('z_mm', 0)),
            'y_mm':         int(data.get('y_mm', 0)),
        }
        idx = fx.add_fixture(entry)
        return jsonify({'ok': True, 'idx': idx, 'rig': fx.rig_to_api()})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/configurator/<int:idx>', methods=['PATCH'])
def update_fixture(idx):
    data = request.get_json(force=True) or {}
    # Convert 1-indexed UI values if present
    patch = {}
    for k, v in data.items():
        if k == 'universe':
            patch[k] = int(v) - 1
        elif k == 'address':
            patch[k] = int(v) - 1
        elif k in ('ch_count', 'x_mm', 'z_mm', 'y_mm'):
            patch[k] = int(v)
        else:
            patch[k] = v
    fx.update_fixture(idx, patch)
    return jsonify({'ok': True, 'rig': fx.rig_to_api()})


@bp.route('/configurator/<int:idx>', methods=['DELETE'])
def remove_fixture(idx):
    fx.remove_fixture(idx)
    return jsonify({'ok': True, 'rig': fx.rig_to_api()})


@bp.route('/configurator/move', methods=['POST'])
def move_fixture():
    data      = request.get_json(force=True) or {}
    idx       = int(data.get('idx', -1))
    direction = int(data.get('direction', 0))
    fx.move_fixture(idx, direction)
    return jsonify({'ok': True, 'rig': fx.rig_to_api()})


@bp.route('/configurator/clear', methods=['POST'])
def clear_rig():
    fx.clear_rig()
    return jsonify({'ok': True})


# ── QXF loading ───────────────────────────────────────────────────────────────

@bp.route('/configurator/load-qxf', methods=['POST'])
def load_qxf():
    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': 'No path provided.'}), 400
    if not os.path.exists(path):
        return jsonify({'error': f'File not found: {path}'}), 400
    try:
        definition = fx.load_qxf(path)
        return jsonify({'ok': True, 'definition': {
            'manufacturer': definition['manufacturer'],
            'model':        definition['model'],
            'type':         definition['type'],
            'modes':        [{'name': n, 'channels': c}
                             for n, c in definition['modes'].items()],
        }})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ── Import from workspace ─────────────────────────────────────────────────────

@bp.route('/configurator/import-from-workspace', methods=['POST'])
def import_from_workspace():
    """Populate the configurator rig from the currently loaded QXW."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    try:
        qxw_root = ws._state['qxw_root']
        fx.import_from_qxw(qxw_root)
        return jsonify({'ok': True, 'rig': fx.rig_to_api(),
                        'stage': fx.get_stage_dims()})
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500


# ── Auto-DMX ─────────────────────────────────────────────────────────────────

@bp.route('/configurator/auto-dmx', methods=['POST'])
def auto_dmx():
    fx.auto_assign_dmx()
    return jsonify({'ok': True, 'rig': fx.rig_to_api()})


# ── Snap to grid ─────────────────────────────────────────────────────────────

@bp.route('/configurator/snap', methods=['POST'])
def snap():
    data = request.get_json(force=True) or {}
    idx  = int(data.get('idx', -1))
    if not (0 <= idx < len(fx.get_rig())):
        return jsonify({'error': 'Invalid fixture index.'}), 400
    rig = fx.get_rig()
    e   = rig[idx]
    x, z = fx.snap_to_grid(e['x_mm'], e['z_mm'])
    fx.update_fixture(idx, {'x_mm': x, 'z_mm': z})
    return jsonify({'ok': True, 'x_mm': x, 'z_mm': z, 'rig': fx.rig_to_api()})


# ── QXW generation ────────────────────────────────────────────────────────────

@bp.route('/configurator/generate-qxw', methods=['POST'])
def generate_qxw():
    """
    Build a new QXW from the configurator rig + current template.
    Returns the file as a download.
    """
    if not fx.get_rig():
        return jsonify({'error': 'Rig is empty. Add at least one fixture.'}), 400

    # Use the workspace as template if available
    template_root = None
    if ws.get_state()['loaded']:
        import copy
        template_root = copy.deepcopy(ws._state['qxw_root'])

    try:
        qxw_bytes = fx.build_qxw(template_root=template_root)
    except Exception as e:
        return jsonify({'error': _safe_err(e)}), 500

    import datetime
    filename = 'rig_' + datetime.date.today().strftime('%Y%m%d') + '.qxw'
    return Response(
        qxw_bytes,
        mimetype='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


# ── Blueprint PDF ─────────────────────────────────────────────────────────────

@bp.route('/configurator/export-pdf', methods=['POST'])
def export_pdf():
    """Return a Blueprint PDF from the configurator rig."""
    data      = request.get_json(force=True) or {}
    show_name = (data.get('show_name') or 'Untitled').strip()
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

    rig = fx.get_rig()
    if not rig:
        # Fall back to workspace fixtures
        rig_src = ws.get_fixtures() if ws.get_state()['loaded'] else []
        fixture_data = [{'name': r['name'], 'patch': r.get('patch', ''),
                         'color': r.get('color', '#888888'),
                         'x': r.get('x_mm', 0), 'y': r.get('y_mm', 0),
                         'z': r.get('z_mm', 0), 'in_3d': r.get('in_3d', False)}
                        for r in rig_src]
    else:
        fixture_data = [{'name': e['name'],
                         'patch': f"U{e['universe']+1}.{e['address']+1:03d}",
                         'color': e.get('color', '#888888'),
                         'x': e.get('x_mm', 0), 'y': e.get('y_mm', 0),
                         'z': e.get('z_mm', 0),
                         'in_3d': e.get('x_mm', 0) != 0 or e.get('z_mm', 0) != 0}
                        for e in rig]

    pdf_bytes = pdf_mod.build_blueprint_pdf(
        fixture_data, show_name=show_name, doc_date=doc_date, W=W, H=H)
    if pdf_bytes is None:
        return jsonify({'error': 'No fixtures have 3D position data.'}), 400

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment; filename=blueprint.pdf'},
    )
