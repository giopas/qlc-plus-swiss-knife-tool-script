#!/usr/bin/env python3
"""
================================================================================
  QLC+ Swiss Knife — Flask / SPA Edition  (v1.0-dev)
================================================================================
  Quickest start (no venv needed after first run):
      python3 app.py          ← auto-detects venv, bootstraps if needed

  Manual venv setup (first time only):
      python3 -m venv .venv
      source .venv/bin/activate          # macOS / Linux
      .venv\\Scripts\\activate.bat        # Windows
      pip install flask
      python3 app.py

  Opens http://localhost:5731 automatically.  Ctrl+C to quit.
================================================================================
"""

# ── Self-bootstrap: if Flask isn't available, try the local .venv first ───────
import sys
import os

def _try_bootstrap():
    """Re-exec under the project's .venv Python if flask is missing."""
    here   = os.path.dirname(os.path.abspath(__file__))
    # Common venv bin locations
    candidates = [
        os.path.join(here, '.venv', 'bin',      'python3'),   # macOS / Linux
        os.path.join(here, '.venv', 'bin',      'python'),    # macOS / Linux alt
        os.path.join(here, '.venv', 'Scripts',  'python.exe'),# Windows
        os.path.join(here, 'venv',  'bin',      'python3'),   # alternate name
        os.path.join(here, 'venv',  'Scripts',  'python.exe'),# alternate name Win
    ]
    for py in candidates:
        if os.path.isfile(py):
            # Only re-exec if we're not already in this venv (avoid infinite loop)
            if os.path.abspath(sys.executable) != os.path.abspath(py):
                os.execv(py, [py] + sys.argv)
    return False   # no venv found

try:
    import flask as _flask_check          # noqa: F401
except ModuleNotFoundError:
    _try_bootstrap()
    # If we reach here, bootstrap didn't find a venv — give a clear error
    import platform
    _system = platform.system()
    print("\n" + "="*70)
    print("  ERROR: Flask is not installed.")
    print("="*70)
    print("""
  Flask is the only required dependency.  Fix it once with:

  ── macOS / Linux ────────────────────────────────────────────────────
    python3 -m venv .venv
    source .venv/bin/activate
    pip install flask
    python3 app.py

  ── Windows (Command Prompt) ──────────────────────────────────────────
    python -m venv .venv
    .venv\\Scripts\\activate.bat
    pip install flask
    python app.py

  ── Windows (PowerShell) ──────────────────────────────────────────────
    python -m venv .venv
    .venv\\Scripts\\Activate.ps1
    pip install flask
    python app.py

  ── Shortcut (all platforms, no venv) ────────────────────────────────
    pip3 install flask          (or: pip install flask)
    python3 app.py

  After the first setup, just run:   python3 app.py
  The app will find the .venv automatically next time.
""")
    if _system == 'Darwin':
        print("  macOS tip: if 'pip3' isn't found, run:  brew install python")
    elif _system == 'Linux':
        print("  Linux tip: you may also need:  sudo apt install python3-venv python3-pip")
    elif _system == 'Windows':
        print("  Windows tip: make sure Python is in PATH (tick the box during install).")
    print("="*70 + "\n")
    sys.exit(1)

# ── Normal imports (Flask is now guaranteed to be importable) ─────────────────
import threading
import webbrowser
from flask import Flask, request, jsonify

from routes.workspace_routes  import bp as workspace_bp
from routes.id_browser_routes import bp as id_browser_bp
from routes.setlist_routes    import bp as setlist_bp
from routes.dictionary_routes import bp as dictionary_bp
from routes.checklist_routes  import bp as checklist_bp
from routes.triggers_routes   import bp as triggers_bp
from routes.fixture_routes    import bp as fixture_bp
from routes.merger_routes     import bp as merger_bp

PORT = 5731

# Allowed Origin / Host values for CSRF protection (localhost only)
_ALLOWED_HOSTS = {f'localhost:{PORT}', f'127.0.0.1:{PORT}'}


def create_app():
    app = Flask(__name__)

    app.register_blueprint(workspace_bp)
    app.register_blueprint(id_browser_bp)
    app.register_blueprint(setlist_bp)
    app.register_blueprint(dictionary_bp)
    app.register_blueprint(checklist_bp)
    app.register_blueprint(triggers_bp)
    app.register_blueprint(fixture_bp)
    app.register_blueprint(merger_bp)

    # ── Security: CSRF origin check ───────────────────────────────────────────
    @app.before_request
    def _csrf_origin_check():
        """Reject state-changing requests from unexpected origins."""
        if request.method in ('POST', 'PATCH', 'PUT', 'DELETE'):
            origin = request.headers.get('Origin', '')
            host   = request.headers.get('Host', '')
            # Strip scheme from Origin for comparison
            origin_host = origin.replace('http://', '').replace('https://', '')
            # Allow requests with no Origin header (curl, Python scripts, etc.)
            # but reject those whose Origin doesn't match localhost
            if origin_host and origin_host not in _ALLOWED_HOSTS:
                return jsonify({'error': 'Forbidden'}), 403
            if host and host not in _ALLOWED_HOSTS:
                return jsonify({'error': 'Forbidden'}), 403

    # ── Security: response headers ────────────────────────────────────────────
    @app.after_request
    def _security_headers(response):
        """Add security headers to every response."""
        # Content-Security-Policy: allow same-origin only; no inline JS eval
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "   # inline needed for SPA event handlers
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self';"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options']        = 'DENY'
        response.headers['Referrer-Policy']        = 'no-referrer'
        return response

    return app


if __name__ == '__main__':
    app = create_app()
    url = f'http://localhost:{PORT}'

    # Open the browser one second after the server starts
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"\n⚡  QLC+ Swiss Knife  →  {url}")
    print("   Press Ctrl+C to quit.\n")

    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)
