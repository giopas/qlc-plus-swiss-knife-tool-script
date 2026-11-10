"""stage_app/folder.py: read a folder that Swiss Knife's Stage Monitor exported.

The folder holds ``index.html`` (the page, with its settings and the setlist
inlined as JSON) and ``serve_stage.py`` (which knows the port the page was
exported for and the show it came from).  This module only reads them.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from core import stage_monitor as sm

PAGE = "index.html"
SCRIPT = "serve_stage.py"
_CFG_MARK = "const CFG = "
_PORT = re.compile(r"^DEFAULT_PORT\s*=\s*(\d+)", re.M)
_SHOW = re.compile(r'^SHOW\s*=\s*("(?:[^"\\]|\\.)*")', re.M)


class NotAPage(ValueError):
    """The folder is not a Stage Monitor export (the message says why)."""


def page_data(html: str) -> dict:
    """The settings and setlist inlined in an exported page."""
    i = html.find(_CFG_MARK)
    if i < 0:
        raise NotAPage("This page has no Stage Monitor settings in it.")
    i += len(_CFG_MARK)
    if html.startswith("/*__CONFIG__*/null", i):
        raise NotAPage("This is the page template, not an exported page.")
    try:
        data, _end = json.JSONDecoder().raw_decode(html, i)
    except ValueError as e:
        raise NotAPage("The settings in this page cannot be read.") from e
    if not isinstance(data, dict) or not isinstance(data.get("lists"), list):
        raise NotAPage("The settings in this page cannot be read.")
    return data


def _int(v, default: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return n if 1 <= n <= 65535 else default


def songs(lst: dict) -> list:
    """The songs of one cue list, as the page shows them (hidden steps left out)."""
    out = []
    for st in lst.get("steps") or []:
        if not isinstance(st, dict) or st.get("hide"):
            continue
        card = st.get("card") if isinstance(st.get("card"), dict) else {}
        out.append({"i": st.get("i"), "name": str(st.get("name") or ""), "note": str(st.get("note") or ""),
                    "card": card, "tc": st.get("tc") if isinstance(st.get("tc"), dict) else None})
    return out


def read(folder: str) -> dict:
    """What the app needs from an exported folder.

    Raises :class:`NotAPage` when *folder* is not a Stage Monitor export."""
    folder = os.path.abspath(os.path.expanduser(str(folder or "")))
    page = os.path.join(folder, PAGE)
    if not os.path.isdir(folder):
        raise NotAPage("That folder does not exist.")
    if not os.path.isfile(page):
        raise NotAPage("There is no Stage Monitor page (index.html) in this folder. "
                       "Export it from the Stage Monitor in QLC+ Swiss Knife first.")
    if not sm.is_own_file(page):
        raise NotAPage("index.html in this folder was not made by the Stage Monitor of QLC+ Swiss Knife.")
    with open(page, encoding="utf-8", errors="replace") as fh:
        data = page_data(fh.read())
    http_port, show = sm.DEFAULT_HTTP_PORT, ""
    script = os.path.join(folder, SCRIPT)
    if os.path.isfile(script):
        with open(script, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        m = _PORT.search(text)
        if m:
            http_port = _int(m.group(1), http_port)
        m = _SHOW.search(text)
        if m:
            try:
                show = str(json.loads(m.group(1)))
            except ValueError:
                show = ""
    lists = []
    for lst in data["lists"]:
        if not isinstance(lst, dict):
            continue
        lists.append({"id": str(lst.get("id")), "label": str(lst.get("label") or ""),
                      "mode": str(lst.get("mode") or "read"), "songs": songs(lst)})
    views = [{"id": str(v.get("id")), "label": str(v.get("label") or v.get("id"))}
             for v in data.get("views") or [] if isinstance(v, dict) and v.get("id")]
    return {"folder": folder, "title": str(data.get("title") or ""), "lists": lists, "views": views,
            "ws_port": _int(data.get("wsPort"), sm.DEFAULT_WS_PORT), "http_port": http_port,
            "lang": str(data.get("lang") or "en"), "show": show,
            "show_name": os.path.basename(show) if show else ""}


def try_read(folder: str) -> "tuple[Optional[dict], str]":
    """``(data, "")`` or ``(None, why)``; never raises for a bad folder."""
    if not folder:
        return None, ""
    try:
        return read(folder), ""
    except NotAPage as e:
        return None, str(e)
    except OSError as e:
        return None, f"The folder cannot be read ({e.strerror or e})."
