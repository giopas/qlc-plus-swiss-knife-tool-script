"""Brightness finds fixture definitions where the rest of Swiss Knife does
(3.6.1): the shared QLC+ library lookup comes first, so the macOS user
folder ~/Library/Application Support/QLC+/Fixtures is searched."""

import os
import platform

from core import brightness


def test_macos_user_folder_is_searched(tmp_path, monkeypatch):
    user = tmp_path / "Library" / "Application Support" / "QLC+" / "Fixtures"
    user.mkdir(parents=True)
    monkeypatch.delenv("QLCPLUS_FIXTURES", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    assert str(user) in brightness._qlc_fixture_dirs()


def test_override_folder_comes_first(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    lib.mkdir()
    monkeypatch.setenv("QLCPLUS_FIXTURES", str(lib))
    dirs = brightness._qlc_fixture_dirs()
    assert dirs[0] == str(lib)
    assert len(dirs) == len(set(dirs))
