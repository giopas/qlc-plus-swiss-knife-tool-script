"""routes/update_routes.py — the update check (v2.8.0).

  GET  /api/update/check[?force=1]   → status (current, latest, newer, asset…)
  POST /api/update/settings          → {"check": true|false}
  POST /api/update/install           → download, verify, swap on exit, then quit
  POST /api/update/open              → open the release page in the system browser
"""
import os
import signal
import threading
import webbrowser

from flask import Blueprint, current_app, jsonify, request

from core import update

bp = Blueprint("update", __name__)


@bp.route("/api/update/check")
def api_check():
    if current_app.config.get("TESTING") and not os.environ.get("QSK_UPDATE_FEED"):
        return jsonify(update.status())          # tests never reach GitHub
    return jsonify(update.check(force=request.args.get("force") == "1"))


@bp.route("/api/update/settings", methods=["POST"])
def api_settings():
    update.set_enabled(bool((request.get_json(silent=True) or {}).get("check", True)))
    return jsonify(update.status())


@bp.route("/api/update/install", methods=["POST"])
def api_install():
    res = update.install()
    if res.get("ok") and res.get("restart") and not current_app.config.get("TESTING"):
        app = current_app._get_current_object()          # the timer thread has no request context

        def _quit():
            w = getattr(app, "_webview_window", None)
            if w is not None:
                try:
                    w.destroy()
                except Exception:  # noqa: BLE001
                    pass
            else:
                try:
                    os.kill(os.getpid(), signal.SIGINT)      # browser mode: stop Flask
                except Exception:  # noqa: BLE001
                    pass
            # the swap script is waiting for this process to be gone
            threading.Timer(2.0, lambda: os._exit(0)).start()

        threading.Timer(1.0, _quit).start()
    return jsonify(res), (200 if res.get("ok") else 400)


_OK_URL = "https://github.com/" + update.REPO + "/"


@bp.route("/api/update/open", methods=["POST"])
def api_open():
    """Only the project's own release pages (never a URL from the page)."""
    url = str((request.get_json(silent=True) or {}).get("url") or "")
    if not url.startswith(_OK_URL):
        url = _OK_URL + "releases/latest"
    if current_app.config.get("TESTING"):
        return jsonify({"ok": True, "url": url})
    try:
        ok = bool(webbrowser.open(url))
    except Exception:  # noqa: BLE001
        ok = False
    return jsonify({"ok": ok, "url": url})
