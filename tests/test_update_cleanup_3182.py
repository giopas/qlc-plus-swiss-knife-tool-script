"""3.18.2: each app removes only its own update leftovers, and only old ones."""

import os

from core import update


def _mk(parent, name, age, now):
    p = parent / name
    p.mkdir()
    os.utime(p, (now - age, now - age))
    return str(p)


def test_only_own_and_old_leftovers(tmp_path, monkeypatch):
    monkeypatch.setitem(update.APP, "prefix", "QLC-Stage-Monitor")
    now = 1_800_000_000
    old_own = _mk(tmp_path, "swk-update-QLC-Stage-Monitor-abc", 3600, now)
    new_own = _mk(tmp_path, "swk-update-QLC-Stage-Monitor-def", 30, now)        # still downloading
    other = _mk(tmp_path, "swk-update-QLC-Swiss-Knife-ghi", 3600, now)          # the other app's
    legacy_old = _mk(tmp_path, "swk-update-7gq5j5kq", 3600, now)                # before 3.18.2
    legacy_new = _mk(tmp_path, "swk-update-zzzzzzzz", 30, now)                  # may be in use
    (tmp_path / "QLC Swiss Knife.app").mkdir()
    got = set(update._leftovers(str(tmp_path), now=now))
    assert got == {old_own, legacy_old}
    assert new_own not in got and other not in got and legacy_new not in got


def test_work_folder_is_named_after_the_app(monkeypatch):
    monkeypatch.setitem(update.APP, "prefix", "QLC-Swiss-Knife")
    assert update._work_prefix() == "swk-update-QLC-Swiss-Knife-"
