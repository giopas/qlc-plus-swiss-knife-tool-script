"""
core/stage_monitor.py — Stage Monitor (3.5.0)
=============================================

A page for a tablet on stage that shows where the setlist is: the current
cue, big, and the next one.  Swiss Knife works at *design time* only:

* :func:`cuelists` reads every Virtual Console CueList of the show (frame
  path, page, chaser, steps with their names and notes, MIDI and key
  bindings).  The show is only read, never changed.
* :func:`reconcile` matches a saved configuration to the show by widget ID:
  what disappeared, what is new.
* :func:`build_page` makes one self-contained ``index.html`` (configuration
  and cue names inlined, no outside resources).
* :func:`export` writes the page and ``serve_stage.py`` into a folder.
* :class:`StageServer` serves that folder on the local network.

At *run time* the page talks to QLC+ directly over its web socket
(``ws://<host>:9999/qlcplusWS``, QLC+ started with ``-w``); Swiss Knife never
relays.  The protocol is in ``docs/STAGE_MONITOR_PROTOCOL.md``.

Standard library only.
"""

from __future__ import annotations

import copy
import ipaddress
import json
import os
import platform
import re
import socket
import subprocess  # nosec B404 — fixed commands, no shell, for the IP list
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_TEMPLATE = os.path.join(_HERE, "stage_page", "page.html")
SERVE_SCRIPT = os.path.join(_HERE, "stage_page", "serve_stage.py")

EXPORT_DIR = "stage_monitor"
SIDECAR_SUFFIX = ".stage.json"
CONFIG_VERSION = 1
FONT_SCALES = ("S", "M", "L", "XL")
THEMES = ("dark", "contrast", "black", "dim")   # black: white song on black; dim: grey song on black
MODES = ("read", "control")
HOLD_CHOICES = (0, 300, 600, 1000, 1500)   # ms a Control button must be held; 0 = a tap acts
STOP_HOLD_MIN = 1200                       # Stop needs at least this, and twice the hold
DEFAULT_WS_PORT = 9999
DEFAULT_HTTP_PORT = 8080

DEFAULTS = {
    "version": CONFIG_VERSION,
    "title": "",
    "font": "M",
    "theme": "dark",
    "show_next": True,
    "show_clock": True,
    "show_numbers": True,
    "show_notes": True,       # the step notes of the CueList, under each name
    "hold_ms": 600,           # Control mode: hold Previous / Next this long (0: a tap acts)
    "ws_port": DEFAULT_WS_PORT,
    "http_port": DEFAULT_HTTP_PORT,
    "lists": [],          # [{id, label, mode, steps: {"<index>": {hide, label}}}] in display order
}

_CONTAINERS = ("Frame", "SoloFrame")
_BINDINGS = (("Next", "next"), ("Previous", "previous"), ("Playback", "play"),
             ("Stop", "stop"))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el, name: str):
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _children(el, name: str):
    return [c for c in el if _local(c.tag) == name]


# ── reading the show ─────────────────────────────────────────────────────────

def _functions(root) -> Dict[str, object]:
    out = {}
    for el in root.iter():
        if _local(el.tag) == "Function" and el.get("ID") is not None and el.get("Type"):
            out[el.get("ID")] = el
    return out


def _page_names(frame) -> Dict[int, str]:
    """Names of a multipage frame's pages (``<Shortcut Page= Name=>``)."""
    names = {}
    for sc in _children(frame, "Shortcut"):
        try:
            names[int(sc.get("Page", ""))] = sc.get("Name") or ""
        except ValueError:
            pass
    return names


def _bindings(cl) -> Dict[str, List[str]]:
    """The keys and external inputs on a CueList's controls, as text."""
    out = {}
    for tag, key in _BINDINGS:
        el = _child(cl, tag)
        if el is None:
            continue
        found = []
        for inp in _children(el, "Input"):
            try:
                found.append(f"MIDI U{int(inp.get('Universe', 0)) + 1} ch {int(inp.get('Channel', 0))}")   # as Show Paperwork writes it
            except ValueError:
                pass
        for k in _children(el, "Key"):
            if (k.text or "").strip():
                found.append(f"key {k.text.strip()}")
        if found:
            out[key] = found
    return out


def cuelists(root) -> List[dict]:
    """Every CueList widget of the Virtual Console, in document order.

    Each item: ``id``, ``caption``, ``path`` (captions of the frames around
    it, the console page first), ``page`` (console page, 0-based),
    ``frame_page`` (page inside the nearest multipage frame, with its name,
    or ``None``), ``chaser`` (``{id, name}`` or ``None``), ``steps``
    (``[{index, fid, name, note}]``), ``layout`` (``stop`` or ``pause``) and ``inputs``.
    """
    vc = None
    for el in root.iter():
        if _local(el.tag) == "VirtualConsole":
            vc = el
            break
    if vc is None:
        return []
    funcs = _functions(root)
    out: List[dict] = []

    def walk(el, path: List[str], page: int, fpage):
        for ch in el:
            tag = _local(ch.tag)
            here = fpage
            # a widget in a multipage frame carries Page="n" (QLC+ 5)
            if ch.get("Page") is not None and _child(el, "Multipage") is not None:
                try:
                    n = int(ch.get("Page"))
                    here = {"page": n, "name": _page_names(el).get(n, "")}
                except ValueError:
                    pass
            if tag in _CONTAINERS:
                walk(ch, path + [ch.get("Caption") or tag], page, here)
            elif tag == "CueList":
                out.append(_one(ch, path, page, here, funcs))

    pages = [c for c in vc if _local(c.tag) in _CONTAINERS]
    for i, pg in enumerate(pages):
        walk(pg, [pg.get("Caption") or f"Page {i + 1}"], i, None)
    return out


def _layout(cl) -> str:
    """What the CueList's second button does: ``stop`` (QLC+'s default, Play/Pause/Stop)
    or ``pause`` (layout Play/Stop/Pause, saved as ``<PlaybackLayout>1``)."""
    el = _child(cl, "PlaybackLayout")
    return "pause" if el is not None and (el.text or "").strip() == "1" else "stop"


def _one(cl, path, page, fpage, funcs) -> dict:
    cid = (_child(cl, "Chaser").text or "").strip() if _child(cl, "Chaser") is not None else ""
    ch = funcs.get(cid)
    steps = []
    if ch is not None:
        raw = _children(ch, "Step")
        raw.sort(key=lambda s: int(s.get("Number", "0")) if (s.get("Number") or "0").isdigit() else 0)
        for i, st in enumerate(raw):
            fid = (st.text or "").strip()
            fn = funcs.get(fid)
            steps.append({"index": i, "fid": fid,
                          "name": fn.get("Name", "") if fn is not None else f"Function {fid}",
                          "note": st.get("Note") or ""})
    return {
        "id": cl.get("ID") or "",
        "caption": cl.get("Caption") or "",
        "path": list(path),
        "page": page,
        "frame_page": fpage,
        "chaser": {"id": cid, "name": ch.get("Name", "")} if ch is not None else None,
        "steps": steps,
        "layout": _layout(cl),
        "inputs": _bindings(cl),
    }


# ── configuration ────────────────────────────────────────────────────────────

def sidecar_path(qxw_path: str) -> str:
    """``<show>.stage.json`` next to the show, without the ``_vN`` suffix, so
    every version of the show shares one configuration."""
    folder = os.path.dirname(os.path.abspath(qxw_path))
    stem = os.path.splitext(os.path.basename(qxw_path))[0]
    stem = re.sub(r"_v\d+$", "", stem)
    return os.path.join(folder, stem + SIDECAR_SUFFIX)


def _port(v, default: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return n if 1 <= n <= 65535 else default


# ── song cards (3.9.0) ───────────────────────────────────────────────────────

CARD_LIMITS = (("tuning", 40), ("starts", 80), ("note", 200))   # text fields and their length
MAX_PLAYERS = 8
BPM_MIN, BPM_MAX = 20, 400
ROLES = ("commander", "vocals", "band")   # the three layouts of the page; a view of your own picks one
FIELD_KEYS = ("tuning", "bpm", "starts", "players", "note")   # what a card can show
MAX_VIEWS = 12
DEFAULT_VIEWS = (
    {"id": "commander", "label": "Commander", "layout": "commander", "fields": list(FIELD_KEYS), "who": ""},
    {"id": "band", "label": "Band", "layout": "band", "fields": list(FIELD_KEYS), "who": ""},
    {"id": "vocals", "label": "Vocals", "layout": "vocals", "fields": ["bpm", "note"], "who": ""},
)
_SLUG = re.compile(r"[^a-z0-9]+")
_NAME_BPM = re.compile(r"[·•\-–—|]\s*(\d{2,3}(?:[.,]\d)?)\s*bpm\s*$", re.I)


def clean_card(card) -> dict:
    """A song card with only what is set: ``tuning``, ``starts`` (who starts and how),
    ``note``, ``bpm`` (a tempo of your own, 20 to 400) and ``players``
    (``[{who, note}]``, up to eight: a pedal or FX setting for a player).
    Empty fields are left out, so an unused card is ``{}``."""
    if not isinstance(card, dict):
        return {}
    out: dict = {}
    for key, n in CARD_LIMITS:
        v = str(card.get(key) or "").strip()[:n]
        if v:
            out[key] = v
    try:
        bpm = int(round(float(str(card.get("bpm")).replace(",", "."))))
    except (TypeError, ValueError):
        bpm = 0
    if BPM_MIN <= bpm <= BPM_MAX:
        out["bpm"] = bpm
    players = []
    for p in card.get("players") or []:
        if not isinstance(p, dict):
            continue
        who, note = str(p.get("who") or "").strip()[:30], str(p.get("note") or "").strip()[:80]
        if who or note:
            players.append({"who": who, "note": note})
    if players:
        out["players"] = players[:MAX_PLAYERS]
    return out


def tempo_from_name(name: str) -> Optional[int]:
    """The tempo in a step name made by Apply tempo (``Song · 128 BPM``), or ``None``."""
    m = _NAME_BPM.search(name or "")
    if not m:
        return None
    try:
        v = int(round(float(m.group(1).replace(",", "."))))
    except ValueError:
        return None
    return v if BPM_MIN <= v <= BPM_MAX else None


def clean_views(views) -> list:
    """The views by role (3.9.0): ``[{id, label, layout, fields, who}]``.

    *id* is what goes after ``?role=`` in the address (lower case letters, digits and
    dashes), *layout* one of ``ROLES`` (how the page is arranged: ``commander`` has the
    buttons, ``band`` a small cue list and a big card, ``vocals`` the card alone),
    *fields* what the card shows and *who* a player whose line is the only one shown.
    At most ``MAX_VIEWS``; a repeated id is dropped."""
    out, seen = [], set()
    for v in views if isinstance(views, list) else []:
        if not isinstance(v, dict):
            continue
        label = str(v.get("label") or "").strip()[:30]
        vid = _SLUG.sub("-", str(v.get("id") or label).lower()).strip("-")[:20]
        if not vid or vid in seen:
            continue
        seen.add(vid)
        fields = v.get("fields")
        out.append({"id": vid, "label": label or vid,
                    "layout": v.get("layout") if v.get("layout") in ROLES else "band",
                    "fields": [f for f in FIELD_KEYS if f in (fields if isinstance(fields, list) else [])],
                    "who": str(v.get("who") or "").strip()[:30]})
        if len(out) >= MAX_VIEWS:
            break
    return out


def views_of(cfg: Optional[dict]) -> list:
    """The views of a configuration: its own, or the three that come with the page."""
    own = (cfg or {}).get("views")
    return clean_views(own) if isinstance(own, list) else copy.deepcopy(list(DEFAULT_VIEWS))


def _base(name: str) -> str:
    """A song name without the tempo Apply tempo adds ("Song · 128 BPM"), for matching."""
    return _NAME_BPM.sub("", str(name or "")).strip().casefold()


def match_steps(names: List[List[str]], steps: List[dict]) -> list:
    """The step of a cue list for each song of a setlist, or ``None``.

    *names*: per song, the names it may go by (the setlist's name, the function's name).
    Songs are matched by name, in order, each step once; when no song matched at all and
    both lists have the same length, by position (a setlist applied to the show in order)."""
    out: list = [None] * len(names)
    used: set = set()
    by_name: Dict[str, List[int]] = {}
    for i, st in enumerate(steps):
        by_name.setdefault(_base(st.get("name")), []).append(i)
    for n, alts in enumerate(names):
        for alt in alts:
            hit = next((i for i in by_name.get(_base(alt), []) if i not in used), None)
            if hit is not None:
                out[n] = steps[hit]
                used.add(hit)
                break
    if not any(out) and len(names) == len(steps):
        out = list(steps)
    return out


def clean_config(cfg: Optional[dict]) -> dict:
    """A configuration with every key, values checked; unknown keys dropped."""
    cfg = cfg if isinstance(cfg, dict) else {}
    out = copy.deepcopy(DEFAULTS)
    out["title"] = str(cfg.get("title") or "")[:120]
    out["font"] = cfg.get("font") if cfg.get("font") in FONT_SCALES else "M"
    out["theme"] = cfg.get("theme") if cfg.get("theme") in THEMES else "dark"
    for k in ("show_next", "show_clock", "show_numbers", "show_notes"):
        if k in cfg:
            out[k] = bool(cfg[k])
    try:
        hold = int(cfg.get("hold_ms", DEFAULTS["hold_ms"]))
    except (TypeError, ValueError):
        hold = DEFAULTS["hold_ms"]
    out["hold_ms"] = hold if hold in HOLD_CHOICES else DEFAULTS["hold_ms"]
    out["ws_port"] = _port(cfg.get("ws_port"), DEFAULT_WS_PORT)
    out["http_port"] = _port(cfg.get("http_port"), DEFAULT_HTTP_PORT)
    if isinstance(cfg.get("views"), list):          # absent: the three that come with the page
        out["views"] = clean_views(cfg["views"])
    seen = set()
    for item in cfg.get("lists") or []:
        if not isinstance(item, dict):
            continue
        wid = str(item.get("id") or "").strip()
        if not wid.isdigit() or wid in seen:
            continue
        seen.add(wid)
        steps = {}
        for k, v in (item.get("steps") or {}).items():
            if str(k).isdigit() and isinstance(v, dict):
                s = {}
                if v.get("hide"):
                    s["hide"] = True
                if str(v.get("label") or "").strip():
                    s["label"] = str(v["label"]).strip()[:120]
                card = clean_card(v.get("card"))
                if card:
                    s["card"] = card
                if s:
                    steps[str(int(k))] = s
        out["lists"].append({
            "id": wid,
            "label": str(item.get("label") or "").strip()[:80],
            "mode": item.get("mode") if item.get("mode") in MODES else "read",
            "steps": steps,
        })
    return out


def load_config(path: str) -> Optional[dict]:
    """The saved configuration, or ``None`` when there is none (or unreadable)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return clean_config(json.load(fh))
    except (OSError, ValueError):
        return None


def save_config(cfg: dict, path: str) -> str:
    """Write the configuration (pretty, keys sorted, so it diffs well)."""
    data = json.dumps(clean_config(cfg), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(data)
    os.replace(tmp, path)
    return path


def default_config(lists: List[dict], title: str = "") -> dict:
    """A first configuration: the show's first CueList, read-only."""
    cfg = clean_config({"title": title})
    if lists:
        cfg["lists"] = [{"id": lists[0]["id"], "label": "", "mode": "read", "steps": {}}]
    return cfg


def reconcile(cfg: dict, lists: List[dict]) -> dict:
    """Match a configuration to the show by widget ID.

    Returns ``{config, missing, new}``: the configuration without the lists
    that are gone, the gone ones (``[{id, label}]``) and the show's CueLists
    the configuration does not mention yet (``[id]``).  Step settings beyond
    a list's last step are dropped.
    """
    cfg = clean_config(cfg)
    by_id = {c["id"]: c for c in lists}
    kept, missing = [], []
    for item in cfg["lists"]:
        cl = by_id.get(item["id"])
        if cl is None:
            missing.append({"id": item["id"], "label": item["label"]})
            continue
        n = len(cl["steps"])
        item["steps"] = {k: v for k, v in item["steps"].items() if int(k) < n}
        kept.append(item)
    cfg["lists"] = kept
    known = {i["id"] for i in kept} | {m["id"] for m in missing}
    return {"config": cfg, "missing": missing,
            "new": [c["id"] for c in lists if c["id"] not in known]}


# ── the page ─────────────────────────────────────────────────────────────────

# The words on the stage page; translated at export from ``static/i18n``.
PAGE_STRINGS = (
    "Stage Monitor", "Connecting…", "Connected", "Not connected", "retry in", "Unknown",
    "Not in the show QLC+ has open", "Playing", "Paused", "Stopped", "NEXT", "Previous", "Next",
    "hold", "Stop", "Pause", "Resume", "hold longer", "Not connected to QLC+",
    "Start QLC+ with web access (qlcplus -w). Trying again by itself.",
    "No cue list chosen. Choose one in Swiss Knife and export again.",
    "Every step of this list is hidden.", "Close",
    "NEXT UP", "TUNING CHANGE", "Tuning", "Tempo", "Starts", "Note", "BPM",
)
LANGS = ("en", "it", "fr", "de", "es", "pt", "ja", "zh")
_I18N = os.path.join(os.path.dirname(_HERE), "static", "i18n")


def page_strings(lang: str) -> Dict[str, str]:
    """The page's words in *lang* (English when there is no translation)."""
    if lang not in LANGS or lang == "en":
        return {}
    try:
        with open(os.path.join(_I18N, f"{lang}.json"), encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: d[k] for k in PAGE_STRINGS if isinstance(d.get(k), str) and d[k].strip()}


def page_data(cfg: dict, lists: List[dict], lang: str = "en") -> dict:
    """What the page needs, nothing more: titles, labels and step names."""
    cfg = reconcile(cfg, lists)["config"]
    by_id = {c["id"]: c for c in lists}
    out_lists = []
    for item in cfg["lists"]:
        cl = by_id[item["id"]]
        steps = []
        last_tuning = ""                       # the tuning of the song before, to show a change
        for st in cl["steps"]:
            s = item["steps"].get(str(st["index"]), {})
            row = {"i": st["index"], "name": s.get("label") or st["name"],
                   "note": st["note"], "hide": bool(s.get("hide"))}
            card = dict(s.get("card") or {})
            bpm = card.get("bpm") or tempo_from_name(st["name"])
            if bpm:
                card["bpm"] = bpm
            if card:
                row["card"] = card
            if not row["hide"] and card.get("tuning"):
                if last_tuning and card["tuning"] != last_tuning:
                    row["tc"] = {"from": last_tuning, "to": card["tuning"]}
                last_tuning = card["tuning"]
            steps.append(row)
        out_lists.append({"id": int(item["id"]),
                          "label": item["label"] or cl["caption"] or (cl["chaser"] or {}).get("name") or f"Cue list {item['id']}",
                          "mode": item["mode"], "layout": cl.get("layout", "stop"), "steps": steps})
    return {"title": cfg["title"], "font": cfg["font"], "theme": cfg["theme"],
            "showNext": cfg["show_next"], "showClock": cfg["show_clock"],
            "showNumbers": cfg["show_numbers"], "showNotes": cfg["show_notes"], "holdMs": cfg["hold_ms"],
            "stopHoldMs": max(STOP_HOLD_MIN, 2 * cfg["hold_ms"]), "wsPort": cfg["ws_port"],
            "views": views_of(cfg), "lists": out_lists, "lang": lang if lang in LANGS else "en", "t": page_strings(lang)}


def _inline_json(data: dict) -> str:
    """JSON safe inside ``<script>``: no ``</script>``, no ``<!--``."""
    s = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") \
        .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def build_page(cfg: dict, lists: List[dict], lang: str = "en") -> str:
    """The self-contained ``index.html`` (deterministic for the same input)."""
    data = page_data(cfg, lists, lang)
    with open(PAGE_TEMPLATE, encoding="utf-8") as fh:
        tpl = fh.read()
    title = data["title"] or data["t"].get("Stage Monitor", "Stage Monitor")
    return tpl.replace("/*__CONFIG__*/null", _inline_json(data)).replace("__TITLE__", _esc(title))


MARK = "QLC+ Swiss Knife"     # in the page, serve_stage.py and the launchers


def is_own_file(path: str) -> bool:
    """True when *path* is a page or server the Stage Monitor wrote (it may replace those)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(4096)
        return MARK in head and "Stage Monitor" in head
    except OSError:
        return False


# Double-click to serve the folder: macOS, Windows, Linux.
LAUNCHERS = ("Start Stage Monitor.command", "Start Stage Monitor.bat", "start-stage-monitor.sh")


class ReplaceNeeded(Exception):
    """The folder already holds a page from an earlier export: replacing it needs a yes."""

    def __init__(self, files: List[str]):
        super().__init__("The folder already has a Stage Monitor page: " + ", ".join(files))
        self.files = files


def export_files(folder: str) -> List[str]:
    """The files an export writes that already exist in *folder* (names)."""
    names = ["index.html", "serve_stage.py"] + list(LAUNCHERS)
    return [n for n in names if os.path.exists(os.path.join(folder, n))]


def export(folder: str, cfg: dict, lists: List[dict], lang: str = "en", show_path: str = "",
           replace: bool = False) -> dict:
    """Write ``index.html``, ``serve_stage.py`` and the "Start Stage Monitor"
    launchers into *folder* (created if needed).  *show_path* is named in the
    hint the server prints when QLC+ is not reachable.

    This is the one place Swiss Knife writes over files: a page and server the
    Stage Monitor wrote earlier.  It refuses files it did not write
    (``ValueError``) and replaces its own only with ``replace=True``
    (``ReplaceNeeded`` otherwise, so the caller can ask).  Returns the paths
    written and ``replaced``, the names that existed before."""
    cfg = clean_config(cfg)
    if not cfg["lists"]:
        raise ValueError("Tick at least one cue list.")
    page = os.path.join(folder, "index.html")
    script = os.path.join(folder, "serve_stage.py")
    launchers = [os.path.join(folder, n) for n in LAUNCHERS]
    for p in [page, script] + launchers:     # replace only what the Stage Monitor wrote itself
        if os.path.exists(p) and not is_own_file(p):
            raise ValueError(f"{os.path.basename(p)} in that folder was not made by the Stage Monitor. "
                             "Choose another folder.")
    existing = export_files(folder)
    if existing and not replace:
        raise ReplaceNeeded(existing)
    os.makedirs(folder, exist_ok=True)
    with open(page, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_page(cfg, lists, lang))
    with open(SERVE_SCRIPT, encoding="utf-8") as src:
        body = (src.read().replace("DEFAULT_PORT = 8080", f"DEFAULT_PORT = {cfg['http_port']}")
                .replace("QLC_PORT = 9999", f"QLC_PORT = {cfg['ws_port']}")
                .replace('SHOW = ""', f"SHOW = {json.dumps(show_path or '')}"))
    with open(script, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    for name, dest in zip(LAUNCHERS, launchers):     # double-click to start the server at the gig
        with open(os.path.join(_HERE, "stage_page", name), "rb") as src, open(dest, "wb") as fh:
            fh.write(src.read())
    for p in [script] + [d for d in launchers if not d.endswith(".bat")]:
        try:
            os.chmod(p, 0o755)
        except OSError:
            pass
    return {"folder": folder, "page": page, "script": script, "launchers": launchers, "replaced": existing}


# ── the network ──────────────────────────────────────────────────────────────

_IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")


def _usable(ip: str) -> bool:
    try:
        a = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return not (a.is_loopback or a.is_unspecified or a.is_multicast or a.is_link_local
                or ip.endswith(".255"))


def parse_addresses(text: str, system: str) -> List[str]:
    """IPv4 addresses of this computer from ``ifconfig`` (macOS),
    ``ip -4 addr`` (Linux) or ``ipconfig`` (Windows) output."""
    found = []
    for line in text.splitlines():
        low = line.lower()
        if system == "Windows":
            if "ipv4" not in low:
                continue
        else:
            if "inet " not in low:
                continue
            line = line.split("inet ", 1)[1].split()[0].split("/")[0]
        for ip in _IPV4.findall(line):
            if _usable(ip) and ip not in found:
                found.append(ip)
                break
    return found


def local_addresses() -> List[str]:
    """This computer's IPv4 addresses on the local networks (best first:
    private addresses, the Internet Sharing / hotspot ones on top)."""
    system = platform.system()
    cmd = {"Darwin": ["ifconfig"], "Linux": ["ip", "-4", "addr"],
           "Windows": ["ipconfig"]}.get(system, ["ifconfig"])
    ips: List[str] = []
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)  # nosec B603
        ips = parse_addresses(res.stdout or "", system)
    except (OSError, subprocess.SubprocessError):
        ips = []
    if not ips:
        try:   # the address the system would use to go out; sends nothing (UDP)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
                if _usable(ip):
                    ips.append(ip)
        except OSError:
            pass
    hotspot = ("192.168.2.", "10.42.0.", "192.168.137.")

    def rank(ip):
        return (0 if ip.startswith(hotspot) else 1 if ipaddress.IPv4Address(ip).is_private else 2)
    return sorted(ips, key=rank)


class _Quiet(SimpleHTTPRequestHandler):
    def handle_one_request(self):
        # A browser asking for https:// sends a TLS handshake (0x16) that plain http cannot
        # answer; remember who, so the screen can say "type http://".
        try:
            first = self.rfile.peek(1)[:1]
        except (OSError, ValueError):
            first = b""
        if first == b"\x16":
            owner = getattr(self.server, "owner", None)
            if owner is not None:
                owner.https_from = self.client_address[0]
            self.close_connection = True
            return
        super().handle_one_request()

    def log_message(self, *_a):   # no request log in Swiss Knife's console
        pass

    # 3.9.7: the tablet is on the LAN, so it gets the page and nothing else: not the other files of the
    # folder (the show, the settings, the launcher), no directory listing, no files behind a symlink.
    PAGE_PATHS = ("/", "/index.html")

    def send_head(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path not in self.PAGE_PATHS:
            self.send_error(404, "Not found")
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
                         "connect-src ws: wss: http:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        super().end_headers()


class StageServer:
    """A static server for the export folder, in a background thread."""

    def __init__(self):
        self._srv: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.folder = ""
        self.port = 0
        self.error = ""
        self.https_from = ""      # a device that asked for https:// (cannot work)

    @property
    def running(self) -> bool:
        return self._srv is not None

    def start(self, folder: str, port: int, host: str = "0.0.0.0") -> None:  # nosec B104 — the tablet is on the LAN
        """Serve *folder* on *port*; stops a server already running first."""
        if not os.path.isfile(os.path.join(folder, "index.html")):
            raise ValueError("Export the page first: there is no index.html in that folder.")
        self.stop()

        def handler(*a, **k):
            return _Quiet(*a, directory=folder, **k)
        try:
            srv = ThreadingHTTPServer((host, port), handler)
        except OSError as e:
            self.error = f"Port {port} is busy or not allowed ({e.strerror or e})."
            raise ValueError(self.error) from e
        srv.daemon_threads = True
        srv.owner = self
        self._srv, self.folder, self.port, self.error, self.https_from = srv, folder, port, "", ""
        self._thread = threading.Thread(target=srv.serve_forever, name="stage-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        srv, self._srv = self._srv, None
        if srv is not None:
            srv.shutdown()
            srv.server_close()
        self._thread = None

    def status(self) -> dict:
        ips = local_addresses()
        return {"running": self.running, "folder": self.folder, "port": self.port,
                "error": self.error, "addresses": ips, "https_from": self.https_from,
                "urls": [f"http://{ip}:{self.port}/" for ip in ips] if self.running else []}


server = StageServer()
