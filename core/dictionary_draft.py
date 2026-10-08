"""
core/dictionary_draft.py
========================
Facts about every function of a show, and a first description drawn from
them (v3.0.1).  Used by the Dictionary's *Draft descriptions* button and by
Claude's ``dictionary_context`` / ``dictionary_set`` tools.

Deterministic: the same show always gives the same text.  A description is
only drawn from what the show says (structure, names, colours read from the
fixture definitions); nothing is guessed.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from core import qxw_io, scene_words, script_cmds


def join_words(items: List[str]) -> str:
    """'a', 'a and b', 'a, b and c'."""
    items = [str(x) for x in items]
    return " and ".join(items) if len(items) <= 2 else ", ".join(items[:-1]) + " and " + items[-1]


def show_facts(root, names: Dict[str, str], fxinfo: Dict[str, dict]) -> Dict[str, dict]:
    """{function id: {facts, used_by, _only_steps, _auto, _look, _dom, _runs}}
    for a namespace-free workspace *root*."""
    eng = root.find("Engine")                      # not the <Function ID=…/> references of VC buttons
    funcs = [(f.get("ID", ""), f.get("Type", ""), f)
             for f in (eng.findall("Function") if eng is not None else [])]
    parents: Dict[str, list] = {}                 # child id → [(parent id, type, step number)]
    out: Dict[str, dict] = {}
    for fid, typ, f in funcs:
        info: Dict[str, Any] = {}
        if typ in ("Chaser", "Collection", "Sequence"):
            kids = [(st.text or "").strip() for st in f.iter("Step")]
            kids = [k for k in kids if k.isdigit()]
            for n, k in enumerate(kids, 1):
                parents.setdefault(k, []).append((fid, typ, n))
            if kids:
                info["facts"] = (f"{len(kids)} step(s): " + ", ".join(names.get(k, "?") for k in kids[:6])
                                 + ("…" if len(kids) > 6 else ""))
        elif typ == "Scene":
            vals = []
            for fv in f.iter("FixtureVal"):
                p_ = (fv.text or "").split(",")
                vals += [int(x) for x in p_[1::2] if x.strip().lstrip("-").isdigit()]
            n = len(list(f.iter("FixtureVal")))
            if not n:
                info["facts"] = "no fixture values"
            else:
                up = sum(1 for v in vals if v > 0)
                info["facts"] = (f"{n} fixture(s); " + ("all values 0 (blackout/neutral)" if not up
                                                       else f"{up} of {len(vals)} channel values above 0"))
                look = scene_words.describe(f, fxinfo) if fxinfo else ""
                if look:
                    info["facts"] += "; looks: " + look
                    info["_look"] = look
                    info["_dom"] = scene_words.dominant(f, fxinfo)
        elif typ == "EFX":
            al = f.find("Algorithm")
            info["facts"] = f"EFX {al.text}" if al is not None and al.text else "EFX"
        elif typ == "RGBMatrix":
            al = f.find("Algorithm")
            sp = f.find("Speed")
            bits = [f"pattern '{al.text}'" if al is not None and al.text else "matrix"]
            if sp is not None and sp.get("Duration"):
                bits.append(f"{sp.get('Duration')} ms per step")
            info["facts"] = ", ".join(bits)
        elif typ == "Script":
            starts, stops = [], []
            for c in f.iter("Command"):
                for verb, ref in script_cmds.func_refs(c.text):
                    (starts if verb == "start" else stops).append(ref)
            bits = []
            if starts:
                bits.append("starts " + ", ".join(names.get(r, "?") for r in dict.fromkeys(starts)))
            if stops:
                bits.append(f"stops {len(set(stops))} function(s)")
            info["facts"] = "script: " + ("; ".join(bits) if bits else "no start/stop commands")
            for r in dict.fromkeys(starts):
                parents.setdefault(r, []).append((fid, typ, 0))
        out[fid] = info
    # what a chaser runs through, by colour, and what a collection starts
    els = {fid: f for fid, _t, f in funcs}
    for fid, typ, f in funcs:
        if typ not in ("Chaser", "Sequence", "Collection") or fid not in out:
            continue
        kids = [k for k in ((st.text or "").strip() for st in f.iter("Step")) if k.isdigit()]
        if typ == "Collection":
            if kids:
                out[fid]["_runs"] = join_words([names.get(k, "?") for k in dict.fromkeys(kids)][:4])
            continue
        doms = [out.get(k, {}).get("_dom", "") for k in kids]
        if kids and all(doms):
            cols, how = scene_words.chase_words([els[k] for k in kids if k in els], fxinfo)
            kind = "chase" if typ == "Chaser" else "sequence"
            n = len(kids)
            if not cols:
                look = ""
            elif how == "level":
                look = f"{n}-step {kind} that keeps {join_words(cols[:3])} and only changes the brightness"
            elif how == "moves":
                look = (f"{n}-step {kind} in {cols[0]}, moving across the fixtures" if len(cols) == 1
                        else f"{n}-step {kind} moving {join_words(cols[:3])} across the fixtures")
            elif len(cols) == 1:
                look = f"{n}-step {kind}, all {cols[0]}"
            else:
                look = f"{n}-step {kind} through {join_words(cols[:5])}"
            out[fid]["_look"] = look
            out[fid]["facts"] = out[fid].get("facts", "") + "; step colours: " + " → ".join(doms[:8])
    for kid, plist in parents.items():
        if kid not in out:
            continue
        out[kid]["used_by"] = [f"{names.get(pid, '?')} ({pt})" for pid, pt, _n in plist][:4]
        only_steps = all(pt in ("Chaser", "Collection", "Sequence") for _pid, pt, _n in plist)
        out[kid]["_only_steps"] = only_steps
        out[kid]["_auto"] = auto_text(kid, plist, names, out)
    return out

def auto_text(kid: str, plist: list, names: Dict[str, str], facts: Dict[str, dict]) -> str:
    """"Step 3 of Rock Loop. Red on …" — where a helper sits, then what it looks like or runs."""
    by_parent: Dict[str, list] = {}
    for pid, pt, n in plist:
        if pt in ("Chaser", "Collection", "Sequence"):
            by_parent.setdefault(pid, [pt, []])[1].append(n)
    if not by_parent:
        return ""
    pid, (pt, nums) = next(iter(by_parent.items()))
    pname = names.get(pid, "?")
    nums = sorted(set(n for n in nums if n))
    if pt == "Chaser" and nums:
        where = (f"Step {nums[0]} of {pname}" if len(nums) == 1
                 else f"Steps {join_words([str(n) for n in nums])} of {pname}")
    else:
        where = f"Part of {pname}"
    others = [n for n in dict.fromkeys(names.get(p, "?") for p in list(by_parent)[1:]) if n != pname]
    if others:
        where += " (also in " + join_words(others[:2]) + (f" and {len(others) - 2} more" if len(others) > 2 else "") + ")"
    fx = facts.get(kid, {})
    what = fx.get("_look") or (f"runs {fx['_runs']}" if fx.get("_runs") else "")
    return f"{where}. {what[0].upper() + what[1:]}." if what else where


def current_facts() -> Dict[str, dict]:
    """:func:`show_facts` for the show in progress (colours when the fixture
    definitions are found next to the show or in the QLC+ library)."""
    from core import workspace
    root = workspace._state.get("qxw_root")
    if root is None:
        return {}
    root = qxw_io.strip_ns(copy.deepcopy(root))
    names = workspace._state.get("func_by_id", {})
    try:
        from core import look_builder
        from routes.doctor_routes import _defs
        fxinfo = look_builder._fixture_info(root, _defs(workspace._state.get("path") or ""))
    except Exception:  # noqa: BLE001 — colours only improve the facts
        fxinfo = {}
    return show_facts(root, names, fxinfo)


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def draft_text(fx: dict, row: dict) -> str:
    """A first description for one function: where a helper sits and what it
    looks like; for the others what they look like, run or do."""
    typ = row.get("type", "")
    if fx.get("_only_steps") and fx.get("_auto") and not row.get("vc_button"):
        return fx["_auto"]
    if fx.get("_look"):
        look = fx["_look"]
        return _cap(look if typ != "Scene" else "static look: " + look) + "."
    if typ == "Collection" and fx.get("_runs"):
        return f"Starts {fx['_runs']}" + (" together." if " and " in fx["_runs"] else ".")
    facts = fx.get("facts", "")
    if typ == "Script" and facts.startswith("script: "):
        return _cap(facts[len("script: "):].replace("; ", ", ")) + "."
    if typ in ("EFX", "RGBMatrix") and facts:
        return _cap(facts) + "."
    if typ == "Scene" and "all values 0" in facts:
        return "All channels at 0 (blackout or reset state)."
    return fx.get("_auto", "")


def draft_all(rows: List[dict], facts: Dict[str, dict], overwrite: bool = False) -> Dict[str, str]:
    """{id: description} for the rows that have none (all rows with *overwrite*)."""
    out: Dict[str, str] = {}
    for r in rows:
        if (r.get("desc") or "").strip() and not overwrite:
            continue
        text = draft_text(facts.get(r["id"], {}), r)
        if text:
            out[r["id"]] = text
    return out
