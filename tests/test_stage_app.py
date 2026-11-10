"""QLC+ Stage Monitor (3.18.0), the companion app in stage_app/.

The tests also guard the line between the two apps: the companion reads what
Swiss Knife exports (one page format), imports only the few core modules it
is allowed to, and nothing in Swiss Knife imports it."""
import ast
import base64
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import pytest

from core import stage_monitor as sm
from stage_app import ALLOWED_CORE, control, folder as fo, qlc_probe, settings, setlist_pdf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.join(ROOT, "stage_app")
LANGS = ("it", "fr", "de", "es", "pt", "ja", "zh")

SHOW = """<Workspace xmlns="http://www.qlcplus.org/Workspace">
 <Engine>
  <Function ID="1" Type="Scene" Name="Intro · 120 bpm"/>
  <Function ID="2" Type="Scene" Name="Song A"/>
  <Function ID="3" Type="Scene" Name="Song B"/>
  <Function ID="4" Type="Scene" Name="Hidden"/>
  <Function ID="10" Type="Chaser" Name="Set 1">
   <Step Number="0">1</Step><Step Number="1" Note="capo 2">2</Step><Step Number="2">3</Step><Step Number="3">4</Step>
  </Function>
  <Function ID="11" Type="Chaser" Name="Set 2"><Step Number="0">3</Step></Function>
 </Engine>
 <VirtualConsole><Frame Caption="Main" ID="0">
  <CueList Caption="Set one" ID="21"><Chaser>10</Chaser></CueList>
  <CueList Caption="Set two" ID="22"><Chaser>11</Chaser></CueList>
 </Frame></VirtualConsole>
</Workspace>"""


def _cfg(**kw):
    cfg = {"title": "Gig night", "http_port": 8091, "ws_port": 9998, "lists": [
        {"id": "21", "label": "First set", "mode": "control", "steps": {
            "1": {"card": {"tuning": "Drop D", "bpm": 96, "starts": "Drums", "note": "Long intro",
                           "players": [{"who": "Bass", "note": "5 strings"}]}},
            "2": {"card": {"tuning": "E"}},
            "3": {"hide": True}}},
        {"id": "22", "label": "", "mode": "read", "steps": {}}]}
    cfg.update(kw)
    return sm.clean_config(cfg)


@pytest.fixture
def exported(tmp_path, monkeypatch):
    monkeypatch.setenv("QLC_STAGE_MONITOR_HOME", str(tmp_path / "home"))
    d = tmp_path / "stage_monitor"
    sm.export(str(d), _cfg(), sm.cuelists(ET.fromstring(SHOW)), lang="it", show_path="/shows/Gig_v3.qxw")
    return str(d)


# ── the page format: what Swiss Knife exports, the app reads ────────────────

def test_reads_what_swiss_knife_exports(exported):
    p = fo.read(exported)
    assert p["title"] == "Gig night" and p["lang"] == "it"
    assert p["http_port"] == 8091 and p["ws_port"] == 9998
    assert p["show_name"] == "Gig_v3.qxw"
    assert [lst["id"] for lst in p["lists"]] == ["21", "22"]
    assert [lst["label"] for lst in p["lists"]] == ["First set", "Set two"]
    songs = p["lists"][0]["songs"]
    assert [s["name"] for s in songs] == ["Intro · 120 bpm", "Song A", "Song B"]      # the hidden one left out
    assert songs[0]["card"]["bpm"] == 120                                              # tempo from the name
    assert songs[1]["card"]["tuning"] == "Drop D" and songs[1]["note"] == "capo 2"
    assert songs[2]["tc"] == {"from": "Drop D", "to": "E"}
    assert [v["id"] for v in p["views"]] == ["commander", "band", "vocals"]


@pytest.mark.parametrize("make, why", [
    (lambda d: None, "does not exist"),
    (lambda d: os.makedirs(d), "no Stage Monitor page"),
    (lambda d: (os.makedirs(d), open(os.path.join(d, "index.html"), "w").write("<html>mine</html>")),
     "was not made by the Stage Monitor"),
])
def test_refuses_folders_that_are_not_an_export(tmp_path, make, why):
    d = str(tmp_path / "x")
    make(d)
    data, msg = fo.try_read(d)
    assert data is None and why in msg


def test_the_template_itself_is_not_a_page():
    with open(sm.PAGE_TEMPLATE, encoding="utf-8") as fh:
        with pytest.raises(fo.NotAPage):
            fo.page_data(fh.read())


# ── QLC+ ──────────────────────────────────────────────────────────────────────

class FakeQLC:
    """A web socket server that answers getWidgetStatus like QLC+ 5 does."""

    def __init__(self, widgets, http_only=False):
        self.widgets, self.http_only = widgets, http_only
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(c,), daemon=True).start()

    def _client(self, c):
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += c.recv(1024)
        if self.http_only:
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            c.close()
            return
        key = re.search(rb"Sec-WebSocket-Key: (\S+)", buf).group(1)
        acc = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
        c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  b"Sec-WebSocket-Accept: " + acc + b"\r\n\r\n")
        self._text(c, "FUNCTION|2|Running")                     # a push first, as QLC+ does
        while True:
            try:
                h = c.recv(2)
                if len(h) < 2 or h[0] & 0x0F == 0x8:
                    break
                n = h[1] & 0x7F
                mask = c.recv(4)
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(c.recv(n)))
            except OSError:
                break
            wid = data.decode().rsplit("|", 1)[-1]
            st = self.widgets.get(wid)
            self._text(c, f"QLC+API|getWidgetStatus|{wid}|{st}" if st else "QLC+API|getWidgetStatus|")
        c.close()

    @staticmethod
    def _text(c, s):
        b = s.encode()
        c.sendall(bytes([0x81, len(b)]) + b)

    def close(self):
        self.sock.close()


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_qlc_off_and_running_without_web_access():
    port = _free_port()
    assert qlc_probe.probe(port, ["21"], running=lambda: False)["state"] == "off"
    assert qlc_probe.probe(port, ["21"], running=lambda: True)["state"] == "no_web"


def test_qlc_ready_with_every_cue_list():
    q = FakeQLC({"21": "PLAY|1", "22": "STOP"})
    try:
        r = qlc_probe.probe(q.port, ["21", "22"])
        assert r["state"] == "ready" and r["found"] == ["21", "22"] and r["playing"] == ["21"]
    finally:
        q.close()


def test_qlc_with_another_show_open():
    q = FakeQLC({"21": "STOP"})
    try:
        r = qlc_probe.probe(q.port, ["21", "22"])
        assert r["state"] == "other_show" and r["missing"] == ["22"]
    finally:
        q.close()


def test_another_program_on_the_port():
    q = FakeQLC({}, http_only=True)
    try:
        assert qlc_probe.probe(q.port, ["21"])["state"] == "not_qlc"
    finally:
        q.close()


def test_the_probe_only_reads():
    assert re.findall(r'API = "(.*?)"', open(os.path.join(APP, "qlc_probe.py")).read()) == ["QLC+API|getWidgetStatus|"]
    src = open(os.path.join(APP, "qlc_probe.py")).read()
    for verb in ("|NEXT", "|PREV", "|PLAY", "|STOP", "|STEP"):
        assert f'"{verb}' not in src and f"'{verb}" not in src


# ── the setlist PDF ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("layout", setlist_pdf.LAYOUTS)
def test_setlist_pdf(exported, layout):
    pdf = setlist_pdf.build(fo.read(exported), layout)
    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF")
    assert pdf.count(b"/Type /Page ") == 2                     # one page per cue list


def test_a_long_setlist_goes_on_more_pages():
    page = {"title": "Long", "lists": [{"label": "All", "songs": [
        {"name": f"Song {i}", "card": {}, "note": ""} for i in range(80)]}]}
    assert setlist_pdf.build(page, "big").count(b"/Type /Page ") > 1
    assert setlist_pdf.build(page, "cards").count(b"/Type /Page ") > 1


def test_fit_cuts_long_names():
    s = setlist_pdf.fit("A very long song name indeed", 20, 100, True)
    assert s.endswith("...") and setlist_pdf.width(s, 20, True) <= 100


# ── the window's server ──────────────────────────────────────────────────────

def _call(ctl, path, body=None, token=True, host=None):
    req = urllib.request.Request(ctl.url.rstrip("/") + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Token", ctl.token)
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_control_server(exported):
    opened = []
    app = control.App(probe=lambda **k: {"state": "ready", "port": k["port"], "found": k["ids"],
                                         "missing": [], "playing": []}, opener=lambda p: opened.append(p) or True)
    ctl = control.Control(app).start()
    try:
        assert _call(ctl, "/api/state", token=False)[0] == 403
        assert _call(ctl, "/api/state", host="evil.example:80")[0] == 403
        assert _call(ctl, "/api/folder", {"folder": exported}, token=False)[0] == 403
        code, html = _call(ctl, "/", token=False)
        assert code == 200 and ctl.token.encode() in html
        code, body = _call(ctl, "/api/folder", {"folder": exported})
        st = json.loads(body)
        assert code == 200 and st["page"]["title"] == "Gig night" and st["lang"] == "it"
        st = json.loads(_call(ctl, "/api/state?force=1")[1])
        assert st["qlc"]["state"] == "ready" and st["qlc"]["found"] == ["21", "22"]
        code, body = _call(ctl, "/api/print", {"layout": "cards"})
        assert code == 200 and opened and os.path.isfile(opened[0])
        assert json.loads(body)["name"] == "Gig night - cards.pdf"
        assert _call(ctl, "/api/qr?text=http%3A%2F%2F10.0.0.2%3A8091%2F", token=False)[1].startswith(b"<svg")
        assert settings.load()["folder"] == os.path.abspath(exported)
    finally:
        app.close()
        ctl.stop()


def test_serves_the_page_and_nothing_else(exported):
    app = control.App(folder=exported, probe=lambda **k: {"state": "off"})
    try:
        port = _free_port()
        st = app.start(port)
        assert st["server"]["running"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
            assert b"Gig night" in r.read()
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/serve_stage.py", timeout=5)
    finally:
        app.close()


def test_start_needs_a_page(tmp_path, monkeypatch):
    monkeypatch.setenv("QLC_STAGE_MONITOR_HOME", str(tmp_path / "home"))
    app = control.App(folder=str(tmp_path), probe=lambda **k: {"state": "off"})
    with pytest.raises(ValueError):
        app.start()


# ── the line between the two apps ────────────────────────────────────────────

def _py_files(top):
    for d, dirs, files in os.walk(top):
        dirs[:] = [x for x in dirs if not x.startswith((".", "_")) and x not in ("tests", "stage_app", "wiki", "dist", "build")]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(d, f)


def test_nothing_in_swiss_knife_imports_the_companion():
    for p in list(_py_files(ROOT)):
        if p == os.path.join(ROOT, "qlc_stage_monitor.py"):
            continue
        tree = ast.parse(open(p, encoding="utf-8").read())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n == "stage_app" or n.startswith("stage_app.") for n in names), p


def _loaded(code):
    out = subprocess.run([sys.executable, "-c", code + "\nimport sys, json; print(json.dumps(sorted(sys.modules)))"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return set(json.loads(out.strip().splitlines()[-1]))


def test_the_companion_imports_only_what_it_may():
    mods = _loaded("import stage_app.app, stage_app.control")
    allowed = _loaded("import " + ", ".join(ALLOWED_CORE))
    core = {m for m in mods if m == "core" or m.startswith("core.")}
    assert core <= allowed, core - allowed
    for banned in ("flask", "routes", "app", "werkzeug"):
        assert banned not in mods


def test_the_bundle_spec_takes_only_the_companion():
    spec = open(os.path.join(ROOT, "packaging", "stagemonitor.spec"), encoding="utf-8").read()
    assert "flask" in spec.lower() and "excludes" in spec           # Flask left out on purpose
    assert "'routes'" not in spec.split("excludes")[0]


# ── the languages ────────────────────────────────────────────────────────────

def ui_strings():
    """Every text the window and the PDF can show (English, the keys of the language files)."""
    keys = set()
    html = open(os.path.join(APP, "ui", "index.html"), encoding="utf-8").read()
    keys |= {m.strip() for m in re.findall(r"<[^>]*\bdata-t\b[^>]*>([^<]+)<", html)}
    keys |= set(re.findall(r'placeholder="([^"]+)"[^>]*data-t-ph', html))
    js = open(os.path.join(APP, "ui", "app.js"), encoding="utf-8").read()
    keys |= set(re.findall(r"\bt\('((?:[^'\\]|\\.)*)'", js))
    block = js.split("const QLC = {", 1)[1].split("};", 1)[0]
    keys |= {s for s in re.findall(r"'((?:[^'\\]|\\.)*)'", block) if s and s not in ("ok", "warn", "bad")}
    for f in ("folder.py", "control.py", "setlist_pdf.py"):
        for node in ast.walk(ast.parse(open(os.path.join(APP, f), encoding="utf-8").read())):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) in ("NotAPage", "ValueError", "t") \
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                keys.add(node.args[0].value)
    return {k.replace("\\'", "'") for k in keys if k.strip()}


def test_strings_found():
    keys = ui_strings()
    assert "Start serving to the tablet" in keys and "QLC+ is ready" in keys and "Song" in keys
    assert "That folder does not exist." in keys and len(keys) > 50


@pytest.mark.parametrize("lang", LANGS)
def test_every_language_has_every_string(lang):
    d = json.load(open(os.path.join(APP, "i18n", f"{lang}.json"), encoding="utf-8"))
    assert d["_language"]
    missing = sorted(k for k in ui_strings() if not str(d.get(k) or "").strip())
    assert not missing, missing
    for k, v in d.items():
        if not k.startswith("_"):
            assert sorted(re.findall(r"\{\d\}", k)) == sorted(re.findall(r"\{\d\}", v)), (lang, k)


def test_window_languages_match_swiss_knife():
    assert set(settings.LANGS) == {"en"} | set(LANGS) == set(sm.LANGS)


def test_a_set_of_25_songs_fits_on_one_floor_page():
    page = {"title": "Gig", "lists": [{"label": "Set", "songs": [
        {"name": f"Song {i}", "card": {}, "note": ""} for i in range(25)]}]}
    assert setlist_pdf.build(page, "big").count(b"/Type /Page ") == 1


# ── updates (3.18.0) ─────────────────────────────────────────────────────────

from core import update  # noqa: E402
from stage_app import updates  # noqa: E402


@pytest.fixture(autouse=True)
def _swiss_knife_updater_untouched():
    """Whatever a test does to the updater, Swiss Knife's own tests get it back as it was."""
    saved, rx = dict(update.APP), update._ASSET_RE
    yield
    update.APP.clear()
    update.APP.update(saved)
    update._ASSET_RE = rx


def _assets(ver="9.9.9"):
    return [{"name": f"{p}-{ver}-macos-arm64.{e}", "browser_download_url": f"https://github.com/x/{p}.{e}"}
            for p in ("QLC-Swiss-Knife", "QLC-Stage-Monitor") for e in ("tar.gz", "dmg")]


def test_each_app_updates_only_itself(tmp_path, monkeypatch):
    assert update.pick_asset(_assets(), "macos", "arm64")["name"].startswith("QLC-Swiss-Knife-")
    monkeypatch.setenv("QLC_STAGE_MONITOR_HOME", str(tmp_path))
    updates.configure()
    assert update.pick_asset(_assets(), "macos", "arm64")["name"] == "QLC-Stage-Monitor-9.9.9-macos-arm64.tar.gz"
    assert update._file() == str(tmp_path / "update.json")               # its own settings and cache
    update.set_enabled(False)
    assert json.load(open(tmp_path / "update.json"))["check"] is False
    assert "QLC+ Stage Monitor" in update.install({"newer": True, "latest": "9.9.9"})["message"] \
        or not update.is_frozen()


def test_the_companion_check_reads_its_own_downloads(tmp_path, monkeypatch):
    monkeypatch.setenv("QLC_STAGE_MONITOR_HOME", str(tmp_path))
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps({"tag_name": "v9.9.9", "assets": _assets() + [
        {"name": "SHA256SUMS", "browser_download_url": "https://github.com/x/SHA256SUMS"}]}))
    monkeypatch.setenv("QSK_UPDATE_FEED", str(feed))
    monkeypatch.setattr(update, "platform_key", lambda: ("macos", "arm64"))
    updates.configure()
    info = updates.Updater().check(force=True)
    assert info["newer"] and info["latest"] == "9.9.9"
    assert info["asset"]["name"].startswith("QLC-Stage-Monitor-")


class FakeUpdater:
    def __init__(self):
        self.info = {"current": "3.18.0", "enabled": True, "frozen": True, "can_install": True,
                     "newer": True, "latest": "3.19.0", "asset": {"name": "QLC-Stage-Monitor-3.19.0-x.tar.gz"},
                     "pending": False, "error": ""}
        self.checked = self.installed = 0

    def status(self):
        return self.info

    def check(self, force=False):
        self.checked += 1
        return self.info

    def set_enabled(self, on):
        self.info["enabled"] = on
        return self.info

    def install(self):
        self.installed += 1
        return {"ok": True, "restart": True, "message": "ready"}

    @staticmethod
    def open_releases():
        return True


def test_update_from_the_window(exported):
    quit_called = threading.Event()
    upd = FakeUpdater()
    app = control.App(folder=exported, probe=lambda **k: {"state": "off"}, updater=upd)
    app.quit = quit_called.set
    ctl = control.Control(app).start()
    try:
        st = json.loads(_call(ctl, "/api/state")[1])
        assert st["update"]["newer"] and st["update"]["latest"] == "3.19.0"
        assert json.loads(_call(ctl, "/api/update/check", {})[1])["update"]["latest"] == "3.19.0" and upd.checked
        assert json.loads(_call(ctl, "/api/update/enable", {"check": False})[1])["update"]["enabled"] is False
        assert _call(ctl, "/api/update/install", {}, token=False)[0] == 403
        code, body = _call(ctl, "/api/update/install", {})
        assert code == 200 and json.loads(body)["restart"] and upd.installed == 1
        assert quit_called.wait(3)                     # the app quits so the swap can run
    finally:
        app.close()
        ctl.stop()


def test_no_updater_no_update(exported):
    app = control.App(folder=exported, probe=lambda **k: {"state": "off"})
    ctl = control.Control(app).start()
    try:
        assert json.loads(_call(ctl, "/api/state")[1])["update"] is None
        assert _call(ctl, "/api/update/install", {})[0] == 400
    finally:
        app.close()
        ctl.stop()
