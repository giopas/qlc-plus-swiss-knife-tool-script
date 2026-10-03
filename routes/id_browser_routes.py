"""
routes/id_browser_routes.py
===========================
  GET  /api/functions              → all Engine functions
  GET  /api/vc-widgets             → all VC widgets (flat list)
  GET  /api/vc/tree                → full nested VC widget tree with positions + colours
  POST /api/vc/patch               → apply position/appearance changes (in-memory XML)
  POST /api/vc/export-qxw         → save patched workspace as new .qxw file
  POST /api/functions/export-pdf  → PDF download
  POST /api/vc-widgets/export-pdf → PDF download
"""

import os
from flask import Blueprint, jsonify, request, Response
from core import workspace as ws
from core import pdf as pdf_mod

bp = Blueprint('id_browser', __name__, url_prefix='/api')


@bp.route('/functions')
def functions():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_functions())


@bp.route('/vc-widgets')
def vc_widgets():
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    return jsonify(ws.get_vc_widgets())


# ── VC Editor endpoints ───────────────────────────────────────────────────────

@bp.route('/vc/tree')
def vc_tree():
    """Return the full nested VC widget tree with positions and colours."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    tree = ws.get_vc_tree()
    if tree is None:
        return jsonify({'error': 'No VirtualConsole found in workspace.'}), 404
    return jsonify(tree)


@bp.route('/vc/patch', methods=['POST'])
def vc_patch():
    """
    Apply position/appearance changes to VC widgets in the in-memory XML.

    Body: { "changes": [ {id, x?, y?, w?, h?, bg_color?, fg_color?,
                           font_size?, font_bold?}, ... ] }
    Returns: { "patched": int, "errors": [str] }
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data    = request.get_json(force=True) or {}
    changes = data.get('changes') or []
    if not isinstance(changes, list):
        return jsonify({'error': "'changes' must be a list"}), 400

    try:
        if changes and data.get('snapshot', True):
            ws.vc_snapshot()                      # makes the flush undoable
        result = ws.patch_vc_widgets(changes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify(result)


@bp.route('/vc/undo', methods=['POST'])
def vc_undo():
    """Undo the last server-side VC edit. Body {"clear": true} empties the stack."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    d = request.get_json(silent=True) or {}
    if d.get('clear'):
        ws.vc_undo_clear()
        return jsonify({'ok': True, 'remaining': 0})
    try:
        return jsonify({'ok': True, **ws.vc_undo()})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/vc/pages')
def vc_pages():
    """Pages and their frames, for the copy/move target pickers."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    from core import vc_ops
    try:
        root = ws._state['qxw_root']
        return jsonify({'pages': vc_ops.list_pages(root),
                        'duplicate_ids': vc_ops.duplicate_ids(root)})
    except vc_ops.VcOpError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/vc/op', methods=['POST'])
def vc_op():
    """
    Structural VC edit on the in-memory workspace (saved later via export).

    Body: {"op": "copy"|"move", "ids": [...], "target_id": "...",
           "x"?: int, "y"?: int, "keep_bindings"?: bool}
       or {"op": "new_page", "caption": "..."}
       or {"op": "copy_page", "page_id": "...", "caption"?: "...", "keep_bindings"?: bool}
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    from core import vc_ops
    d = request.get_json(force=True) or {}
    op = d.get('op')
    try:
        if op in ('copy', 'move'):
            kw = {'ids': [str(i) for i in (d.get('ids') or [])],
                  'target_id': str(d.get('target_id', '')),
                  'x': d.get('x'), 'y': d.get('y')}
            if op == 'copy':
                kw['keep_bindings'] = bool(d.get('keep_bindings'))
        elif op == 'new_page':
            kw = {'caption': d.get('caption', '')}
        elif op == 'fix_ids':
            kw = {}
        elif op == 'copy_page':
            kw = {'page_id': str(d.get('page_id', '')), 'caption': d.get('caption', ''),
                  'keep_bindings': bool(d.get('keep_bindings'))}
        elif op in _BUILDER_ARGS:
            kw = _builder_kw(op, d)
        else:
            return jsonify({'error': f'Unknown operation: {op}'}), 400
        return jsonify({'ok': True, **ws.vc_structural_edit(op, **kw)})
    except vc_ops.VcOpError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)[:300]}), 500


# VC Builder (WORKPLAN 2.4) — whitelisted arguments per operation
_BUILDER_ARGS = {
    'create':          {'parent_id': str, 'kind': str, 'caption': str, 'x': int, 'y': int,
                        'w': int, 'h': int, 'func_id': str, 'bg_color': str},
    'delete':          {'ids': list},
    'duplicate':       {'ids': list, 'keep_bindings': bool},
    'wire':            {'widget_id': str, 'func_id': str},
    'rename_page':     {'page_id': str, 'caption': str},
    'move_page':       {'page_id': str, 'index': int},
    'delete_page':     {'page_id': str},
    'label_panel':     {'parent_id': str, 'lines': list, 'columns': int, 'title': str,
                        'label_w': int, 'label_h': int},
    'auto_arrange':    {'frame_id': str, 'profile': str, 'columns': int},
    'screen':          {'profile_id': str, 'page_ids': list, 'scale': bool},
    'apply_template':  {'name': str, 'caption': str},
    'setlist_cuelist': {'chaser_id': str, 'cuelist_id': str, 'page_id': str},
}


def _builder_kw(op: str, d: dict) -> dict:
    kw = {}
    for k, t in _BUILDER_ARGS[op].items():
        v = d.get(k)
        if v is None or v == '':
            continue
        if t is list:
            kw[k] = [str(x) for x in v] if k != 'lines' else [str(x) for x in v]
        elif t is bool:
            kw[k] = bool(v)
        else:
            kw[k] = t(v)
    if op == 'auto_arrange':
        from core.quick_start import nomenclature
        ref = kw.pop('profile', None)
        try:
            kw['profile'] = nomenclature.load_profile(os.path.basename(ref)) if ref else None
        except ValueError:
            kw['profile'] = None
    return kw


@bp.route('/vc/builder-info')
def vc_builder_info():
    """Functions (with nomenclature prefix), kinds, screens, templates, profiles."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    from core import vc_builder
    from core.quick_start import nomenclature
    ref = request.args.get('profile') or 'plain'
    try:
        prof = nomenclature.load_profile(os.path.basename(ref))
    except ValueError:
        prof = nomenclature.load_profile('plain')
    fns = vc_builder.functions(ws._state['qxw_root'])
    items = []
    for fid, f in sorted(fns.items(), key=lambda kv: (kv[1]['name'].lower(), kv[0])):
        pre = prof.prefix_of(f['name'])
        letters = [c for c in pre if c.isalnum() or c == '*']
        items.append({'id': fid, 'name': f['name'], 'type': f['type'],
                      'group': letters[0] if letters else '',
                      'effect': letters[1] if len(letters) > 1 else ''})
    setlist = [i for i in items if i['type'] == 'Chaser']
    setlist.sort(key=lambda i: (not i['name'].lower().startswith('setlist'), i['name'].lower()))
    return jsonify({'functions': items, 'kinds': list(vc_builder.KINDS),
                    'screens': [{'id': k, **v} for k, v in vc_builder.SCREENS.items()],
                    'templates': vc_builder.list_templates(),
                    'profiles': nomenclature.list_profiles(),
                    'legend': vc_builder.legend_lines(prof),
                    'groups': prof.groups, 'effects': prof.effects,
                    'chasers': setlist,
                    'cuelists': vc_builder.cuelists(ws._state['qxw_root'])})


@bp.route('/vc/template', methods=['POST'])
def vc_template():
    """{"action": "save", "page_id", "name"} | {"action": "delete", "name"}"""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400
    from core import vc_builder, vc_ops
    d = request.get_json(force=True) or {}
    try:
        if d.get('action') == 'delete':
            ok = vc_builder.delete_template(str(d.get('name', '')))
            return (jsonify({'ok': True, 'templates': vc_builder.list_templates()}) if ok
                    else (jsonify({'error': 'Template not found.'}), 404))
        res = vc_builder.save_template(ws._state['qxw_root'], str(d.get('page_id', '')),
                                       str(d.get('name', '')))
        return jsonify({'ok': True, **res, 'templates': vc_builder.list_templates()})
    except vc_ops.VcOpError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/vc/export-qxw', methods=['POST'])
def vc_export_qxw():
    """
    Write the current (patched) workspace to a new .qxw file.

    Body: { "path": "/absolute/path/to/output.qxw" }
         or use the native picker by omitting/leaving path empty (falls back to
         /api/picker/save-name on the client side).
    Returns: { "ok": true, "path": "..." } or { "error": "..." }
    """
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data = request.get_json(force=True) or {}
    path = (data.get('path') or '').strip()

    if not path:
        return jsonify({'error': 'No output path provided.'}), 400

    # Safety: must end in .qxw
    if not path.lower().endswith('.qxw'):
        path += '.qxw'

    try:
        ws.export_qxw(path)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'ok': True, 'path': path})


# ── PDF exports ───────────────────────────────────────────────────────────────

@bp.route('/functions/export-pdf', methods=['POST'])
def functions_pdf():
    """Return the Functions table as a PDF download."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data  = request.get_json(force=True) or {}
    paper = data.get('paper', 'A4 Landscape')
    fsize = int(data.get('fsize', 8))
    W, H  = _paper_size(paper)

    rows_raw = ws.get_functions()
    headers  = ['ID', 'Name', 'Type', 'Contains']
    rows     = [[r['id'], r['name'], r['type'], r['contains']] for r in rows_raw]

    state = ws.get_state()
    title = f"Functions — {os.path.basename(state.get('path') or 'workspace')}"

    pdf_bytes = pdf_mod.build_table_pdf(rows, headers, title=title, W=W, H=H, fsize=fsize)
    filename  = 'functions.pdf'
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


@bp.route('/vc-widgets/export-pdf', methods=['POST'])
def vc_widgets_pdf():
    """Return the VC Widgets table as a PDF download (ID, Type, Caption, Func, Frame)."""
    if not ws.get_state()['loaded']:
        return jsonify({'error': 'No workspace loaded.'}), 400

    data  = request.get_json(force=True) or {}
    paper = data.get('paper', 'A4 Landscape')
    fsize = int(data.get('fsize', 8))
    W, H  = _paper_size(paper)

    rows_raw = ws.get_vc_widgets()
    # X/Y/W/H are now managed in the VC Editor, not in the PDF table
    headers  = ['Widget ID', 'Type', 'Caption', 'Func ID', 'Function', 'Frame Path']
    rows     = [[r['widget_id'], r['type'], r['caption'],
                 r['func_id'], r['func_name'], r['frame_path']]
                for r in rows_raw]

    state = ws.get_state()
    title = f"VC Widgets — {os.path.basename(state.get('path') or 'workspace')}"

    pdf_bytes = pdf_mod.build_table_pdf(rows, headers, title=title, W=W, H=H, fsize=fsize)
    filename  = 'vc_widgets.pdf'
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _paper_size(name: str):
    sizes = {
        'A4 Portrait':         (595.0, 842.0),
        'A4 Landscape':        (842.0, 595.0),
        'US Letter Portrait':  (612.0, 792.0),
        'US Letter Landscape': (792.0, 612.0),
    }
    return sizes.get(name, (842.0, 595.0))
