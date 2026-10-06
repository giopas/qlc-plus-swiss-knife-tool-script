#!/usr/bin/env python3
"""
================================================================================
  QLC+ Swiss Knife — Flask / SPA Edition  (v1.1.0)
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

try:                                    # cp1252 consoles / windowed apps must not stop on ⚡ ⚠
    from core.console import make_stdio_safe
    make_stdio_safe()
except Exception:                       # noqa: BLE001 — never block the start
    pass

def _try_bootstrap():
    """Re-exec under the project's .venv Python if flask is missing."""
    here   = os.path.dirname(os.path.abspath(__file__))
    # Common venv bin locations
    # Same lookup order as run.sh: $SWK_VENV, ~/.venvs/swissknife, then local
    shared = []
    if os.environ.get('SWK_VENV'):
        shared += [os.path.join(os.environ['SWK_VENV'], 'bin', 'python3'),
                   os.path.join(os.environ['SWK_VENV'], 'Scripts', 'python.exe')]
    home_venv = os.path.join(os.path.expanduser('~'), '.venvs', 'swissknife')
    shared += [os.path.join(home_venv, 'bin', 'python3'),
               os.path.join(home_venv, 'Scripts', 'python.exe')]
    candidates = shared + [
        os.path.join(here, '.venv', 'bin',      'python3'),   # macOS / Linux
        os.path.join(here, '.venv', 'bin',      'python'),    # macOS / Linux alt
        os.path.join(here, '.venv', 'Scripts',  'python.exe'),# Windows
        os.path.join(here, 'venv',  'bin',      'python3'),   # alternate name
        os.path.join(here, 'venv',  'Scripts',  'python.exe'),# alternate name Win
    ]
    if os.environ.get('_SWK_REEXEC'):      # already re-exec'd once: don't loop
        return False
    os.environ['_SWK_REEXEC'] = '1'
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
from flask import Flask, g, request, jsonify

WIKI_URL = "https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/"

from routes.workspace_routes  import bp as workspace_bp
from routes.id_browser_routes import bp as id_browser_bp
from routes.setlist_routes    import bp as setlist_bp
from routes.dictionary_routes import bp as dictionary_bp
from routes.checklist_routes  import bp as checklist_bp
from routes.techrider_routes  import bp as techrider_bp
from routes.triggers_routes   import bp as triggers_bp
from routes.fixture_routes    import bp as fixture_bp
from routes.brightness_routes import bp as brightness_bp
from routes.session_routes    import bp as session_bp
from routes.native_picker_routes import bp as picker_bp
from routes.quick_start_routes   import bp as quickstart_bp
from routes.porter_routes    import bp as porter_bp
from routes.showbook_routes import bp as showbook_bp
from routes.doctor_routes import bp as doctor_bp
from routes.reducer_routes import bp as reducer_bp
from routes.looks_routes import bp as looks_bp
from routes.stage_routes import bp as stage_bp
from routes.inputs_routes import bp as inputs_bp
from routes.show_routes import bp as show_bp
from routes.profile_routes import bp as profile_bp
from routes.compare_routes import bp as compare_bp
from routes.library_routes import bp as library_bp
from routes.update_routes import bp as update_bp
from routes.mcp_routes import bp as mcp_bp

PORT = 5731

# Allowed Origin / Host values for CSRF protection (localhost only)
_ALLOWED_HOSTS = {f'localhost:{PORT}', f'127.0.0.1:{PORT}'}


def _asset_version() -> str:
    """Short hash of static-file mtimes, appended as ?v= to CSS/JS URLs."""
    import hashlib
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    h = hashlib.sha1()
    for d, _dirs, files in sorted(os.walk(root)):
        for f in sorted(files):
            try:
                h.update(f'{f}{os.path.getmtime(os.path.join(d, f))}'.encode())
            except OSError:
                pass
    return h.hexdigest()[:10]


def create_app():
    app = Flask(__name__)

    app.register_blueprint(workspace_bp)
    app.register_blueprint(show_bp)
    app.register_blueprint(compare_bp)
    app.register_blueprint(id_browser_bp)
    app.register_blueprint(setlist_bp)
    app.register_blueprint(dictionary_bp)
    app.register_blueprint(checklist_bp)
    app.register_blueprint(techrider_bp)
    app.register_blueprint(triggers_bp)
    app.register_blueprint(fixture_bp)
    app.register_blueprint(brightness_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(picker_bp)
    app.register_blueprint(quickstart_bp)
    app.register_blueprint(porter_bp)
    app.register_blueprint(showbook_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(reducer_bp)
    app.register_blueprint(looks_bp)
    app.register_blueprint(stage_bp)
    app.register_blueprint(inputs_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(update_bp)
    app.register_blueprint(mcp_bp)

    # ── Security: CSRF origin check ───────────────────────────────────────────
    @app.before_request
    def _csrf_origin_check():
        """
        Reject state-changing requests whose Origin header explicitly names a
        non-localhost origin.  Requests with no Origin header (curl, Python
        scripts, same-origin browser fetches that omit Origin) are allowed
        because the server only listens on 127.0.0.1 — no remote host can
        reach it without Origin spoofing, which is browser-enforced.
        """
        if request.method not in ('POST', 'PATCH', 'PUT', 'DELETE'):
            return
        origin = request.headers.get('Origin', '')
        if not origin:
            return   # no Origin = same-origin or non-browser client → allow
        # Strip scheme and compare
        origin_host = origin.replace('http://', '').replace('https://', '').rstrip('/')
        if origin_host not in _ALLOWED_HOSTS:
            return jsonify({'error': 'Forbidden'}), 403

    # ── The recipe (WORKPLAN 2.9): every change to the show, for the replay ──
    # Before the call: what the IDs it names *are*, while the show is as the
    # call sees it (core/retarget.py) — so it can be replayed on another show.
    @app.before_request
    def _symbolize_for_recipe():
        try:
            from core import recipe
            if recipe.active() and recipe.recordable(request.method, request.path):
                g.recipe_sym = recipe.symbolize(request.method, request.path,
                                                request.get_json(silent=True))
        except Exception:  # noqa: BLE001 — recording never breaks a request
            g.recipe_sym = None

    @app.after_request
    def _record_recipe(response):
        try:
            from core import recipe
            if recipe.active() and recipe.recordable(request.method, request.path):
                recipe.record(request.method, request.path,
                              request.get_json(silent=True), response.status_code,
                              sym=getattr(g, 'recipe_sym', None))
        except Exception:  # noqa: BLE001 — recording never breaks a request
            pass
        return response

    # ── Security: response headers ────────────────────────────────────────────
    @app.after_request
    def _security_headers(response):
        """Add security headers to every response."""
        # CSP: allow same-origin resources + the jsdelivr CDN used for Grid.js
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self' https://api.github.com; "
            "object-src 'none'; "
            "base-uri 'self';"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options']        = 'DENY'
        response.headers['Referrer-Policy']        = 'no-referrer'
        return response

    # ── Settings endpoint ──────────────────────────────────────────────────────
    @app.route('/api/settings')
    def api_settings():
        import json as _json, getpass as _getpass
        here = os.path.dirname(os.path.abspath(__file__))
        settings_file = os.path.join(here, 'settings.json')
        name = None
        try:
            with open(settings_file) as f:
                data = _json.load(f)
                name = data.get('user_name')
        except Exception:
            pass
        if not name:
            try:
                u = _getpass.getuser()
                if u.lower() not in ('root', 'user', 'admin', 'administrator', 'default'):
                    name = u
            except Exception:
                pass
        return jsonify({'user_name': name})

    # ── Help: open a wiki page in the system browser ─────────────────────────
    @app.route('/api/help', methods=['POST'])
    def api_help():
        """Open the tool's wiki page. Only page names (letters, digits, '-')
        under the project wiki are accepted."""
        import re
        page = str((request.get_json(silent=True) or {}).get('page') or 'Home')
        if not re.fullmatch(r'[A-Za-z0-9-]{1,60}', page):
            return jsonify({'ok': False, 'error': 'bad page'}), 400
        url = WIKI_URL + page
        if app.config.get('TESTING'):
            return jsonify({'ok': True, 'url': url})
        try:
            ok = bool(webbrowser.open(url))
        except Exception:
            ok = False
        return jsonify({'ok': ok, 'url': url})

    # ── Quit endpoint ────────────────────────────────────────────────────────
    app._webview_window = None  # set by __main__ when running in webview mode

    @app.route('/api/quit', methods=['POST'])
    def api_quit():
        """Shut down the server (and native window if applicable)."""
        import signal

        def _shutdown():
            if app._webview_window is not None:
                # pywebview mode — destroy the window; webview.start()
                # will return and os._exit(0) handles the rest
                try:
                    app._webview_window.destroy()
                except Exception:
                    os._exit(0)
            else:
                # Browser mode — send SIGINT to stop Flask
                os.kill(os.getpid(), signal.SIGINT)

        threading.Timer(0.5, _shutdown).start()
        return jsonify({'ok': True, 'message': 'Shutting down…'})

    # ── Template context: inject version ─────────────────────────────────────
    # Static files: always revalidate, and bust the embedded browser's cache
    # (pywebview / WKWebView kept serving old JS after an update).
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    @app.context_processor
    def inject_version():
        from core.workspace import VERSION
        return {'version': VERSION, 'asset_v': _asset_version()}

    return app


def _smoke(app) -> int:
    """Release-build check: the page, its scripts and the bundled data files
    all answer.  Prints one line per failure; exit 0 when none."""
    c = app.test_client()
    bad = []
    for path in ('/', '/api/status', '/static/js/app.js', '/static/css/style.css',
                 '/static/i18n/it.json', '/static/i18n/fr.json', '/api/update/check'):
        r = c.get(path)
        if r.status_code != 200:
            bad.append(f'{path} → {r.status_code}')
    try:
        from core import look_builder
        from core.quick_start import nomenclature
        if not look_builder.palettes():
            bad.append('no built-in palettes')
        if not nomenclature.list_profiles():
            bad.append('no naming profiles')
    except Exception as e:  # noqa: BLE001
        bad.append(f'data files: {e!r}')
    from core.workspace import VERSION
    for b in bad:
        print('SMOKE FAIL:', b)
    print(f'SMOKE {"OK" if not bad else "FAILED"} — v{VERSION}')
    return 1 if bad else 0


if __name__ == '__main__':
    if '--mcp' in sys.argv:                 # Claude connects here: JSON on stdin/stdout, no window
        sys.argv.remove('--mcp')
        from core import mcp_server
        sys.exit(mcp_server.main(sys.argv[1:]))
    import argparse
    parser = argparse.ArgumentParser(description='QLC+ Swiss Knife')
    parser.add_argument('--browser', action='store_true',
                        help='Force browser mode (skip pywebview even if installed)')
    parser.add_argument('--smoke', action='store_true',
                        help='Start, load the page and the data files, then exit (used by the release build)')
    args = parser.parse_args()

    app = create_app()
    if args.smoke:
        sys.exit(_smoke(app))
    try:                                  # packaged app: drop the version we just replaced
        from core import update as _update
        _update.cleanup_after_update()
    except Exception:  # noqa: BLE001
        pass
    url = f'http://localhost:{PORT}'

    use_webview = False
    if not args.browser:
        try:
            import webview                      # pywebview
            use_webview = True
        except ImportError:
            pass

    if use_webview:
        # ── Native window mode (pywebview) ────────────────────────────────
        def _start_flask():
            import logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.WARNING)
            app.run(host='127.0.0.1', port=PORT, debug=False,
                    use_reloader=False)

        flask_thread = threading.Thread(target=_start_flask, daemon=True)
        flask_thread.start()

        # Open the window only once the server answers: a WKWebView that loads
        # too early stays white (no retry), and a port already taken by an
        # older Swiss Knife is said plainly instead of showing that one.
        import socket
        import time as _time
        import urllib.request
        ready, t0 = False, _time.time()
        while _time.time() - t0 < 15:
            try:
                with urllib.request.urlopen(url + '/api/status', timeout=1) as r:
                    ready = r.status == 200
                    break
            except Exception:  # noqa: BLE001 — not listening yet
                _time.sleep(0.15)
        if not flask_thread.is_alive():
            print(f"\n⚠  Could not start the server on port {PORT} — is another Swiss Knife still running?"
                  "\n   Close it (or: lsof -ti tcp:%d | xargs kill) and start again.\n" % PORT)
            sys.exit(1)
        if not ready:
            print("\n⚠  The server did not answer within 15 s; the window may stay empty — "
                  "reload it, or run: python3 app.py --browser\n")

        print(f"\n⚡  QLC+ Swiss Knife  →  {url}  (native window)")
        print("   Close the window to quit.\n")

        window = webview.create_window(
            'QLC+ Swiss Knife',
            url,
            width=1280,
            height=820,
            min_size=(900, 600),
            confirm_close=True,
        )
        app._webview_window = window   # let /api/quit destroy it
        # QSK_DEBUG=1: right-click › Inspect Element in the window (WebKit console)
        webview.start(debug=bool(os.environ.get('QSK_DEBUG')))  # blocks until window is closed
        print("\n⚡  Window closed — bye!\n")
        os._exit(0)
    else:
        # ── Browser mode ──────────────────────────────────────────────────
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

        print(f"\n⚡  QLC+ Swiss Knife  →  {url}")
        print("   Press Ctrl+C to quit.\n")

        app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)
