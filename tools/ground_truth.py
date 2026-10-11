"""Ground truth — what git and GitHub say, before trusting any note.

The work plan and the session notes say what a past session *believed*:
"pushed", "released", "the wiki is up to date".  This tool reads the facts
from git (and GitHub, when the ``gh`` command is installed) and prints where
they need attention.  Run it at the start of a session and after a release.

It checks:

1. **Working trees** — uncommitted changes in the repository and in ``wiki/``.
2. **main and the wiki against origin** — commits not pushed, or not pulled.
3. **Branches** — local branches with commits that are neither in
   ``origin/main`` nor pushed: work that exists only on this disk.
4. **The release** — ``VERSION`` (``core/workspace.py``) has its tag, here and
   on origin, on a commit of ``origin/main``; the GitHub release for it is
   published, not a draft (needs ``gh``).
5. **CI** — the last ``tests`` run on ``main`` (needs ``gh``).
6. **Stale lock files** under ``.git`` — left by a git that could not delete
   them (the Claude sandbox), they make the next git command fail.
7. **CHANGELOG** — whether ``[Unreleased]`` holds entries (for information).

Every line is ``OK``, ``INFO``, ``DRIFT`` (something to act on) or
``UNKNOWN`` (a check that could not run: never read it as a pass).

Usage::

    python3 tools/ground_truth.py              # fetches origin first
    python3 tools/ground_truth.py --offline    # no network: remote checks skipped
    python3 tools/ground_truth.py --no-github  # skip the gh checks

Exit code: 0 = nothing to act on, 1 = drift, 2 = a check could not run.
Standard library only; needs ``git``.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OK, INFO, DRIFT, UNKNOWN = "OK", "INFO", "DRIFT", "UNKNOWN"


class Report:
    """Collects check results and turns them into an exit code."""

    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []

    def add(self, level: str, text: str) -> None:
        self.lines.append((level, text))
        print(f"{level:<7} {text}", flush=True)

    def exit_code(self) -> int:
        levels = {lvl for lvl, _ in self.lines}
        if UNKNOWN in levels:
            return 2
        if DRIFT in levels:
            return 1
        return 0


def git(repo: Path, *args: str) -> tuple[int, str]:
    """Run git in *repo*; return (exit code, stripped stdout or stderr)."""
    p = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    return p.returncode, (p.stdout if p.returncode == 0 else p.stderr).strip()


def read_version(root: Path) -> str | None:
    """VERSION from core/workspace.py, the single source of truth."""
    try:
        src = (root / "core" / "workspace.py").read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', src, re.M)
    return m.group(1) if m else None


def check_tree(rep: Report, repo: Path, name: str) -> None:
    code, out = git(repo, "status", "--porcelain")
    if code:
        rep.add(UNKNOWN, f"{name}: git status failed: {out}")
    elif out:
        n = len(out.splitlines())
        rep.add(DRIFT, f"{name}: {n} uncommitted change(s) — git -C {repo} status")
    else:
        rep.add(OK, f"{name}: working tree clean")


def check_branch_vs_remote(rep: Report, repo: Path, name: str, branch: str,
                           fetched: bool) -> None:
    code, out = git(repo, "rev-list", "--left-right", "--count",
                    f"{branch}...origin/{branch}")
    if code:
        rep.add(UNKNOWN, f"{name}: cannot compare {branch} with origin/{branch}: {out}")
        return
    ahead, behind = (int(x) for x in out.split())
    stale = "" if fetched else " (origin not fetched)"
    if ahead:
        rep.add(DRIFT, f"{name}: {branch} has {ahead} commit(s) not pushed{stale}")
    if behind:
        rep.add(DRIFT, f"{name}: {branch} is {behind} commit(s) behind origin{stale}")
    if not ahead and not behind:
        rep.add(OK, f"{name}: {branch} = origin/{branch}{stale}")


def check_local_branches(rep: Report, repo: Path) -> None:
    code, out = git(repo, "for-each-ref", "--format=%(refname:short)|%(upstream:short)",
                    "refs/heads")
    if code:
        rep.add(UNKNOWN, f"branches: cannot list: {out}")
        return
    found = False
    for line in out.splitlines():
        branch, upstream = line.split("|", 1)
        if branch == "main":
            continue
        code, n = git(repo, "rev-list", "--count", f"origin/main..{branch}")
        if code:
            rep.add(UNKNOWN, f"branch {branch}: {n}")
            continue
        if int(n) == 0:
            continue  # fully in origin/main
        found = True
        if upstream:
            code, ahead = git(repo, "rev-list", "--count", f"{upstream}..{branch}")
            if code == 0 and int(ahead) == 0:
                rep.add(INFO, f"branch {branch}: {n} commit(s) not in main, pushed to {upstream}")
                continue
        rep.add(DRIFT, f"branch {branch}: {n} commit(s) not in origin/main and not pushed")
    if not found:
        rep.add(OK, "branches: every local branch is in origin/main or pushed")


def check_tag(rep: Report, repo: Path, version: str | None, fetched: bool,
              offline: bool) -> None:
    if not version:
        rep.add(UNKNOWN, "release: VERSION not found in core/workspace.py")
        return
    tag = f"v{version}"
    code, local = git(repo, "rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{commit}}")
    if code:
        rep.add(INFO, f"release: {tag} not tagged yet (VERSION bumped, release pending?)")
        return
    if offline:
        rep.add(INFO, f"release: {tag} tagged here; origin not checked (--offline)")
        return
    code, remote = git(repo, "ls-remote", "--tags", "origin", f"refs/tags/{tag}")
    if code:
        rep.add(UNKNOWN, f"release: cannot read tags on origin: {remote}")
        return
    if not remote:
        rep.add(DRIFT, f"release: {tag} exists here but not on origin — git push origin {tag}")
        return
    code, _ = git(repo, "merge-base", "--is-ancestor", local, "origin/main")
    if code:
        rep.add(DRIFT, f"release: {tag} is not on origin/main")
    else:
        rep.add(OK, f"release: {tag} on origin and in main")


def gh_json(repo: Path, *args: str) -> tuple[int, object]:
    p = subprocess.run(["gh", *args], cwd=repo, capture_output=True, text=True)
    if p.returncode:
        return p.returncode, (p.stderr or p.stdout).strip()
    try:
        return 0, json.loads(p.stdout or "null")
    except ValueError:
        return 1, "unreadable output from gh"


def check_github(rep: Report, repo: Path, version: str | None) -> None:
    if not shutil.which("gh"):
        rep.add(INFO, "github: gh not installed — CI and release page not checked")
        return
    code, runs = gh_json(repo, "run", "list", "--branch", "main", "--workflow", "tests.yml",
                         "--limit", "1", "--json", "headSha,status,conclusion,url")
    if code or not isinstance(runs, list):
        rep.add(UNKNOWN, f"github: cannot read CI runs: {runs}")
    elif not runs:
        rep.add(INFO, "github: no tests run on main yet")
    else:
        run = runs[0]
        _, head = git(repo, "rev-parse", "origin/main")
        which = "" if run["headSha"] == head else \
            f" (for {run['headSha'][:7]}; later pushes changed only docs or did not run)"
        if run["status"] != "completed":
            rep.add(INFO, f"github: tests on main still {run['status']}{which}")
        elif run["conclusion"] == "success":
            rep.add(OK, f"github: tests on main passed{which}")
        else:
            rep.add(DRIFT, f"github: tests on main {run['conclusion']}{which} — {run['url']}")
    if not version:
        return
    tag = f"v{version}"
    code, rel = gh_json(repo, "release", "view", tag, "--json", "isDraft,url")
    if code:
        if "not found" in str(rel).lower():
            rep.add(INFO, f"github: no release for {tag} yet")
        else:
            rep.add(UNKNOWN, f"github: cannot read release {tag}: {rel}")
    elif rel.get("isDraft"):
        rep.add(DRIFT, f"github: release {tag} is still a draft — {rel['url']}")
    else:
        rep.add(OK, f"github: release {tag} published")


def check_locks(rep: Report, repos: list[tuple[Path, str]]) -> None:
    found = []
    for repo, name in repos:
        gitdir = repo / ".git"
        if not gitdir.is_dir():
            continue
        for p in gitdir.rglob("*"):
            if p.is_file() and (p.name.endswith(".lock") or
                                (p.name.startswith("stale-") and "lock" in p.name)):
                found.append(p)
    if found:
        for p in found:
            rep.add(DRIFT, f"lock file: {p} — delete it if no git is running")
    else:
        rep.add(OK, "lock files: none")


def check_changelog(rep: Report, root: Path) -> None:
    try:
        text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        rep.add(UNKNOWN, "changelog: CHANGELOG.md not readable")
        return
    m = re.search(r"^## \[Unreleased\]\s*\n(.*?)(?=^## \[)", text, re.M | re.S)
    body = m.group(1).strip().strip("-").strip() if m else ""
    if body:
        n = len([ln for ln in body.splitlines() if ln.lstrip().startswith("- ")])
        rep.add(INFO, f"changelog: [Unreleased] holds {n} entr{'y' if n == 1 else 'ies'}")
    else:
        rep.add(OK, "changelog: [Unreleased] is empty")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root")
    ap.add_argument("--offline", action="store_true", help="do not fetch or ask origin")
    ap.add_argument("--no-github", action="store_true", help="skip the gh checks")
    args = ap.parse_args(argv)

    if not shutil.which("git"):
        print("UNKNOWN git not installed")
        return 2
    root = args.root.resolve()
    wiki = root / "wiki"
    has_wiki = (wiki / ".git").exists()
    rep = Report()

    fetched = {}
    for repo, name in [(root, "repo")] + ([(wiki, "wiki")] if has_wiki else []):
        if args.offline:
            fetched[name] = False
            continue
        code, out = git(repo, "fetch", "--quiet", "--tags", "--prune", "origin")
        fetched[name] = code == 0
        if code:
            rep.add(UNKNOWN, f"{name}: git fetch failed: {out.splitlines()[-1] if out else code}")

    check_tree(rep, root, "repo")
    check_branch_vs_remote(rep, root, "repo", "main", fetched["repo"])
    check_local_branches(rep, root)
    if has_wiki:
        check_tree(rep, wiki, "wiki")
        check_branch_vs_remote(rep, wiki, "wiki", "master", fetched["wiki"])
    else:
        rep.add(INFO, "wiki: no clone in wiki/ — not checked")
    version = read_version(root)
    check_tag(rep, root, version, fetched["repo"], args.offline)
    if not (args.offline or args.no_github):
        check_github(rep, root, version)
    check_locks(rep, [(root, "repo")] + ([(wiki, "wiki")] if has_wiki else []))
    check_changelog(rep, root)

    code = rep.exit_code()
    print("GROUND TRUTH:", {0: "clean", 1: "drift — see DRIFT lines",
                            2: "incomplete — see UNKNOWN lines"}[code])
    return code


if __name__ == "__main__":
    sys.exit(main())
