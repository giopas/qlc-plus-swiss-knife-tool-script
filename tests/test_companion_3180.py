"""Swiss Knife's side of QLC+ Stage Monitor (3.18.0): finding the companion
app, starting it on the exported folder, the routes and Claude's tool."""
import os
import shutil
import sys

import pytest

from core import companion
from core import mcp_server

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")


def _exe(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("#!/bin/sh\n")
    os.chmod(path, 0o755)
    return path


@pytest.fixture
def packaged(monkeypatch):
    """Swiss Knife as a packaged app: the sources' stage_app is not used."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("QLC_STAGE_MONITOR", raising=False)


def test_from_the_sources_the_same_repository_is_used(monkeypatch):
    monkeypatch.delenv("QLC_STAGE_MONITOR", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    f = companion.find()
    assert f == {"installed": True, "how": "source", "path": os.path.join(companion.ROOT, "stage_app")}
    assert companion.command(f, "/x")[1:] == ["-m", "stage_app", "--folder", "/x"]


def test_windows_per_user_install(tmp_path, packaged, monkeypatch):
    exe = _exe(str(tmp_path / "Programs" / "QLC Stage Monitor" / "QLC Stage Monitor.exe"))
    monkeypatch.setattr(companion, "_own_dir", lambda: str(tmp_path / "elsewhere"))
    f = companion.find("Windows", {"LOCALAPPDATA": str(tmp_path)})
    assert f == {"installed": True, "how": "app", "path": exe}
    assert companion.command(f, "C:/gig/stage_monitor", "Windows") == [exe, "--folder", "C:/gig/stage_monitor"]


def test_macos_app_next_to_swiss_knife(tmp_path, packaged, monkeypatch):
    app = tmp_path / "QLC Stage Monitor.app"
    app.mkdir()
    monkeypatch.setattr(companion, "_own_dir", lambda: str(tmp_path))
    f = companion.find("Darwin", {})
    assert f["path"] == str(app)
    # -n: a second start hands the folder to the open window
    assert companion.command(f, "/gig", "Darwin") == ["open", "-n", "-a", str(app), "--args", "--folder", "/gig"]


def test_linux_and_not_installed(tmp_path, packaged, monkeypatch):
    monkeypatch.setattr(companion, "_own_dir", lambda: str(tmp_path))
    monkeypatch.setattr(companion.shutil, "which", lambda n: None)
    monkeypatch.setattr(companion.os.path, "expanduser", lambda p: str(tmp_path / "home"))
    assert companion.find("Linux", {})["installed"] is False
    exe = _exe(str(tmp_path / "QLC-Stage-Monitor" / "QLC-Stage-Monitor"))
    assert companion.find("Linux", {})["path"] == exe


def test_the_environment_wins(tmp_path, packaged):
    exe = _exe(str(tmp_path / "sm"))
    assert companion.find("Linux", {"QLC_STAGE_MONITOR": exe}) == {"installed": True, "how": "env", "path": exe}


def test_launch_needs_an_exported_page(tmp_path):
    with pytest.raises(ValueError):
        companion.launch(str(tmp_path))
    (tmp_path / "index.html").write_text("x")
    calls = []
    r = companion.launch(str(tmp_path), popen=lambda cmd, **kw: calls.append((cmd, kw)))
    assert r["launched"] and calls and calls[0][0][-2:] == ["--folder", str(tmp_path)]
    assert calls[0][1]["stdin"] is not None


def test_launch_when_not_installed(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("x")
    monkeypatch.setattr(companion, "find", lambda *a, **k: {"installed": False, "how": "", "path": ""})
    with pytest.raises(LookupError):
        companion.launch(str(tmp_path), popen=lambda *a, **k: None)


# ── the routes ───────────────────────────────────────────────────────────────

def _client(tmp_path):
    import app
    p = tmp_path / "Pub_6fix.qxw"
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), p)
    c = app.create_app().test_client()
    assert c.post("/api/load", json={"path": str(p)}).status_code == 200
    return c


def test_routes(tmp_path, monkeypatch):
    c = _client(tmp_path)
    d = c.get("/api/stagemon/lists").get_json()
    assert d["companion"]["installed"] in (True, False) and d["companion"]["download"].startswith("https://github.com/")
    assert "companion" in c.get("/api/stagemon/status").get_json()
    r = c.post("/api/stagemon/companion", json={"folder": str(tmp_path / "nothing")})
    assert r.status_code == 400
    assert c.post("/api/stagemon/export", json={"config": d["config"]}).status_code == 200
    calls = []
    monkeypatch.setattr(companion, "launch", lambda folder, **k: calls.append(folder) or
                        {"launched": True, "how": "app", "folder": folder})
    r = c.post("/api/stagemon/companion", json={})
    assert r.status_code == 200 and calls == [str(tmp_path / "stage_monitor")]

    def missing(folder, **k):
        raise LookupError
    monkeypatch.setattr(companion, "launch", missing)
    r = c.post("/api/stagemon/companion", json={})
    assert r.status_code == 404 and r.get_json()["installed"] is False
    assert c.post("/api/stagemon/get-companion").get_json()["url"] == companion.DOWNLOAD_URL


def test_launching_frees_the_port_of_swiss_knifes_own_server(tmp_path, monkeypatch):
    from core import stage_monitor as sm
    c = _client(tmp_path)
    cfg = c.get("/api/stagemon/lists").get_json()["config"]
    cfg["http_port"] = 0
    c.post("/api/stagemon/export", json={"config": cfg})
    folder = str(tmp_path / "stage_monitor")
    sm.server.start(folder, 0)
    try:
        monkeypatch.setattr(companion, "launch", lambda f, **k: {"launched": True, "how": "app", "folder": f})
        r = c.post("/api/stagemon/companion", json={"folder": folder}).get_json()
        assert r["server"]["running"] is False
    finally:
        sm.server.stop()


# ── Claude's tool ────────────────────────────────────────────────────────────

def test_the_tool_knows_open_app():
    tool = next(t for t in mcp_server.TOOLS if t["name"] == "stage_monitor")
    assert "open_app" in tool["inputSchema"]["properties"]
    assert "QLC+ Stage Monitor" in tool["description"]
