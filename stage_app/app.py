"""stage_app/app.py: start QLC+ Stage Monitor.

    python3 -m stage_app                       the window (the last folder)
    python3 -m stage_app --folder <dir>        the window, on that exported folder
    python3 -m stage_app --browser             in the browser instead of a window
    python3 -m stage_app --smoke               check the bundle and quit (CI)

QLC+ Swiss Knife starts it with ``--folder``.  When the app is already open,
a second start hands the folder to that window and quits.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser

from stage_app import APP_NAME, settings
from stage_app.control import App, Control


def hand_over(folder: str) -> bool:
    """Give *folder* to the window already open; True when it took it."""
    inst = settings.read_instance()
    if not inst:
        return False
    base = f"http://127.0.0.1:{inst['port']}"
    headers = {"Content-Type": "application/json", "X-Token": inst["token"]}
    try:
        if folder:
            req = urllib.request.Request(base + "/api/folder", data=json.dumps({"folder": folder}).encode(),
                                         headers=headers, method="POST")
            urllib.request.urlopen(req, timeout=2).read()  # nosec B310 — our own window on 127.0.0.1
        req = urllib.request.Request(base + "/api/raise", data=b"{}", headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=2).read()  # nosec B310
        return True
    except (OSError, ValueError):
        return False


def smoke() -> int:
    """Everything the bundle needs, without a window: CI runs it on every build."""
    from core import qr
    from core import stage_monitor as sm
    from stage_app import folder as fo, qlc_probe, setlist_pdf
    from stage_app.control import UI, translations
    lists = [{"id": "1", "caption": "Set", "path": [], "frame_page": None, "layout": "stop",
              "chaser": {"id": "9", "name": "Set"}, "inputs": {},
              "steps": [{"index": 0, "name": "Intro · 120 bpm", "note": "", "function": "1"},
                        {"index": 1, "name": "Song", "note": "", "function": "2"}]}]
    cfg = sm.clean_config({"title": "Smoke", "lists": [{"id": "1", "label": "Set", "mode": "read", "steps": {}}]})
    with tempfile.TemporaryDirectory() as d:
        sm.export(d, cfg, lists)
        page = fo.read(d)
        assert page["lists"][0]["songs"][0]["card"]["bpm"] == 120
        for layout in setlist_pdf.LAYOUTS:
            assert setlist_pdf.build(page, layout).startswith(b"%PDF")
    assert qr.svg("http://192.168.2.1:8080/").startswith("<svg")
    assert qlc_probe.probe(port=1, ids=[], running=lambda: False)["state"] in ("off", "not_qlc")
    for f in ("index.html", "app.js", "app.css", "icon.svg"):
        assert os.path.isfile(os.path.join(UI, f)), f
    assert translations("it")
    print(f"{APP_NAME} smoke test: ok")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qlc-stage-monitor", description=APP_NAME)
    ap.add_argument("--folder", default="", help="the folder the Stage Monitor of Swiss Knife exported")
    ap.add_argument("--lang", default="", help="en, it, fr, de, es, pt, ja or zh")
    ap.add_argument("--browser", action="store_true", help="use the browser instead of a window")
    ap.add_argument("--smoke", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("folder_arg", nargs="?", default="", help=argparse.SUPPRESS)
    a, _rest = ap.parse_known_args(argv)           # macOS may add -psn_… when started from Finder
    if a.smoke:
        return smoke()
    folder = a.folder or a.folder_arg
    if hand_over(folder):
        return 0
    app = App(folder=folder, lang=a.lang)
    ctl = Control(app).start()
    settings.write_instance(ctl.port, ctl.token)
    try:
        webview = None
        if not a.browser:
            try:
                import webview  # type: ignore
            except ImportError:
                webview = None
        if webview is not None:
            win = webview.create_window(APP_NAME, ctl.url, width=600, height=860, min_size=(440, 560))

            def pick() -> str:
                res = win.create_file_dialog(getattr(webview, "FOLDER_DIALOG", 20), directory=app.folder or "")
                return (res[0] if isinstance(res, (list, tuple)) and res else res) or ""

            def raise_window() -> None:
                try:
                    win.restore()
                    win.show()
                except Exception:  # noqa: BLE001
                    pass
            app.picker, app.raise_window = pick, raise_window
            webview.start()
        else:
            print(f"{APP_NAME}: {ctl.url}  (close with Ctrl+C)")
            threading.Timer(0.3, lambda: webbrowser.open(ctl.url)).start()
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        settings.clear_instance(ctl.token)
        ctl.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
