"""
routes/songbuilder_routes.py
============================
Flask routes for the Song Builder (3.9.8): a table of parts becomes one Show.

  GET  /api/songbuilder/list      — the Shows the Song Builder made
  GET  /api/songbuilder/open      — the table a Show was built with (?id=)
  POST /api/songbuilder/preview   — part starts, length, warnings; changes nothing
  POST /api/songbuilder/music     — name and length of a sound file (by path)
  POST /api/songbuilder/build     — build or rebuild the Show in the show in progress
  POST /api/songbuilder/click     — make a click track (.wav) next to the show (3.10.0)
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
    # a relative path counts from the show's folder, as QLC+ reads it; a file picked inside
    # that folder is written relative, so the show and its music can move together (3.13.0)
    folder = ws.show_folder()
    if folder and os.path.isabs(path):
        try:
            rel = os.path.relpath(path, folder)
            if not rel.startswith('..') and not os.path.isabs(rel):
                path = rel.replace(os.sep, '/')
        except ValueError:                       # another drive (Windows)
            pass
    full = song_builder.resolve(path, folder)
    return jsonify({'name': os.path.basename(path), 'path': path, 'found': os.path.isfile(full),
                    'length_ms': media.audio_length_ms(full)})


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


@bp.route('/click', methods=['POST'])
def song_click():
    """A click track at the table's BPM and length, saved next to the show under a free name.
    The page sends no path: the folder is the show's, the name is reduced to a plain file name."""
    try:
        out = ws.song_click(request.get_json(force=True) or {})
        out['found'] = True
        return jsonify(out)
    except ValueError as e:
        return _err(e)
    except OSError as e:
        return jsonify({'error': 'The click track could not be saved: ' + str(e.strerror or e)[:200]}), 500
