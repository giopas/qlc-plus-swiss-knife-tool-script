"""
core/input_manager.py — the controller side of a show (WORKPLAN 3.6, v2.6.0)
===========================================================================
Works on namespace-stripped trees (``qxw_io.strip_ns``); the routes put the
result back into the show in progress.

* **Patch.** ``<Engine><InputOutputMap><Universe><Input Plugin Name UID Line
  Profile/>``: :func:`universes` lists every universe with its input device,
  feedback and the Virtual Console bindings that listen to it;
  :func:`set_input` / :func:`clear_input` change it.  QLC+ saves
  ``Plugin="None"`` when the controller was not plugged in at that moment —
  the "MIDI input saved as None" case: :func:`remember_controller` keeps a
  controller in ``~/.qlc_swiss_knife/controllers.json`` so it can be patched
  into any show in one click.
* **Re-patch.** :func:`move_bindings` moves the bindings of a universe to
  another (optionally shifting the channels), :func:`swap_universes` swaps
  two.
* **MIDI messages.** QLC+'s MIDI plugin numbers a message as
  ``offset + data1`` (+ ``MIDI channel << 12`` in OMNI mode); the XML stores
  it 0-based, the QLC+ screens show it +1.  :func:`encode` / :func:`decode`
  convert; :func:`simulate` says what a message would trigger — a MIDI-learn
  without the controller.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, List, Optional

from core import porter_input as pi, vc_ops

# (kind, first stored channel, how many) — QLC+ plugins/midi/src/common/midiprotocol.h
KINDS = [
    ("cc", "Control change", 0, 128),
    ("note", "Note", 128, 128),
    ("note_at", "Note aftertouch", 256, 128),
    ("program", "Program change", 384, 128),
    ("chan_at", "Channel aftertouch", 512, 1),
    ("pitch", "Pitch wheel", 513, 1),
]
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
INPUT_PLUGINS = ["MIDI", "OSC", "HID", "ArtNet", "E1.31", "Loopback", "Serial"]


class InputError(ValueError):
    pass


def note_name(n: int) -> str:
    return f"{_NOTES[n % 12]}{n // 12 - 1}"


def encode(kind: str, number: int = 0, midi_channel: Optional[int] = None) -> int:
    """Stored (0-based) input channel of a MIDI message.  *midi_channel*
    1–16 for OMNI mode (the plugin adds ``(channel − 1) << 12``), else None."""
    row = next((k for k in KINDS if k[0] == kind), None)
    if row is None:
        raise InputError(f"Unknown message type '{kind}'.")
    number = int(number)
    if not 0 <= number < row[3]:
        raise InputError(f"{row[1]}: the number must be 0–{row[3] - 1}.")
    ch = row[2] + number
    if midi_channel not in (None, ""):
        m = int(midi_channel)
        if not 1 <= m <= 16:
            raise InputError("MIDI channel must be 1–16.")
        ch |= (m - 1) << 12
    return ch


def decode(channel) -> dict:
    """``{kind, label, number, midi_channel, text}`` of a stored channel."""
    try:
        c = int(channel)
    except (TypeError, ValueError):
        return {"kind": "", "label": "", "number": None, "midi_channel": None, "text": ""}
    mc = (c >> 12) + 1 if c >= 4096 else None
    base = c & 0xFFF
    for kind, label, off, n in KINDS:
        if off <= base < off + n:
            num = base - off
            extra = f" ({note_name(num)})" if kind in ("note", "note_at") else ""
            what = label if n == 1 else f"{label} {num}{extra}"
            return {"kind": kind, "label": label, "number": num, "midi_channel": mc,
                    "text": what + (f" · MIDI ch {mc}" if mc else "")}
    return {"kind": "", "label": "", "number": None, "midi_channel": mc,
            "text": f"channel {c + 1}"}


# ── the patch ────────────────────────────────────────────────────────────────

def _iom(root: ET.Element, create: bool = False) -> Optional[ET.Element]:
    eng = root.find("Engine")
    iom = eng.find("InputOutputMap") if eng is not None else None
    if iom is None and create and eng is not None:
        iom = ET.SubElement(eng, "InputOutputMap")
    return iom


def _uni(root: ET.Element, uid: str, create: bool = False) -> Optional[ET.Element]:
    iom = _iom(root, create)
    if iom is None:
        return None
    u = next((x for x in iom.findall("Universe") if x.get("ID") == str(uid)), None)
    if u is None and create and str(uid).isdigit():
        u = ET.Element("Universe", {"Name": f"Universe {int(uid) + 1}", "ID": str(uid)})
        before = [x for x in iom.findall("Universe") if int(x.get("ID", "0")) < int(uid)]
        iom.insert(list(iom).index(before[-1]) + 1 if before else len(
            [c for c in iom if c.tag != "Universe"]), u)
    return u


def _bindings(root: ET.Element) -> Dict[str, List[ET.Element]]:
    """``universe → [<Input Universe Channel> elements of the VC]``."""
    out: Dict[str, List[ET.Element]] = {}
    vc = root.find("VirtualConsole")
    for el in (vc.iter("Input") if vc is not None else []):
        if el.get("Universe") is not None and el.get("Channel") is not None:
            out.setdefault(el.get("Universe"), []).append(el)
    return out


def universes(root: ET.Element) -> List[dict]:
    """Every universe: ``{id, name, input, feedback, output, bindings, status}``;
    status ``ok`` / ``no_input`` (bindings but no device — they stay silent)
    / ``idle`` (no device, no bindings)."""
    bind = _bindings(root)
    patch = pi.read_patch(root)
    iom = _iom(root)
    out = []
    ids = {u.get("ID") for u in (iom.findall("Universe") if iom is not None else [])} | set(bind)
    for uid in sorted(ids, key=lambda x: int(x) if x.isdigit() else 0):
        u = _uni(root, uid)
        inp = u.find("Input") if u is not None else None
        fb = u.find("Feedback") if u is not None else None
        o = u.find("Output") if u is not None else None
        p = patch.get(uid, {})
        n = len(bind.get(uid, []))
        dev = p.get("device", "")
        out.append({
            "id": uid, "name": (u.get("Name") if u is not None else "") or f"Universe {int(uid) + 1}",
            "exists": u is not None,
            "input": {"plugin": p.get("plugin", ""), "device": dev, "line": p.get("line", ""),
                      "profile": p.get("profile", ""), "uid": inp.get("UID", "") if inp is not None else ""},
            "feedback": {"plugin": fb.get("Plugin", "") if fb is not None else "",
                         "device": pi.device_name(fb)},
            "output": {"plugin": o.get("Plugin", "") if o is not None else "",
                       "device": pi.device_name(o)},
            "bindings": n,
            "status": "ok" if dev else ("no_input" if n else "idle"),
        })
    return out


def set_input(root: ET.Element, uid: str, *, plugin: str = "MIDI", device: str = "",
              line="0", profile: str = "", feedback: Optional[bool] = None) -> dict:
    """Patch an input device on universe *uid* (the universe is created when
    missing).  Feedback follows the input when *feedback* is true."""
    device = (device or "").strip()
    if not device:
        raise InputError("Give the device name as QLC+ shows it (Inputs/Outputs tab).")
    u = _uni(root, str(uid), create=True)
    if u is None:
        raise InputError("This workspace has no <Engine>.")
    old = u.find("Input")
    attrs = {"Plugin": plugin or "MIDI", "Line": str(line or "0")}
    if profile:
        attrs["Profile"] = profile
    attrs["Name"] = device
    attrs["UID"] = (old.get("UID") if old is not None and pi.device_name(old).casefold() == device.casefold()
                    and old.get("UID") else device)
    new = ET.Element("Input", attrs)
    if old is not None:
        i = list(u).index(old)
        u.remove(old)
        u.insert(i, new)
    else:
        u.insert(0, new)
    if feedback:
        old_fb = u.find("Feedback")
        fb = ET.Element("Feedback", {k: v for k, v in attrs.items() if k != "Profile"})
        if old_fb is not None:
            i = list(u).index(old_fb)
            u.remove(old_fb)
            u.insert(i, fb)
        else:
            u.append(fb)
    return {"universe": str(uid), "device": device, "plugin": attrs["Plugin"]}


def clear_input(root: ET.Element, uid: str) -> dict:
    u = _uni(root, str(uid))
    if u is None or u.find("Input") is None:
        raise InputError(f"Universe {uid} has no input to clear.")
    u.remove(u.find("Input"))
    fb = u.find("Feedback")
    if fb is not None:
        u.remove(fb)
    return {"universe": str(uid)}


# ── re-patch ─────────────────────────────────────────────────────────────────

def move_bindings(root: ET.Element, src: str, dst: str, shift: int = 0) -> dict:
    """Move every VC binding of universe *src* to *dst*, adding *shift* to
    each channel.  Returns ``{moved, clashes}``; a binding that would land on
    one the destination already has is reported, and the whole move refused."""
    src, dst, shift = str(src), str(dst), int(shift or 0)
    if src == dst and not shift:
        raise InputError("Nothing to do: same universe and no shift.")
    bind = _bindings(root)
    mine = bind.get(src, [])
    if not mine:
        raise InputError(f"No binding listens to universe {int(src) + 1 if src.isdigit() else src}.")
    taken = {(e.get("Channel")) for e in bind.get(dst, []) if e not in mine}
    clashes, new_ch = [], []
    for e in mine:
        c = int(e.get("Channel")) + shift
        if c < 0:
            raise InputError(f"A channel would go below 1 (shift {shift}).")
        if str(c) in taken:
            clashes.append(c)
        new_ch.append(c)
    if clashes:
        raise InputError(f"Channel(s) {sorted(set(c + 1 for c in clashes))} already have a binding on "
                         f"universe {int(dst) + 1 if dst.isdigit() else dst} — nothing moved.")
    for e, c in zip(mine, new_ch):
        e.set("Universe", dst)
        e.set("Channel", str(c))
    return {"moved": len(mine), "src": src, "dst": dst, "shift": shift}


def swap_universes(root: ET.Element, a: str, b: str) -> dict:
    a, b = str(a), str(b)
    if a == b:
        raise InputError("Choose two different universes.")
    bind = _bindings(root)
    na, nb = len(bind.get(a, [])), len(bind.get(b, []))
    if not na and not nb:
        raise InputError("Neither universe has bindings.")
    la, lb = list(bind.get(a, [])), list(bind.get(b, []))
    for e in la:
        e.set("Universe", b)
    for e in lb:
        e.set("Universe", a)
    return {"a": a, "b": b, "moved_a": na, "moved_b": nb}


# ── simulate ─────────────────────────────────────────────────────────────────

def _funcs(root: ET.Element) -> Dict[str, str]:
    eng = root.find("Engine")
    return {f.get("ID", ""): f.get("Name", "") for f in (eng.findall("Function") if eng is not None else [])}


def _walk(el: ET.Element, trail: List[str], out: list) -> None:
    for c in el:
        if vc_ops._is_widget(c):
            cap = c.get("Caption", "") or f"{vc_ops._local(c.tag)} {c.get('ID', '')}"
            t = trail + [cap]
            out.append((c, " › ".join(trail)))
            _walk(c, t, out)
        elif len(c):
            _walk(c, trail, out)


def widgets_with_input(root: ET.Element) -> List[dict]:
    """Every VC widget with an input binding: ``{id, caption, type, path,
    function, bindings: [{slot, universe, channel, text}]}``."""
    vc = root.find("VirtualConsole")
    if vc is None:
        return []
    funcs = _funcs(root)
    flat: list = []
    _walk(vc, [], flat)
    out = []
    for w, path in flat:
        bs = [(slot, el) for slot, _p, el in pi.widget_bindings(w)
              if el.tag == "Input" and el.get("Universe") is not None and el.get("Channel") is not None]
        if not bs:
            continue
        fn = next((c for c in w if c.tag in ("Function", "Chaser") and c.get("ID")), None)
        out.append({"id": w.get("ID", ""), "caption": w.get("Caption", ""), "type": vc_ops._local(w.tag),
                    "path": path, "function": funcs.get(fn.get("ID"), "") if fn is not None else "",
                    "bindings": [{"slot": s, "universe": e.get("Universe"), "channel": e.get("Channel"),
                                  "text": decode(e.get("Channel"))["text"]} for s, e in bs]})
    return out


def simulate(root: ET.Element, universe: str, channel: int) -> dict:
    """What a message on *universe* / stored *channel* would trigger, with a
    hint when the same number exists on another MIDI channel (OMNI)."""
    universe = str(universe)
    hits, near = [], []
    for w in widgets_with_input(root):
        for b in w["bindings"]:
            if b["universe"] != universe:
                continue
            row = {k: w[k] for k in ("id", "caption", "type", "path", "function")}
            row.update(slot=b["slot"], channel=b["channel"], text=b["text"])
            if int(b["channel"]) == int(channel):
                hits.append(row)
            elif (int(b["channel"]) & 0xFFF) == (int(channel) & 0xFFF):
                near.append(row)
    u = next((x for x in universes(root) if x["id"] == universe), None)
    notes = []
    if u is None or u["status"] == "no_input" or (u and not u["input"]["device"]):
        notes.append("This universe has no input device patched — in QLC+ nothing would answer.")
    if not hits and near:
        notes.append("The same number is bound on another MIDI channel — see 'near misses' "
                     "(OMNI mode adds the MIDI channel to the number).")
    elif not hits:
        notes.append("Nothing in the Virtual Console listens to this message.")
    if len(hits) > 1:
        notes.append(f"{len(hits)} widgets share this message — all of them fire.")
    return {"universe": universe, "channel": int(channel), "decoded": decode(channel),
            "hits": hits, "near": near, "notes": notes}


# ── remembered controllers and input profiles ────────────────────────────────

def _controllers_path() -> str:
    return os.environ.get("QSK_CONTROLLERS") or os.path.join(
        os.path.expanduser("~"), ".qlc_swiss_knife", "controllers.json")


def controllers() -> List[dict]:
    try:
        with open(_controllers_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    return [c for c in data.get("controllers", []) if isinstance(c, dict) and c.get("name")]


def remember_controller(name: str, *, plugin: str = "MIDI", device: str = "", line="0",
                        profile: str = "", feedback: bool = True) -> List[dict]:
    name, device = (name or "").strip(), (device or "").strip()
    if not name or not device:
        raise InputError("Give the controller a name and its device name.")
    items = [c for c in controllers() if c["name"].casefold() != name.casefold()]
    items.append({"name": name, "plugin": plugin or "MIDI", "device": device, "line": str(line or "0"),
                  "profile": profile or "", "feedback": bool(feedback)})
    items.sort(key=lambda c: c["name"].casefold())
    os.makedirs(os.path.dirname(_controllers_path()), exist_ok=True)
    with open(_controllers_path(), "w", encoding="utf-8") as fh:
        json.dump({"controllers": items}, fh, indent=1, ensure_ascii=False)
    return items


def forget_controller(name: str) -> List[dict]:
    items = [c for c in controllers() if c["name"].casefold() != (name or "").strip().casefold()]
    os.makedirs(os.path.dirname(_controllers_path()), exist_ok=True)
    with open(_controllers_path(), "w", encoding="utf-8") as fh:
        json.dump({"controllers": items}, fh, indent=1, ensure_ascii=False)
    return items


PROFILE_DIRS = [
    os.path.join(os.path.expanduser("~"), ".qlcplus", "inputprofiles"),
    os.path.join(os.path.expanduser("~"), "Library", "Application Support", "QLC+", "inputprofiles"),
    "/Applications/QLC+.app/Contents/Resources/InputProfiles",
    "/Applications/QLC+.app/Contents/Resources/inputprofiles",
    "/usr/share/qlcplus/inputprofiles", "/usr/local/share/qlcplus/inputprofiles",
    "C:\\QLC+5\\InputProfiles", "C:\\QLC+\\InputProfiles",
]


def profiles(dirs=None) -> List[str]:
    """Names of the installed input profiles (``Manufacturer Model``, as the
    workspace stores them)."""
    env = os.environ.get("QLCPLUS_INPUTPROFILES")
    dirs = dirs if dirs is not None else (env.split(os.pathsep) if env else PROFILE_DIRS)
    names = set()
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.lower().endswith(".qxi"):
                continue
            try:
                t = ET.parse(os.path.join(d, f)).getroot()
            except (ET.ParseError, OSError):
                continue
            mfg = next((e.text for e in t.iter() if e.tag.endswith("Manufacturer")), "") or ""
            model = next((e.text for e in t.iter() if e.tag.endswith("Model")), "") or ""
            n = f"{mfg.strip()} {model.strip()}".strip()
            if n:
                names.add(n)
    return sorted(names, key=str.casefold)
