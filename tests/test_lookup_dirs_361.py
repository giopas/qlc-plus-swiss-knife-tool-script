"""Folder lookups that a gig would show up (3.6.1).

Show Paperwork's cabling section reads the rig with the same fixture
definitions as the Cabling screen (3.6.1): the show's folder and then the
installed QLC+ library.  Before, only the show's folder was searched, so a
stock fixture lost its connector on paper (3-pin guessed, C101)."""

import os
import shutil

import app
from core import showbook, workspace
from core.cabling import plan as cplan

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


def test_cabling_section_finds_library_definitions(tmp_path, monkeypatch):
    show = tmp_path / "Pub_6fix.qxw"                  # no .qxf next to the show
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), show)
    monkeypatch.setenv("QLCPLUS_FIXTURES", CORPUS)    # the definitions are in the "QLC+ library"
    client = app.create_app().test_client()
    assert client.post("/api/load", json={"path": str(show)}).status_code == 200
    monkeypatch.setattr(cplan, "load_plan", lambda _p: {"chains": [{}]})
    monkeypatch.setattr(cplan, "evaluate", lambda p, r: {})
    _ev, _plan, rig = showbook._cabling_context(workspace._state)
    assert rig["fixtures"]
    assert all(f["definition"] for f in rig["fixtures"]), [f["model"] for f in rig["fixtures"] if not f["definition"]]


def test_input_profile_folders_match_qlcplus():
    """Input profiles (the MIDI pedal) are looked for where QLC+ keeps them:
    the macOS user folder spelled as QLC+ spells it, the Windows user folder
    and an app installed in ~/Applications."""
    from core import input_manager as im
    home = os.path.expanduser("~")
    dirs = im.PROFILE_DIRS
    assert os.path.join(home, "Library", "Application Support", "QLC+", "InputProfiles") in dirs
    assert os.path.join(home, "QLC+", "InputProfiles") in dirs
    assert os.path.join(home, "Applications", "QLC+.app", "Contents", "Resources", "InputProfiles") in dirs
    assert len(dirs) == len(set(dirs))
