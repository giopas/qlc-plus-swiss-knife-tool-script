"""
core/porter_input.py — key / MIDI input control for the Function Porter
======================================================================
WORKPLAN Phase 1.6: port the controller setup that ported VC bindings
depend on, so they still respond in the new file.

* **Input patch.** ``<Engine><InputOutputMap><Universe ID><Input …>`` says
  which device (plugin + UID/Name, line, input profile) feeds a universe.
  VC bindings (``<Input Universe="1" Channel="40"/>``) only respond when that
  universe has a device.  :func:`apply_patch` copies the source's input
  (and feedback) to the target universe the bindings end up on when the
  target has no device there; if the target has a *different* device there
  the bindings are kept and a warning says so.
* **Universe mapping.** Bindings can move to another target universe
  (``{source universe ID: target universe ID}``, QLC+ IDs, 0-based):
  :func:`remap_universes` rewrites ``<Input Universe>`` in ported widgets.
* **Bindings only.** :func:`copy_bindings` copies the key/MIDI bindings of
  source widgets onto *matching* target widgets (same function after
  porting, else same type + caption) — for a rebuilt VC that keeps the
  controller layout.

Binding keys: ``("key", "Space")`` or ``("input", universe, channel)``.
Binding *slots*: bindings sit directly in a widget (``""``) or in a child
such as ``Next`` / ``Previous`` / ``Stop`` of a CueList or ``Enable`` of a
frame (slot = that tag path).  Works on namespace-stripped trees.
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET  # nosec B405
from typing import Dict, Iterable, List, Optional, Tuple

from core import vc_ops

_local = vc_ops._local
_is_widget = vc_ops._is_widget
BINDING_TAGS = ("Input", "Key")
NONE_DEV = ("", "None", None)


# ── the input patch ──────────────────────────────────────────────────────────

def _iomap(root: ET.Element) -> Optional[ET.Element]:
    eng = root.find("Engine")
    return eng.find("InputOutputMap") if eng is not None else None


def device_name(inp: Optional[ET.Element]) -> str:
    """Device of an ``<Input>`` patch ('' when none): QLC+ 5.2.2 saves Name +
    a numeric UID, 5.2.1 GIT saves only UID="<name>"."""
    if inp is None or inp.get("Plugin") in NONE_DEV:
        return ""
    for k in ("Name", "UID"):
        v = inp.get(k)
        if v not in NONE_DEV:
            return v
    return ""


def read_patch(root: ET.Element) -> Dict[str, dict]:
    """``universe ID → {name, plugin, device, profile, line}`` for every universe."""
    out: Dict[str, dict] = {}
    iom = _iomap(root)
    if iom is None:
        return out
    for u in iom.findall("Universe"):
        inp = u.find("Input")
        out[u.get("ID", "")] = {
            "name": u.get("Name", ""),
            "plugin": (inp.get("Plugin", "") if inp is not None else ""),
            "device": device_name(inp),
            "profile": (inp.get("Profile", "") if inp is not None else ""),
            "line": (inp.get("Line", "") if inp is not None else ""),
        }
    return out


def _same_device(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def apply_patch(src_root: ET.Element, tgt_root: ET.Element,
                used: Dict[str, str], copy_input: bool = True) -> List[dict]:
    """Make sure every target universe that ported bindings use has the
    source's input device.

    *used*: source universe → target universe of the bindings kept.
    Returns one entry per target universe:
    ``{src, tgt, device, action, message}`` with action ``ok`` (same device
    already patched), ``copied``, ``other_device`` (warning), ``none``
    (source had no device either — warning) or ``skipped`` (copy disabled).
    """
    src_iom = _iomap(src_root)
    src_patch = read_patch(src_root)
    tgt_patch = read_patch(tgt_root)
    out: List[dict] = []
    for su, tu in sorted(used.items(), key=lambda kv: (int(kv[1]) if kv[1].isdigit() else 0, kv[0])):
        sdev = src_patch.get(su, {}).get("device", "")
        tdev = tgt_patch.get(tu, {}).get("device", "")
        label = f"universe {int(tu) + 1 if tu.isdigit() else tu}"
        e = {"src": su, "tgt": tu, "device": sdev}
        if not sdev:
            e.update(action="none", message=f"{label}: the source has no input device on "
                     f"universe {int(su) + 1 if su.isdigit() else su} either — bindings won't respond until one is patched")
        elif tdev and _same_device(sdev, tdev):
            e.update(action="ok", message=f"{label}: already patched with {tdev}")
        elif tdev:
            e.update(action="other_device", message=f"{label}: the target has another device "
                     f"({tdev}); the ported bindings will listen to it, not to {sdev}")
        elif not copy_input:
            e.update(action="skipped", message=f"{label}: input patch not copied (option off) — "
                     f"bindings won't respond until {sdev} is patched")
        else:
            _copy_input(src_iom, su, tgt_root, tu)
            e.update(action="copied", message=f"{label}: input patch copied from the source ({sdev})")
        out.append(e)
    return out


def _copy_input(src_iom: ET.Element, su: str, tgt_root: ET.Element, tu: str) -> None:
    su_el = next(u for u in src_iom.findall("Universe") if u.get("ID") == su)
    eng = tgt_root.find("Engine")
    iom = eng.find("InputOutputMap")
    if iom is None:
        iom = ET.SubElement(eng, "InputOutputMap")
    tu_el = next((u for u in iom.findall("Universe") if u.get("ID") == tu), None)
    if tu_el is None:
        tu_el = ET.Element("Universe", {"Name": f"Universe {int(tu) + 1}", "ID": tu})
        unis = iom.findall("Universe")
        after = [u for u in unis if int(u.get("ID", "0")) < int(tu)]
        pos = list(iom).index(after[-1]) + 1 if after else len(
            [c for c in iom if c.tag != "Universe"])
        iom.insert(pos, tu_el)
    for tag in ("Input", "Feedback"):
        old = tu_el.find(tag)
        new = su_el.find(tag)
        if new is None:
            continue
        new = copy.deepcopy(new)
        if old is not None:
            idx = list(tu_el).index(old)
            tu_el.remove(old)
            tu_el.insert(idx, new)
        else:
            # QLC+ order: Input, Output, Feedback
            if tag == "Input":
                tu_el.insert(0, new)
            else:
                tu_el.append(new)
    for k in ("Passthrough",):
        if su_el.get(k) is not None and tu_el.get(k) is None:
            tu_el.set(k, su_el.get(k))


def summary(src_root: Optional[ET.Element], tgt_root: Optional[ET.Element]) -> dict:
    """For the Porter UI: source universes that VC bindings use (with their
    device and binding count) and every target universe with its device.
    ``{"source": [{universe, name, device, profile, bindings}], "target": [...],
    "keys": <number of key bindings in the source VC>}``."""
    out = {"source": [], "target": [], "keys": 0}
    if src_root is not None:
        patch = read_patch(src_root)
        counts: Dict[str, int] = {}
        vc = src_root.find("VirtualConsole")
        if vc is not None:
            for el in vc.iter():
                k = binding_key(el) if _local(el.tag) in BINDING_TAGS else None
                if k and k[0] == "input" and k[2]:
                    counts[k[1]] = counts.get(k[1], 0) + 1
                elif k and k[0] == "key":
                    out["keys"] += 1
        for u in sorted(counts, key=lambda x: int(x) if x.isdigit() else 0):
            p = patch.get(u, {})
            out["source"].append({"universe": u, "name": p.get("name") or f"Universe {int(u) + 1}",
                                  "device": p.get("device", ""), "profile": p.get("profile", ""),
                                  "bindings": counts[u]})
    if tgt_root is not None:
        for u, p in sorted(read_patch(tgt_root).items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
            out["target"].append({"universe": u, "name": p["name"], "device": p["device"]})
    return out


# ── bindings ─────────────────────────────────────────────────────────────────

def binding_key(el: ET.Element):
    tag = _local(el.tag)
    if tag == "Key":
        return ("key", (el.text or "").strip())
    if tag == "Input":
        return ("input", el.get("Universe", ""), el.get("Channel", ""))
    return None


def describe(key) -> str:
    if key[0] == "key":
        return f"key {key[1]}"
    u = key[1]
    return f"MIDI/input U{int(u) + 1 if u.isdigit() else u} ch {key[2]}"


def widget_bindings(w: ET.Element) -> List[Tuple[str, ET.Element, ET.Element]]:
    """``[(slot, parent, binding element)]`` of widget *w* itself (child
    widgets excluded)."""
    out = []

    def walk(el, slot):
        for c in el:
            if _is_widget(c):
                continue
            if _local(c.tag) in BINDING_TAGS:
                out.append((slot, el, c))
            elif len(c):
                walk(c, f"{slot}/{_local(c.tag)}" if slot else _local(c.tag))
    walk(w, "")
    return out


def remap_universes(unit: ET.Element, umap: Dict[str, str]) -> int:
    """Rewrite ``<Input Universe>`` in *unit* through *umap*; returns count."""
    n = 0
    if not umap:
        return 0
    for el in unit.iter("Input"):
        u = el.get("Universe")
        if u is not None and u in umap and umap[u] != u and el.get("Channel") is not None:
            el.set("Universe", umap[u])
            n += 1
    return n


def input_universes(elements: Iterable[ET.Element]) -> set:
    """Universes of the ``<Input Universe Channel>`` bindings inside *elements*."""
    out = set()
    for e in elements:
        for el in e.iter("Input"):
            if el.get("Universe") is not None and el.get("Channel") is not None:
                out.add(el.get("Universe"))
    return out


def target_binding_owners(vc: Optional[ET.Element]) -> Dict[tuple, List[ET.Element]]:
    """``binding key → [target widgets that use it]``."""
    owners: Dict[tuple, List[ET.Element]] = {}
    if vc is None:
        return owners
    for w in vc.iter():
        if w is vc or not _is_widget(w):
            continue
        for _slot, _p, el in widget_bindings(w):
            k = binding_key(el)
            if k is not None:
                owners.setdefault(k, []).append(w)
    return owners


def remove_binding(w: ET.Element, key) -> int:
    """Remove every binding *key* from widget *w* (not its children)."""
    n = 0
    for _slot, p, el in widget_bindings(w):
        if binding_key(el) == key:
            p.remove(el)
            n += 1
    return n


def widget_label(w: ET.Element) -> str:
    return f"{_local(w.tag)} '{w.get('Caption', '')}' (ID {w.get('ID', '?')})"


# ── bindings only: copy onto matching target widgets ─────────────────────────

_NORM = re.compile(r"[^0-9a-z]+")


def _norm_caption(s: str) -> str:
    return _NORM.sub(" ", (s or "").casefold()).strip()


def copy_bindings(src_root: ET.Element, tgt_root: ET.Element, fmap: Dict[str, str],
                  opts: dict, src_widgets: Optional[List[ET.Element]] = None) -> dict:
    """Copy key/MIDI bindings of source widgets onto matching target widgets.

    Match: a target widget using the ported copy of the source widget's
    function (``fmap``), else the only target widget of the same type with
    the same caption (letters/digits compared, case-insensitive).  The
    binding policy (``opts["bindings"]``: keep_free | keep | source_wins |
    drop) and universe map (``opts["universe_map"]``) apply as for ported
    widgets.  Returns ``{log, used}`` (``used``: source → target universe).
    """
    from core.porter_vc import widget_function_refs
    mode = opts.get("bindings") or "keep_free"
    umap = {str(k): str(v) for k, v in (opts.get("universe_map") or {}).items()}
    log: List[dict] = []
    used: Dict[str, str] = {}
    src_vc, tgt_vc = src_root.find("VirtualConsole"), tgt_root.find("VirtualConsole")
    if src_vc is None or tgt_vc is None or mode == "drop":
        return {"log": log, "used": used}
    tgt_widgets = [w for w in tgt_vc.iter() if w is not tgt_vc and _is_widget(w)]
    by_func: Dict[str, List[ET.Element]] = {}
    by_cap: Dict[tuple, List[ET.Element]] = {}
    for w in tgt_widgets:
        for f in widget_function_refs(w):
            by_func.setdefault(f, []).append(w)
        by_cap.setdefault((_local(w.tag), _norm_caption(w.get("Caption", ""))), []).append(w)
    owners = target_binding_owners(tgt_vc)
    sources = src_widgets if src_widgets is not None else [
        w for w in src_vc.iter() if w is not src_vc and _is_widget(w)]
    for sw in sources:
        binds = widget_bindings(sw)
        if not binds:
            continue
        match = None
        for f in widget_function_refs(sw):
            cands = [w for w in by_func.get(fmap.get(f, ""), []) if _local(w.tag) == _local(sw.tag)]
            if len(cands) == 1:
                match, how = cands[0], "same function"
                break
        if match is None:
            cands = by_cap.get((_local(sw.tag), _norm_caption(sw.get("Caption", ""))), [])
            if len(cands) == 1 and _norm_caption(sw.get("Caption", "")):
                match, how = cands[0], "same caption"
        if match is None:
            for _s, _p, el in binds:
                k = binding_key(el)
                log.append({"widget": widget_label(sw), "binding": describe(k),
                            "action": "not copied: no matching target widget"})
            continue
        for slot, _p, el in binds:
            new = copy.deepcopy(el)
            if _local(new.tag) == "Input" and new.get("Universe") in umap:
                new.set("Universe", umap[new.get("Universe")])
            k = binding_key(new)
            others = [w for w in owners.get(k, []) if w is not match]
            mine = [w for w in owners.get(k, []) if w is match]
            entry = {"widget": widget_label(match), "binding": describe(k),
                     "from": widget_label(sw), "how": how}
            if mine:
                entry["action"] = "already there"
                log.append(entry)
                continue
            if others and mode == "keep_free":
                entry["action"] = "not copied: used by " + ", ".join(widget_label(w) for w in others)
                log.append(entry)
                continue
            if others and mode == "source_wins":
                for w in others:
                    remove_binding(w, k)
                    owners[k].remove(w)
                entry["action"] = "copied, removed from " + ", ".join(widget_label(w) for w in others)
            else:
                entry["action"] = "copied"
            parent = match
            for tag in [t for t in slot.split("/") if t]:
                nxt = parent.find(tag)
                if nxt is None:
                    nxt = ET.SubElement(parent, tag)
                parent = nxt
            parent.append(new)
            owners.setdefault(k, []).append(match)
            if k[0] == "input":
                src_u = el.get("Universe", "")
                used[src_u] = k[1]
            log.append(entry)
    return {"log": log, "used": used}
