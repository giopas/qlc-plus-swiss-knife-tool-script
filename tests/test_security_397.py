"""Security hardening of 3.9.7 (see docs/SECURITY_AUDIT_3.9.7.md): one test per finding."""
import io
import os
import tarfile
import threading
import urllib.error
import urllib.request

import pytest

import app as app_mod
from core import gh_fetch, safe_paths, stage_monitor, update, xml_safe

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS = os.path.join(HERE, "corpus")


@pytest.fixture()
def client():
    a = app_mod.create_app()
    a.config["TESTING"] = True
    return a.test_client()


# ── F1: Host and Origin ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("host", ["localhost:5731", "127.0.0.1:5731", "[::1]:5731", "localhost"])
def test_own_host_names_are_served(client, host):
    assert client.get("/api/status", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["evil.example:5731", "localhost.evil.example", "127.0.0.1.evil.example:5731",
                                  "192.168.1.20:5731", "127.0.0.1:9999", "localhost:5731@evil.example", ""])
def test_other_host_names_are_refused(client, host):
    """DNS rebinding: a page on another name that resolves to 127.0.0.1 must not read answers."""
    assert client.get("/api/status", headers={"Host": host}).status_code == 403


@pytest.mark.parametrize("origin", ["http://evil.example", "null", "http://localhost:5731.evil.example",
                                    "http://localhost", "http://localhost:80", "file://", "http://127.0.0.1:5731@evil.example"])
def test_other_origins_cannot_post(client, origin):
    r = client.post("/api/help", json={"page": "Home"}, headers={"Origin": origin})
    assert r.status_code == 403


def test_own_origin_and_scripts_can_post(client):
    assert client.post("/api/help", json={"page": "Home"}, headers={"Origin": "http://127.0.0.1:5731"}).status_code == 200
    assert client.post("/api/help", json={"page": "Home"}).status_code == 200          # curl: no Origin, no Sec-Fetch-Site


def test_browser_saying_cross_site_cannot_post(client):
    for v in ("cross-site", "same-site"):
        assert client.post("/api/help", json={"page": "Home"}, headers={"Sec-Fetch-Site": v}).status_code == 403
    assert client.post("/api/help", json={"page": "Home"}, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200


# ── F2: nothing from a CDN ─────────────────────────────────────────────────────────

def test_page_loads_nothing_from_the_internet(client):
    html = client.get("/").get_data(as_text=True)
    import re
    # scripts, styles, images, frames: nothing may come from another host (a link the user clicks is fine)
    external = re.findall(r'<(?:script|img|iframe|source|embed)[^>]*\ssrc="(https?://[^"]+)"|<link[^>]*\shref="(https?://[^"]+)"', html)
    assert external == []
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "jsdelivr" not in csp and "connect-src 'self';" in csp and "frame-ancestors 'none'" in csp
    assert client.get("/").headers["Cross-Origin-Opener-Policy"] == "same-origin"


# ── F3: the tablet server serves the page and nothing else ─────────────────────────

def test_tablet_server_serves_only_the_page(tmp_path):
    (tmp_path / "index.html").write_text("<html>page</html>")
    (tmp_path / "show.stage.json").write_text("secret")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("x")
    srv = stage_monitor.StageServer()
    srv.start(str(tmp_path), 0, host="127.0.0.1")
    port = srv._srv.server_address[1]

    def get(p):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{p}", timeout=3) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, b"", e.headers
    try:
        for p in ("/", "/index.html", "/?x=1"):
            st, body, hdr = get(p)
            assert st == 200 and b"page" in body
            assert hdr["X-Content-Type-Options"] == "nosniff" and "default-src 'none'" in hdr["Content-Security-Policy"]
        for p in ("/show.stage.json", "/sub/", "/sub/a.txt", "/../x", "/%2e%2e/etc/passwd", "//etc/passwd"):
            assert get(p)[0] == 404, p
    finally:
        srv.stop()


def test_exported_serve_script_has_the_same_guard():
    src = open(stage_monitor.SERVE_SCRIPT, encoding="utf-8").read()
    assert "PAGE_PATHS" in src and "def list_directory" in src and "def send_head" in src


# ── F4: text exports are text files ────────────────────────────────────────────────

def test_safe_text_path(tmp_path):
    ok = safe_paths.check_text_save_path(str(tmp_path / "setlist.txt"))
    assert ok.endswith("setlist.txt")
    assert safe_paths.check_text_save_path(str(tmp_path / "setlist"))             # no extension is fine
    for bad in ("", str(tmp_path / ".zshrc"), str(tmp_path / "run.sh"), str(tmp_path / "x.qxw"),
                str(tmp_path / "a.command"), str(tmp_path / "missing" / "a.txt"), str(tmp_path)):
        with pytest.raises(safe_paths.UnsafePath):
            safe_paths.check_text_save_path(bad)
    link = tmp_path / "l.txt"
    link.symlink_to(tmp_path / "target")
    with pytest.raises(safe_paths.UnsafePath):
        safe_paths.check_text_save_path(str(link))


def test_setlist_save_routes_refuse_other_files(client, tmp_path):
    from core import workspace as ws
    ws.load_qxw(os.path.join(CORPUS, "Pub_6fix.qxw"))
    victim = tmp_path / "victim.qxw"
    victim.write_text("keep me")
    slot = ws.get_cuelist_slots()
    for path in (str(victim), str(tmp_path / ".profile"), str(tmp_path / "go.sh")):
        r = client.post("/api/setlist/save", json={"path": path})
        assert r.status_code == 400, path
        r = client.post("/api/setlist/%s/save-file" % (slot[0]["id"] if slot else "0"), json={"path": path})
        assert r.status_code == 400, path
    assert victim.read_text() == "keep me"
    r = client.post("/api/setlist/save", json={"path": str(tmp_path / "ok.txt")})
    assert r.status_code == 200 and (tmp_path / "ok.txt").exists()


# ── F5: the updater ────────────────────────────────────────────────────────────────

def _tar(tmp_path, members):
    t = tmp_path / "a.tar"
    with tarfile.open(t, "w") as tf:
        for ti, data in members:
            tf.addfile(ti, io.BytesIO(data) if data is not None else None)
    return str(t)


def test_tar_with_an_escaping_symlink_is_refused(tmp_path):
    ti = tarfile.TarInfo("App/link")
    ti.type, ti.linkname = tarfile.SYMTYPE, "../../outside"
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError):
        update._safe_extract(_tar(tmp_path, [(ti, None)]), str(out))
    ab = tarfile.TarInfo("App/abs")
    ab.type, ab.linkname = tarfile.SYMTYPE, "/etc/passwd"
    with pytest.raises(ValueError):
        update._safe_extract(_tar(tmp_path, [(ab, None)]), str(out))


def test_tar_with_a_device_or_a_path_outside_is_refused(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    dev = tarfile.TarInfo("App/dev")
    dev.type = tarfile.CHRTYPE
    with pytest.raises(ValueError):
        update._safe_extract(_tar(tmp_path, [(dev, None)]), str(out))
    esc = tarfile.TarInfo("../escape.txt")
    esc.size = 1
    with pytest.raises(ValueError):
        update._safe_extract(_tar(tmp_path, [(esc, b"x")]), str(out))
    assert not (tmp_path / "escape.txt").exists()


def test_downloads_start_on_github_only(monkeypatch):
    monkeypatch.delenv("QSK_UPDATE_FEED", raising=False)
    for url in ("https://evil.example/x.tar.gz", "https://github.com.evil.example/x", "https://127.0.0.1/x"):
        with pytest.raises(ValueError):
            update._check_host(url)
    for url in ("https://api.github.com/repos/a/b/releases/latest", "https://github.com/a/b/releases/download/v1/x.zip",
                "https://objects.githubusercontent.com/x"):
        update._check_host(url)
    monkeypatch.setenv("QSK_UPDATE_FEED", "https://mirror.example/feed")       # tests and mirrors of your own
    update._check_host("https://mirror.example/x")


# ── F6: names that go into a GitHub address ────────────────────────────────────────

@pytest.mark.parametrize("name,qxf,ok", [("Eurolite", False, True), ("Showtec & Co.", False, True), ("..", False, False),
                                         (".", False, False), ("a/../b", False, False), ("a\n", False, False),
                                         ("x%2f", False, False), ("Spot-4.qxf", True, True), ("Spot.txt", True, False),
                                         ("../Spot.qxf", True, False), ("", False, False)])
def test_github_path_components(name, qxf, ok):
    assert gh_fetch.valid_component(name, qxf=qxf) is ok


def test_routes_refuse_a_dotdot_manufacturer(client):
    assert client.get("/api/quickstart/gh/fixtures?manufacturer=..").status_code == 400
    r = client.post("/api/quickstart/gh/load", json={"manufacturer": "..", "filename": "x.qxf"})
    assert r.status_code == 400
    r = client.post("/api/cabling/fixture-item", json={"gh_manufacturer": "..", "filename": "x.qxf"})
    assert r.status_code == 400


# ── F7: XML with entities ──────────────────────────────────────────────────────────

BOMB = ('<?xml version="1.0"?>\n<!DOCTYPE Workspace [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>\n'
        '<Workspace xmlns="http://www.qlcplus.org/Workspace"><Creator><Name>&b;</Name></Creator></Workspace>')


def test_a_workspace_with_entities_is_refused(tmp_path):
    from core import qxw_io
    p = tmp_path / "bomb.qxw"
    p.write_text(BOMB)
    with pytest.raises(ValueError):
        qxw_io.load_qxw(str(p))
    with pytest.raises(ValueError):
        qxw_io.loads_qxw(BOMB.encode())


def test_real_shows_still_load():
    from core import qxw_io
    for n in ("Pub_6fix.qxw", "Festival_14fix.qxw", "Wizard530_small.qxw"):
        assert qxw_io.load_qxw(os.path.join(CORPUS, n)).getroot() is not None


def test_a_definition_with_entities_is_refused(tmp_path):
    p = tmp_path / "x.qxf"
    p.write_text(BOMB)
    with pytest.raises(xml_safe.UnsafeXML):
        xml_safe.parse(str(p), xml_safe.MAX_DEFINITION_BYTES)
    assert issubclass(xml_safe.UnsafeXML, ValueError)


# ── F11: the AppleScript text of the file dialogs ──────────────────────────────────

def _read_applescript_literal(lit: str):
    """The string an AppleScript literal means, and whether the literal ends where the text ends."""
    assert lit[0] == '"'
    out, i = [], 1
    while i < len(lit):
        c = lit[i]
        if c == "\\" and i + 1 < len(lit):
            out.append(lit[i + 1])
            i += 2
            continue
        if c == '"':
            return "".join(out), i == len(lit) - 1
        out.append(c)
        i += 1
    return "".join(out), False


@pytest.mark.parametrize("text", ['plain', 'say "hi"', 'ends with a backslash\\', 'quote after backslash \\" & (do shell script "id") & "',
                                  'a\\\\"b', "two\nlines", ""])
def test_applescript_literal_cannot_be_closed_early(text):
    from routes.native_picker_routes import _as_str
    value, closed_at_end = _read_applescript_literal(_as_str(text))
    assert closed_at_end
    assert value == text.replace("\r", " ").replace("\n", " ")
