#!/usr/bin/env python3
"""Pictures of the Stage Monitor: the screen in Swiss Knife and the page on a tablet.

Easier: python3 tools/shots.py stage (starts the app, compares, contact sheet).

    python3 app.py --browser &
    python3 tools/make_stage_shots.py [OUT_DIR]

Writes OUT_DIR/19-stage-monitor.png (the screen, 1440 x 900),
20-stage-page.png (the tablet page, dark), 21-stage-page-black.png (black,
white song), both 800 x 1280 like a 10-inch tablet in portrait, and
stage-monitor.gif (a pedal moving through the setlist, then QLC+ gone and back).

No QLC+ is needed: the page's web socket is answered by a stand-in that speaks
the messages of docs/STAGE_MONITOR_PROTOCOL.md.  Uses the scrubbed corpus show
Festival_14fix.  SWK_LANG=it (or fr, de, es, pt, ja, zh) takes them in another
language.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.request

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import stage_monitor as sm  # noqa: E402
from core.workspace import VERSION  # noqa: E402

CORPUS = os.path.join(ROOT, "tests", "corpus")
BASE = os.environ.get("SWK_URL", "http://127.0.0.1:5731")
LANG = os.environ.get("SWK_LANG", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "screenshots")
TABLET = {"width": 800, "height": 1280}
LIST_ID = "4001"
CONFIG = {
    "title": "Festival", "font": "M", "theme": "dark", "show_next": True, "show_clock": False,
    "show_numbers": True,
    "lists": [{"id": LIST_ID, "label": "Set A", "mode": "control",
               "steps": {"0": {"label": "Walk-in"}, "1": {"label": "Intro"}, "3": {"hide": True},
                         "4": {"hide": True}, "7": {"hide": True}}},
              {"id": "4101", "label": "Set B", "mode": "read", "steps": {}}],
}


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data, {"Content-Type": "application/json"}, method=method)
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")


class FakeQlc:
    """Answers the page's web socket like QLC+ 5 does: status on request, pushes on a change."""

    def __init__(self):
        self.idx, self.socket = 2, None

    def attach(self, ws):
        self.socket = ws

        def on(msg):
            p = str(msg).split("|")
            if p[:2] == ["QLC+API", "getWidgetStatus"]:
                ws.send(f"QLC+API|getWidgetStatus|{p[2]}|PLAY|{self.idx}" if p[2] == LIST_ID
                        else f"QLC+API|getWidgetStatus|{p[2]}|STOP")
        ws.on_message(on)

    def press_next(self):
        self.idx += 1
        if self.socket:
            self.socket.send(f"{LIST_ID}|CUE|{self.idx}")
            self.socket.send(f"{LIST_ID}|CUE_STATE|1|{self.idx}|{self.idx + 1}|100|1")

    def stop(self):
        """QLC+ quits: the socket closes (the page tries again after a second)."""
        if self.socket:
            self.socket.close()
            self.socket = None


def tablet_page(b, url, fake):
    ctx = b.new_context(viewport=TABLET, device_scale_factor=1)
    pg = ctx.new_page()
    pg.route_web_socket("**/qlcplusWS", fake.attach)
    pg.route("**/vc.json", lambda r: r.fulfill(body="{}", content_type="application/json"))
    pg.goto(url)
    pg.wait_for_timeout(1500)
    return ctx, pg


def main():
    os.makedirs(OUT, exist_ok=True)
    show_dir = tempfile.mkdtemp(prefix="sk-stage-show-")      # the settings file goes next to the show
    show = os.path.join(show_dir, "Festival_14fix.qxw")
    shutil.copy(os.path.join(CORPUS, "Festival_14fix.qxw"), show)
    add_notes(show)
    global SHOW_PATH
    SHOW_PATH = show
    api("POST", "/api/load", {"path": show})
    api("GET", "/api/stagemon/lists")
    api("POST", "/api/stagemon/config", {"config": CONFIG})
    folder = tempfile.mkdtemp(prefix="sk-stage-")
    lang = LANG or "en"
    server = sm.StageServer()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()

            # the screen in Swiss Knife
            pg = b.new_page(viewport={"width": 1440, "height": 900})
            pg.route("**/api/update/**", lambda r: r.fulfill(json={
                "current": VERSION, "latest": VERSION, "enabled": True, "frozen": False,
                "can_install": False, "platform": "x", "error": "", "newer": False}))
            if LANG:
                pg.add_init_script(f"try {{ localStorage.setItem('sk-lang', '{LANG}') }} catch (e) {{}}")
            pg.goto(BASE + "/")
            pg.wait_for_timeout(1200)
            pg.evaluate("go('stagemon')")
            pg.wait_for_timeout(1500)
            pg.evaluate("stagemonSteps('4001')")
            pg.evaluate("document.body.classList.remove('no-native-picker')")   # as in the app: no path box
            pg.wait_for_timeout(600)
            pg.mouse.move(1420, 880)
            pg.screenshot(path=os.path.join(OUT, "19-stage-monitor.png"))
            print("  ✓ 19-stage-monitor.png")

            # the page on the tablet, served as on stage
            for name, theme in (("20-stage-page.png", "dark"), ("21-stage-page-black.png", "black")):
                shutil.rmtree(folder, ignore_errors=True)
                sm.export(folder, dict(CONFIG, theme=theme, show_clock=False), sm_lists(), lang)
                server.start(folder, free_port(), host="127.0.0.1")
                fake = FakeQlc()
                ctx, tp = tablet_page(b, f"http://127.0.0.1:{server.port}/", fake)
                tp.screenshot(path=os.path.join(OUT, name))
                print("  ✓", name)
                if theme == "dark":
                    frames = [tp.screenshot()]
                    for _ in range(3):
                        fake.press_next()
                        tp.wait_for_timeout(900)
                        frames.append(tp.screenshot())
                    fake.stop()
                    tp.wait_for_timeout(300)
                    frames.append(tp.screenshot())
                    tp.wait_for_timeout(2500)          # the page is back by itself
                    frames.append(tp.screenshot())
                    imgs = [Image.open(io.BytesIO(f)).convert("RGB").resize((400, 640)) for f in frames]
                    imgs = [im.quantize(colors=128) for im in imgs]
                    imgs[0].save(os.path.join(OUT, "stage-monitor.gif"), save_all=True, append_images=imgs[1:],
                                 duration=[1600, 1300, 1300, 1600, 2200, 1800], loop=0, optimize=True)
                    print("  ✓ stage-monitor.gif", len(imgs), "frames")
                ctx.close()
                server.stop()
            b.close()
    finally:
        server.stop()
        shutil.rmtree(folder, ignore_errors=True)
        shutil.rmtree(show_dir, ignore_errors=True)


SHOW_PATH = os.path.join(CORPUS, "Festival_14fix.qxw")
NOTES = {"2": "Capo 2 · drums count in", "5": "Key of E", "6": "Slow start, bass alone"}   # step number → note


def add_notes(path):
    """Step notes on the setlist chaser of the copy, so the pictures show them."""
    import re
    text = open(path, encoding="utf-8").read()
    start = text.index('<Function ID="1756"')
    end = text.index("</Function>", start)
    block = text[start:end]
    for num, note in NOTES.items():
        block = re.sub(rf'(<Step Number="{num}")', rf'\1 Note="{note}"', block, count=1)
    open(path, "w", encoding="utf-8").write(text[:start] + block + text[end:])


def sm_lists():
    import xml.etree.ElementTree as ET
    return sm.cuelists(ET.parse(SHOW_PATH).getroot())


def free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


if __name__ == "__main__":
    main()
