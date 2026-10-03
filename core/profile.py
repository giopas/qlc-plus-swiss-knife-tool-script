"""core/profile.py — **Show Profiles** (WORKPLAN 3.1, v2.1.0): the changes of a
show, kept to be done again on **another show** — tonight's venue, next
month's rig, a friend's show.

A profile is the recipe (core/recipe.py) made portable:

* every step says what it changes **by meaning** — *the Scene "Red"*, *the
  fixture "Drums" at 1.8*, *the page "Looks"* — not by the IDs of the show it
  was made on (core/retarget.py), so it applies to any show that has those
  things;
* the files a step uses (a setlist ``.txt``, another show for the Porter, a
  mesh) become **parameters**: give them when you apply the profile, or put
  files with the same names next to it;
* the VC page templates it uses travel inside it;
* it holds no paths of the computer it was made on.

Profiles live in ``~/.qlc_swiss_knife/profiles/`` (``QSK_PROFILES`` overrides).

Command line::

    python -m core.profile build Pub.profile.json --show Venue.qxw --out Venue_pub.qxw
    python -m core.profile build Pub.profile.json --show Venue.qxw --param Setlist.txt=~/tonight.txt
    python -m core.profile show Pub.profile.json
    python -m core.profile make Show_v2.recipe.json --name "Pub night"   # from a recipe
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from typing import Optional

from core import recipe as rcp

FORMAT = "qsk-profile/1"


class ProfileError(ValueError):
    pass


def profiles_dir() -> str:
    return os.environ.get("QSK_PROFILES") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "profiles")


def slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_ -]+", "", (name or "").strip()).strip().replace(" ", "_")
    if not s:
        raise ProfileError("A profile needs a name.")
    return s[:60]


def _replace_strings(obj, mapping: dict):
    if isinstance(obj, dict):
        return {_replace_strings(k, mapping): _replace_strings(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_strings(v, mapping) for v in obj]
    if isinstance(obj, str) and obj in mapping:
        return mapping[obj]
    return obj


def make(recipe: dict, name: str, description: str = "") -> dict:
    """A profile from a recipe (with its calls by meaning — 2.1.0+)."""
    if recipe.get("format") != rcp.FORMAT:
        raise ProfileError("Not a Swiss Knife recipe.")
    if rcp.needs_symbols(recipe):
        raise ProfileError("This recipe was recorded before Swiss Knife 2.1. Make the profile on "
                           "the command line, next to the show it was made on: "
                           "python -m core.profile make <recipe> --name …")
    params, swap = {}, {}
    for inp in recipe.get("inputs", []):
        key = inp["name"]
        n = 2
        while key in params:
            key, n = f"{os.path.splitext(inp['name'])[0]}_{n}{os.path.splitext(inp['name'])[1]}", n + 1
        params[key] = {"kind": "file", "name": inp["name"], "sha256": inp.get("sha256", ""),
                       "description": f"the file used when the profile was made ({inp['name']})"}
        swap[inp["path"]] = f"@param:{key}"
    src = recipe.get("source", {})
    if src.get("path"):
        swap.setdefault(src["path"], "@show")
    steps = []
    templates = {}
    for c in recipe.get("calls", []):
        st = {"title": rcp.describe(c), "method": c["method"], "path": c["path"],
              "body": _replace_strings(copy.deepcopy(c.get("body")), swap)}
        if c.get("sym"):
            st["sym"] = _replace_strings(copy.deepcopy(c["sym"]), swap)
        steps.append(st)
        b = c.get("body") if isinstance(c.get("body"), dict) else {}
        if c["path"] == "/api/vc/op" and b.get("op") == "apply_template" and b.get("name"):
            t = _read_template(b["name"])
            if t:
                templates[b["name"]] = t
    return {"format": FORMAT, "name": name.strip() or "Profile", "description": description.strip(),
            "swiss_knife": rcp._version(), "created": time.strftime("%Y-%m-%d %H:%M"),
            "made_on": src.get("name", ""), "params": params,
            "assets": {"vc_templates": templates} if templates else {},
            "steps": steps}


def _read_template(name: str) -> Optional[dict]:
    from core import vc_builder
    try:
        p = os.path.join(vc_builder.templates_dir(), vc_builder._slug(name) + ".json")
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError, vc_builder.VcOpError):
        return None


def install_assets(profile: dict) -> list:
    """Put the profile's VC templates where the VC Editor finds them (an
    existing template with the same name is kept)."""
    from core import vc_builder
    done = []
    for name, t in ((profile.get("assets") or {}).get("vc_templates") or {}).items():
        p = os.path.join(vc_builder.templates_dir(), vc_builder._slug(name) + ".json")
        if not os.path.isfile(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(t, fh, indent=1)
            done.append(name)
    return done


def save(profile: dict, folder: Optional[str] = None) -> str:
    folder = folder or profiles_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, slug(profile["name"]) + ".profile.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=1, ensure_ascii=False)
    return path


def load(path_or_name: str) -> dict:
    p = path_or_name
    if not os.path.isfile(p):
        p = os.path.join(profiles_dir(), slug(path_or_name) + ".profile.json")
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        raise ProfileError(f"Cannot read the profile {path_or_name}: {e}")
    if data.get("format") == rcp.FORMAT:          # a recipe works as a profile
        data = make(data, os.path.basename(p).split(".")[0])
    if data.get("format") != FORMAT:
        raise ProfileError(f"{os.path.basename(p)} is not a Swiss Knife profile.")
    data["_path"] = os.path.abspath(p)
    return data


def list_profiles() -> list:
    d = profiles_dir()
    out = []
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".profile.json"):
                try:
                    with open(os.path.join(d, fn), encoding="utf-8") as fh:
                        p = json.load(fh)
                except (OSError, ValueError):
                    continue
                out.append({"name": p.get("name", fn), "description": p.get("description", ""),
                            "steps": len(p.get("steps", [])), "params": list((p.get("params") or {})),
                            "made_on": p.get("made_on", ""), "created": p.get("created", ""),
                            "file": fn, "path": os.path.join(d, fn)})
    return out


def delete(name: str) -> bool:
    p = os.path.join(profiles_dir(), slug(name) + ".profile.json")
    if os.path.isfile(p):
        os.remove(p)
        return True
    return False


def resolve_params(profile: dict, given: Optional[dict] = None, inputs_dir: str = "") -> dict:
    """``{"@param:<name>": path}`` for every parameter; a file not given is
    looked up by name in *inputs_dir* and next to the profile."""
    given = {k: os.path.expanduser(v) for k, v in (given or {}).items() if v}
    here = os.path.dirname(profile.get("_path", "")) if profile.get("_path") else ""
    out, missing = {}, []
    for key, spec in (profile.get("params") or {}).items():
        v = given.get(key)
        if not v:
            for d in (inputs_dir, here):
                q = os.path.join(d, spec.get("name", key)) if d else ""
                if q and os.path.isfile(q):
                    v = q
                    break
        if not v:
            missing.append(key)
        elif spec.get("kind") == "file" and not os.path.isfile(v):
            raise ProfileError(f"{key}: file not found ({v}).")
        else:
            out[f"@param:{key}"] = os.path.abspath(v) if spec.get("kind") == "file" else v
    if missing:
        raise ProfileError("The profile needs: " + ", ".join(missing)
                           + " — give the file(s), or put them next to the profile.")
    return out


def _calls(profile: dict) -> list:
    return [{"method": s["method"], "path": s["path"], "body": s.get("body"),
             **({"sym": s["sym"]} if s.get("sym") else {})} for s in profile.get("steps", [])]


def apply_live(client, profile: dict, params: Optional[dict] = None, inputs_dir: str = "",
               show_path: str = "") -> dict:
    """Apply the profile to the show open in the app (*client*: a test client
    of the running app).  Returns ``{steps, applied, skipped, failed, templates}``."""
    mapping = resolve_params(profile, params, inputs_dir)
    if show_path:
        mapping["@show"] = show_path
    templates = install_assets(profile)
    steps = rcp.run_calls(client, _calls(profile), mapping, onto=True)
    for s, p in zip(steps, profile.get("steps", [])):
        s["title"] = p.get("title") or s["title"]
    return {"steps": steps, "templates": templates,
            "applied": sum(s["status"] == "applied" for s in steps),
            "skipped": sum(s["status"] == "skipped" for s in steps),
            "failed": sum(s["status"] == "failed" for s in steps)}


def build(profile: dict, show: str, out: Optional[str] = None, params: Optional[dict] = None,
          inputs_dir: str = "", log=None) -> dict:
    """The command-line pipeline: open *show*, apply the profile, save *out*."""
    import app as app_mod
    from core import qxw_io
    if not os.path.isfile(show):
        raise ProfileError(f"Show not found: {show}")
    client = app_mod.create_app().test_client()
    r = client.post("/api/load", json={"path": os.path.abspath(show)})
    if r.status_code != 200:
        raise ProfileError(f"Could not open {show}: {(r.get_json(silent=True) or {}).get('error')}")
    res = apply_live(client, profile, params, inputs_dir, os.path.abspath(show))
    for s in res["steps"]:
        if log:
            extra = s.get("why") or s.get("note") or ""
            log(f"  {s['n']:3d}  {s['status']:8s} {s['title']}" + (f" — {extra}" if extra else ""))
    res["out"] = ""
    if out:
        out = os.path.abspath(out)
        if out == os.path.abspath(show):
            out = qxw_io.next_version_path(out)
        r = client.post("/api/show/save", json={"path": out})
        if r.status_code != 200:
            raise ProfileError(f"Could not save: {(r.get_json(silent=True) or {}).get('error')}")
        res["out"] = out
        res["doctor"] = (client.get("/api/doctor/check").get_json(silent=True) or {}).get("summary", {})
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m core.profile",
                                 description="Show Profiles: the changes of a show, done again on another show.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="apply a profile to a show and save the result")
    b.add_argument("profile", help="a .profile.json (or a name in the profiles folder, or a .recipe.json)")
    b.add_argument("--show", required=True, help="the show to start from (never changed)")
    b.add_argument("--out", help="where to save (default: <show>_v<n+1>.qxw next to it)")
    b.add_argument("--param", action="append", default=[], metavar="NAME=VALUE",
                   help="a file (or value) the profile needs; repeat for more")
    b.add_argument("--inputs", default="", help="folder with the files the profile needs")
    b.add_argument("--dry-run", action="store_true", help="apply and report, save nothing")
    s = sub.add_parser("show", help="list a profile's steps and parameters")
    s.add_argument("profile")
    m = sub.add_parser("make", help="make a profile from a recipe")
    m.add_argument("recipe")
    m.add_argument("--name", required=True)
    m.add_argument("--description", default="")
    m.add_argument("--source", help="the show the recipe was made on (recipes before 2.1)")
    m.add_argument("-o", "--out", help="where to write the profile (default: the profiles folder)")
    sub.add_parser("list", help="the profiles in the profiles folder")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "list":
            for p in list_profiles():
                print(f"{p['name']}: {p['steps']} steps" + (f", needs {', '.join(p['params'])}" if p["params"] else "")
                      + (f" — {p['description']}" if p["description"] else ""))
            return 0
        if a.cmd == "make":
            rec = json.load(open(a.recipe, encoding="utf-8"))
            if rcp.needs_symbols(rec):
                src = rcp._find_source(rec, a.source, os.path.dirname(os.path.abspath(a.recipe)), "")
                rec = rcp.add_symbols(rec, src, os.path.dirname(os.path.abspath(a.recipe)))
            prof = make(rec, a.name, a.description)
            if a.out:
                with open(a.out, "w", encoding="utf-8") as fh:
                    json.dump(prof, fh, indent=1, ensure_ascii=False)
                path = a.out
            else:
                path = save(prof)
            print(f"Profile '{prof['name']}': {len(prof['steps'])} steps → {path}")
            return 0
        prof = load(a.profile)
        if a.cmd == "show":
            print(f"{prof['name']} — {prof.get('description') or 'no description'}")
            print(f"  made on {prof.get('made_on') or '?'} with Swiss Knife {prof.get('swiss_knife')}")
            for n, st in enumerate(prof["steps"], 1):
                print(f"  {n:3d}  {st.get('title') or st['path']}")
            for k, v in (prof.get("params") or {}).items():
                print(f"  needs: {k} ({v.get('kind')})")
            return 0
        params = dict(p.split("=", 1) for p in a.param if "=" in p)
        out = None if a.dry_run else (a.out or _next_to(a.show))
        res = build(prof, a.show, out, params, a.inputs, log=print)
    except (ProfileError, rcp.ReplayError) as e:
        print(f"PROFILE FAILED: {e}", file=sys.stderr)
        return 1
    print(f"{prof['name']} on {os.path.basename(a.show)}: {res['applied']} applied, "
          f"{res['skipped']} left out, {res['failed']} failed.")
    if res.get("out"):
        d = res.get("doctor") or {}
        print(f"Saved: {res['out']}" + (f" — Doctor {d.get('error', 0)} errors, {d.get('warning', 0)} warnings"
                                         if d else ""))
    return 0 if not res["failed"] else 3


def _next_to(show: str) -> str:
    from core import qxw_io
    return qxw_io.next_version_path(os.path.abspath(show))


if __name__ == "__main__":
    sys.exit(main())
