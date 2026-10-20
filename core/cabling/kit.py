"""
core/cabling/kit.py — the kit model
===================================

Every device is a set of **ports**.  A port has a role (``in``, ``out``,
``thru``), a connector (``xlr3``, ``xlr5``, ``rj45``, ``usb``, ``wireless``,
``jack35``) and a gender (``m``, ``f``; none for ``usb`` and ``wireless``).
Outputs also say whether they are isolated and how many devices they drive.

Nothing below is specific to one product: the Enttec DMX USB Pro has a 5-pin
female out and a 3-pin splitter has a 3-pin male in, and *that* is what makes
an adapter appear.  Presets are starting points to copy and correct.

Kinds of kit item:

``interface``   computer → DMX (USB or network), one ``out`` per universe line
``splitter``    one ``in`` (+ ``thru``), several isolated ``out``
``node``        network ``in`` (rj45), DMX ``out`` per universe
``wireless_tx`` / ``wireless_rx``  a wireless pair
``cable``       two ends (``a`` plugs into an *out*/thru, ``b`` into an *in*),
                a length in m and a type (``dmx`` 110 Ω or ``mic``)
``adapter``     two ends, changes connector and/or gender
``terminator``  one plug, 120 Ω
``fixture``     a fixture model you own (manufacturer, model, ports,
                termination, count) — see :func:`fixture_item`

The **base inventory** is what you own, in your settings
(``~/.qlc_swiss_knife/cabling_kit.json``, or ``$QSK_CABLING_KIT``).
**Tonight** is a copy kept in the show's plan file, adjusted per gig.
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Dict, List, Optional, Tuple

CONNECTORS = ("xlr3", "xlr5", "rj45", "usb", "wireless", "jack35")
GENDERLESS = ("usb", "wireless")
ROLES = ("in", "out", "thru")
KINDS = ("interface", "splitter", "node", "wireless_tx", "wireless_rx",
         "cable", "adapter", "terminator", "fixture")
DEVICE_KINDS = ("interface", "splitter", "node", "wireless_tx", "wireless_rx", "fixture")
CABLE_TYPES = ("dmx", "mic", "net")
TERMINATION = ("none", "switch", "auto", "unknown")
OWNERS = ("mine", "borrowed", "venue")
DEFAULT_DRIVE = 32                 # devices one DMX output may drive (EIA-485 unit loads)
KIT_VERSION = 1

CONNECTOR_LABEL = {"xlr3": "3-pin", "xlr5": "5-pin", "rj45": "RJ45", "usb": "USB",
                   "wireless": "wireless", "jack35": "3.5 mm jack"}


class KitError(ValueError):
    """A kit item or inventory that cannot be used."""


# ─────────────────────────────────────────────────────────────────────────────
# ports and plugs
# ─────────────────────────────────────────────────────────────────────────────

def port(role: str, conn: str, gender: str = "", *, name: str = "",
         isolated: bool = False, drive: int = DEFAULT_DRIVE) -> dict:
    """One port.  ``gender`` is the socket's gender as seen on the device."""
    p = {"role": role, "conn": conn, "gender": "" if conn in GENDERLESS else gender}
    if name:
        p["name"] = name
    if role == "out":
        p["isolated"] = bool(isolated)
        p["drive"] = int(drive)
    return p


def end(conn: str, gender: str = "") -> dict:
    """One end of a cable or adapter (the plug's own gender)."""
    return {"conn": conn, "gender": "" if conn in GENDERLESS else gender}


def other(gender: str) -> str:
    return {"m": "f", "f": "m"}.get(gender, "")


def mates(plug: dict, socket: dict) -> bool:
    """Does *plug* go into *socket*?  Same connector, opposite gender."""
    if plug.get("conn") != socket.get("conn"):
        return False
    if plug.get("conn") in GENDERLESS:
        return True
    return bool(plug.get("gender")) and plug.get("gender") == other(socket.get("gender", ""))


def label(p: dict) -> str:
    """``5-pin ♀`` — for messages and the screen."""
    g = {"m": " ♂", "f": " ♀"}.get(p.get("gender", ""), "")
    return CONNECTOR_LABEL.get(p.get("conn", ""), p.get("conn", "?")) + g


# ─────────────────────────────────────────────────────────────────────────────
# DmxConnector from a .qxf
# ─────────────────────────────────────────────────────────────────────────────

def connectors_from_qxf(value: str) -> Tuple[List[str], bool]:
    """``(connectors, known)`` from a .qxf ``DmxConnector``.

    QLC+ writes ``3-pin``, ``5-pin``, ``3-pin and 5-pin``, ``3-pin IP65``,
    ``5-pin IP65``, ``3.5 mm stereo jack`` or ``Other``.  Unknown or empty
    gives ``(["xlr3"], False)``: 3-pin is assumed and C101 says so."""
    v = (value or "").strip().lower()
    out: List[str] = []
    if "3-pin" in v or "3 pin" in v:
        out.append("xlr3")
    if "5-pin" in v or "5 pin" in v:
        out.append("xlr5")
    if "jack" in v:
        out.append("jack35")
    if not out:
        return ["xlr3"], False
    return out, True


# ─────────────────────────────────────────────────────────────────────────────
# presets
# ─────────────────────────────────────────────────────────────────────────────

def _device(kind: str, name: str, ports: List[dict], **extra) -> dict:
    d = {"kind": kind, "name": name, "ports": ports, "count": 1}
    d.update(extra)
    return d


def cable_word(conn: str, ctype: str = "dmx") -> str:
    """``3-pin DMX cable``, ``3-pin mic cable``, ``Network cable (RJ45)``."""
    if conn == "rj45":
        return "Network cable (RJ45)"
    return f"{CONNECTOR_LABEL[conn]} {'mic' if ctype == 'mic' else 'DMX'} cable"


def _cable(length: float, conn: str = "xlr3", ctype: str = "dmx", count: int = 1) -> dict:
    if conn == "rj45":                             # a patch lead: the same plug at both ends
        return {"kind": "cable", "name": f"{cable_word(conn)} {_m(length)}", "a": end(conn, "m"),
                "b": end(conn, "m"), "length": float(length), "type": "net", "count": count}
    return {"kind": "cable", "name": f"{cable_word(conn, ctype)} {_m(length)}",
            "a": end(conn, "m"), "b": end(conn, "f"), "length": float(length),
            "type": ctype, "count": count}


def _m(length: float) -> str:
    return (f"{length:g}" if length == int(length) or length * 10 != int(length * 10) else f"{length:.1f}") + " m"


def _adapter(a: dict, b: dict, name: str = "", count: int = 1) -> dict:
    return {"kind": "adapter", "name": name or f"Adapter {label(a)} → {label(b)}", "a": a, "b": b, "count": count}


def _splitter(n: int, conn: str = "xlr3", thru: bool = True, name: str = "") -> dict:
    ports = [port("in", conn, "m", name="IN")]
    if thru:
        ports.append(port("thru", conn, "f", name="THRU"))
    ports += [port("out", conn, "f", name=f"OUT {i}", isolated=True) for i in range(1, n + 1)]
    return _device("splitter", name or f"Splitter 1 → {n} ({CONNECTOR_LABEL[conn]})", ports,
                   termination="unknown", power="mains")


PRESETS: Dict[str, dict] = {
    "enttec_usb_pro": _device("interface", "Enttec DMX USB Pro",
                              [port("in", "usb", name="USB"), port("out", "xlr5", "f", name="DMX OUT")],
                              plugin="DMX USB", match=["dmx usb pro", "enttec"], power="usb"),
    "usb_dmx_3pin": _device("interface", "USB–DMX interface (3-pin)",
                            [port("in", "usb", name="USB"), port("out", "xlr3", "f", name="DMX OUT")],
                            plugin="DMX USB", match=["dmx usb"], power="usb"),
    "lixada_1x8": _device("splitter", "Lixada DMX512 splitter 1 → 8",
                          # the spec: 1 input, 1 output directly (thru, not buffered), 8 independent
                          # outputs, 1000 V isolation between input and outputs and between outputs,
                          # DC 9-12 V; no termination switch, so its thru takes a terminator when unused
                          [port("in", "xlr3", "m", name="DMX IN"), port("thru", "xlr3", "f", name="DMX THRU")]
                          + [port("out", "xlr3", "f", name=f"DMX OUT {i}", isolated=True) for i in range(1, 9)],
                          termination="none", power="dc adapter", match=["lixada"]),
    "splitter_1x4": _splitter(4),
    "splitter_1x8": _splitter(8),
    # the computer's own network port: what feeds an Art-Net / sACN node (never packed)
    "computer_lan": _device("interface", "Computer network port (Art-Net / sACN)",
                            [port("out", "rj45", "f", name="LAN")], power="computer"),
    "artnet_node_1": _device("node", "Art-Net / sACN node, 1 universe",
                             [port("in", "rj45", "f", name="NET"),
                              port("out", "xlr3", "f", name="DMX OUT", isolated=True)],
                             plugin="ArtNet", power="mains", termination="none"),
    "artnet_node_4": _device("node", "Art-Net / sACN node, 4 universes",
                             [port("in", "rj45", "f", name="NET")]
                             + [port("out", "xlr5", "f", name=f"OUT {c}", isolated=True) for c in "ABCD"],
                             plugin="ArtNet", power="mains", termination="none"),
    "artnet_node_2": _device("node", "Art-Net / sACN node, 2 universes",
                             [port("in", "rj45", "f", name="NET"),
                              port("out", "xlr5", "f", name="OUT A", isolated=True),
                              port("out", "xlr5", "f", name="OUT B", isolated=True)],
                             plugin="ArtNet", power="mains", termination="none"),
    "wireless_tx": _device("wireless_tx", "Wireless DMX transmitter",
                           [port("in", "xlr3", "m", name="DMX IN"), port("out", "wireless", name="RF")],
                           range_m=100.0, power="mains"),
    "wireless_rx": _device("wireless_rx", "Wireless DMX receiver",
                           [port("in", "wireless", name="RF"), port("out", "xlr3", "f", name="DMX OUT")],
                           power="mains", termination="none"),
    "wireless_tx_batt": _device("wireless_tx", "Wireless DMX transmitter, battery (3-pin plug)",
                                [port("in", "xlr3", "m", name="DMX IN"), port("out", "wireless", name="RF")],
                                range_m=300.0, power="battery"),
    "wireless_rx_batt": _device("wireless_rx", "Wireless DMX receiver, battery (3-pin plug)",
                                [port("in", "wireless", name="RF"), port("out", "xlr3", "m", name="DMX OUT")],
                                power="battery", termination="none"),
    "adapter_5m_3f": _adapter(end("xlr5", "m"), end("xlr3", "f")),
    "adapter_3m_5f": _adapter(end("xlr3", "m"), end("xlr5", "f")),
    "gender_3ff": _adapter(end("xlr3", "f"), end("xlr3", "f"), "Gender changer 3-pin ♀–♀"),
    "gender_3mm": _adapter(end("xlr3", "m"), end("xlr3", "m"), "Gender changer 3-pin ♂–♂"),
    "terminator_3": {"kind": "terminator", "name": "Terminator 3-pin 120 Ω", "plug": end("xlr3", "m"), "count": 1},
    "terminator_5": {"kind": "terminator", "name": "Terminator 5-pin 120 Ω", "plug": end("xlr5", "m"), "count": 1},
    "cable_3_1.5": _cable(1.5), "cable_3_3": _cable(3), "cable_3_5": _cable(5),
    "cable_3_10": _cable(10), "cable_3_20": _cable(20), "cable_5_1.5": _cable(1.5, "xlr5"),
    "cable_net_10": _cable(10, "rj45"), "cable_net_20": _cable(20, "rj45"), "cable_net_50": _cable(50, "rj45"),
}


def presets() -> List[dict]:
    """``[{id, item}]`` sorted by kind then name."""
    order = {k: i for i, k in enumerate(KINDS)}
    return [{"id": k, "item": copy.deepcopy(v)}
            for k, v in sorted(PRESETS.items(), key=lambda kv: (order[kv[1]["kind"]], kv[1]["name"]))]


def fixture_item(manufacturer: str, model: str, *, count: int = 1,
                 conns: Optional[List[str]] = None, thru: bool = True,
                 termination: str = "unknown", sources: Optional[dict] = None) -> dict:
    """A fixture model in the kit: DMX in (♂) and thru (♀) on each connector."""
    conns = conns or ["xlr3"]
    ports = [port("in", c, "m", name="DMX IN") for c in conns]
    if thru:
        ports += [port("thru", c, "f", name="DMX THRU") for c in conns]
    it = {"kind": "fixture", "name": f"{manufacturer} {model}".strip(),
          "manufacturer": manufacturer, "model": model, "ports": ports,
          "termination": termination, "count": int(count)}
    if sources:
        it["sources"] = dict(sources)
    return it


# ─────────────────────────────────────────────────────────────────────────────
# checking an item
# ─────────────────────────────────────────────────────────────────────────────

def _clean_end(e, where: str) -> dict:
    if not isinstance(e, dict) or e.get("conn") not in CONNECTORS:
        raise KitError(f"{where}: unknown connector.")
    g = e.get("gender", "")
    if e["conn"] not in GENDERLESS and g not in ("m", "f"):
        raise KitError(f"{where}: gender must be m or f.")
    return end(e["conn"], g)


def _clean_port(p, where: str) -> dict:
    if not isinstance(p, dict) or p.get("role") not in ROLES:
        raise KitError(f"{where}: role must be in, out or thru.")
    e = _clean_end(p, where)
    try:
        drive = int(p.get("drive", DEFAULT_DRIVE))
    except (TypeError, ValueError):
        drive = DEFAULT_DRIVE
    return port(p["role"], e["conn"], e["gender"], name=str(p.get("name") or "")[:40],
                isolated=bool(p.get("isolated")), drive=max(1, min(drive, 512)))


def clean_item(item) -> dict:
    """A kit item with every key checked; raises :class:`KitError`."""
    if not isinstance(item, dict) or item.get("kind") not in KINDS:
        raise KitError("Unknown kind of kit item.")
    kind = item["kind"]
    name = str(item.get("name") or "").strip()[:120]
    if not name:
        raise KitError("A kit item needs a name.")
    try:
        count = int(item.get("count", 1))
    except (TypeError, ValueError):
        raise KitError(f"{name}: count must be a whole number.")
    if not 0 <= count <= 999:
        raise KitError(f"{name}: count must be 0 to 999.")
    out = {"kind": kind, "name": name, "count": count}
    if kind in DEVICE_KINDS:
        ports = [_clean_port(p, f"{name}, port {i + 1}") for i, p in enumerate(item.get("ports") or [])]
        if not ports:
            raise KitError(f"{name}: a device needs at least one port.")
        out["ports"] = ports
        for k in ("plugin", "power"):
            if item.get(k):
                out[k] = str(item[k])[:40]
        if item.get("match"):
            out["match"] = [str(m).lower()[:60] for m in item["match"] if str(m).strip()][:8]
        if "termination" in item or kind in ("splitter", "fixture"):
            t = item.get("termination", "unknown")
            out["termination"] = t if t in TERMINATION else "unknown"
        if kind == "fixture":
            out["manufacturer"] = str(item.get("manufacturer") or "").strip()[:80]
            out["model"] = str(item.get("model") or "").strip()[:80]
            if not out["model"]:
                raise KitError(f"{name}: a fixture needs its model.")
        if item.get("range_m"):
            out["range_m"] = float(item["range_m"])
    elif kind in ("cable", "adapter"):
        out["a"] = _clean_end(item.get("a"), f"{name}, end A")
        out["b"] = _clean_end(item.get("b"), f"{name}, end B")
        if kind == "cable":
            try:
                length = float(item.get("length"))
            except (TypeError, ValueError):
                raise KitError(f"{name}: length in m.")
            if not 0.1 <= length <= 500:
                raise KitError(f"{name}: length must be 0.1 to 500 m.")
            out["length"] = round(length, 2)
            out["type"] = item.get("type") if item.get("type") in CABLE_TYPES else "dmx"
    elif kind == "terminator":
        out["plug"] = _clean_end(item.get("plug"), f"{name}, plug")
    if isinstance(item.get("sources"), dict):
        out["sources"] = {str(k)[:40]: str(v)[:40] for k, v in item["sources"].items()}
    if item.get("id"):
        out["id"] = re.sub(r"[^A-Za-z0-9_.-]", "", str(item["id"]))[:60]
    if item.get("owner") in OWNERS:
        out["owner"] = item["owner"]
    return out


def clean_inventory(inv) -> dict:
    """``{"version", "items": [...]}``; items that cannot be used are dropped
    and listed in ``"dropped"`` with the reason."""
    inv = inv if isinstance(inv, dict) else {}
    items, dropped = [], []
    for i, raw in enumerate(inv.get("items") or []):
        try:
            items.append(clean_item(raw))
        except KitError as e:
            dropped.append({"index": i, "reason": str(e)})
    _number(items)
    out = {"version": KIT_VERSION, "items": items}
    if inv.get("units") in ("m", "ft"):            # lengths shown in metres or feet
        out["units"] = inv["units"]
    if dropped:
        out["dropped"] = dropped
    return out


def _number(items: List[dict]) -> None:
    """Give every item a stable id (kind + a counter) if it has none."""
    used = {it["id"] for it in items if it.get("id")}
    n: Dict[str, int] = {}
    for it in items:
        if it.get("id"):
            continue
        while True:
            n[it["kind"]] = n.get(it["kind"], 0) + 1
            cand = f"{it['kind']}{n[it['kind']]}"
            if cand not in used:
                break
        it["id"] = cand
        used.add(cand)


# ─────────────────────────────────────────────────────────────────────────────
# the base inventory (settings) and tonight's copy
# ─────────────────────────────────────────────────────────────────────────────

def kit_path() -> str:
    return os.environ.get("QSK_CABLING_KIT") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "cabling_kit.json")


def load_base() -> dict:
    """Your kit; empty when there is none yet."""
    try:
        with open(kit_path(), encoding="utf-8") as fh:
            return clean_inventory(json.load(fh))
    except (OSError, ValueError):
        return {"version": KIT_VERSION, "items": []}


def load_units() -> str:
    """``m`` or ``ft``: how your kit shows lengths."""
    return load_base().get("units", "m")


def save_base(inv: dict) -> str:
    """Write your kit (keys sorted, so it diffs well).  This file holds only
    your kit, so it is replaced like the Stage Monitor's settings."""
    data = clean_inventory(inv)
    data.pop("dropped", None)
    path = kit_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return path


def tonight_from(base: dict) -> dict:
    """Tonight's copy of the base: every item, owner *mine*."""
    inv = copy.deepcopy(clean_inventory(base))
    inv.pop("dropped", None)
    for it in inv["items"]:
        it.setdefault("owner", "mine")
    return inv


def by_kind(inv: dict, kind: str) -> List[dict]:
    return [it for it in inv.get("items", []) if it["kind"] == kind and it.get("count", 0) > 0]


def find_adapter(inv: dict, plug_needed: dict, socket: dict) -> Optional[dict]:
    """An adapter whose end *a* takes ``plug_needed``'s opposite… more simply:
    an adapter that goes into *socket* with one end and offers a socket that
    *plug_needed* fits with the other.  ``plug_needed`` is the plug arriving
    (e.g. a cable end); ``socket`` is the device's port.  Either way round."""
    for ad in by_kind(inv, "adapter"):
        for x, y in ((ad["a"], ad["b"]), (ad["b"], ad["a"])):
            # x goes into the socket; y meets the arriving plug
            if mates(x, socket) and mates(plug_needed, {"conn": y["conn"], "gender": y["gender"]}):
                return ad
    return None
