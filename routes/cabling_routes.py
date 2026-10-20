"""routes/cabling_routes.py — Cabling (3.6.0).

Plans the DMX cabling of the show in progress with your kit.  The show is
only read; the plan lives in ``<show>.cabling.json`` next to it and your kit
in settings.

    GET  /api/cabling/state        rig, tonight's plan, evaluation, found in the show
    POST /api/cabling/plan         {plan}: keep tonight's plan (<show>.cabling.json)
    POST /api/cabling/export       {plan, what}: a download — plot (pdf, svg), pick list
                                   (pdf, csv, txt), labels (pdf, txt), load-in order (txt)
    POST /api/cabling/evaluate     {plan}: check a plan without keeping it
    POST /api/cabling/auto         {plan}: two or three alternatives, best first
    GET  /api/cabling/kit          your kit and the presets
    POST /api/cabling/kit          {kit}: keep your kit (settings)
    POST /api/cabling/kit/item     {item}: check one kit item (the clean item or the error)
    GET  /api/cabling/kit/export   your kit as a file (a Library pack, .qsklib.json)
    POST /api/cabling/kit/import   {text, mode: preview | add | replace}: a kit from a file
    GET  /api/cabling/fixtures?q=  fixture models of the installed QLC+ library
    POST /api/cabling/fixture-item {manufacturer, model} or {gh_manufacturer, filename}:
                                   a kit item for that model (connector from its definition)
"""

import copy
import os
import re

import datetime

from flask import Blueprint, Response, jsonify, request

from core import qxw_io, workspace
from core.cabling import auto as auto_mod
from core.cabling import fixtures as fixtures_mod
from core.cabling import kit as kit_mod
from core.cabling import outputs as out_mod
from core.cabling import plan as plan_mod
from core.cabling import rig as rig_mod
from routes.doctor_routes import _defs, _open_workspace

bp = Blueprint('cabling', __name__, url_prefix='/api/cabling')

_mem = {'for': None, 'plan': None}   # when the show has no folder of its own


@bp.before_request
def _units():
    """Every text of this request shows lengths in the unit of your kit."""
    from core.cabling import units as units_mod
    units_mod._cur.set(kit_mod.load_units())


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def _real_path() -> str:
    p = workspace.get_state().get('path') or ''
    return p if p and os.path.isfile(p) else ''


def _sidecar() -> str:
    p = _real_path()
    return plan_mod.sidecar_path(p) if p else ''


def _rig():
    """The show in progress as the planner sees it, read fresh each time (a
    fixture moved on the stage moves its cable)."""
    root, path, name = _open_workspace()
    if root is None:
        return None
    if _mem['for'] != (path, name):           # another show: its own plan
        _mem.update({'for': (path, name), 'plan': None})
    stripped = qxw_io.strip_ns(copy.deepcopy(root))
    return rig_mod.read_rig(stripped, _defs(path), path or '')


def _current_plan() -> tuple:
    side = _sidecar()
    saved = plan_mod.load_plan(side) if side else None
    return (saved or _mem['plan'] or plan_mod.new_plan()), bool(saved)


def _show_name() -> str:
    _root, path, name = _open_workspace()
    stem = os.path.splitext(name or os.path.basename(path or '') or 'show')[0]
    return re.sub(r'_v\d+$', '', stem)


def _view(p: dict, r: dict) -> dict:
    """The evaluation, the numbered cables and the plot of a plan."""
    ev = plan_mod.evaluate(p, r)
    rig = plan_mod.with_extras(r, p)
    nums = out_mod.numbered(ev, p)
    return {'evaluation': ev, 'cables': nums, 'svg': out_mod.plot_svg(ev, p, rig, _show_name()),
            'pick': out_mod.pick_list(ev, p), 'load_in': out_mod.load_in(ev, p)}


@bp.route('/state')
def state():
    r = _rig()
    if r is None:
        return jsonify({'error': 'No workspace open.'}), 400
    p, saved = _current_plan()
    return jsonify({'rig': r, 'plan': p, 'saved': saved, 'show': _show_name(),
                    'sidecar': os.path.basename(_sidecar()) if _sidecar() else '',
                    'base': kit_mod.load_base(), 'presets': kit_mod.presets(),
                    'found': plan_mod.not_in_inventory(p, r), **_view(p, r)})


@bp.route('/evaluate', methods=['POST'])
def evaluate():
    r = _rig()
    if r is None:
        return jsonify({'error': 'No workspace open.'}), 400
    p = plan_mod.clean_plan((request.get_json(silent=True) or {}).get('plan'))
    return jsonify({'plan': p, 'found': plan_mod.not_in_inventory(p, r), **_view(p, r)})


@bp.route('/auto', methods=['POST'])
def auto():
    r = _rig()
    if r is None:
        return jsonify({'error': 'No workspace open.'}), 400
    p = plan_mod.clean_plan((request.get_json(silent=True) or {}).get('plan'))
    if not r['fixtures']:
        return jsonify({'error': 'The show has no fixtures.'}), 400
    alts = auto_mod.alternatives(p, r)
    rig = plan_mod.with_extras(r, p)
    for a in alts:
        a['svg'] = out_mod.plot_svg(a['evaluation'], a['plan'], rig, _show_name())
    return jsonify({'alternatives': alts})


_EXPORTS = {
    'plot_pdf': ('Cabling_plot', 'pdf', 'application/pdf'),
    'plot_svg': ('Cabling_plot', 'svg', 'image/svg+xml'),
    'pick_pdf': ('Pick_list', 'pdf', 'application/pdf'),
    'pick_csv': ('Pick_list', 'csv', 'text/csv; charset=utf-8'),
    'pick_txt': ('Pick_list', 'txt', 'text/plain; charset=utf-8'),
    'labels_pdf': ('Cable_labels', 'pdf', 'application/pdf'),
    'labels_txt': ('Cable_labels', 'txt', 'text/plain; charset=utf-8'),
    'loadin_txt': ('Load-in_order', 'txt', 'text/plain; charset=utf-8'),
}


@bp.route('/export', methods=['POST'])
def export():
    r = _rig()
    if r is None:
        return jsonify({'error': 'No workspace open.'}), 400
    data = request.get_json(silent=True) or {}
    what = data.get('what')
    if what not in _EXPORTS:
        return jsonify({'error': 'Unknown export.'}), 400
    p = plan_mod.clean_plan(data.get('plan'))
    if not p['chains']:
        return jsonify({'error': 'The plan has no chains yet.'}), 400
    ev = plan_mod.evaluate(p, r)
    rig = plan_mod.with_extras(r, p)
    show = _show_name()
    date = str(data.get('date') or datetime.date.today().isoformat())[:10]
    nums = out_mod.numbered(ev, p)
    width = 32 if str(data.get('width')) == '58' else 42
    if what == 'plot_pdf':
        body = out_mod.plot_pdf(ev, p, rig, f'{show} - DMX cabling')
    elif what == 'plot_svg':
        body = out_mod.plot_svg(ev, p, rig, f'{show} - DMX cabling').encode('utf-8')
    elif what.startswith('pick_'):
        pl = out_mod.pick_list(ev, p)
        body = {'pick_pdf': lambda: out_mod.pick_list_pdf(pl, show, date),
                'pick_csv': lambda: out_mod.pick_list_csv(pl).encode('utf-8'),
                'pick_txt': lambda: out_mod.pick_list_text(pl, show, date, width).encode('utf-8')}[what]()
    elif what == 'labels_pdf':
        body = out_mod.labels_pdf(nums, show)
    elif what == 'labels_txt':
        body = out_mod.labels_text(nums, width).encode('utf-8')
    else:
        body = ('\n'.join(f'{i + 1}. {s}' for i, s in enumerate(out_mod.load_in(ev, p))) + '\n').encode('utf-8')
    stem, ext, mime = _EXPORTS[what]
    safe = re.sub(r'[^\w-]', '_', show).strip('_') or 'show'
    name = f'{safe}_{stem}.{ext}'
    return Response(body, mimetype=mime, headers={
        'Content-Disposition': f'attachment; filename="{name}"', 'X-Suggested-Filename': name,
        'Access-Control-Expose-Headers': 'X-Suggested-Filename'})


@bp.route('/plan', methods=['POST'])
def save_plan():
    r = _rig()
    if r is None:
        return jsonify({'error': 'No workspace open.'}), 400
    p = plan_mod.clean_plan((request.get_json(silent=True) or {}).get('plan'))
    side = _sidecar()
    if not side:
        _mem['plan'] = p
        return jsonify({'ok': True, 'saved': False, 'plan': p})
    try:
        plan_mod.save_plan(p, side)
    except OSError as e:
        return jsonify({'error': _safe_err(e)}), 500
    return jsonify({'ok': True, 'saved': True, 'sidecar': os.path.basename(side), 'plan': p})


def _kit_where() -> str:
    """Where your kit is kept, with your home folder as ~."""
    p = kit_mod.kit_path()
    home = os.path.expanduser('~')
    return '~' + p[len(home):] if p.startswith(home + os.sep) else p


@bp.route('/kit', methods=['GET'])
def get_kit():
    return jsonify({'kit': kit_mod.load_base(), 'presets': kit_mod.presets(), 'path': _kit_where(),
                    'library': fixtures_mod.has_library(),
                    'connectors': list(kit_mod.CONNECTORS), 'kinds': list(kit_mod.KINDS)})


@bp.route('/kit', methods=['POST'])
def save_kit():
    data = (request.get_json(silent=True) or {}).get('kit')
    if isinstance(data, dict) and 'units' not in data:     # keep the unit you chose
        data = {**data, 'units': kit_mod.load_units()}
    if isinstance(data, dict) and 'wishlist' not in data:  # and the wishlist
        data = {**data, 'wishlist': kit_mod.load_base().get('wishlist', [])}
    inv = kit_mod.clean_inventory(data)
    if inv.get('dropped'):
        return jsonify({'error': 'Some items cannot be used.', 'dropped': inv['dropped']}), 400
    try:
        kit_mod.save_base(inv)
    except OSError as e:
        return jsonify({'error': _safe_err(e)}), 500
    return jsonify({'ok': True, 'kit': kit_mod.load_base(), 'path': _kit_where()})


@bp.route('/kit/item', methods=['POST'])
def check_item():
    try:
        return jsonify({'item': kit_mod.clean_item((request.get_json(silent=True) or {}).get('item'))})
    except kit_mod.KitError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/fixtures')
def search_fixtures():
    q = (request.args.get('q') or '')[:80]
    return jsonify({'results': fixtures_mod.search(q), 'library': fixtures_mod.has_library()})


@bp.route('/fixture-item', methods=['POST'])
def fixture_item():
    """A kit item for a fixture model: from the installed library, or from the
    QLC+ library on GitHub (the screen says so before it goes on the internet)."""
    d = request.get_json(silent=True) or {}
    try:
        if d.get('gh_manufacturer'):
            mfg, fn = str(d['gh_manufacturer']).strip(), str(d.get('filename') or '').strip()
            if not re.match(r'^[\w\s\-\.&]+$', mfg) or not fn.lower().endswith('.qxf') or '/' in fn or '..' in fn:
                return jsonify({'error': 'Not a QLC+ fixture file.'}), 400
            from core.gh_fetch import gh_get_raw, GH_RAW_BASE
            raw = gh_get_raw(f"{GH_RAW_BASE}/{mfg.replace(' ', '%20')}/{fn.replace(' ', '%20')}")
            item = fixtures_mod.item_from_qxf_bytes(raw)
        else:
            mf, md = str(d.get('manufacturer') or '').strip()[:80], str(d.get('model') or '').strip()[:80]
            if not md:
                return jsonify({'error': 'A fixture needs its model.'}), 400
            item = fixtures_mod.item_from_library(mf, md)
    except kit_mod.KitError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:                       # GitHub unreachable, a broken file
        return jsonify({'error': _safe_err(e)}), 502
    return jsonify({'item': item})


@bp.route('/kit/export')
def export_kit():
    """Your kit as a Library pack: opens in Library or in Cabling › My kit › Import."""
    import json as _json
    from core import library as lib
    base = kit_mod.load_base()
    if not base['items']:
        return jsonify({'error': 'Your kit is empty: nothing to export.'}), 400
    pack = lib.export_pack([{'kind': 'cabling_kit', 'name': lib.KIT_NAME}], 'My cabling kit')
    pack['items'][0]['data']['units'] = base.get('units', 'm')
    body = _json.dumps(pack, indent=1, ensure_ascii=False)
    return Response(body, mimetype='application/json',
                    headers={'X-Suggested-Filename': 'cabling_kit' + lib.EXT,
                             'Content-Disposition': 'attachment; filename="cabling_kit' + lib.EXT + '"'})


def _kit_from_text(text: str) -> dict:
    """A kit from a file's text: a Library pack (its first cabling kit) or a
    plain kit file (``{items: [...]}``).  Raises ValueError with the reason."""
    import json as _json
    from core import library as lib
    try:
        data = _json.loads(text)
    except (ValueError, TypeError):
        raise ValueError('This is not a kit file (not JSON).')
    if isinstance(data, dict) and data.get('format') == lib.FORMAT:
        kits = [it for it in data.get('items') or [] if isinstance(it, dict) and it.get('kind') == 'cabling_kit']
        if not kits:
            raise ValueError('This library file holds no cabling kit.')
        data = kits[0].get('data') or {}
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('This is not a kit file.')
    try:
        clean = lib._check_cabling_kit({**data, 'name': 'kit'})
    except lib.LibraryError as e:
        raise ValueError(f'The kit cannot be used: {e}.')
    return {'items': clean['items'], 'units': data.get('units') if data.get('units') in ('m', 'ft') else None}


@bp.route('/kit/import', methods=['POST'])
def import_kit():
    d = request.get_json(silent=True) or {}
    text = d.get('text') or ''
    if len(text) > 4 * 1024 * 1024:
        return jsonify({'error': 'The file is too large for a kit.'}), 400
    try:
        got = _kit_from_text(text)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    base = kit_mod.load_base()
    have = {(it['kind'], it['name'].lower()) for it in base['items']}
    new = [it for it in got['items'] if (it['kind'], it['name'].lower()) not in have]
    mode = d.get('mode', 'preview')
    if mode == 'preview':
        return jsonify({'items': len(got['items']), 'new': len(new), 'names': [it['name'] for it in new][:20],
                        'units': got['units']})
    units = got['units'] or base.get('units', 'm')
    wish = base.get('wishlist', [])
    if mode == 'replace':
        inv = {'items': got['items'], 'units': units, 'wishlist': wish}
    elif mode == 'add':
        inv = {'items': base['items'] + [{k: v for k, v in it.items() if k != 'id'} for it in new],
               'units': base.get('units', 'm'), 'wishlist': wish}
    else:
        return jsonify({'error': 'Choose add or replace.'}), 400
    try:
        kit_mod.save_base(inv)
    except OSError as e:
        return jsonify({'error': _safe_err(e)}), 500
    return jsonify({'ok': True, 'kit': kit_mod.load_base(), 'path': _kit_where(), 'added': len(new)})
