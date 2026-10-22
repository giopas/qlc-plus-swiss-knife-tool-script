"""
routes/songbuilder_routes.py
============================
Flask routes for the Song Builder (3.9.8): a table of parts becomes one Show.

  GET  /api/songbuilder/list      — the Shows the Song Builder made
  GET  /api/songbuilder/open      — the table a Show was built with (?id=)
  POST /api/songbuilder/preview   — part starts, length, warnings; changes nothing
  POST /api/songbuilder/music     — name and length of a sound file (by path)
  POST /api/songbuilder/build     — build or rebuild the Show in the show in progress
"""

import os

from flask import Blueprint, jsonify, request

import core.workspace as ws
from core import media, song_builder

bp = Blueprint('songbuilder', __name__, url_prefix='/api/songbuilder')


def _err(e):
    return jsonify({'error': str(e)[:300]}), 400


@bp.route('/list')
def song_list():
    try:
        return jsonify(ws.song_list())
    except ValueError as e:
        return _err(e)


@bp.route('/open')
def song_open():
    try:
        return jsonify(ws.song_open(request.args.get('id', '')))
    except ValueError as e:
        return _err(e)


@bp.route('/preview', methods=['POST'])
def song_preview():
    try:
        return jsonify(ws.song_plan(request.get_json(force=True) or {}, lenient=True))
    except ValueError as e:
        return _err(e)


@bp.route('/music', methods=['POST'])
def song_music():
    path = str((request.get_json(force=True) or {}).get('path') or '').strip()
    if not path:
        return jsonify({'error': 'Give the path of the music file.'}), 400
    if os.path.splitext(path)[1].lower() not in media.AUDIO_EXTS:
        return jsonify({'error': 'The music must be a sound file (.wav, .mp3, .ogg, .flac, .m4a).'}), 400
    return jsonify({'name': os.path.basename(path), 'found': os.path.isfile(path),
                    'length_ms': media.audio_length_ms(path)})


@bp.route('/build', methods=['POST'])
def song_build():
    try:
        from core import show
        out = ws.song_build(request.get_json(force=True) or {})
        show.close_step()
        out['show'] = show.status()
        return jsonify(out)
    except ValueError as e:
        return _err(e)
    except Exception as e:  # noqa: BLE001
        return jsonify({'error': str(e)[:300]}), 500
