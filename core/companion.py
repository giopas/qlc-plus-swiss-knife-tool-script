"""core/companion.py — find and start QLC+ Stage Monitor (3.18.0).

QLC+ Stage Monitor is Swiss Knife's companion app (``stage_app/`` in this
repository, its own download).  At the gig it serves the page the Stage
Monitor exported, says whether QLC+ is ready, shows the address with a QR
code and prints the setlist.  Swiss Knife never imports it: it only looks for
the installed app and starts it with ``--folder <exported folder>``.

Where it looks, in order:

1. ``$QLC_STAGE_MONITOR``: a path to the app (``.app``, ``.exe`` or program);
2. Swiss Knife run from the sources: ``python -m stage_app`` from this same
   repository, so the two always match;
3. the app installed next to Swiss Knife or in the usual place of the system
   (``/Applications``, ``%LOCALAPPDATA%\\Programs``, ``~/.local/share``…).

Standard library only.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess  # nosec B404 — fixed program, no shell
import sys
from typing import List, Optional

NAME = "QLC Stage Monitor"            # the files; the window says "QLC+ Stage Monitor"
LINUX_NAME = "QLC-Stage-Monitor"
DOWNLOAD_URL = "https://github.com/giopas/qlc-plus-swiss-knife-tool-script/releases/latest"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _own_dir() -> str:
    """The folder Swiss Knife runs from (the .app's parent on macOS)."""
    exe = os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
    parts = exe.split(os.sep)
    for i, p in enumerate(parts):
        if p.endswith(".app"):
            return os.sep.join(parts[:i]) or os.sep
    return os.path.dirname(os.path.dirname(exe))


def candidates(system: Optional[str] = None, env: Optional[dict] = None) -> List[str]:
    """Paths where an installed QLC+ Stage Monitor can be, most likely first."""
    system = system or platform.system()
    env = os.environ if env is None else env
    home = os.path.expanduser("~")
    own = _own_dir()
    if system == "Darwin":
        return [os.path.join(own, f"{NAME}.app"), os.path.join("/Applications", f"{NAME}.app"),
                os.path.join(home, "Applications", f"{NAME}.app")]
    if system == "Windows":
        out = [os.path.join(own, NAME, f"{NAME}.exe")]
        for var in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            base = env.get(var)
            if base:
                out.append(os.path.join(base, "Programs", NAME, f"{NAME}.exe") if var == "LOCALAPPDATA"
                           else os.path.join(base, NAME, f"{NAME}.exe"))
        return out
    out = [os.path.join(own, LINUX_NAME, LINUX_NAME),
           os.path.join(home, ".local", "share", LINUX_NAME, LINUX_NAME),
           os.path.join("/opt", LINUX_NAME, LINUX_NAME)]
    found = shutil.which("qlc-stage-monitor")
    if found:
        out.insert(0, found)
    return out


def _usable(path: str, system: str) -> bool:
    if system == "Darwin" and path.endswith(".app"):
        return os.path.isdir(path)
    return os.path.isfile(path) and (system == "Windows" or os.access(path, os.X_OK))


def find(system: Optional[str] = None, env: Optional[dict] = None) -> dict:
    """``{installed, how, path}``: ``how`` is ``env``, ``app`` or ``source`` (``installed`` False: none)."""
    system = system or platform.system()
    env = os.environ if env is None else env
    own = env.get("QLC_STAGE_MONITOR")
    if own and (_usable(own, system) or (own.endswith(".app") and os.path.isdir(own))):
        return {"installed": True, "how": "env", "path": own}
    if not getattr(sys, "frozen", False) and os.path.isfile(os.path.join(ROOT, "stage_app", "app.py")):
        return {"installed": True, "how": "source", "path": os.path.join(ROOT, "stage_app")}
    for p in candidates(system, env):
        if _usable(p, system):
            return {"installed": True, "how": "app", "path": p}
    return {"installed": False, "how": "", "path": ""}


def command(found: dict, folder: str, system: Optional[str] = None) -> List[str]:
    """The command that starts the app on *folder*."""
    system = system or platform.system()
    path = found["path"]
    if found["how"] == "source":
        return [sys.executable, "-m", "stage_app", "--folder", folder]
    if system == "Darwin" and path.endswith(".app"):
        # -n: a new process even when the app is open; it hands the folder to the open window and quits
        return ["open", "-n", "-a", path, "--args", "--folder", folder]
    return [path, "--folder", folder]


def status() -> dict:
    """What the Stage Monitor screen shows: installed or not, and where to get it."""
    f = find()
    return {"installed": f["installed"], "how": f["how"], "download": DOWNLOAD_URL,
            "where": os.path.basename(f["path"]) if f["how"] != "source" else "stage_app (sources)"}


def launch(folder: str, popen=subprocess.Popen) -> dict:
    """Start QLC+ Stage Monitor on *folder* (an exported Stage Monitor folder).

    Raises ``ValueError`` when the folder has no page and ``LookupError`` when
    the app is not installed."""
    folder = os.path.abspath(os.path.expanduser(folder))
    if not os.path.isfile(os.path.join(folder, "index.html")):
        raise ValueError("Export the page first: there is no index.html in that folder.")
    f = find()
    if not f["installed"]:
        raise LookupError("QLC+ Stage Monitor is not installed.")
    cmd = command(f, folder)
    kw = {"cwd": ROOT} if f["how"] == "source" else {}
    if platform.system() == "Windows":
        kw["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kw["start_new_session"] = True
    popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)  # nosec B603
    return {"launched": True, "how": f["how"], "folder": folder}
