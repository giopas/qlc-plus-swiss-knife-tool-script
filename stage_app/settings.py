"""stage_app/settings.py: what the app remembers (the last folder, the language)
and how a second start hands its folder to the window already open."""

from __future__ import annotations

import json
import os
import platform
from typing import Optional

LANGS = ("en", "it", "fr", "de", "es", "pt", "ja", "zh")


def config_dir() -> str:
    """This app's own settings folder (never Swiss Knife's)."""
    env = os.environ.get("QLC_STAGE_MONITOR_HOME")
    if env:
        return env
    system = platform.system()
    home = os.path.expanduser("~")
    if system == "Darwin":
        return os.path.join(home, "Library", "Application Support", "QLC Stage Monitor")
    if system == "Windows":
        return os.path.join(os.environ.get("APPDATA") or home, "QLC Stage Monitor")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config"), "qlc-stage-monitor")


def _path(name: str) -> str:
    return os.path.join(config_dir(), name)


def _load(name: str) -> dict:
    try:
        with open(_path(name), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(name: str, data: dict) -> None:
    try:
        os.makedirs(config_dir(), exist_ok=True)
        tmp = _path(name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, _path(name))
    except OSError:
        pass                                  # remembering is a convenience, never a reason to stop


def load() -> dict:
    d = _load("settings.json")
    lang = d.get("lang") if d.get("lang") in LANGS else ""
    return {"folder": str(d.get("folder") or ""), "lang": lang}


def save(**kw) -> None:
    d = load()
    d.update({k: v for k, v in kw.items() if k in ("folder", "lang")})
    _save("settings.json", d)


def write_instance(port: int, token: str) -> None:
    _save("instance.json", {"port": int(port), "token": token, "pid": os.getpid()})


def read_instance() -> Optional[dict]:
    d = _load("instance.json")
    try:
        return {"port": int(d["port"]), "token": str(d["token"])}
    except (KeyError, TypeError, ValueError):
        return None


def clear_instance(token: str) -> None:
    d = _load("instance.json")
    if d.get("token") == token:
        try:
            os.remove(_path("instance.json"))
        except OSError:
            pass
