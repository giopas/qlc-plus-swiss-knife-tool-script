"""routes/stagemon_routes.py — Stage Monitor (3.5.0).

A page for a tablet on stage that shows the current and the next cue of the
show's CueLists, live from QLC+.  The show is only read.

    GET  /api/stagemon/lists       the CueLists, the saved settings, what changed
    POST /api/stagemon/config      {config}: keep the settings (<show>.stage.json)
    POST /api/stagemon/preview     {config, lang}: the page to look at here
    GET  /api/stagemon/preview     that page (talks to QLC+ on this computer)
    POST /api/stagemon/export      {config, folder?, lang}: index.html + serve_stage.py
    POST /api/stagemon/serve       {folder?, port?}: serve the folder to the tablet
    POST /api/stagemon/stop        stop serving
    GET  /api/stagemon/status      serving or not, this computer's addresses
"""

import os
import re

from flask import Blueprint, Response, jsonify, request

from core import stage_monitor as sm
from core import workspace
from routes.doctor_routes import _open_workspace

bp = Blueprint('stagemon', __name__, url_prefix='/api/stagemon')

_mem = {'config': None, 'preview': None, 'folder': ''}   # when the show has no folder of its own


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def _real_path() -> str:
    """The show's file on disk, or '' (uploaded show: no folder to write to)."""
    p = workspace.get_state().get('path') or ''
    return p if p and os.path.isfile(p) else ''


def _sidecar() -> str:
    p = _real_path()
    return sm.sidecar_path(p) if p else ''


def _default_folder() -> str:
    p = _real_path()
    if p:
        return os.path.join(os.path.dirname(os.path.abspath(p)), sm.EXPORT_DIR)
    out = workspace.get_output_dir()
    return os.path.join(out, sm.EXPORT_DIR) if out else ''


def _lists():
    root, path, name = _open_workspace()
    if root is None:
        return None, None
    if _mem.get('for') != (path, name):      # another show: its own folder and settings
        _mem.update({'config': None, 'preview': None, 'folder': '', 'for': (path, name)})
    return sm.cuelists(root), name


def _title_from(name: str) -> str:
    stem = os.path.splitext(name or '')[0]
    return re.sub(r'_v\d+$', '', stem)


@bp.route('/lists')
def lists():
    cls, name = _lists()
    if cls is None:
        return jsonify({'error': 'No workspace open.'}), 400
    side = _sidecar()
    saved = sm.load_config(side) if side else None
    cfg = saved or _mem['config'] or sm.default_config(cls, _title_from(name))
    rec = sm.reconcile(cfg, cls)
    folder = _mem['folder'] or _default_folder()
    return jsonify({
        'lists': cls, 'config': rec['config'], 'missing': rec['missing'], 'new': rec['new'],
        'saved': bool(saved), 'sidecar': os.path.basename(side) if side else '',
        'folder': folder, 'server': sm.server.status(),
    })


@bp.route('/config', methods=['POST'])
def config():
    body = request.get_json(silent=True) or {}
    cfg = sm.clean_config(body.get('config'))
    _mem['config'] = cfg
    side = _sidecar()
    if not side:
        return jsonify({'saved': False, 'note': 'The show was not opened from a folder: the settings last until Swiss Knife closes.'})
    try:
        sm.save_config(cfg, side)
        return jsonify({'saved': True, 'sidecar': os.path.basename(side)})
    except OSError as e:
        return jsonify({'error': _safe_err(e)}), 500


@bp.route('/preview', methods=['POST'])
def preview_set():
    cls, _name = _lists()
    if cls is None:
        return jsonify({'error': 'No workspace open.'}), 400
    body = request.get_json(silent=True) or {}
    _mem['preview'] = sm.build_page(sm.clean_config(body.get('config')), cls, str(body.get('lang') or 'en'))
    url = request.host_url.rstrip('/') + '/api/stagemon/preview'
    # Opened by the system browser: the app's own window (pywebview) opens no new windows,
    # and a real browser is what the tablet runs anyway.
    if body.get('open') is not True:          # only the page's Preview button asks for a browser
        return jsonify({'url': '/api/stagemon/preview', 'opened': False})
    try:
        import webbrowser
        opened = bool(webbrowser.open(url))
    except Exception:  # noqa: BLE001
        opened = False
    return jsonify({'url': '/api/stagemon/preview', 'opened': opened})


@bp.route('/preview')
def preview_get():
    if not _mem['preview']:
        return Response('Press Preview in Swiss Knife first.', mimetype='text/plain')
    return Response(_mem['preview'], mimetype='text/html')


@bp.route('/export', methods=['POST'])
def export():
    cls, _name = _lists()
    if cls is None:
        return jsonify({'error': 'No workspace open.'}), 400
    body = request.get_json(silent=True) or {}
    cfg = sm.clean_config(body.get('config'))
    folder = (body.get('folder') or '').strip() or _default_folder()
    if not folder:
        return jsonify({'error': 'Choose a folder for the page.'}), 400
    folder = os.path.abspath(os.path.expanduser(folder))
    parent = os.path.dirname(folder)
    if not os.path.isdir(folder) and not os.path.isdir(parent):
        return jsonify({'error': 'That folder does not exist.'}), 400
    try:
        out = sm.export(folder, cfg, cls, str(body.get('lang') or 'en'))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except OSError as e:
        return jsonify({'error': _safe_err(e)}), 500
    _mem['folder'] = folder
    _mem['config'] = cfg
    side = _sidecar()
    if side:
        try:
            sm.save_config(cfg, side)
        except OSError:
            side = ''
    return jsonify({'folder': out['folder'], 'page': out['page'], 'script': out['script'],
                    'sidecar': os.path.basename(side) if side else '',
                    'lists': len(cfg['lists']), 'server': sm.server.status()})


@bp.route('/serve', methods=['POST'])
def serve():
    body = request.get_json(silent=True) or {}
    folder = (body.get('folder') or '').strip() or _mem['folder'] or _default_folder()
    port = sm._port(body.get('port'), sm.DEFAULT_HTTP_PORT)
    if not folder:
        return jsonify({'error': 'Export the page first.'}), 400
    try:
        sm.server.start(os.path.abspath(os.path.expanduser(folder)), port)
    except ValueError as e:
        return jsonify({'error': str(e), 'server': sm.server.status()}), 400
    return jsonify({'server': sm.server.status()})


@bp.route('/stop', methods=['POST'])
def stop():
    sm.server.stop()
    return jsonify({'server': sm.server.status()})


@bp.route('/status')
def status():
    return jsonify({'server': sm.server.status()})
