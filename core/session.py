"""
core/session.py
===============
In-memory session state for the QLC+ Swiss Knife app.

Tracks the file paths loaded during a session so they can be saved to a
.qsk (QLC+ Swiss Knife) project file and restored on next launch.

The session file is a plain JSON file — easy to version-control, easy to
inspect.  Paths are stored as absolute strings so the file can be shared
across machines (with path editing if needed).

Format (version 1):
{
  "version": 1,
  "workspace": "/abs/path/to/showfile.qxw",
  "dictionary": "/abs/path/to/descriptions.txt",
  "slot_paths": {
    "4001": "/abs/path/to/slot_20minutes_setlist.txt",
    "4101": "/abs/path/to/slot_unread_setlist.txt"
  },
  "brightness_forced": {
    "eurolite||led-4c-12-silent-slim-spot": "/abs/path/to/fixture.qxf"
  }
}

Note: "setlist_backup" key is kept for backward compat when reading old .qsk files.

"""

import json
import os

_SESSION_VERSION = 1

# ── In-memory session state ───────────────────────────────────────────────────
_sess: dict = {
    'workspace':          None,   # absolute path to the .qxw file
    'dictionary':         None,   # absolute path to descriptions .txt
    'slot_paths':         {},     # slot_id (str) → absolute path to per-slot .txt file
    'brightness_forced':  {},     # "norm_mfr||norm_model" → absolute path
    'dirty':              False,  # True if state differs from last save/load
    'session_file':       None,   # path of the .qsk file last loaded / saved
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_session() -> dict:
    """Return a copy of the current session state (safe for JSON serialisation)."""
    return dict(_sess)


def mark_dirty() -> None:
    _sess['dirty'] = True


def clear_dirty() -> None:
    _sess['dirty'] = False


# ── Field setters (each marks dirty when the value actually changes) ──────────

def set_workspace(path: str | None) -> None:
    _set_if_changed('workspace', path)


def set_dictionary(path: str | None) -> None:
    _set_if_changed('dictionary', path)


def set_slot_path(slot_id: str, path: str | None) -> None:
    """Remember the file path associated with a specific setlist slot."""
    sid = str(slot_id)
    old = _sess['slot_paths'].get(sid)
    new = path or None
    if old != new:
        if new is None:
            _sess['slot_paths'].pop(sid, None)
        else:
            _sess['slot_paths'][sid] = new
        mark_dirty()


def get_slot_path(slot_id: str) -> str | None:
    return _sess['slot_paths'].get(str(slot_id))


def set_brightness_forced(forced: dict) -> None:
    """Replace the forced-QXF map.  forced is {"norm_mfr||norm_model": path}."""
    if forced != _sess['brightness_forced']:
        _sess['brightness_forced'] = dict(forced)
        mark_dirty()


# ── Session file save / load ──────────────────────────────────────────────────

def to_export() -> dict:
    """Return a dict ready to be JSON-serialised as a .qsk file."""
    return {
        'version':           _SESSION_VERSION,
        'workspace':         _sess['workspace'],
        'dictionary':        _sess['dictionary'],
        'slot_paths':        _sess['slot_paths'],
        'brightness_forced': _sess['brightness_forced'],
    }


def apply_import(data: dict, session_file_path: str | None = None) -> None:
    """
    Overwrite the in-memory state from a parsed .qsk dict.
    Does NOT load any files — callers must do that separately.
    """
    _sess['workspace']         = data.get('workspace')
    _sess['dictionary']        = data.get('dictionary')
    _sess['slot_paths']        = data.get('slot_paths') or {}
    _sess['brightness_forced'] = data.get('brightness_forced') or {}
    _sess['session_file']      = session_file_path
    _sess['dirty']             = False


def set_session_file(path: str | None) -> None:
    """Record the path where the session was last saved or loaded from."""
    _sess['session_file'] = path
    clear_dirty()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_if_changed(key: str, value) -> None:
    if _sess.get(key) != value:
        _sess[key] = value
        mark_dirty()
