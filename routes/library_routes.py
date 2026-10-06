"""routes/library_routes.py — the community library (WORKPLAN 3.7, v2.7.0).

Share templates, palettes, presets, naming profiles, VC styles and Show
Profiles as one plain file; install what someone shared with you.  Local
files only — nothing here touches the network or the show in progress.

    GET  /api/library/state    kinds, what you have (shareable), your folders
    POST /api/library/pack     {selection:[{kind,name}], title, author, description} → the pack (JSON)
    POST /api/library/read     {path | text} → the preview of a library file (kept for /install)
    POST /api/library/install  {choices:{index: skip|replace|copy}, default} → what was installed

None of these calls is recorded in the recipe.
"""

import json
import os
import re

from flask import Blueprint, jsonify, request

from core import library as lib

bp = Blueprint('library', __name__, url_prefix='/api/library')

_pending: dict = {}          # the pack read by /read, waiting for /install


def _safe_err(exc: Exception) -> str:
    return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))


def folders() -> dict:
    from core import profile, vc_builder, look_builder
    from core.quick_start import nomenclature, vc_style
    return {'VC templates': vc_builder.templates_dir(),
            'Palettes': look_builder.user_palettes_path(),
            'Look presets': look_builder.user_presets_path(),
            'Naming profiles': nomenclature.user_dir(),
            'VC styles': vc_style.user_dir(),
            'Show Profiles': profile.profiles_dir()}


@bp.route('/state')
def state():
    return jsonify({'kinds': lib.kinds(), 'items': lib.inventory(), 'folders': folders(), 'ext': lib.EXT})


@bp.route('/pack', methods=['POST'])
def pack():
    d = request.get_json(force=True) or {}
    try:
        p = lib.export_pack(d.get('selection') or [], str(d.get('title') or ''), str(d.get('author') or ''),
                            str(d.get('description') or ''))
    except lib.LibraryError as e:
        return jsonify({'error': _safe_err(e)}), 400
    return jsonify({'pack': p, 'filename': lib.pack_filename(p), 'items': len(p['items'])})


@bp.route('/read', methods=['POST'])
def read():
    d = request.get_json(force=True) or {}
    src = d.get('text') if d.get('text') else str(d.get('path') or '')
    if not src:
        return jsonify({'error': 'Pick a library file first.'}), 400
    try:
        if d.get('path') and not d.get('text') and not os.path.isfile(src):
            raise lib.LibraryError('That file was not found.')
        p = lib.read_pack(src)
        pv = lib.preview(p)
    except (lib.LibraryError, OSError, UnicodeDecodeError) as e:
        return jsonify({'error': _safe_err(e)}), 400
    _pending.clear()
    _pending['pack'] = p
    return jsonify(pv)


@bp.route('/install', methods=['POST'])
def install():
    d = request.get_json(force=True) or {}
    p = _pending.get('pack')
    if p is None:
        return jsonify({'error': 'Open a library file first.'}), 400
    try:
        res = lib.install(p, {str(k): str(v) for k, v in (d.get('choices') or {}).items()},
                          str(d.get('default') or 'skip'))
    except lib.LibraryError as e:
        return jsonify({'error': _safe_err(e)}), 400
    _pending.clear()
    return jsonify({**res, **{'state': {'items': lib.inventory()}}})
