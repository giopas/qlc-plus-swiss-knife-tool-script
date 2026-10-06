"""core/update.py — the update check and "Update and restart" (v2.8.0).

The only network call Swiss Knife makes on its own (besides the optional
fixture-library fetch): at start, one request to the GitHub Releases API for
the latest release.  It can be switched off (``update.json``, *Settings* on the
Start page) and nothing is sent about you or your shows.

* **Check** — ``check()`` asks for ``/releases/latest``, compares the tag with
  ``VERSION`` and finds the right download for this computer (macOS arm64 /
  x86_64, Windows x64, Linux x64).  The answer is cached for 12 hours.
* **Packaged app** — ``install()`` downloads that file, checks its SHA-256
  against the release's ``SHA256SUMS``, unpacks it next to the install and
  writes a small helper script that waits for Swiss Knife to quit, swaps the
  folder (or the ``.app``) and starts it again.
* **Run from sources** — the badge only says what to do (``git pull``).

Everything the user keeps lives in ``~/.qlc_swiss_knife/`` and is never part of
an update.  ``QSK_UPDATE_FEED`` (a URL or a JSON file path) replaces the GitHub
API — used by the tests.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import platform
import posixpath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import ssl
import tempfile
import time
import urllib.request
import zipfile
from typing import Dict, List, Optional, Tuple

from core.workspace import VERSION

REPO = "giopas/qlc-plus-swiss-knife-tool-script"
FEED = f"https://api.github.com/repos/{REPO}/releases/latest"
CACHE_HOURS = 12
TIMEOUT = 5
MAX_DOWNLOAD = 400 * 1024 * 1024
_ASSET_RE = re.compile(r"^QLC-Swiss-Knife-(?P<ver>\d+\.\d+\.\d+)-(?P<os>macos|windows|linux)-(?P<arch>arm64|x86_64|x64)\.(?P<ext>zip|tar\.gz|dmg)$")


# ─────────────────────────────────────────────────────────────────────────────
# settings + cache
# ─────────────────────────────────────────────────────────────────────────────

def _file() -> str:
    return os.environ.get("QSK_UPDATE") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "update.json")


def _load() -> dict:
    try:
        with open(_file(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    p = _file()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    except OSError:
        pass                                  # a cache; never a reason to fail


def enabled() -> bool:
    return bool(_load().get("check", True))


def set_enabled(on: bool) -> None:
    d = _load()
    d["check"] = bool(on)
    _save(d)


# ─────────────────────────────────────────────────────────────────────────────
# versions and assets
# ─────────────────────────────────────────────────────────────────────────────

def parse_version(s: str) -> Tuple[int, ...]:
    """'v2.8.0' → (2, 8, 0); anything unreadable → ()."""
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", str(s or "").strip())
    return tuple(int(x) for x in m.groups()) if m else ()


def is_newer(latest: str, current: str = VERSION) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return bool(a) and bool(b) and a > b


def platform_key() -> Tuple[str, str]:
    """(os, arch) as used in the asset names."""
    sysname = platform.system()
    mach = platform.machine().lower()
    if sysname == "Darwin":
        return "macos", "arm64" if mach in ("arm64", "aarch64") else "x86_64"
    if sysname == "Windows":
        return "windows", "x64"
    return "linux", "x64"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_root() -> Optional[str]:
    """What an update replaces: the folder of the packaged app, or the ``.app``
    on macOS.  ``None`` when running from sources."""
    if not is_frozen():
        return None
    exe = os.path.abspath(sys.executable)
    if platform.system() == "Darwin":
        d = exe
        while d and d != os.path.dirname(d):
            if d.endswith(".app"):
                return d
            d = os.path.dirname(d)
    return os.path.dirname(exe)


def pick_asset(assets: List[dict], os_name: str = None, arch: str = None) -> Optional[dict]:
    """The download for this computer: its own .zip / .tar.gz (the updater
    uses archives; a .dmg is only for the first install)."""
    os_name, arch = (os_name, arch) if os_name else platform_key()
    best = None
    for a in assets or []:
        m = _ASSET_RE.match(str(a.get("name", "")))
        if not m or m["os"] != os_name or m["arch"] != arch or m["ext"] == "dmg":
            continue
        best = a
    return best


_CA_FILES = ("/etc/ssl/cert.pem",                      # macOS (and some Linux)
             "/etc/ssl/certs/ca-certificates.crt",     # Debian / Ubuntu
             "/etc/pki/tls/certs/ca-bundle.crt")       # Fedora / RHEL


def _ssl_context() -> ssl.SSLContext:
    """A bundled (PyInstaller) Python often has no list of trusted certificates and then cannot
    open any https:// address: use certifi's list, else the system's file, else the default."""
    cafile = None
    try:
        import certifi
        cafile = certifi.where()
    except Exception:  # noqa: BLE001
        for p in _CA_FILES:
            if os.path.isfile(p):
                cafile = p
                break
    if cafile and os.path.isfile(cafile):
        try:
            return ssl.create_default_context(cafile=cafile)
        except Exception:  # noqa: BLE001
            pass
    return ssl.create_default_context()


def _read(url: str, limit: int = 2_000_000) -> bytes:
    if os.path.isfile(url):
        with open(url, "rb") as f:
            return f.read(limit)
    if not url.startswith("https://"):
        raise ValueError("only https:// or a local file")
    req = urllib.request.Request(url, headers={"User-Agent": f"QLC-Swiss-Knife/{VERSION}",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context()) as r:
        return r.read(limit)


def _feed_url() -> str:
    return os.environ.get("QSK_UPDATE_FEED") or FEED


# ─────────────────────────────────────────────────────────────────────────────
# check
# ─────────────────────────────────────────────────────────────────────────────

def _summary(rel: dict) -> dict:
    tag = str(rel.get("tag_name") or "")
    asset = pick_asset(rel.get("assets") or [])
    sums = next((a for a in rel.get("assets") or [] if a.get("name") == "SHA256SUMS"), None)
    return {
        "latest": tag.lstrip("v"),
        "tag": tag,
        "newer": is_newer(tag),
        "url": rel.get("html_url") or f"https://github.com/{REPO}/releases/latest",
        "notes": str(rel.get("body") or "")[:4000],
        "asset": ({"name": asset.get("name"), "url": asset.get("browser_download_url"),
                   "size": asset.get("size")} if asset else None),
        "sums_url": sums.get("browser_download_url") if sums else None,
    }


def status(result: Optional[dict] = None, error: str = "") -> dict:
    """What the page needs: the check result plus how this copy runs."""
    d = {
        "current": VERSION,
        "enabled": enabled(),
        "frozen": is_frozen(),
        "can_install": bool(is_frozen() and install_root()),
        "platform": "-".join(platform_key()),
        "error": error,
    }
    if result:
        d.update(result)
    return d


def check(force: bool = False, now: float = None) -> dict:
    """Ask GitHub (or use the answer from the last 12 hours)."""
    now = time.time() if now is None else now
    st = _load()
    if not force:
        if not st.get("check", True):
            return status(error="")
        c = st.get("cache")
        if c and now - float(c.get("at", 0)) < CACHE_HOURS * 3600 and c.get("for") == VERSION:
            return status(c.get("result"))
    try:
        rel = json.loads(_read(_feed_url()).decode("utf-8"))
        if not isinstance(rel, dict):
            raise ValueError("unexpected answer")
        res = _summary(rel)
    except Exception as e:  # noqa: BLE001 — offline at the venue is normal
        return status(error=f"Could not check for updates ({type(e).__name__}).")
    st["cache"] = {"at": now, "for": VERSION, "result": res}
    _save(st)
    return status(res)


# ─────────────────────────────────────────────────────────────────────────────
# install: download, verify, unpack, swap on exit
# ─────────────────────────────────────────────────────────────────────────────

def parse_sums(text: str) -> Dict[str, str]:
    """``sha256sum`` output → {file name: hex}."""
    out = {}
    for line in str(text).splitlines():
        m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$", line)
        if m:
            out[os.path.basename(m.group(2))] = m.group(1).lower()
    return out


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: str) -> None:
    if os.path.isfile(url):
        shutil.copyfile(url, dest)
        return
    if not url.startswith("https://"):
        raise ValueError("only https:// downloads")
    req = urllib.request.Request(url, headers={"User-Agent": f"QLC-Swiss-Knife/{VERSION}"})
    got = 0
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            got += len(chunk)
            if got > MAX_DOWNLOAD:
                raise ValueError("download too large")
            f.write(chunk)


def _safe_extract(archive: str, dest: str) -> None:
    """Unpack, refusing paths that leave ``dest``."""
    dest_real = os.path.realpath(dest)

    def ok(name: str) -> bool:
        p = os.path.realpath(os.path.join(dest, name))
        return p == dest_real or p.startswith(dest_real + os.sep)

    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            bad = [n for n in z.namelist() if not ok(n)]
            if bad:
                raise ValueError(f"unsafe path in the archive: {bad[0]}")
            for info in z.infolist():
                mode = info.external_attr >> 16
                target = os.path.join(dest, info.filename)
                if mode and stat.S_ISLNK(mode):       # a .app is full of symlinks
                    link = z.read(info).decode("utf-8")
                    if not ok(os.path.join(os.path.dirname(info.filename), link)):
                        raise ValueError(f"unsafe link in the archive: {info.filename}")
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    if os.path.lexists(target):
                        os.remove(target)
                    os.symlink(link, target)
                    continue
                z.extract(info, dest)
                if mode and stat.S_ISREG(mode):       # keep the executable bit
                    os.chmod(target, mode & 0o7777)
    else:
        with tarfile.open(archive) as t:
            bad = [m.name for m in t.getmembers() if not ok(m.name) or m.islnk() and not ok(m.linkname)]
            if bad:
                raise ValueError(f"unsafe path in the archive: {bad[0]}")
            t.extractall(dest)


def _payload(unpacked: str) -> str:
    """The folder (or .app) inside the unpacked archive."""
    items = [i for i in os.listdir(unpacked) if not i.startswith(".")]
    if len(items) == 1:
        return os.path.join(unpacked, items[0])
    return unpacked


def helper_script(pid: int, old: str, new: str, system: str = None, exe: str = None) -> Tuple[str, str]:
    """(file name, text) of the script that swaps the install after we quit.
    Kept the old version as ``<name>.old`` until the new one has started."""
    system = system or platform.system()
    pth = ntpath if system == "Windows" else posixpath
    if system == "Windows":
        text = (
            "@echo off\r\n"
            f"set PID={pid}\r\n"
            ":wait\r\n"
            'tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL\r\n'
            "if not errorlevel 1 (timeout /t 1 /nobreak >NUL & goto wait)\r\n"
            f'if exist "{old}.old" rmdir /s /q "{old}.old"\r\n'
            f'move /y "{old}" "{old}.old" >NUL\r\n'
            f'move /y "{new}" "{old}" >NUL\r\n'
            f'start "" "{pth.join(old, pth.basename(exe or "QLC Swiss Knife.exe"))}"\r\n'
        )
        return "swk-update.bat", text
    q = lambda s: "'" + str(s).replace("'", "'\\''") + "'"       # noqa: E731
    start = f"open {q(old)}" if system == "Darwin" else q(pth.join(old, pth.basename(exe or "QLC-Swiss-Knife")))
    clear = (f"xattr -dr com.apple.quarantine {q(old)} 2>/dev/null\n" if system == "Darwin" else "")
    text = (
        "#!/bin/sh\n"
        f"while kill -0 {int(pid)} 2>/dev/null; do sleep 1; done\n"
        f"rm -rf {q(old + '.old')}\n"
        f"mv {q(old)} {q(old + '.old')} || exit 1\n"
        f"if mv {q(new)} {q(old)}; then\n"
        f"  {clear}  {start} &\n"
        "else\n"
        f"  mv {q(old + '.old')} {q(old)}\n"
        "fi\n"
    )
    return "swk-update.sh", text


def keep_uninstaller(old: str, new: str) -> None:
    """The Windows installer puts ``unins000.exe/.dat`` in the app folder; the swap
    replaces the folder, so carry them over (Apps & features keeps working)."""
    try:
        for n in os.listdir(old):
            if n.lower().startswith("unins") and os.path.isfile(os.path.join(old, n)):
                shutil.copy2(os.path.join(old, n), os.path.join(new, n))
    except OSError:
        pass


def cleanup_after_update() -> None:
    """At start of a packaged app: remove the previous version (``<name>.old``)
    and the leftovers of the swap.  Never raises."""
    root = install_root()
    if not root:
        return
    try:
        shutil.rmtree(root + ".old", ignore_errors=True)
        parent = os.path.dirname(root)
        for n in os.listdir(parent):
            if n.startswith("swk-update-") and os.path.isdir(os.path.join(parent, n)):
                shutil.rmtree(os.path.join(parent, n), ignore_errors=True)
    except OSError:
        pass


def install(info: dict = None) -> dict:
    """Download the newer version for this computer, verify it, unpack it and
    arrange the swap.  Returns ``{'ok', 'message', 'restart'}``; the caller
    quits the app when ``restart`` is true."""
    info = info or check(force=True)
    if not info.get("newer"):
        return {"ok": False, "message": "You already have the latest version."}
    root = install_root()
    if not root:
        return {"ok": False, "message": "Running from sources — update with: git pull "
                                        "(or download the new release)."}
    asset, sums_url = info.get("asset"), info.get("sums_url")
    if not asset or not asset.get("url"):
        return {"ok": False, "message": "This release has no download for this computer."}
    if not sums_url:
        return {"ok": False, "message": "This release has no SHA256SUMS file — not installing it."}
    work = tempfile.mkdtemp(prefix="swk-update-", dir=os.path.dirname(root) if os.access(os.path.dirname(root), os.W_OK) else None)
    try:
        sums = parse_sums(_read(sums_url).decode("utf-8", "replace"))
        want = sums.get(asset["name"])
        if not want:
            raise ValueError("the file is not listed in SHA256SUMS")
        arc = os.path.join(work, asset["name"])
        _download(asset["url"], arc)
        got = sha256_of(arc)
        if got != want:
            raise ValueError("the download does not match its SHA-256 — not installing it")
        unpacked = os.path.join(work, "unpacked")
        os.makedirs(unpacked)
        _safe_extract(arc, unpacked)
        new = os.path.join(work, "new")
        shutil.move(_payload(unpacked), new)
        keep_uninstaller(root, new)
        name, text = helper_script(os.getpid(), root, new, exe=os.path.basename(sys.executable))
        script = os.path.join(work, name)
        with open(script, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.chmod(script, 0o755)
        if platform.system() == "Windows":
            subprocess.Popen(["cmd", "/c", script], creationflags=0x00000008, close_fds=True)   # DETACHED_PROCESS
        else:
            subprocess.Popen(["/bin/sh", script], start_new_session=True, close_fds=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "restart": True,
                "message": f"Version {info.get('latest')} is ready — Swiss Knife quits and starts again."}
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(work, ignore_errors=True)
        return {"ok": False, "message": f"Could not update: {e}"}
