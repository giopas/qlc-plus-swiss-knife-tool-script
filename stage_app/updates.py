"""stage_app/updates.py: QLC+ Stage Monitor updates itself (3.18.0).

It uses Swiss Knife's own updater (``core.update``: the GitHub release,
SHA-256 checked against ``SHA256SUMS``, unpacked next to the app and swapped
after the app quits), set up for this app: it looks only for the
``QLC-Stage-Monitor-…`` downloads and keeps its own settings and cache in this
app's folder, so Swiss Knife and its companion never update each other.

One request to GitHub at start (cached 12 hours), nothing about you or your
shows; *Check for updates* in the window switches it off.
"""

from __future__ import annotations

import os
import threading
import webbrowser
from typing import Optional

from core import update

from stage_app import APP_NAME, settings

PREFIX = "QLC-Stage-Monitor"
RELEASES = "https://github.com/" + update.REPO + "/releases/latest"


def configure() -> None:
    """Point the updater at this app.  Called once, at the start of the app's own process."""
    update.configure(PREFIX, APP_NAME, os.path.join(settings.config_dir(), "update.json"))


class Updater:
    """The window's view of the updater (a fake one in the tests)."""

    def __init__(self, mod=update):
        self.mod = mod
        self.info: Optional[dict] = None
        self._lock = threading.Lock()

    def check(self, force: bool = False) -> dict:
        info = self.mod.check(force=force)
        with self._lock:
            self.info = info
        return info

    def check_soon(self) -> None:
        """The check at start, in the background (offline at the venue is normal)."""
        threading.Thread(target=self.check, name="stage-app-update", daemon=True).start()

    def status(self) -> dict:
        with self._lock:
            info = self.info
        return info or self.mod.status()

    def set_enabled(self, on: bool) -> dict:
        self.mod.set_enabled(bool(on))
        with self._lock:
            self.info = None
        return self.check(force=True) if on else self.status()

    def install(self) -> dict:
        info = self.status()
        return self.mod.install(info if info.get("newer") else None)

    @staticmethod
    def open_releases() -> bool:
        try:
            return bool(webbrowser.open(RELEASES))
        except Exception:  # noqa: BLE001
            return False
