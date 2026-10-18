"""
core/cabling/chain.py — the connector walk
==========================================

A **chain** starts at one output (an interface's DMX out, a splitter or node
output) and runs through devices in order: a splitter's input, fixtures'
inputs.  Between two devices there is a cable, plugged with end ``a`` into
the *out* or *thru* socket behind it and with end ``b`` into the *in* socket
ahead.  Walking the chain port by port tells:

* where a plug does not fit its socket, and the adapter from the kit that
  makes it fit (C001 when there is none);
* whether the last device needs a terminator on its thru (it does unless it
  terminates itself), and which one (C002 when the kit has none left);
* how many devices hang on the output (C003 above what it drives);
* what was assumed: a fixture's connector (C101), its thru (C102).

The walk never looks at lengths or the stage; :mod:`core.cabling.plan` adds
those.  Counts are checked across all chains of a plan in :func:`check`.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from core.cabling import kit as kit_mod

SEVERITY = {"C001": "error", "C002": "error", "C003": "error", "C004": "error",
            "C005": "error", "C006": "error",
            "C101": "info", "C102": "info", "C103": "info", "C104": "info", "C105": "info"}


def fixture_device(fx: dict, item: Optional[dict] = None) -> dict:
    """A rig fixture (:func:`core.cabling.rig.read_rig`) as a device with
    ports.  A matching kit item's ports and termination win over the
    definition's connector."""
    if item and item.get("ports"):
        return {"name": fx["name"], "fixture": fx["id"], "ports": item["ports"],
                "termination": item.get("termination", "unknown"),
                "assumed_conn": False, "assumed_thru": not (item.get("sources") or {}).get("thru")}
    ports = [kit_mod.port("in", c, "m") for c in fx["conns"]]
    ports += [kit_mod.port("thru", c, "f") for c in fx["conns"]]
    return {"name": fx["name"], "fixture": fx["id"], "ports": ports, "termination": "unknown",
            "assumed_conn": not fx["connector_known"], "assumed_thru": True,
            "venue": fx.get("owner") == "venue"}


def _ports(dev: dict, role: str) -> List[dict]:
    return [p for p in dev.get("ports", []) if p["role"] == role]


def _generic_cable(conn: str) -> dict:
    if conn in ("rj45", "usb", "wireless"):
        return {"kind": "cable", "id": "", "name": {"rj45": "network", "usb": "USB",
                                                    "wireless": "radio"}[conn],
                "a": kit_mod.end(conn, "m"), "b": kit_mod.end(conn, "m"), "type": conn, "generic": True}
    return {"kind": "cable", "id": "", "name": f"{kit_mod.CONNECTOR_LABEL[conn]} DMX cable",
            "a": kit_mod.end(conn, "m"), "b": kit_mod.end(conn, "f"), "type": "dmx", "generic": True}


def pick_cable_conn(from_sock: dict, to_dev: dict, inventory: dict) -> str:
    """Which connector a cable should have when none is chosen: the one the
    device ahead takes if the kit has such cables (adapter at the source,
    as with a 5-pin interface feeding 3-pin fixtures), else the source's."""
    if from_sock["conn"] in ("rj45", "usb", "wireless"):
        return from_sock["conn"]
    have = {c["a"]["conn"] for c in kit_mod.by_kind(inventory, "cable")}
    ins = [p["conn"] for p in _ports(to_dev, "in")]
    for c in ins:
        if c in have:
            return c
    if from_sock["conn"] in have or not ins:
        return from_sock["conn"]
    return ins[0]


def _fit(plug: dict, socket: dict, inventory: dict) -> Optional[dict]:
    """``{"direct": True}``, ``{"adapter": item}`` or ``None``."""
    if kit_mod.mates(plug, socket):
        return {"direct": True}
    ad = kit_mod.find_adapter(inventory, plug, socket)
    return {"adapter": ad} if ad else None


def _issue(code: str, text: str, where: str = "", fix: str = "", buy: Optional[dict] = None) -> dict:
    """One check result.  ``buy`` (``{"what", "count"}``) puts it on the
    shopping list."""
    d = {"code": code, "severity": SEVERITY.get(code, "warning"), "text": text}
    if where:
        d["where"] = where
    if fix:
        d["fix"] = fix
    if buy:
        d["buy"] = buy
    return d


def adapter_name(socket: dict, plug: dict) -> str:
    """The adapter that takes *plug* into *socket*: its end into the socket,
    its other end facing the plug."""
    a = kit_mod.end(socket["conn"], kit_mod.other(socket["gender"]))
    b = kit_mod.end(plug["conn"], kit_mod.other(plug["gender"]))
    return f"Adapter {kit_mod.label(a)} → {kit_mod.label(b)}"


def walk(source: dict, out_port: dict, devices: List[dict], inventory: dict,
         cables: Optional[List[Optional[dict]]] = None, name: str = "") -> dict:
    """Walk one chain.

    ``source`` is the device whose ``out_port`` starts the chain; ``devices``
    the devices along it, in order; ``cables[i]`` the kit cable that reaches
    ``devices[i]`` (``None``: a DMX cable picked by :func:`pick_cable_conn`).

    Returns ``{"name", "links": [...], "terminator": {...} | None,
    "adapters": [item ids], "issues": [...]}``.  Adapter and terminator
    counts against the kit are checked by :func:`check`."""
    cables = list(cables or []) + [None] * (len(devices) - len(cables or []))
    links, adapters, issues = [], [], []
    assumed_conn: List[str] = []
    assumed_thru: List[str] = []
    behind_dev, behind_sock = source, out_port
    where_chain = name or f"{source['name']} {out_port.get('name', 'out')}"
    for i, dev in enumerate(devices):
        cab = cables[i] or _generic_cable(pick_cable_conn(behind_sock, dev, inventory))
        link = {"from": behind_dev["name"], "to": dev["name"], "cable": cab.get("id") or None,
                "cable_name": cab["name"], "conn": cab["a"]["conn"], "adapters": []}
        if cab.get("type") == "mic":
            issues.append(_issue("C010", f"{cab['name']} is a microphone cable.", dev["name"],
                                 "Use a 110 Ω DMX cable of the same length."))
        # end a into the socket behind
        f = _fit(cab["a"], behind_sock, inventory)
        if f is None:
            issues.append(_issue("C001", f"{kit_mod.label(cab['a'])} plug does not fit the "
                                 f"{kit_mod.label(behind_sock)} socket of {behind_dev['name']}.",
                                 behind_dev["name"], f"Add an {adapter_name(behind_sock, cab['a'])[0].lower()}"
                                 f"{adapter_name(behind_sock, cab['a'])[1:]}.",
                                 {"what": adapter_name(behind_sock, cab["a"]), "count": 1}))
        elif f.get("adapter"):
            link["adapters"].append({"at": behind_dev["name"], "id": f["adapter"]["id"], "name": f["adapter"]["name"]})
            adapters.append(f["adapter"]["id"])
        # end b into an in socket ahead (the one that fits, if any)
        ins = _ports(dev, "in")
        sock = next((p for p in ins if kit_mod.mates(cab["b"], p)), None)
        if sock is None and ins:
            for p in ins:
                f = _fit(cab["b"], p, inventory)
                if f is not None:
                    sock = p
                    link["adapters"].append({"at": dev["name"], "id": f["adapter"]["id"], "name": f["adapter"]["name"]})
                    adapters.append(f["adapter"]["id"])
                    break
            else:
                sock = ins[0]
                issues.append(_issue("C001", f"{kit_mod.label(cab['b'])} plug does not fit the "
                                     f"{kit_mod.label(sock)} socket of {dev['name']}.", dev["name"],
                                     f"Add an {adapter_name(sock, cab['b'])[0].lower()}{adapter_name(sock, cab['b'])[1:]}.",
                                     {"what": adapter_name(sock, cab["b"]), "count": 1}))
        if dev.get("assumed_conn"):
            assumed_conn.append(dev["name"])
        link["socket"] = sock
        links.append(link)
        if i < len(devices) - 1:
            thrus = _ports(dev, "thru") or _ports(dev, "out")
            if not thrus:
                issues.append(_issue("C001", f"{dev['name']} has no DMX thru: the chain cannot go on.", dev["name"],
                                     "End the chain here, or start a new one from a splitter output."))
                break
            if dev.get("assumed_thru") and dev.get("fixture") is not None:
                assumed_thru.append(dev["name"])
            same = [p for p in thrus if sock and p["conn"] == sock["conn"]]
            behind_dev, behind_sock = dev, (same or thrus)[0]
        if dev.get("termination") == "auto" and i < len(devices) - 1:
            issues.append(_issue("C008", f"{dev['name']} terminates itself but is not last: "
                                 "the fixtures after it may get no signal.", dev["name"],
                                 "Move it to the end of the chain, or switch its termination off."))
    if assumed_conn:
        issues.append(_issue("C101", "DMX connector assumed 3-pin (the definition does not say): "
                             + ", ".join(assumed_conn) + ".", assumed_conn[0],
                             "Ask Claude, or set it once in the kit."))
    if assumed_thru:
        issues.append(_issue("C102", "Thru assumed the same as the input: " + ", ".join(assumed_thru) + ".",
                             assumed_thru[0]))
    term = None
    if devices:
        last = devices[-1]
        if _ports(last, "out") and last.get("fixture") is None:
            # a splitter or node: its input must be terminated, by its switch
            # or a terminator on the unused thru (C009, not counted as C002)
            if last.get("termination") not in ("switch", "auto"):
                issues.append(_issue("C009", f"{last['name']}: thru unused and input termination "
                                     f"{'unknown' if last.get('termination', 'unknown') == 'unknown' else 'off'}.",
                                     last["name"], "Switch its termination on, or put a terminator on its thru."))
        elif last.get("termination") not in ("auto", "switch"):
            thrus = _ports(last, "thru")
            sock = thrus[0] if thrus else None
            want = kit_mod.end(sock["conn"], kit_mod.other(sock["gender"])) if sock else kit_mod.end("xlr3", "m")
            item = next((t for t in kit_mod.by_kind(inventory, "terminator") if kit_mod.mates(t["plug"], sock or {})), None)
            term = {"at": last["name"], "plug": want, "id": item["id"] if item else None}
    if len(devices) > out_port.get("drive", kit_mod.DEFAULT_DRIVE):
        issues.append(_issue("C003", f"{len(devices)} devices on {where_chain}, which drives "
                             f"{out_port.get('drive', kit_mod.DEFAULT_DRIVE)}.", where_chain,
                             "Split the chain onto a free output."))
    if any(d.get("venue") for d in devices) and devices[-1].get("venue_point"):
        issues.append(_issue("C104", "House cabling after the venue DMX point is not checked.", devices[-1]["name"]))
    return {"name": where_chain, "links": links, "terminator": term, "adapters": adapters, "issues": issues}


def check(chains: List[dict], inventory: dict) -> List[dict]:
    """Counts across a plan's walked chains: adapters and terminators against
    the kit (C001, C002), and what is left (C103).  Returns the extra issues."""
    stock = {it["id"]: it["count"] for it in inventory.get("items", [])}
    names = {it["id"]: it["name"] for it in inventory.get("items", [])}
    used: Dict[str, int] = {}
    issues = []
    for ch in chains:
        for a in ch["adapters"]:
            used[a] = used.get(a, 0) + 1
    for a, n in sorted(used.items()):
        if n > stock.get(a, 0):
            issues.append(_issue("C001", f"The plan needs {n} × {names.get(a, a)}, the kit has {stock.get(a, 0)}.",
                                 fix=f"Add {n - stock.get(a, 0)} to the shopping list.",
                                 buy={"what": names.get(a, a), "count": n - stock.get(a, 0)}))
    need = [ch["terminator"] for ch in chains if ch.get("terminator")]
    by_plug: Dict[str, List[dict]] = {}
    for t in need:
        by_plug.setdefault(kit_mod.label(t["plug"]), []).append(t)
    for lab, ts in sorted(by_plug.items()):
        have = sum(it["count"] for it in kit_mod.by_kind(inventory, "terminator")
                   if kit_mod.label(it["plug"]) == lab)
        if len(ts) > have:
            short = ts[have:]
            issues.append(_issue("C002", f"{len(ts)} chain ends need a {lab} terminator, the kit has {have}: "
                                 + ", ".join(t["at"] for t in short) + " without one.",
                                 short[0]["at"], f"Add {len(ts) - have} × Terminator {lab} to the shopping list.",
                                 {"what": f"Terminator {lab}", "count": len(ts) - have}))
    left = []
    for it in inventory.get("items", []):
        if it["kind"] in ("adapter", "terminator"):
            n = it["count"] - used.get(it["id"], 0) - (
                sum(1 for t in need if t.get("id") == it["id"]) if it["kind"] == "terminator" else 0)
            if n > 0:
                left.append(f"{n} × {it['name']}")
    if left:
        issues.append(_issue("C103", "Left in the bag: " + ", ".join(left) + "."))
    return issues
