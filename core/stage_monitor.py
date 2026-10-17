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
    (``[{index, fid, name, note}]``) and ``inputs``.
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


def clean_config(cfg: Optional[dict]) -> dict:
    """A configuration with every key, values checked; unknown keys dropped."""
    cfg = cfg if isinstance(cfg, dict) else {}
    out = copy.deepcopy(DEFAULTS)
    out["title"] = str(cfg.get("title") or "")[:120]
    out["font"] = cfg.get("font") if cfg.get("font") in FONT_SCALES else "M"
    out["theme"] = cfg.get("theme") if cfg.get("theme") in THEMES else "dark"
    for k in ("show_next", "show_clock", "show_numbers"):
        if k in cfg:
            out[k] = bool(cfg[k])
    out["ws_port"] = _port(cfg.get("ws_port"), DEFAULT_WS_PORT)
    out["http_port"] = _port(cfg.get("http_port"), DEFAULT_HTTP_PORT)
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
    "hold", "Not connected to QLC+",
    "Start QLC+ with web access (qlcplus -w). Trying again by itself.",
    "No cue list chosen. Choose one in Swiss Knife and export again.",
    "Every step of this list is hidden.", "Close",
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
        for st in cl["steps"]:
            s = item["steps"].get(str(st["index"]), {})
            steps.append({"i": st["index"], "name": s.get("label") or st["name"],
                          "note": st["note"], "hide": bool(s.get("hide"))})
        out_lists.append({"id": int(item["id"]),
                          "label": item["label"] or cl["caption"] or (cl["chaser"] or {}).get("name") or f"Cue list {item['id']}",
                          "mode": item["mode"], "steps": steps})
    return {"title": cfg["title"], "font": cfg["font"], "theme": cfg["theme"],
            "showNext": cfg["show_next"], "showClock": cfg["show_clock"],
            "showNumbers": cfg["show_numbers"], "wsPort": cfg["ws_port"],
            "lists": out_lists, "lang": lang if lang in LANGS else "en", "t": page_strings(lang)}


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


MARK = "QLC+ Swiss Knife — Stage Monitor"     # in the page and in serve_stage.py


def is_own_file(path: str) -> bool:
    """True when *path* is a page or server the Stage Monitor wrote (it may replace those)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return MARK in fh.read(4096)
    except OSError:
        return False


def export(folder: str, cfg: dict, lists: List[dict], lang: str = "en") -> dict:
    """Write ``index.html`` and ``serve_stage.py`` into *folder* (created if
    needed).  Returns the paths written."""
    cfg = clean_config(cfg)
    if not cfg["lists"]:
        raise ValueError("Tick at least one cue list.")
    page = os.path.join(folder, "index.html")
    script = os.path.join(folder, "serve_stage.py")
    for p in (page, script):     # replace only what the Stage Monitor wrote itself
        if os.path.exists(p) and not is_own_file(p):
            raise ValueError(f"{os.path.basename(p)} in that folder was not made by the Stage Monitor. "
                             "Choose another folder.")
    os.makedirs(folder, exist_ok=True)
    with open(page, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_page(cfg, lists, lang))
    with open(SERVE_SCRIPT, encoding="utf-8") as src:
        body = src.read().replace("DEFAULT_PORT = 8080", f"DEFAULT_PORT = {cfg['http_port']}")
    with open(script, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    try:
        os.chmod(script, 0o755)
    except OSError:
        pass
    return {"folder": folder, "page": page, "script": script}


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

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
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
