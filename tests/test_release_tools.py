"""The release title and text come from CHANGELOG.md (tools/release_notes.py)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import release_notes as rn  # noqa: E402

TEXT = """# Changelog

## [Unreleased]

## [2.0.0] — 2026-01-02 — Big step

Intro line.

### Added
- One thing.

---

## [1.9.0] — 2025-12-01

### Fixed
- Another thing.
"""


def test_title_and_body_from_the_section():
    name, notes = rn.release("v2.0.0", TEXT)
    assert name == "v2.0.0 · Big step"
    assert notes.startswith("Intro line.") and "One thing." in notes
    assert "Another thing" not in notes and "CHANGELOG" in notes


def test_a_section_without_a_short_title_is_called_by_its_version():
    assert rn.release("1.9.0", TEXT)[0] == "v1.9.0"


def test_the_current_version_has_a_section_and_a_short_title():
    from core.workspace import VERSION
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        name, notes = rn.release(VERSION, f.read())
    assert " · " in name, "give the release heading a short title: ## [X.Y.Z] — date — Short title"
    assert len(notes) > 200


def test_the_release_workflow_uses_it():
    with open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8") as f:
        wf = f.read()
    assert "tools/release_notes.py" in wf and "--notes-file notes.md" in wf


def test_shots_tool_has_its_commands():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "shots.py"), "--help"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and "readme" in out.stdout and "state" in out.stdout
