"""
routes/native_picker_routes.py
==============================
Native OS file-picker shim — opens the real OS dialog from the Flask
process and returns the selected path to the browser.

This works around the browser security restriction that hides full file
paths from <input type="file"> elements.

  GET  /api/picker/available  — True if native picker is usable on this OS
  POST /api/picker/pick       — open the dialog; return selected path

Body for /pick:
  {
    "title":       "Select dictionary",           // dialog prompt
    "types":       [{"label": "Text", "exts": [".txt"]}],
    "initial_dir": "/Users/gio/Shows"             // optional starting dir
  }

Response:
  { "path": "/abs/path/to/file.txt", "cancelled": false }
  { "path": null, "cancelled": true }
"""

import os
import platform
import subprocess
import threading

from flask import Blueprint, jsonify, request

bp = Blueprint('picker', __name__, url_prefix='/api/picker')


# ── availability ──────────────────────────────────────────────────────────────

def _is_available() -> bool:
    if platform.system() == 'Darwin':
        return True  # osascript always present
    try:
        import tkinter  # noqa: F401
        return True
    except ImportError:
        return False


@bp.route('/available')
def available():
    return jsonify({'available': _is_available()})


# ── pick ──────────────────────────────────────────────────────────────────────

@bp.route('/pick', methods=['POST'])
def pick():
    data        = request.get_json(force=True) or {}
    title       = data.get('title', 'Select file')
    types       = data.get('types', [])       # [{label, exts:['.txt']}]
    initial_dir = (data.get('initial_dir') or '').strip()

    # Validate: initial_dir must exist (don't expose arbitrary server paths)
    if initial_dir and not os.path.isdir(initial_dir):
        initial_dir = ''

    path = _open_picker(title, types, initial_dir)
    return jsonify({'path': path, 'cancelled': path is None})


# ── platform implementations ──────────────────────────────────────────────────

def _open_picker(title: str, types: list, initial_dir: str) -> str | None:
    system = platform.system()
    if system == 'Darwin':
        return _pick_macos(title, types, initial_dir)
    return _pick_tkinter(title, types, initial_dir)


def _pick_macos(title: str, types: list, initial_dir: str) -> str | None:
    """Use AppleScript choose-file dialog (always available on macOS)."""
    # Build the AppleScript
    script = f'POSIX path of (choose file with prompt {_as_str(title)})'
    # Note: 'of type' in choose file accepts file-type codes (4-char) or
    # UTIs, not plain extensions. Restricting by type is fragile for custom
    # extensions like .qxf / .qxw, so we omit the restriction and rely on
    # the user picking the right file.
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            path = result.stdout.strip()
            if path and os.path.isfile(path):
                return path
    except Exception:
        pass
    return None


def _pick_tkinter(title: str, types: list, initial_dir: str) -> str | None:
    """Use tkinter filedialog (Linux / Windows fallback)."""
    result_box: list = [None]
    exc_box:    list = [None]

    def _run():
        try:
            import tkinter as tk
            from tkinter import filedialog

            # Build filetypes list for tkinter
            tk_types = []
            for t in types:
                exts = ' '.join(f'*{e}' for e in (t.get('exts') or []))
                if exts:
                    tk_types.append((t.get('label', 'Files'), exts))
            if not tk_types:
                tk_types = [('All files', '*.*')]

            root = tk.Tk()
            root.withdraw()
            try:
                root.attributes('-topmost', True)
            except Exception:
                pass

            kwargs: dict = {'title': title, 'filetypes': tk_types}
            if initial_dir:
                kwargs['initialdir'] = initial_dir

            path = filedialog.askopenfilename(**kwargs)
            root.destroy()
            result_box[0] = path or None
        except Exception as e:
            exc_box[0] = e

    # tkinter must run on the main thread on many platforms.
    # Since Flask's dev server is single-threaded and this endpoint is
    # called from a user interaction, we run it directly.
    _run()

    if exc_box[0]:
        return None
    return result_box[0]


# ── helpers ───────────────────────────────────────────────────────────────────

def _as_str(s: str) -> str:
    """Wrap a Python string as an AppleScript string literal."""
    return '"' + s.replace('"', '\\"') + '"'
