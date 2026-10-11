"""tools/ground_truth.py reads the facts from git and reports drift."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import ground_truth  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git not installed")

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull,
       "GIT_CONFIG_NOSYSTEM": "1"}


def g(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A clone with VERSION 1.0.0 tagged and pushed to a local bare origin."""
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)

    origin = tmp_path / "origin.git"
    g(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    g(tmp_path, "clone", "-q", str(origin), str(work))
    g(work, "checkout", "-q", "-B", "main")
    (work / "core").mkdir()
    (work / "core" / "workspace.py").write_text('VERSION = "1.0.0"\n')
    (work / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n\n## [1.0.0]\n")
    g(work, "add", ".")
    g(work, "commit", "-q", "-m", "init")
    g(work, "tag", "v1.0.0")
    g(work, "push", "-q", "-u", "origin", "main", "v1.0.0")
    return work


def run(work, capsys):
    code = ground_truth.main(["--root", str(work), "--no-github"])
    return code, capsys.readouterr().out


def test_clean(repo, capsys):
    code, out = run(repo, capsys)
    assert code == 0, out
    assert "GROUND TRUTH: clean" in out


def test_unpushed_commit_on_main(repo, capsys):
    (repo / "a.txt").write_text("x")
    g(repo, "add", ".")
    g(repo, "commit", "-q", "-m", "local only")
    code, out = run(repo, capsys)
    assert code == 1
    assert "main has 1 commit(s) not pushed" in out


def test_uncommitted_change(repo, capsys):
    (repo / "b.txt").write_text("x")
    code, out = run(repo, capsys)
    assert code == 1 and "uncommitted" in out


def test_branch_only_on_this_disk(repo, capsys):
    g(repo, "checkout", "-q", "-b", "feat/v1.0.1")
    (repo / "c.txt").write_text("x")
    g(repo, "add", ".")
    g(repo, "commit", "-q", "-m", "wip")
    g(repo, "checkout", "-q", "main")
    code, out = run(repo, capsys)
    assert code == 1
    assert "feat/v1.0.1: 1 commit(s) not in origin/main and not pushed" in out


def test_tag_not_pushed(repo, capsys):
    (repo / "core" / "workspace.py").write_text('VERSION = "1.0.1"\n')
    g(repo, "commit", "-q", "-am", "bump")
    g(repo, "push", "-q", "origin", "main")
    g(repo, "tag", "v1.0.1")
    code, out = run(repo, capsys)
    assert code == 1 and "v1.0.1 exists here but not on origin" in out


def test_stale_lock_file(repo, capsys):
    (repo / ".git" / "index.lock").write_text("")
    code, out = run(repo, capsys)
    assert code == 1 and "index.lock" in out


def test_fetch_failure_is_unknown(repo, capsys):
    g(repo, "remote", "set-url", "origin", str(repo.parent / "missing.git"))
    code, out = run(repo, capsys)
    assert code == 2
    assert "GROUND TRUTH: incomplete" in out
