"""stage_app/control.py: the app's own window talks to this small server.

It listens on 127.0.0.1 only, on a free port, and answers only a page that
sends this run's token and the right ``Host`` (no other web page on this
computer can drive it).  The tablet never sees it: the tablet gets the Stage
Monitor page from :class:`core.stage_monitor.StageServer` on the network.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
import subprocess  # nosec B404 — fixed commands, no shell, to open the PDF
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

from core import qr
from core import stage_monitor as sm
from core.workspace import VERSION

from stage_app import APP_NAME, folder as fo, qlc_probe, settings, setlist_pdf

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "ui")
I18N = os.path.join(HERE, "i18n")
HOME_URL = "https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/QLC-Stage-Monitor"
_STATIC = {"/app.js", "/app.css", "/icon.svg"}


def translations(lang: str) -> dict:
    """The app's words in *lang* ({} for English or a missing file)."""
    if lang == "en" or lang not in settings.LANGS:
        return {}
    try:
        with open(os.path.join(I18N, f"{lang}.json"), encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in d.items() if not k.startswith("_") and isinstance(v, str) and v.strip()}


def open_file(path: str) -> bool:
    """Open *path* with the computer's own viewer (the PDF, to print it)."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])  # nosec B603 B607
        elif sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]  # nosec B606
        else:
            subprocess.Popen(["xdg-open", path])  # nosec B603 B607
        return True
    except OSError:
        return False


def safe_name(s: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", s, flags=re.UNICODE).strip()
    return s[:60] or "Setlist"


class App:
    """Everything the window can ask for, without the HTTP part (tests use it directly)."""

    def __init__(self, folder: str = "", lang: str = "", probe: Callable = qlc_probe.probe,
                 opener: Callable = open_file, updater=None):
        st = settings.load()
        self.updater = updater                 # stage_app.updates.Updater in the app; None: no update check
        self.quit: Optional[Callable[[], None]] = None      # set by the window: close the app
        self.server = sm.StageServer()
        self.probe_fn = probe
        self.opener = opener
        self.lang = lang if lang in settings.LANGS else st["lang"]
        self.folder = ""
        self.page: Optional[dict] = None
        self.error = ""
        self.qlc = {"state": "unknown", "port": sm.DEFAULT_WS_PORT, "found": [], "missing": [], "playing": []}
        self.qlc_at = 0.0
        self._lock = threading.Lock()
        self.picker: Optional[Callable[[], str]] = None      # set by the window (native folder dialog)
        self.raise_window: Optional[Callable[[], None]] = None
        self.set_folder(folder or st["folder"], remember=bool(folder))   # a folder given at start is the one to reopen (after an update too)

    # ── the folder ───────────────────────────────────────────────────────────
    def set_folder(self, folder: str, remember: bool = True) -> dict:
        folder = os.path.abspath(os.path.expanduser(folder)) if folder else ""
        page, why = fo.try_read(folder)
        if self.server.running and folder != self.folder:
            self.server.stop()
        self.folder, self.page, self.error = folder, page, why
        if page and not self.lang:
            self.lang = page["lang"] if page["lang"] in settings.LANGS else "en"
        self.qlc_at = 0.0
        if remember and page:
            settings.save(folder=folder)
        return self.state()

    def reload(self) -> None:
        """Read the folder again (Swiss Knife may have exported a new page)."""
        if self.folder:
            page, why = fo.try_read(self.folder)
            self.page, self.error = page, why

    # ── QLC+ ─────────────────────────────────────────────────────────────────
    def check_qlc(self, force: bool = False) -> dict:
        with self._lock:
            if not force and time.monotonic() - self.qlc_at < 2.5:
                return self.qlc
            self.qlc_at = time.monotonic()
        port = self.page["ws_port"] if self.page else sm.DEFAULT_WS_PORT
        ids = [lst["id"] for lst in self.page["lists"]] if self.page else []
        try:
            res = self.probe_fn(port=port, ids=ids)
        except Exception:  # noqa: BLE001 — a probe must never stop the window
            res = {"state": "unknown", "port": port, "found": [], "missing": [], "playing": []}
        labels = {lst["id"]: lst["label"] for lst in self.page["lists"]} if self.page else {}
        res["missing_labels"] = [labels.get(i, i) for i in res.get("missing", [])]
        self.qlc = res
        return res

    # ── the tablet server ────────────────────────────────────────────────────
    def start(self, port: Optional[int] = None) -> dict:
        self.reload()
        if not self.page:
            raise ValueError(self.error or "Choose the folder Swiss Knife exported first.")
        self.server.start(self.folder, int(port or self.page["http_port"]))
        return self.state()

    def stop(self) -> dict:
        self.server.stop()
        return self.state()

    # ── printing ─────────────────────────────────────────────────────────────
    def print_setlist(self, layout: str = "big") -> dict:
        self.reload()
        if not self.page:
            raise ValueError(self.error or "Choose the folder Swiss Knife exported first.")
        tr = translations(self.lang)
        words = [self.page["title"]] + [lst["label"] for lst in self.page["lists"]]
        use = tr if all(setlist_pdf.printable(v) for v in tr.values()) else {}

        def t(s):
            return use.get(s, s)
        data = setlist_pdf.build(self.page, layout, t)
        name = f"{safe_name(self.page['title'] or 'Setlist')} - {'setlist' if layout == 'big' else 'cards'}.pdf"
        path = os.path.join(self.folder, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return {"path": path, "name": name, "opened": bool(self.opener(path)),
                "unprintable": not all(setlist_pdf.printable(w) for w in words)}

    # ── what the window shows ────────────────────────────────────────────────
    def state(self) -> dict:
        sv = self.server.status()
        page = None
        if self.page:
            page = {k: self.page[k] for k in ("title", "views", "ws_port", "http_port", "show_name", "lang")}
            page["lists"] = [{"id": lst["id"], "label": lst["label"], "mode": lst["mode"],
                              "songs": len(lst["songs"])} for lst in self.page["lists"]]
        return {"app": APP_NAME, "version": VERSION, "folder": self.folder, "page": page, "error": self.error,
                "server": sv, "qlc": self.qlc, "lang": self.lang or "en", "langs": list(settings.LANGS),
                "can_pick": self.picker is not None, "home": HOME_URL,
                "update": self.updater.status() if self.updater else None}

    # ── updates ──────────────────────────────────────────────────────────────
    def install_update(self) -> dict:
        if not self.updater:
            raise ValueError("Updates are not available here.")
        res = self.updater.install()
        if res.get("restart") and self.quit:
            self.server.stop()
            threading.Timer(1.0, self.quit).start()      # the swap waits for this process to end
        return res

    def close(self) -> None:
        self.server.stop()


class Handler(BaseHTTPRequestHandler):
    app: App = None            # type: ignore[assignment]
    token: str = ""
    port: int = 0
    server_version = "QLCStageMonitor"
    sys_version = ""

    def log_message(self, *_a):
        pass

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").lower()
        return host in (f"127.0.0.1:{self.port}", f"localhost:{self.port}")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                         "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, data: dict) -> None:
        self._send(code, json.dumps(data).encode("utf-8"), "application/json")

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return self._send(403, b"Forbidden", "text/plain")
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            with open(os.path.join(UI, "index.html"), encoding="utf-8") as fh:
                html = fh.read().replace("__TOKEN__", self.token)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if u.path in _STATIC:
            p = os.path.join(UI, u.path[1:])
            with open(p, "rb") as fh:
                return self._send(200, fh.read(), (mimetypes.guess_type(p)[0] or "text/plain") + "; charset=utf-8")
        q = parse_qs(u.query)
        if u.path == "/api/qr":            # an <img> sends no token; a QR code of a text gives nothing away
            text = (q.get("text") or [""])[0]
            if not re.match(r"^https?://", text):
                return self._json(400, {"error": "A QR code is made for an http:// address."})
            return self._send(200, qr.svg(text).encode("utf-8"), "image/svg+xml")
        if self.headers.get("X-Token") != self.token:
            return self._send(403, b"Forbidden", "text/plain")
        if u.path == "/api/state":
            app = self.app
            app.reload()
            app.check_qlc(force=q.get("force") == ["1"])
            return self._json(200, app.state())
        if u.path == "/api/i18n":
            lang = (q.get("lang") or [self.app.lang])[0]
            return self._json(200, translations(lang))
        return self._send(404, b"Not found", "text/plain")

    def do_POST(self):  # noqa: N802
        if not self._host_ok() or self.headers.get("X-Token") != self.token:
            return self._send(403, b"Forbidden", "text/plain")
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 65536)
            body = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(body, dict):
                body = {}
        except ValueError:
            body = {}
        app = self.app
        path = urlparse(self.path).path
        try:
            if path == "/api/folder":
                return self._json(200, app.set_folder(str(body.get("folder") or "")))
            if path == "/api/pick":
                if app.picker is None:
                    return self._json(400, {"error": "Type the folder's path: this window has no folder dialog."})
                chosen = app.picker() or ""
                return self._json(200, app.set_folder(chosen) if chosen else app.state())
            if path == "/api/start":
                return self._json(200, app.start(body.get("port")))
            if path == "/api/stop":
                return self._json(200, app.stop())
            if path == "/api/print":
                return self._json(200, app.print_setlist(str(body.get("layout") or "big")))
            if path == "/api/lang":
                lang = str(body.get("lang") or "")
                if lang in settings.LANGS:
                    app.lang = lang
                    settings.save(lang=lang)
                return self._json(200, app.state())
            if path == "/api/update/check":
                if not app.updater:
                    raise ValueError("Updates are not available here.")
                app.updater.check(force=True)
                return self._json(200, app.state())
            if path == "/api/update/enable":
                if not app.updater:
                    raise ValueError("Updates are not available here.")
                app.updater.set_enabled(bool(body.get("check", True)))
                return self._json(200, app.state())
            if path == "/api/update/install":
                res = app.install_update()
                return self._json(200 if res.get("ok") else 400, {**res, "error": "" if res.get("ok") else res.get("message", "")})
            if path == "/api/update/open":
                return self._json(200, {"ok": bool(app.updater and app.updater.open_releases())})
            if path == "/api/raise":           # a second start handed its folder over
                if app.raise_window:
                    app.raise_window()
                return self._json(200, {"ok": True})
        except ValueError as e:
            return self._json(400, {"error": str(e), "state": app.state()})
        except OSError as e:
            return self._json(500, {"error": f"{e.strerror or e}", "state": app.state()})
        return self._send(404, b"Not found", "text/plain")


class Control:
    """The control server in a background thread."""

    def __init__(self, app: App, port: int = 0):
        self.token = secrets.token_urlsafe(24)
        handler = type("H", (Handler,), {"app": app, "token": self.token})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        handler.port = self.port
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="stage-app-control", daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def start(self) -> "Control":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
