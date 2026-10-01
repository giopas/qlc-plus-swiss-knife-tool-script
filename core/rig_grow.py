"""
Grow a rig: wire new fixtures into the show's existing looks (WORKPLAN 2.7).

A fixture copied into a show (Function Porter, step 2) only plays the
functions ported with it.  The show's own scenes, chasers, cue lists and
buttons don't know it, so it stays dark when you press them.  Here every
new fixture can **play like** an existing one (its *template*): every scene
and sequence step that sets the template also sets the new fixture —
translated by capability when the fixture types differ, every channel
declared.  Chasers, collections, cue lists, shows and VC buttons play scenes,
so they follow with no change.  EFX that move the template get the new
fixture too.

What is not wired is said plainly (:func:`not_wired`): RGB matrices run on a
fixture group (left as they are — their pattern would change), scripts that
set the template's channels directly, *Channels* sliders.

Pure functions on an (un-namespaced) workspace root, deterministic; the
Porter calls :func:`wire` inside its build, so the result is one step of the
show in progress and goes through the Doctor gate.
"""
from __future__ import annotations

import copy
import math
import xml.etree.ElementTree as ET


def _engine(root: ET.Element):
    return root.find("Engine")


def _infos(root: ET.Element) -> dict[str, dict]:
    from core.porter import _fixture_infos
    return _fixture_infos(root)


def _def_of(info: dict, defs: dict):
    return defs.get((info["manufacturer"].strip().lower(), info["model"].strip().lower()))


def _type_key(info: dict) -> tuple:
    return (info["manufacturer"], info["model"], info["mode"])


# ── Which existing fixture should a new one follow? ─────────────────────────

HIGH_MM = 1500   # above this a fixture hangs (truss, ceiling); below it stands on the floor


def suggest(root: ET.Element, new_ids, exclude=()) -> dict[str, dict]:
    """``new id → {"template": id | "", "why": text}``.

    Default: an existing fixture **at the same level** (hanging above
    1.5 m, or on the floor — so ceiling lights follow ceiling lights), on the
    **same side** (nearest left–right on the 3D stage, then nearest overall).
    Without positions: the first existing fixture of the same type, else
    none.  *exclude*: ids that can't be templates (the other new fixtures)."""
    from core.porter import _positions
    infos = _infos(root)
    pos = _positions(root)
    skip = set(map(str, new_ids)) | set(map(str, exclude))
    cands = [i for i in infos if i not in skip]
    out = {}
    for n in map(str, new_ids):
        best, why = "", "no existing fixture to follow"
        placed = [c for c in cands if c in pos]
        if n in pos and placed:
            high = pos[n][1] >= HIGH_MM
            level = [c for c in placed if (pos[c][1] >= HIGH_MM) == high] or placed
            best = min(level, key=lambda c: (abs(pos[n][0] - pos[c][0]),
                                             math.dist(pos[n], pos[c]),
                                             int(c) if c.isdigit() else 0))
            where = "hanging" if pos[best][1] >= HIGH_MM else "on the floor"
            why = f"nearest fixture {where}, same side of the stage"
        elif n in infos:
            same = [c for c in cands if _type_key(infos[c]) == _type_key(infos[n])]
            if same:
                best, why = same[0], "same fixture type"
            elif cands:
                best, why = cands[0], "first fixture of the show (no 3D positions)"
        out[n] = {"template": best, "why": why}
    return out


def usage(root: ET.Element) -> dict[str, int]:
    """``fixture id → number of scenes / sequences that set it`` — how many
    looks a new fixture would join by following it."""
    eng = _engine(root)
    out: dict[str, int] = {}
    if eng is None:
        return out
    for fn in eng.findall("Function"):
        if fn.get("Type") not in ("Scene", "Sequence"):
            continue
        for i in {fv.get("ID", "") for fv in fn.findall("FixtureVal")}:
            out[i] = out.get(i, 0) + 1
    return out


# ── Wiring ──────────────────────────────────────────────────────────────────

def _pairs(text: str) -> dict[int, int]:
    parts = (text or "").strip().split(",")
    out = {}
    for i in range(0, len(parts) - 1, 2):
        try:
            out[int(parts[i])] = int(parts[i + 1])
        except ValueError:
            continue
    return out


def _value_maker(root: ET.Element, plan: dict[str, str], defs: dict):
    """``(new, template) → fn(text) -> text | None`` for each wired pair.

    Same fixture type: the template's values, completed to every channel.
    Different types: translated by capability (``core.capability_map``);
    ``None`` when a definition is missing (reported, not guessed)."""
    from core.capability_map import can_translate, translate_text
    from core.porter import _neutral_maps, _complete
    infos = _infos(root)
    neutral = _neutral_maps(infos, defs)
    makers, problems = {}, {}
    for n, t in plan.items():
        ni, ti = infos.get(n), infos.get(t)
        if not ni or not ti:
            problems[n] = "fixture not found"
            continue
        nn = neutral.get(n)
        if _type_key(ni) == _type_key(ti):
            makers[n] = (lambda text, nn=nn: _complete(text, nn) if nn else (text or "").strip())
            continue
        nd, td = _def_of(ni, defs), _def_of(ti, defs)
        if can_translate(td, ti["mode"]) and can_translate(nd, ni["mode"]):
            def mk(text, td=td, tm=ti["mode"], nd=nd, nm=ni["mode"], nn=nn):
                out, _notes = translate_text(td, tm, nd, nm, text or "")
                return _complete(out, nn) if nn else out
            makers[n] = mk
        else:
            problems[n] = (f"the fixture definition (.qxf) of {(ti if not td else ni)['model']} "
                           "was not found, so its values can't be translated — put the .qxf "
                           "next to the show or in QLC+'s own fixtures folder, then check again")
    return makers, problems


def wire(root: ET.Element, plan: dict[str, str], defs: dict | None = None,
         functions=None) -> dict:
    """Wire each new fixture (key) into the scenes, sequences and EFX of its
    template (value; ``""`` = leave it out).  Changes *root* in place.

    *functions*: only these function IDs (the show's own, not the ones
    ported in the same step); ``None`` = all.

    Idempotent: a scene that already sets the new fixture is left as it is.
    Returns the report: ``{"fixtures": {new: {template, scenes, steps, efx}},
    "problems": {new: why}, "not_wired": [...lines], "total": n}``."""
    defs = defs or {}
    plan = {str(n): str(t) for n, t in (plan or {}).items() if t not in (None, "")}
    eng = _engine(root)
    rep = {"fixtures": {}, "problems": {}, "not_wired": [], "total": 0}
    if eng is None or not plan:
        return rep
    makers, problems = _value_maker(root, plan, defs)
    rep["problems"] = problems
    stats = {n: {"template": t, "scenes": 0, "steps": 0, "efx": 0} for n, t in plan.items()
             if n in makers}
    only = None if functions is None else set(map(str, functions))
    for fn in eng.findall("Function"):
        ftype = fn.get("Type")
        if only is not None and fn.get("ID", "") not in only:
            continue
        if ftype in ("Scene", "Sequence"):
            vals = fn.findall("FixtureVal")
            have = {fv.get("ID", "") for fv in vals}
            for n, st in stats.items():
                t = st["template"]
                if t in have and n not in have:
                    src = next(fv for fv in vals if fv.get("ID") == t)
                    el = copy.deepcopy(src)
                    el.set("ID", n)
                    el.text = makers[n](src.text or "")
                    fn.insert(list(fn).index(vals[-1]) + 1, el)
                    vals.append(el)
                    have.add(n)
                    if ftype == "Scene":
                        st["scenes"] += 1
            if ftype == "Sequence":
                for step in fn.findall("Step"):
                    items = _seq_items(step.text or "")
                    ids = [f for f, _ in items]
                    added = False
                    for n, st in stats.items():
                        t = st["template"]
                        if t in ids and n not in ids:
                            items.append((n, makers[n](dict(items)[t])))
                            ids.append(n)
                            st["steps"] += 1
                            added = True
                    if added:
                        step.text = ":".join(f"{f}:{v}" for f, v in items)
                        step.set("Values", str(sum(len(_pairs(v)) for _, v in items)))
        elif ftype == "EFX":
            fxs = [e for e in fn.findall("Fixture")]
            have = {(e.findtext("ID") or "").strip() for e in fxs}
            for n, st in stats.items():
                t = st["template"]
                if t in have and n not in have:
                    src = next(e for e in fxs if (e.findtext("ID") or "").strip() == t)
                    el = copy.deepcopy(src)
                    el.find("ID").text = n
                    if el.find("Head") is not None:
                        el.find("Head").text = "0"
                    fn.insert(list(fn).index(fxs[-1]) + 1, el)
                    fxs.append(el)
                    have.add(n)
                    st["efx"] += 1
    rep["fixtures"] = stats
    rep["total"] = sum(s["scenes"] + s["steps"] + s["efx"] for s in stats.values())
    rep["not_wired"] = not_wired(root, plan)
    return rep


def _seq_items(text: str) -> list[tuple[str, str]]:
    parts = (text or "").strip().split(":")
    out = []
    for i in range(0, len(parts) - 1, 2):
        f = parts[i].strip()
        if f.isdigit():
            out.append((f, parts[i + 1].strip()))
    return out


def not_wired(root: ET.Element, plan: dict[str, str]) -> list[str]:
    """What following the template does **not** reach, each with what to do."""
    eng = _engine(root)
    if eng is None:
        return []
    new = set(plan)
    tmpl = {t for t in plan.values() if t}
    names = {i: inf["name"] for i, inf in _infos(root).items()}
    groups = {}
    for g in eng.findall("FixtureGroup"):
        heads = {h.get("Fixture", "") for h in g.findall("Head")}
        groups[g.get("ID", "")] = (g.findtext("Name") or g.get("ID", ""), heads)
    lines = []
    by_group: dict[str, list[str]] = {}
    for fn in eng.findall("Function"):
        ftype = fn.get("Type")
        if ftype == "RGBMatrix":
            gid = (fn.findtext("FixtureGroup") or "").strip()
            gname, heads = groups.get(gid, (gid, set()))
            if heads & tmpl and not heads & new:
                by_group.setdefault(gname, []).append(fn.get("Name", ""))
        elif ftype == "Script":
            cmds = " ".join((c.text or "") for c in fn.findall("Command"))
            if any(f"setfixture:{t}" in cmds for t in tmpl):
                lines.append(f"Script '{fn.get('Name', '')}' sets channels of a followed "
                             "fixture directly — edit it in QLC+ to include the new ones.")
    for gname, mats in sorted(by_group.items()):
        lines.append(f"RGB matrices on group '{gname}' ({', '.join(sorted(mats))}) stay on that "
                     "group — their pattern would change with more heads. To include the new "
                     "fixtures, add them to the group in QLC+ (or a copy of it).")
    for sl in root.iter("Slider"):
        chans = [c for c in sl.findall("Channel") if c.get("Fixture") in tmpl]
        if chans:
            lines.append(f"VC slider '{sl.get('Caption', '')}' controls channels of a followed "
                         "fixture — add the new fixture's channels in QLC+ if it should too.")
    return lines


def summary_lines(rep: dict, names: dict[str, str] | None = None) -> list[str]:
    """Human lines for the report / step 4."""
    names = names or {}
    out = []
    for n, st in rep.get("fixtures", {}).items():
        bits = [f"{st['scenes']} scene(s)"]
        if st["steps"]:
            bits.append(f"{st['steps']} sequence step(s)")
        if st["efx"]:
            bits.append(f"{st['efx']} EFX")
        out.append(f"'{names.get(n, n)}' plays like '{names.get(st['template'], st['template'])}' "
                   f"— added to {', '.join(bits)}")
    for n, why in rep.get("problems", {}).items():
        out.append(f"'{names.get(n, n)}' not wired: {why}")
    return out
