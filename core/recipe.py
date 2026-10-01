"""core/recipe.py — the show's *recipe* (WORKPLAN 2.9): every change made to
the show in progress, recorded as the API calls the tools made, so the
command line can replay them on the opened file and get the same `.qxw`.

How it works
------------
* Opening a show (``/api/load``) starts a new recipe: the source file, its
  SHA-256 and the Swiss Knife version.
* Every request that changes something (POST / PATCH / DELETE under
  ``/api/``) is appended in order — except the calls that only read, export
  or talk to the desktop (:data:`SKIP`).  Undo and redo are recorded like any
  other call, so the replay goes through the same history.
* *💾 Save as new file…* writes ``<name>.recipe.json`` next to the file and
  its report, with the SHA-256 of the saved ``.qxw``.
* ``python -m core.recipe replay <name>.recipe.json`` opens the source in a
  fresh app, replays the calls and saves; it says whether the result is
  byte-identical (``--out`` to keep it).

Files a call names (another show for the Porter, a setlist ``.txt``…) are
listed as *inputs* with their SHA-256; on another computer they are looked up
next to the recipe (or in ``--inputs``) by name.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from typing import Any, Optional

FORMAT = "qsk-recipe/1"

# Paths never recorded: reads, previews that change nothing, exports, desktop
# dialogs, sessions, other tools' scratch state, and the save itself.
SKIP = [
    r"^/api/load$", r"^/api/reload$", r"^/api/quit$", r"^/api/help$", r"^/api/output-dir$",
    r"^/api/picker/", r"^/api/session/", r"^/api/show/save$", r"^/api/show/saved$",
    r"^/api/compare/", r"^/api/dictionary/", r"^/api/quickstart/", r"^/api/fixture/",
    r"^/api/merger/", r"^/api/showbook/", r"^/api/checklist/", r"^/api/techrider/",
    r"/export", r"/save-report$", r"/save-file$", r"/preview", r"^/api/doctor/fix$",
    r"^/api/reducer/reduce$", r"^/api/looks/build$", r"^/api/looks/presets",
    r"^/api/porter/execute$", r"^/api/porter/report$", r"^/api/stage/save$",
    r"^/api/vc/export-qxw$", r"^/api/triggers/save", r"^/api/setlist/.*/generate-qxw$",
    r"^/api/setlist/generate-all-qxw$", r"^/api/setlist/save$", r"^/api/stage/library-dirs$",
    r"^/api/brightness/apply$", r"^/api/brightness/fetch-github$", r"^/api/brightness/upload-qxf$",
]
_SKIP = [re.compile(p) for p in SKIP]

_rec: dict = {}


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _version() -> str:
    from core.workspace import VERSION
    return VERSION


def reset(source_path: str) -> None:
    """A show was opened: a new recipe starts."""
    _rec.clear()
    try:
        sha = _sha(source_path) if source_path and os.path.isfile(source_path) else ""
    except OSError:
        sha = ""
    _rec.update({"source": {"path": os.path.abspath(source_path) if source_path else "",
                            "name": os.path.basename(source_path or ""), "sha256": sha},
                 "calls": [], "inputs": {}, "started": time.time()})


def active() -> bool:
    return bool(_rec)


def recordable(method: str, path: str) -> bool:
    if method not in ("POST", "PATCH", "PUT", "DELETE") or not path.startswith("/api/"):
        return False
    return not any(p.search(path) for p in _SKIP)


def _scan_inputs(obj: Any) -> None:
    """Remember the files a call names (with their hash)."""
    if isinstance(obj, dict):
        for v in obj.values():
            _scan_inputs(v)
    elif isinstance(obj, list):
        for v in obj:
            _scan_inputs(v)
    elif isinstance(obj, str) and len(obj) < 1024 and (os.sep in obj or "/" in obj):
        p = obj
        if os.path.isabs(p) and os.path.isfile(p) and p not in _rec["inputs"]:
            try:
                _rec["inputs"][p] = {"name": os.path.basename(p), "sha256": _sha(p)}
            except OSError:
                pass


def record(method: str, path: str, body: Any, status: int) -> None:
    """Called after each request (app.py)."""
    if not _rec or status >= 400 or not recordable(method, path):
        return
    _rec["calls"].append({"method": method, "path": path, "body": copy.deepcopy(body)})
    _scan_inputs(body)


def snapshot(saved_path: str = "") -> dict:
    """The recipe as JSON-able dict (with the saved file's hash when given)."""
    out = {
        "format": FORMAT,
        "swiss_knife": _version(),
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": dict(_rec.get("source", {})),
        "inputs": [{"path": p, **v} for p, v in _rec.get("inputs", {}).items()],
        "calls": copy.deepcopy(_rec.get("calls", [])),
    }
    if saved_path and os.path.isfile(saved_path):
        out["result"] = {"name": os.path.basename(saved_path), "sha256": _sha(saved_path)}
    return out


def recipe_path(qxw_path: str) -> str:
    return os.path.splitext(qxw_path)[0] + ".recipe.json"


def write_next_to(qxw_path: str) -> str:
    """Write the recipe next to the saved show; returns its path ('' if none)."""
    if not _rec or not qxw_path or not os.path.isfile(qxw_path):
        return ""
    from core import qxw_io
    rp = recipe_path(qxw_path)
    data = json.dumps(snapshot(qxw_path), indent=1, ensure_ascii=False).encode("utf-8")
    qxw_io.write_bytes(data, rp, protect=[_rec.get("source", {}).get("path", "")])
    return rp


# ── replay ──────────────────────────────────────────────────────────────────

class ReplayError(RuntimeError):
    pass


def _resolve_inputs(recipe: dict, recipe_dir: str, inputs_dir: str) -> dict:
    """{recorded path: path here}, by name next to the recipe / in inputs_dir."""
    out = {}
    for inp in recipe.get("inputs", []):
        p = inp["path"]
        if os.path.isfile(p):
            out[p] = p
            continue
        for d in (inputs_dir, recipe_dir):
            q = os.path.join(d, inp["name"]) if d else ""
            if q and os.path.isfile(q):
                out[p] = q
                break
        else:
            raise ReplayError(f"Input file not found: {inp['name']} (was {p}). "
                              "Put it next to the recipe or pass --inputs.")
    return out


def _swap(obj: Any, mapping: dict) -> Any:
    if isinstance(obj, dict):
        return {k: _swap(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_swap(v, mapping) for v in obj]
    if isinstance(obj, str) and obj in mapping:
        return mapping[obj]
    return obj


def replay(recipe: dict, source: Optional[str] = None, out: Optional[str] = None,
           recipe_dir: str = "", inputs_dir: str = "", log=None) -> dict:
    """Open *source* (default: the recorded one, or one with its name next to
    the recipe), replay the calls, save to *out* (default: a temp file).
    Returns ``{out, sha256, identical, calls, warnings}``."""
    import app as app_mod
    say = log or (lambda *_: None)
    warnings = []
    if recipe.get("format") != FORMAT:
        raise ReplayError(f"Not a Swiss Knife recipe ({recipe.get('format')!r}).")
    if recipe.get("swiss_knife") != _version():
        warnings.append(f"Recorded with Swiss Knife {recipe.get('swiss_knife')}, replayed with "
                        f"{_version()}: the result may differ.")
    src = recipe.get("source", {})
    if not source:
        cands = [src.get("path", ""), os.path.join(inputs_dir, src.get("name", "")) if inputs_dir else "",
                 os.path.join(recipe_dir, src.get("name", "")) if recipe_dir else ""]
        source = next((c for c in cands if c and os.path.isfile(c)), "")
    if not source or not os.path.isfile(source):
        raise ReplayError(f"Source show not found: {src.get('name')} — pass --source.")
    if src.get("sha256") and _sha(source) != src["sha256"]:
        warnings.append(f"{os.path.basename(source)} is not the file the recipe was recorded on "
                        "(different content).")
    mapping = _resolve_inputs(recipe, recipe_dir, inputs_dir)
    if src.get("path") and src["path"] != os.path.abspath(source):
        mapping[src["path"]] = os.path.abspath(source)

    client = app_mod.create_app().test_client()
    r = client.post("/api/load", json={"path": os.path.abspath(source)})
    if r.status_code != 200:
        raise ReplayError(f"Could not open {source}: {r.get_json()}")
    calls = recipe.get("calls", [])
    for n, c in enumerate(calls, 1):
        body = _swap(c.get("body"), mapping)
        r = client.open(c["path"], method=c["method"], json=body)
        if r.status_code >= 400:
            msg = (r.get_json(silent=True) or {}).get("error", r.status_code)
            raise ReplayError(f"Call {n}/{len(calls)} {c['method']} {c['path']} failed: {msg}")
        say(f"  {n:3d}/{len(calls)}  {c['method']} {c['path']}")
    keep = bool(out)
    if not out:
        fd, out = tempfile.mkstemp(suffix=".qxw")
        os.close(fd)
        os.remove(out)
    r = client.post("/api/show/save", json={"path": os.path.abspath(out)})
    if r.status_code != 200:
        raise ReplayError(f"Could not save: {r.get_json()}")
    sha = _sha(out)
    want = (recipe.get("result") or {}).get("sha256")
    res = {"out": out if keep else "", "sha256": sha, "expected": want,
           "identical": bool(want) and sha == want, "calls": len(calls), "warnings": warnings}
    if not keep:
        for p in (out, os.path.splitext(out)[0] + "_report.txt", recipe_path(out)):
            try:
                os.remove(p)
            except OSError:
                pass
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m core.recipe",
                                 description="Replay a Swiss Knife recipe (<show>.recipe.json).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("replay", help="replay the recipe and check the result")
    rp.add_argument("recipe")
    rp.add_argument("--source", help="the show the recipe starts from (default: as recorded)")
    rp.add_argument("--out", help="where to save the result (default: check only)")
    rp.add_argument("--inputs", default="", help="folder with the other files the recipe uses")
    rp.add_argument("-v", "--verbose", action="store_true", help="list every call")
    sh = sub.add_parser("show", help="list the steps of a recipe")
    sh.add_argument("recipe")
    a = ap.parse_args(argv)
    try:
        recipe = json.load(open(a.recipe, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"Cannot read {a.recipe}: {e}", file=sys.stderr)
        return 2
    if a.cmd == "show":
        print(f"{FORMAT}: {recipe.get('source', {}).get('name')} → "
              f"{(recipe.get('result') or {}).get('name', '?')} — Swiss Knife {recipe.get('swiss_knife')}")
        for n, c in enumerate(recipe.get("calls", []), 1):
            print(f"  {n:3d}  {c['method']:5s} {c['path']}")
        for i in recipe.get("inputs", []):
            print(f"  input: {i['name']}")
        return 0
    try:
        res = replay(recipe, a.source, a.out, os.path.dirname(os.path.abspath(a.recipe)), a.inputs,
                     log=print if a.verbose else None)
    except ReplayError as e:
        print(f"REPLAY FAILED: {e}", file=sys.stderr)
        return 1
    for w in res["warnings"]:
        print(f"warning: {w}")
    if res["out"]:
        print(f"Saved: {res['out']}")
    if not res["expected"]:
        print(f"Replayed {res['calls']} call(s); the recipe has no result hash to compare with.")
        return 0
    if res["identical"]:
        print(f"RESULT: IDENTICAL — {res['calls']} call(s) replayed, same .qxw (sha256 {res['sha256'][:12]}…).")
        return 0
    print(f"RESULT: DIFFERENT — replayed {res['calls']} call(s), but the .qxw differs "
          f"({res['sha256'][:12]}… vs recorded {res['expected'][:12]}…).")
    return 3


if __name__ == "__main__":
    sys.exit(main())
