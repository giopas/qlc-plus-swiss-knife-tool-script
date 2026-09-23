"""VERSION in core/workspace.py is the single source of truth (WORKPLAN §4)."""
import os
import re

from core.workspace import VERSION

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(REPO, name), encoding="utf-8") as fh:
        return fh.read()


def test_version_matches_latest_changelog_release():
    released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", _read("CHANGELOG.md"), re.M)
    assert released and released[0] == VERSION


def test_version_matches_readme_title():
    assert _read("README.md").splitlines()[0].endswith(f"v{VERSION}")


def test_ui_shows_version():
    import app
    html = app.create_app().test_client().get("/").get_data(as_text=True)
    assert VERSION in html
