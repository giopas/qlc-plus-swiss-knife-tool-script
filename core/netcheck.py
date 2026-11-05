"""core/netcheck.py — is this computer online? (3.11.0)

Claude Desktop needs the internet even when Swiss Knife's MCP server is
connected: the MCP part runs on this computer, Claude itself does not.  So
the window shows a dot:

* **green** (``online``): claude.ai answers;
* **orange** (``limited``): something answers but not claude.ai (a captive
  portal, a firewall, a venue Wi-Fi that blocks it), or the answer was slow;
* **red** (``offline``): no name can be looked up and nothing answers.

The check only opens a TCP connection to port 443 and closes it: nothing is
sent, nothing about you or your shows.  The answer is kept for 20 seconds.
"""

from __future__ import annotations

import socket
import time
from typing import Dict, Optional, Tuple

HOSTS: Tuple[Tuple[str, int], ...] = (("claude.ai", 443), ("github.com", 443))
TIMEOUT_S = 2.5
SLOW_S = 1.5
KEEP_S = 20.0

_cache: Dict[str, object] = {"at": 0.0, "result": None}


def _reach(host: str, port: int, timeout: float) -> Tuple[bool, bool, float]:
    """(name looked up, connected, seconds) for one host."""
    t0 = time.monotonic()
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        return False, False, time.monotonic() - t0
    for fam, kind, proto, _n, addr in infos[:3]:
        try:
            with socket.socket(fam, kind, proto) as s:
                s.settimeout(timeout)
                s.connect(addr)
                return True, True, time.monotonic() - t0
        except OSError:
            continue
    return True, False, time.monotonic() - t0


def classify(results: Dict[str, Tuple[bool, bool, float]]) -> str:
    """``online``, ``limited`` or ``offline`` from :func:`_reach` per host.
    The first host is the one Claude needs."""
    first = next(iter(results.values()), (False, False, 0.0))
    if first[1] and first[2] <= SLOW_S:
        return "online"
    if any(r[0] or r[1] for r in results.values()):
        return "limited"
    return "offline"


def check(force: bool = False, now: Optional[float] = None, reach=_reach) -> dict:
    """``{"state", "claude", "other", "checked"}``; kept for :data:`KEEP_S`."""
    now = time.time() if now is None else now
    if not force and _cache["result"] is not None and now - float(_cache["at"]) < KEEP_S:
        return dict(_cache["result"])                         # type: ignore[arg-type]
    res = {f"{h}:{p}": reach(h, p, TIMEOUT_S) for h, p in HOSTS}
    vals = list(res.values())
    out = {"state": classify(res), "claude": bool(vals[0][1]), "other": any(v[1] for v in vals[1:]),
           "checked": int(now)}
    _cache.update({"at": now, "result": out})
    return dict(out)
