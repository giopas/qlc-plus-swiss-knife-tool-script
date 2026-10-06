"""v2.8.0 — update check, verified download, swap script, packaging files."""
import hashlib
import io
import json
import os
import tarfile
import zipfile

import pytest

import app as appmod
from core import update
from core.workspace import VERSION

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _iso(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_UPDATE", str(tmp_path / "update.json"))
    monkeypatch.delenv("QSK_UPDATE_FEED", raising=False)


def _feed(tmp_path, tag="v99.0.0", assets=None):
    f = tmp_path / "feed.json"
    f.write_text(json.dumps({"tag_name": tag, "html_url": "https://github.com/x/y/releases/tag/" + tag,
                             "body": "notes", "assets": assets or []}))
    return str(f)


def test_versions():
    assert update.parse_version("v2.8.0") == (2, 8, 0)
    assert update.parse_version("garbage") == ()
    assert update.is_newer("v2.10.0", "2.9.0") and not update.is_newer("2.7.0", "2.7.0")
    assert not update.is_newer("nonsense", "2.7.0")


def test_pick_asset_by_platform():
    a = [{"name": f"QLC-Swiss-Knife-2.8.0-{o}-{r}.{e}"} for o, r, e in
         (("macos", "arm64", "zip"), ("macos", "arm64", "dmg"), ("macos", "x86_64", "zip"),
          ("windows", "x64", "zip"), ("linux", "x64", "tar.gz"))] + [{"name": "SHA256SUMS"}]
    assert update.pick_asset(a, "macos", "arm64")["name"].endswith("arm64.zip")      # not the .dmg
    assert update.pick_asset(a, "macos", "x86_64")["name"].endswith("x86_64.zip")
    assert update.pick_asset(a, "windows", "x64")["name"].endswith("windows-x64.zip")
    assert update.pick_asset(a, "linux", "x64")["name"].endswith(".tar.gz")
    assert update.pick_asset(a, "linux", "arm64") is None


def test_check_newer_and_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_UPDATE_FEED", _feed(tmp_path))
    r = update.check()
    assert r["newer"] and r["latest"] == "99.0.0" and r["current"] == VERSION and not r["frozen"]
    # cached: a feed that no longer exists is not asked again within 12 h
    monkeypatch.setenv("QSK_UPDATE_FEED", str(tmp_path / "gone.json"))
    assert update.check()["latest"] == "99.0.0"
    assert update.check(force=True)["error"]


def test_same_version_is_not_newer(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_UPDATE_FEED", _feed(tmp_path, "v" + VERSION))
    assert update.check()["newer"] is False


def test_off_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_UPDATE_FEED", _feed(tmp_path))
    update.set_enabled(False)
    r = update.check()
    assert not r["enabled"] and "newer" not in r
    update.set_enabled(True)
    assert update.check()["newer"]


def test_offline_is_calm(monkeypatch):
    monkeypatch.setenv("QSK_UPDATE_FEED", "/no/such/file.json")
    r = update.check()
    assert r["error"] and not r.get("newer")


def test_parse_sums():
    h = "a" * 64
    assert update.parse_sums(f"{h}  QLC-Swiss-Knife-1.zip\n{h.upper()} *dir/x.tar.gz\njunk") == {
        "QLC-Swiss-Knife-1.zip": h, "x.tar.gz": h}


def _tar(tmp_path, name, files):
    p = tmp_path / name
    with tarfile.open(p, "w:gz") as t:
        for n, data in files.items():
            ti = tarfile.TarInfo(n)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
    return str(p)


def test_safe_extract_refuses_escape(tmp_path):
    z = tmp_path / "bad.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../evil.txt", "x")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError):
        update._safe_extract(str(z), str(out))
    t = _tar(tmp_path, "bad.tar.gz", {"../evil.txt": b"x"})
    with pytest.raises(ValueError):
        update._safe_extract(t, str(out))
    assert not (tmp_path / "evil.txt").exists()


def test_install_verifies_and_stages(tmp_path, monkeypatch):
    """A frozen install: download → SHA-256 → unpack → swap script (not run here)."""
    inst = tmp_path / "apps" / "QLC-Swiss-Knife"
    inst.mkdir(parents=True)
    exe = inst / "QLC-Swiss-Knife"
    exe.write_text("old")
    monkeypatch.setattr(update, "is_frozen", lambda: True)
    monkeypatch.setattr(update.sys, "executable", str(exe))
    monkeypatch.setattr(update.platform, "system", lambda: "Linux")
    monkeypatch.setattr(update, "platform_key", lambda: ("linux", "x64"))
    ran = []
    monkeypatch.setattr(update.subprocess, "Popen", lambda *a, **k: ran.append(a))
    name = "QLC-Swiss-Knife-99.0.0-linux-x64.tar.gz"
    arc = _tar(tmp_path, name, {"QLC-Swiss-Knife/QLC-Swiss-Knife": b"new", "QLC-Swiss-Knife/x.txt": b"1"})
    good = hashlib.sha256(open(arc, "rb").read()).hexdigest()
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{good}  {name}\n")
    feed = _feed(tmp_path, assets=[{"name": name, "browser_download_url": arc, "size": 1},
                                   {"name": "SHA256SUMS", "browser_download_url": str(sums)}])
    monkeypatch.setenv("QSK_UPDATE_FEED", feed)
    r = update.install()
    assert r["ok"] and r["restart"], r
    assert ran and "swk-update.sh" in ran[0][0][-1]
    # a wrong checksum is refused and nothing is started
    ran.clear()
    sums.write_text(f"{'0' * 64}  {name}\n")
    r = update.install(update.check(force=True))
    assert not r["ok"] and "SHA-256" in r["message"] and not ran
    # no checksum file: refused
    feed2 = _feed(tmp_path, assets=[{"name": name, "browser_download_url": arc}])
    monkeypatch.setenv("QSK_UPDATE_FEED", feed2)
    assert not update.install(update.check(force=True))["ok"]


def test_install_from_sources_only_explains(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_UPDATE_FEED", _feed(tmp_path))
    r = update.install()
    assert not r["ok"] and "git pull" in r["message"]


def test_helper_scripts():
    _n, sh = update.helper_script(4242, "/opt/App", "/tmp/new", "Linux", "App")
    assert "kill -0 4242" in sh and "mv '/opt/App' '/opt/App.old'" in sh and "'/opt/App/App' &" in sh
    _n, mac = update.helper_script(7, "/Applications/QLC Swiss Knife.app", "/tmp/n", "Darwin")
    assert "xattr -dr com.apple.quarantine" in mac and "open '/Applications/QLC Swiss Knife.app'" in mac
    n, bat = update.helper_script(9, r"C:\Apps\QSK", r"C:\tmp\new", "Windows", "QLC Swiss Knife.exe")
    assert n.endswith(".bat") and "tasklist" in bat and "QLC Swiss Knife.exe" in bat
    _n, q = update.helper_script(1, "/o'brien/App", "/n", "Linux", "App")
    assert "'/o'\\''brien/App'" in q                                   # quoting survives an apostrophe


def test_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("QSK_UPDATE_FEED", _feed(tmp_path))
    a = appmod.create_app()
    a.config["TESTING"] = True
    c = a.test_client()
    d = c.get("/api/update/check").get_json()
    assert d["newer"] and not d["can_install"]
    assert c.post("/api/update/install").status_code == 400            # from sources
    assert c.post("/api/update/settings", json={"check": False}).get_json()["enabled"] is False
    # only the project's own pages may be opened
    u = c.post("/api/update/open", json={"url": "https://evil.example/"}).get_json()["url"]
    assert u.startswith("https://github.com/giopas/qlc-plus-swiss-knife-tool-script/")


def test_testing_never_reaches_github():
    a = appmod.create_app()
    a.config["TESTING"] = True
    d = a.test_client().get("/api/update/check").get_json()
    assert "latest" not in d


def test_smoke_passes():
    assert appmod._smoke(appmod.create_app()) == 0


def test_packaging_files_are_consistent():
    spec = open(os.path.join(ROOT, "packaging", "swissknife.spec"), encoding="utf-8").read()
    for p in ("templates", "static", "looks", "profiles"):
        assert p in spec
    wf = open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8").read()
    for want in ("macos-14", "macos-13", "windows-latest", "ubuntu-22.04", "SHA256SUMS", "--smoke",
                 "QLC-Swiss-Knife-"):
        assert want in wf
    import importlib.util
    sp = importlib.util.spec_from_file_location("make_archive", os.path.join(ROOT, "packaging", "make_archive.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    for ext, o, a in (("zip", "macos", "arm64"), ("zip", "windows", "x64"), ("tar.gz", "linux", "x64")):
        assert update._ASSET_RE.match(m.asset_name(ext, o, a))
