"""core/library.py — the community library (v2.7.0).

Share what you built with other QLC+ users, as **one plain file** and nothing
else: no server, no account, no network.  A *library pack* is a JSON file
(``*.qsklib.json``) holding any of

* ``vc_template``   a Virtual Console page (layout, colours, function names)
* ``palette``       a Look Builder colour palette
* ``look_preset``   a Look Builder chaser preset
* ``nomenclature``  a function-naming profile
* ``vc_style``      a Virtual Console style (button size, gaps, fonts)
* ``show_profile``  a Show Profile (the changes of a show, to do again)

Your controllers (they carry a device UID of *your* computer), sessions and
mesh folders are never shared.

Importing is a preview first (what is new, what you already have, what is
refused and why), then the choice per item: skip, replace, or keep both
(the new one is named "… (2)").  Built-in names are never replaced.  Every
item is validated before anything is written: sizes are capped, a Virtual
Console page may hold no DOCTYPE/entity, and a Show Profile may only call the
steps a recipe can record.
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

FORMAT = "qsk-library/1"
EXT = ".qsklib.json"
MAX_FILE = 8 * 1024 * 1024
MAX_ITEMS = 500

KINDS = [
    ("vc_template", "VC template", "A Virtual Console page"),
    ("palette", "Palette", "A Look Builder colour palette"),
    ("look_preset", "Look preset", "A chaser preset for the Look Builder"),
    ("nomenclature", "Naming profile", "How functions are named"),
    ("vc_style", "VC style", "Button size, gaps, fonts"),
    ("show_profile", "Show Profile", "The changes of a show, to do again"),
]
_KIND_IDS = [k for k, _l, _d in KINDS]
_PATH_RE = re.compile(r"^(?:/(?:Users|home|root|private|Volumes|mnt)/|[A-Za-z]:\\)")


class LibraryError(ValueError):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def _name(v) -> str:
    n = " ".join(str(v or "").split())
    if not n:
        raise LibraryError("an item has no name")
    if len(n) > 80:
        raise LibraryError(f"'{n[:30]}…' — the name is longer than 80 characters")
    return n


def _walk_strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)
    elif isinstance(obj, str):
        yield obj


def _has_path(obj) -> bool:
    return any(_PATH_RE.match(s) for s in _walk_strings(obj))


def _size_ok(obj, limit=2 * 1024 * 1024) -> bool:
    return len(json.dumps(obj, ensure_ascii=False)) <= limit


# ─────────────────────────────────────────────────────────────────────────────
# the stores (what you have)
# ─────────────────────────────────────────────────────────────────────────────

def _read_json_files(folder: str, suffix: str = ".json"):
    if not os.path.isdir(folder):
        return
    for fn in sorted(os.listdir(folder)):
        if fn.endswith(suffix):
            try:
                with open(os.path.join(folder, fn), encoding="utf-8") as fh:
                    yield fn, json.load(fh)
            except (OSError, ValueError):
                continue


def _own(kind: str) -> Dict[str, dict]:
    """``{name: data}`` of YOUR items of that kind (built-ins are not listed)."""
    out: Dict[str, dict] = {}
    if kind == "vc_template":
        from core import vc_builder
        for fn, t in _read_json_files(vc_builder.templates_dir()):
            if isinstance(t, dict):
                out[str(t.get("name") or fn[:-5])] = t
    elif kind == "palette":
        from core import look_builder as lb
        for p in lb._user_palettes():
            out[p["name"]] = {"name": p["name"], "colours": p["colours"]}
    elif kind == "look_preset":
        from core import look_builder as lb
        for p in lb._user_presets():
            out[p["name"]] = p
    elif kind == "nomenclature":
        from core.quick_start import nomenclature as nm
        for fn, p in _read_json_files(nm.user_dir()):
            if isinstance(p, dict):
                out[str(p.get("label") or p.get("id") or fn[:-5])] = p
    elif kind == "vc_style":
        from core.quick_start import vc_style as vs
        for fn, p in _read_json_files(vs.user_dir()):
            if isinstance(p, dict):
                out[str(p.get("label") or p.get("id") or fn[:-5])] = p
    elif kind == "show_profile":
        from core import profile as prof
        for fn, p in _read_json_files(prof.profiles_dir(), ".profile.json"):
            if isinstance(p, dict) and p.get("format") == prof.FORMAT:
                out[str(p.get("name") or fn)] = p
    else:
        raise LibraryError(f"Unknown kind: {kind}")
    return out


def _summary(kind: str, d: dict) -> str:
    if kind == "vc_template":
        return f"{d.get('widgets', 0)} widget(s), {len(d.get('functions') or {})} function name(s)"
    if kind == "palette":
        return f"{len(d.get('colours') or [])} colour(s)"
    if kind == "look_preset":
        return f"{d.get('pattern', 'chaser')}, {d.get('steps', '?')} step(s)"
    if kind == "nomenclature":
        return d.get("format", "")
    if kind == "vc_style":
        return f"button {d.get('btn_w', '?')}×{d.get('btn_h', '?')}, gap {d.get('gap', '?')}"
    if kind == "show_profile":
        bits = [f"{len(d.get('steps') or [])} step(s)"]
        if d.get("start"):
            bits.append("with its rig")
        return ", ".join(bits)
    return ""


def kinds() -> List[dict]:
    return [{"id": k, "label": l, "description": d} for k, l, d in KINDS]


def inventory() -> List[dict]:
    """Every shareable item you have: ``[{kind, name, summary, private}]``."""
    out = []
    for k in _KIND_IDS:
        for name, data in sorted(_own(k).items(), key=lambda kv: kv[0].lower()):
            out.append({"kind": k, "name": name, "summary": _summary(k, data),
                        "private": _has_path(data) if k == "show_profile" else False})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# export
# ─────────────────────────────────────────────────────────────────────────────

def export_pack(selection: List[dict], title: str = "", author: str = "", description: str = "") -> dict:
    """A pack with the chosen items (``[{kind, name}]``); each is read from
    what you have.  An unknown item is an error, not silently left out."""
    if not selection:
        raise LibraryError("Tick at least one item to share.")
    if len(selection) > MAX_ITEMS:
        raise LibraryError(f"At most {MAX_ITEMS} items in a pack.")
    cache: Dict[str, Dict[str, dict]] = {}
    items = []
    for s in selection:
        kind, name = s.get("kind"), s.get("name")
        if kind not in _KIND_IDS:
            raise LibraryError(f"Unknown kind: {kind}")
        mine = cache.setdefault(kind, _own(kind))
        if name not in mine:
            raise LibraryError(f"You have no {kind.replace('_', ' ')} called '{name}'.")
        data = copy.deepcopy(mine[name])
        if kind == "show_profile":
            data.pop("_path", None)
        items.append({"kind": kind, "name": name, "data": data})
    from core.workspace import VERSION
    return {"format": FORMAT, "swiss_knife": VERSION, "created": time.strftime("%Y-%m-%d %H:%M"),
            "title": " ".join(str(title or "").split())[:120], "author": " ".join(str(author or "").split())[:80],
            "description": str(description or "").strip()[:1000], "items": items}


def pack_filename(pack: dict) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", pack.get("title") or "swiss-knife-library").strip("_") or "library"
    return base[:60] + EXT


def write_pack(pack: dict, path: str) -> str:
    """Write the pack to *path* (``.qsklib.json`` is appended when missing);
    never overwrites: ``name_2.qsklib.json`` …"""
    if not path.endswith(EXT):
        path = re.sub(r"\.json$", "", path) + EXT
    stem = path[:-len(EXT)]
    n = 2
    while os.path.exists(path):
        path, n = f"{stem}_{n}{EXT}", n + 1
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(pack, fh, indent=1, ensure_ascii=False)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# validation of one item (nothing is written here)
# ─────────────────────────────────────────────────────────────────────────────

def _check_vc_template(d: dict) -> dict:
    xml = d.get("xml")
    if not isinstance(xml, str) or not xml.strip():
        raise LibraryError("the page has no content")
    if "<!" in xml:
        raise LibraryError("the page carries a DOCTYPE or an entity, which is not allowed")
    try:
        root = ET.fromstring(xml)           # qxw-io: not output (validation only)
    except ET.ParseError as e:
        raise LibraryError(f"the page is not valid XML ({e})")
    if not root.tag.endswith("Frame"):
        raise LibraryError("the page is not a Virtual Console frame")
    fns = d.get("functions") or {}
    if not isinstance(fns, dict):
        raise LibraryError("the function names are malformed")
    return {"name": d.get("name"), "caption": str(d.get("caption", "")), "widgets": int(d.get("widgets") or 0),
            "functions": {str(k): v for k, v in fns.items()}, "xml": xml}


def _check_palette(d: dict) -> dict:
    from core import look_builder as lb
    cols = d.get("colours")
    if not isinstance(cols, list) or not cols or len(cols) > 64:
        raise LibraryError("a palette needs 1–64 colours")
    clean = []
    for c in cols:
        if not isinstance(c, dict) or not c.get("hex"):
            raise LibraryError("a colour of the palette is not valid")
        try:
            cc = lb.colour(c)
        except (ValueError, TypeError):
            raise LibraryError("a colour of the palette is not valid")
        clean.append({"name": cc["name"], "hex": cc["hex"], **({"white": cc["white"]} if cc["white"] else {})})
    return {"name": d.get("name"), "colours": clean}


def _check_look_preset(d: dict) -> dict:
    from core import look_builder as lb
    clean = {"name": d.get("name")}
    clean.update({k: d[k] for k in lb.PRESET_KEYS if k in d and d[k] not in (None, "")})
    try:
        lb.chaser_spec(clean)
    except Exception as e:                         # the builder's own validation
        raise LibraryError(f"the preset is not valid ({e})")
    return clean


def _check_nomenclature(d: dict) -> dict:
    fmt = str(d.get("format") or "{name}")
    if "{name}" not in fmt or set(re.findall(r"\{(\w*)\}", fmt)) - {"group", "effect", "name"}:
        raise LibraryError("the format may only use {group}, {effect} and {name}, and must contain {name}")
    if not _size_ok(d, 64 * 1024):
        raise LibraryError("the profile is too large")
    return {k: d[k] for k in ("id", "label", "description", "format", "groups", "effects", "category_group",
                              "effect_letters", "prefix_captions", "auto_group_letter") if k in d}


def _check_vc_style(d: dict) -> dict:
    from core.quick_start import vc_style as vs
    try:
        vs.VCStyle(d)
    except (ValueError, TypeError):
        raise LibraryError("the style has values that are not numbers")
    return {k: d[k] for k in vs.DEFAULTS if k in d}


def _check_show_profile(d: dict) -> dict:
    from core import profile as prof, recipe
    if d.get("format") != prof.FORMAT:
        raise LibraryError("not a Swiss Knife Show Profile")
    if not _size_ok(d, 4 * 1024 * 1024):
        raise LibraryError("the profile is too large")
    steps = d.get("steps") or []
    if not isinstance(steps, list) or (not steps and not d.get("start")):
        raise LibraryError("the profile does nothing (no steps, no rig)")
    for i, st in enumerate(steps, 1):
        if not isinstance(st, dict) or not recipe.recordable(str(st.get("method")), str(st.get("path"))):
            raise LibraryError(f"step {i} calls '{st.get('path') if isinstance(st, dict) else '?'}', "
                               "which a profile may not do")
    clean = copy.deepcopy(d)
    clean.pop("_path", None)
    return clean


_CHECKS = {"vc_template": _check_vc_template, "palette": _check_palette, "look_preset": _check_look_preset,
           "nomenclature": _check_nomenclature, "vc_style": _check_vc_style, "show_profile": _check_show_profile}


def _reserved(kind: str, name: str) -> bool:
    """Is *name* taken by a built-in item (never replaced)?"""
    low = name.lower()
    if kind == "palette":
        from core import look_builder as lb
        return any(low in (k.lower(), (v.get("label") or "").lower())
                   for k, v in lb._load_json("palettes.json")["palettes"].items())
    if kind == "look_preset":
        from core import look_builder as lb
        return any(p["name"].lower() == low for p in lb._load_json("presets.json")["presets"])
    if kind == "nomenclature":
        from core.quick_start import nomenclature as nm
        return any(p["builtin"] and (p["id"].lower() == low or p["label"].lower() == low) for p in nm.list_profiles())
    if kind == "vc_style":
        from core.quick_start import vc_style as vs
        return any(p["builtin"] and (p["id"].lower() == low or p["label"].lower() == low) for p in vs.list_styles())
    return False


# ─────────────────────────────────────────────────────────────────────────────
# read + preview
# ─────────────────────────────────────────────────────────────────────────────

def read_pack(path_or_text) -> dict:
    """Read and *structurally* check a pack (file path, JSON text or a dict).
    Items are validated one by one in :func:`preview`."""
    if isinstance(path_or_text, dict):
        pack = path_or_text
    else:
        text = path_or_text
        if os.path.isfile(str(path_or_text)):
            if os.path.getsize(path_or_text) > MAX_FILE:
                raise LibraryError("The file is larger than 8 MB — too big for a library pack.")
            with open(path_or_text, encoding="utf-8") as fh:
                text = fh.read()
        try:
            pack = json.loads(text)
        except (ValueError, TypeError):
            raise LibraryError("This is not a Swiss Knife library file (not JSON).")
    if not isinstance(pack, dict) or pack.get("format") != FORMAT:
        raise LibraryError("This is not a Swiss Knife library file.")
    items = pack.get("items")
    if not isinstance(items, list) or not items:
        raise LibraryError("The library file holds no items.")
    if len(items) > MAX_ITEMS:
        raise LibraryError(f"More than {MAX_ITEMS} items — refused.")
    return pack


def preview(pack: dict) -> dict:
    """``{title, author, description, swiss_knife, items: [{index, kind, name, summary, status, reason, warning}]}``.

    status: ``new`` · ``same`` (you have exactly this) · ``exists`` (the name is taken by a
    different one) · ``reserved`` (a built-in name) · ``invalid`` (reason says why)."""
    rows = []
    mine_cache: Dict[str, Dict[str, dict]] = {}
    seen = set()
    for i, it in enumerate(pack.get("items") or []):
        row = {"index": i, "kind": (it or {}).get("kind"), "name": "", "summary": "", "status": "invalid",
               "reason": "", "warning": ""}
        try:
            if not isinstance(it, dict) or it.get("kind") not in _KIND_IDS:
                raise LibraryError(f"unknown kind '{(it or {}).get('kind') if isinstance(it, dict) else it}'")
            kind = it["kind"]
            name = _name(it.get("name"))
            row["name"] = name
            data = it.get("data")
            if not isinstance(data, dict):
                raise LibraryError("the item has no content")
            clean = _CHECKS[kind]({**data, "name": data.get("name") or name} if kind != "show_profile" else data)
            row["summary"] = _summary(kind, clean)
            if (kind, name.lower()) in seen:
                raise LibraryError("the same name appears twice in the file")
            seen.add((kind, name.lower()))
            mine = mine_cache.setdefault(kind, {k.lower(): v for k, v in _own(kind).items()})
            have = mine.get(name.lower())
            if _reserved(kind, name):
                row["status"], row["reason"] = "reserved", "this name belongs to a built-in item"
            elif have is None:
                row["status"] = "new"
            elif json.dumps(_CHECKS[kind]({**have, "name": have.get("name") or name} if kind != "show_profile" else have),
                            sort_keys=True) == json.dumps(clean, sort_keys=True):
                row["status"] = "same"
            else:
                row["status"] = "exists"
            if kind == "show_profile" and _has_path(clean):
                row["warning"] = "it names a folder of the computer it was made on — steps that read those files will be skipped"
        except LibraryError as e:
            row["status"], row["reason"] = "invalid", str(e)
        rows.append(row)
    return {"title": str(pack.get("title") or ""), "author": str(pack.get("author") or ""),
            "description": str(pack.get("description") or ""), "swiss_knife": str(pack.get("swiss_knife") or ""),
            "items": rows}


# ─────────────────────────────────────────────────────────────────────────────
# install
# ─────────────────────────────────────────────────────────────────────────────

def _free_name(kind: str, name: str) -> str:
    taken = {k.lower() for k in _own(kind)}
    if name.lower() not in taken and not _reserved(kind, name):
        return name
    n = 2
    while f"{name} ({n})".lower() in taken or _reserved(kind, f"{name} ({n})"):
        n += 1
    return f"{name} ({n})"


def _write_item(kind: str, name: str, clean: dict) -> None:
    if kind == "vc_template":
        from core import vc_builder
        os.makedirs(vc_builder.templates_dir(), exist_ok=True)
        with open(os.path.join(vc_builder.templates_dir(), vc_builder._slug(name) + ".json"), "w",
                  encoding="utf-8") as fh:
            json.dump({**clean, "name": name}, fh, indent=1)
    elif kind == "palette":
        from core import look_builder as lb
        lb.save_palette(name, clean["colours"])
    elif kind == "look_preset":
        from core import look_builder as lb
        lb.save_preset({**clean, "name": name})
    elif kind in ("nomenclature", "vc_style"):
        if kind == "nomenclature":
            from core.quick_start import nomenclature as nm
            folder = nm.user_dir()
        else:
            from core.quick_start import vc_style as vs
            folder = vs.user_dir()
        slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:60] or "item"
        os.makedirs(folder, exist_ok=True)
        # the id must not clash with a built-in: user items are known by their own slug
        with open(os.path.join(folder, slug + ".json"), "w", encoding="utf-8") as fh:
            json.dump({**clean, "id": slug, "label": name}, fh, indent=1, ensure_ascii=False)
    elif kind == "show_profile":
        from core import profile as prof
        prof.save({**clean, "name": name})


def install(pack: dict, choices: Optional[Dict[str, str]] = None, default: str = "skip") -> dict:
    """Install the items.  *choices*: ``{"<index>": "skip" | "replace" | "copy"}`` for items
    that already exist (and "skip" leaves a new one out); *default* is used for the others.  New items are installed unless left out;
    ``same`` / ``reserved`` / ``invalid`` never are (reserved ones can be kept with *copy*).

    Returns ``{installed, replaced, copied, skipped, refused, items: [{index, kind, name, result, as?}]}``."""
    if default not in ("skip", "replace", "copy"):
        raise LibraryError("The default must be skip, replace or copy.")
    choices = choices or {}
    pv = preview(pack)
    done, counts = [], {"installed": 0, "replaced": 0, "copied": 0, "skipped": 0, "refused": 0}
    for row in pv["items"]:
        i, kind, name, st = row["index"], row["kind"], row["name"], row["status"]
        pick = choices.get(str(i), default)
        if pick not in ("skip", "replace", "copy"):
            raise LibraryError(f"Unknown choice '{pick}' for item {i}.")
        entry = {"index": i, "kind": kind, "name": name}
        if st == "invalid":
            entry["result"], entry["reason"] = "refused", row["reason"]
            counts["refused"] += 1
        elif st == "same":
            entry["result"] = "skipped"
            entry["reason"] = "you already have it"
            counts["skipped"] += 1
        else:
            it = pack["items"][i]
            data = it["data"]
            clean = _CHECKS[kind]({**data, "name": data.get("name") or name} if kind != "show_profile" else data)
            if st == "new" and choices.get(str(i)) == "skip":
                entry["result"], entry["reason"] = "skipped", "you left it out"
                counts["skipped"] += 1
            elif st == "new":
                _write_item(kind, name, clean)
                entry["result"] = "installed"
                counts["installed"] += 1
            elif pick == "skip":
                entry["result"] = "skipped"
                entry["reason"] = "kept yours" if st == "exists" else row["reason"]
                counts["skipped"] += 1
            elif pick == "replace" and st == "exists":
                _write_item(kind, name, clean)
                entry["result"] = "replaced"
                counts["replaced"] += 1
            else:                                      # copy (also for a reserved name, and replace on reserved)
                new = _free_name(kind, f"{name}" if st == "reserved" else name)
                if new.lower() == name.lower():
                    new = _free_name(kind, name + " (shared)")
                _write_item(kind, new, clean)
                entry["result"], entry["as"] = "copied", new
                counts["copied"] += 1
        done.append(entry)
    return {**counts, "items": done}
