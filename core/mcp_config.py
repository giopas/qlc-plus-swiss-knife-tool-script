"""core/mcp_config.py — which folders Claude may touch through the MCP server.

The list lives in ``~/.qlc_swiss_knife/mcp.json`` (``{"folders": [...]}``).
For tests and one-off runs, ``QSK_MCP_FOLDERS`` (folders separated by the OS
path separator) is added to it, and ``--folder`` on the command line too.

Nothing outside those folders is read or written: every path Claude names is
checked here first (symbolic links are resolved).  Saving never overwrites:
:func:`new_file_path` returns the next free name.
"""

from __future__ import annotations

import json
import os
from typing import Iterable, List, Optional

from core import qxw_io


class NotAllowed(Exception):
    """A path outside the folders the user listed."""


def config_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".qlc_swiss_knife", "mcp.json")


def _norm(p: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.expanduser(str(p))))


def load_folders() -> List[str]:
    try:
        with open(config_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        return [str(f) for f in (data.get("folders") or []) if str(f).strip()]
    except (OSError, ValueError, AttributeError):
        return []


def save_folders(folders: Iterable[str]) -> List[str]:
    clean: List[str] = []
    for f in folders:
        f = str(f).strip()
        if f and os.path.isdir(os.path.expanduser(f)) and f not in clean:
            clean.append(os.path.abspath(os.path.expanduser(f)))
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"folders": clean}, fh, indent=2)
    return clean


def env_folders() -> List[str]:
    raw = os.environ.get("QSK_MCP_FOLDERS", "")
    return [f for f in raw.split(os.pathsep) if f.strip()]


class Allowlist:
    def __init__(self, extra: Optional[Iterable[str]] = None):
        self.extra = [str(f) for f in (extra or [])]

    def folders(self) -> List[str]:
        out: List[str] = []
        for f in load_folders() + env_folders() + self.extra:
            if f not in out:
                out.append(f)
        return out

    def check(self, path: str) -> str:
        """The absolute path, if it is inside a listed folder; else NotAllowed."""
        if not str(path or "").strip():
            raise NotAllowed("No path given.")
        real = _norm(path)
        folders = self.folders()
        for f in folders:
            base = _norm(f)
            if real == base or real.startswith(base.rstrip(os.sep) + os.sep):
                return os.path.abspath(os.path.expanduser(str(path)))
        if not folders:
            raise NotAllowed("No folder is shared with Claude yet. In Swiss Knife open "
                             "Settings › Connect to Claude and add the folder with your shows.")
        raise NotAllowed("That file is outside the folders shared with Claude: "
                         + ", ".join(folders))

    def new_file_path(self, folder_or_name: str, source_name: str = "") -> str:
        """A free ``.qxw`` path inside an allowed folder (never an existing file)."""
        p = self.check(folder_or_name)
        if os.path.isdir(p):
            base = source_name or "Show.qxw"
            p = qxw_io.next_version_path(os.path.join(p, base))
        else:
            if not p.lower().endswith(".qxw"):
                raise NotAllowed("The new file must end in .qxw.")
            if os.path.exists(p):
                p = qxw_io.next_version_path(p)
        self.check(p)
        return p

    def list_shows(self, limit: int = 200) -> List[dict]:
        out = []
        for f in self.folders():
            for root, dirs, files in os.walk(os.path.expanduser(f)):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for n in sorted(files):
                    if n.lower().endswith(".qxw"):
                        full = os.path.join(root, n)
                        try:
                            st = os.stat(full)
                        except OSError:
                            continue
                        out.append({"path": full, "name": n, "bytes": st.st_size,
                                    "modified": int(st.st_mtime)})
                if len(out) >= limit:
                    break
        out.sort(key=lambda r: -r["modified"])
        return out[:limit]
