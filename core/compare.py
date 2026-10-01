"""
Compare two shows by what they *do*, not by their XML (WORKPLAN 2.8 — the
Pub test's measuring stick: is the show built with Swiss Knife as good as the
hand-made one?).

IDs differ between files, so things are matched by meaning:

* **fixtures** by DMX patch (universe + address), else by name;
* **fixture groups** by name; their heads compared through the fixture match;
* **functions** by type + name (``[imported]`` and Swiss Knife / two-letter
  prefixes ignored), in file order when a name repeats;
* **scenes** per matched fixture: decoded to level + colour with the fixture
  definitions when known (tolerance :data:`TOL`), else channel by channel;
* **chasers / sequences** step by step (the step's function by name, fade /
  hold / out), with run order and direction; **collections** by members;
  **EFX** by algorithm and fixtures; **RGB matrices** by algorithm and group;
* **Virtual Console** pages by caption, buttons / sliders / cue lists by
  caption and the function they run;
* **setlist** cue lists: the chaser they run and its songs (step names).

Result: per section ``{"same": n, "different": [...], "only_a": [...],
"only_b": [...]}``; :func:`report` writes it as text.  A is "this show" (the
show in progress), B the other file.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict

TOL = 0.06          # level / colour difference (0..1) still "the same look"
NONE_ID = "4294967295"
SECTIONS = [("fixtures", "Fixtures and patch"), ("groups", "Fixture groups"),
            ("scenes", "Scenes (looks)"), ("chasers", "Chasers and sequences"),
            ("collections", "Collections"), ("efx", "EFX"), ("matrices", "RGB matrices"),
            ("other", "Scripts and shows"), ("vc", "Virtual Console"), ("setlist", "Setlist cue lists")]


def _eng(root):
    return root.find("Engine")


def _norm(name: str) -> str:
    n = (name or "").strip()
    n = re.sub(r"^\[imported\]\s*", "", n, flags=re.I)
    n = re.sub(r"^[A-Z*][A-Z*]\s*·\s*", "", n)          # two-letter prefix "AS · "
    return re.sub(r"\s+", " ", n).strip().lower()


def _pairs(text: str) -> dict[int, int]:
    parts = (text or "").strip().split(",")
    out = {}
    for i in range(0, len(parts) - 1, 2):
        try:
            out[int(parts[i])] = int(parts[i + 1])
        except ValueError:
            continue
    return out


# ── fixtures ────────────────────────────────────────────────────────────────

def _fixtures(root) -> dict[str, dict]:
    out = {}
    eng = _eng(root)
    for f in (eng.findall("Fixture") if eng is not None else []):
        fid = (f.findtext("ID") or "").strip()
        out[fid] = {"id": fid, "name": (f.findtext("Name") or "").strip(),
                    "manufacturer": (f.findtext("Manufacturer") or "").strip(),
                    "model": (f.findtext("Model") or "").strip(),
                    "mode": (f.findtext("Mode") or "").strip(),
                    "universe": (f.findtext("Universe") or "0").strip(),
                    "address": (f.findtext("Address") or "0").strip(),
                    "channels": (f.findtext("Channels") or "").strip()}
    return out


def match_fixtures(a, b) -> dict[str, str]:
    """``{a id: b id}`` — same universe + address first, then same name."""
    fa, fb = _fixtures(a), _fixtures(b)
    out, used = {}, set()
    by_addr = {(f["universe"], f["address"]): i for i, f in fb.items()}
    for i, f in fa.items():
        j = by_addr.get((f["universe"], f["address"]))
        if j is not None and j not in used:
            out[i] = j
            used.add(j)
    by_name = {f["name"].lower(): i for i, f in fb.items() if i not in used}
    for i, f in fa.items():
        if i not in out:
            j = by_name.get(f["name"].lower())
            if j is not None and j not in used:
                out[i] = j
                used.add(j)
    return out


def _sec():
    return {"same": 0, "different": [], "only_a": [], "only_b": [], "unused_a": [], "unused_b": []}


def _unused(root) -> set:
    """IDs of functions nothing uses: no button, slider or cue list, and not
    a step or member of another function (the Doctor's D016)."""
    from core.doctor.checks import _Workspace
    try:
        ws = _Workspace(root, {})
        return {f.get("ID") for f in ws.function_els
                if not ws.parents.get(f.get("ID")) and not ws.vc_refs.get(f.get("ID"))}
    except Exception:  # noqa: BLE001
        return set()


def _cmp_fixtures(a, b, fmap) -> dict:
    s = _sec()
    fa, fb = _fixtures(a), _fixtures(b)
    for i, f in fa.items():
        if i not in fmap:
            s["only_a"].append(f"{f['name']} ({f['model']}, U{int(f['universe']) + 1} @{int(f['address']) + 1})")
            continue
        g = fb[fmap[i]]
        diff = []
        for k, lab in (("model", "model"), ("mode", "mode"), ("universe", "universe"), ("address", "address")):
            if f[k] != g[k]:
                va, vb = f[k], g[k]
                if k in ("universe", "address"):
                    va, vb = int(va) + 1, int(vb) + 1
                diff.append(f"{lab} {va} vs {vb}")
        if f["name"] != g["name"]:
            diff.append(f"name '{f['name']}' vs '{g['name']}'")
        if diff:
            s["different"].append(f"{f['name']}: " + "; ".join(diff))
        else:
            s["same"] += 1
    rev = set(fmap.values())
    s["only_b"] = [f"{f['name']} ({f['model']}, U{int(f['universe']) + 1} @{int(f['address']) + 1})"
                   for j, f in fb.items() if j not in rev]
    return s


# ── groups ──────────────────────────────────────────────────────────────────

def _groups(root) -> dict[str, list[str]]:
    eng = _eng(root)
    out = {}
    for g in (eng.findall("FixtureGroup") if eng is not None else []):
        heads = sorted(g.findall("Head"), key=lambda h: (int(h.get("Y", 0)), int(h.get("X", 0))))
        out[(g.findtext("Name") or "").strip()] = [h.get("Fixture", "") for h in heads]
    return out


def _cmp_groups(a, b, fmap) -> dict:
    s = _sec()
    ga, gb = _groups(a), _groups(b)
    nb = {k.lower(): k for k in gb}
    na = _fixtures(a)
    seen = set()
    for name, heads in ga.items():
        k = nb.get(name.lower())
        if k is None:
            s["only_a"].append(f"{name} ({len(heads)} heads)")
            continue
        seen.add(k)
        mapped = [fmap.get(h, f"?{h}") for h in heads]
        if mapped == gb[k]:
            s["same"] += 1
        elif sorted(mapped) == sorted(gb[k]):
            s["different"].append(f"{name}: same fixtures, other order")
        else:
            miss = [na.get(h, {}).get("name", h) for h, m in zip(heads, mapped) if m not in gb[k]]
            s["different"].append(f"{name}: {len(heads)} vs {len(gb[k])} heads"
                                  + (f"; not in the other: {', '.join(miss)}" if miss else ""))
    s["only_b"] = [f"{k} ({len(v)} heads)" for k, v in gb.items() if k not in seen]
    return s


# ── functions ───────────────────────────────────────────────────────────────

def _functions(root) -> list[ET.Element]:
    eng = _eng(root)
    return eng.findall("Function") if eng is not None else []


def match_functions(a, b) -> dict[str, str]:
    """``{a id: b id}`` by type + normalised name (file order for repeats)."""
    pool = defaultdict(list)
    for f in _functions(b):
        pool[(f.get("Type"), _norm(f.get("Name", "")))].append(f.get("ID"))
    out = {}
    for f in _functions(a):
        k = (f.get("Type"), _norm(f.get("Name", "")))
        if pool.get(k):
            out[f.get("ID")] = pool[k].pop(0)
    # a look can be a Scene in one show and a Collection in the other
    look = ("Scene", "Collection")
    for f in _functions(a):
        if f.get("ID") in out or f.get("Type") not in look:
            continue
        other = look[1 - look.index(f.get("Type"))]
        k = (other, _norm(f.get("Name", "")))
        if pool.get(k):
            out[f.get("ID")] = pool[k].pop(0)
    return out


class _Looks:
    """Decode a fixture's scene values to (level, colour) when its definition
    is known."""
    def __init__(self, root, defs):
        self.fx = _fixtures(root)
        self.defs = defs or {}

    def state(self, fid, text):
        from core.capability_map import decode, can_translate
        f = self.fx.get(fid)
        vals = _pairs(text)
        if f:
            d = self.defs.get((f["manufacturer"].lower(), f["model"].lower()))
            if d and can_translate(d, f["mode"]):
                try:
                    st = decode(d, f["mode"], vals)
                    lvl = st.level if st.level is not None else 1.0
                    col = st.colour if (st.colour and lvl > 0.02) else None
                    if st.shutter == "closed":
                        lvl = 0.0
                    return ("look", round(lvl, 3), tuple(round(c * lvl, 3) for c in col) if col else None)
                except Exception:  # noqa: BLE001
                    pass
        return ("raw", tuple(sorted(vals.items())))


def _same_state(x, y) -> bool:
    if x[0] != y[0]:
        return False
    if x[0] == "raw":
        return x[1] == y[1]
    if abs(x[1] - y[1]) > TOL:
        return False
    if (x[2] is None) != (y[2] is None):
        return (x[2] or (0, 0, 0)) == (0, 0, 0) or (y[2] or (0, 0, 0)) == (0, 0, 0) or max(x[1], y[1]) < TOL
    if x[2] is None:
        return True
    return all(abs(p - q) <= TOL for p, q in zip(x[2], y[2]))


def _cmp_scene(fa, fb, fmap, la, lb, names) -> list[str]:
    va = {v.get("ID"): v.text for v in fa.findall("FixtureVal")}
    vb = {v.get("ID"): v.text for v in fb.findall("FixtureVal")}
    rev = {j: i for i, j in fmap.items()}
    diff = []
    for i, t in va.items():
        j = fmap.get(i)
        if j is None:
            continue
        if j not in vb:
            diff.append(f"{names.get(i, i)} only here")
        elif not _same_state(la.state(i, t), lb.state(j, vb[j])):
            diff.append(f"{names.get(i, i)} looks different")
    for j in vb:
        if j in rev and rev[j] not in va:
            diff.append(f"{names.get(rev[j], rev[j])} only in the other")
    return diff


def _steps(fn, fid_names) -> list[tuple]:
    out = []
    for st in fn.findall("Step"):
        t = (st.text or "").strip()
        if fn.get("Type") == "Sequence":
            t = ""
        out.append((fid_names.get(t, t), st.get("FadeIn", ""), st.get("Hold", ""), st.get("FadeOut", "")))
    return out


def _cmp_functions(a, b, defs) -> tuple[dict, dict]:
    fmap = match_fixtures(a, b)
    fnmap = match_functions(a, b)
    rev = set(fnmap.values())
    na = {f.get("ID"): _norm(f.get("Name", "")) for f in _functions(a)}
    nb = {f.get("ID"): _norm(f.get("Name", "")) for f in _functions(b)}
    names = {i: f["name"] for i, f in _fixtures(a).items()}
    la, lb = _Looks(a, defs), _Looks(b, defs)
    fb = {f.get("ID"): f for f in _functions(b)}
    gb = {g.get("ID"): (g.findtext("Name") or "") for g in (_eng(b).findall("FixtureGroup") if _eng(b) is not None else [])}
    ga = {g.get("ID"): (g.findtext("Name") or "") for g in (_eng(a).findall("FixtureGroup") if _eng(a) is not None else [])}
    secs = {k: _sec() for k in ("scenes", "chasers", "collections", "efx", "matrices", "other")}
    ua, ub = _unused(a), _unused(b)
    kind = {"Scene": "scenes", "Chaser": "chasers", "Sequence": "chasers", "Collection": "collections",
            "EFX": "efx", "RGBMatrix": "matrices"}
    for f in _functions(a):
        sec = secs[kind.get(f.get("Type"), "other")]
        label = f"{f.get('Name', '')}"
        j = fnmap.get(f.get("ID"))
        if j is None:
            sec["unused_a" if f.get("ID") in ua else "only_a"].append(label)
            continue
        g = fb[j]
        t = f.get("Type")
        diff = []
        if g.get("Type") != t:
            sec["different"].append(f"{label}: a {t} here, a {g.get('Type')} in the other")
            continue
        if t in ("Scene", "Sequence"):
            diff = _cmp_scene(f, g, fmap, la, lb, names)
        if t in ("Chaser", "Sequence"):
            sa, sb = _steps(f, na), _steps(g, nb)
            if len(sa) != len(sb):
                diff.append(f"{len(sa)} vs {len(sb)} steps")
            else:
                bad = [n for n, (x, y) in enumerate(zip(sa, sb), 1) if x != y]
                if bad:
                    diff.append(f"step(s) {', '.join(map(str, bad[:6]))}{'…' if len(bad) > 6 else ''} differ")
            for tag in ("Direction", "RunOrder"):
                if (f.findtext(tag) or "") != (g.findtext(tag) or ""):
                    diff.append(f"{tag} {f.findtext(tag)} vs {g.findtext(tag)}")
        elif t == "Collection":
            ma = sorted(na.get((s.text or "").strip(), "?") for s in f.findall("Step"))
            mb = sorted(nb.get((s.text or "").strip(), "?") for s in g.findall("Step"))
            if ma != mb:
                diff.append(f"members differ ({len(ma)} vs {len(mb)})")
        elif t == "EFX":
            if (f.findtext("Algorithm") or "") != (g.findtext("Algorithm") or ""):
                diff.append(f"algorithm {f.findtext('Algorithm')} vs {g.findtext('Algorithm')}")
            xa = sorted(fmap.get((e.findtext("ID") or "").strip(), "?") for e in f.findall("Fixture"))
            xb = sorted((e.findtext("ID") or "").strip() for e in g.findall("Fixture"))
            if xa != xb:
                diff.append(f"fixtures differ ({len(xa)} vs {len(xb)})")
        elif t == "RGBMatrix":
            if (f.findtext("Algorithm") or "") != (g.findtext("Algorithm") or ""):
                diff.append("algorithm differs")
            ka = ga.get((f.findtext("FixtureGroup") or "").strip(), "?")
            kb = gb.get((g.findtext("FixtureGroup") or "").strip(), "?")
            if ka.lower() != kb.lower():
                diff.append(f"group '{ka}' vs '{kb}'")
        if diff:
            sec["different"].append(f"{label}: " + "; ".join(diff[:4]) + (" …" if len(diff) > 4 else ""))
        else:
            sec["same"] += 1
    for g in _functions(b):
        if g.get("ID") not in rev:
            secs[kind.get(g.get("Type"), "other")]["unused_b" if g.get("ID") in ub else "only_b"].append(
                g.get("Name", ""))
    return secs, {"fixtures": fmap, "functions": fnmap}


# ── Virtual Console and setlist ─────────────────────────────────────────────

def _vc_items(root) -> dict[str, list[tuple]]:
    """``{page caption: [(widget type, caption, function name)…]}``."""
    from core.porter_vc import widget_function_refs
    vc = root.find("VirtualConsole")
    names = {f.get("ID"): f.get("Name", "") for f in _functions(root)}
    out = {}
    if vc is None:
        return out
    pages = [c for c in vc if c.tag in ("Frame", "SoloFrame")]
    if len(pages) == 1 and not pages[0].get("Caption"):
        pages = [c for c in pages[0] if c.tag in ("Frame", "SoloFrame")] or pages
    for p in pages:
        items = []
        for w in p.iter():
            if w is p or w.tag not in ("Button", "Slider", "CueList", "Knob", "XYPad", "SpeedDial"):
                continue
            refs = widget_function_refs(w)
            fn = _norm(names.get(refs[0], "")) if refs else ""
            items.append((w.tag, re.sub(r"\s+", " ", (w.get("Caption") or "").strip()).lower(), fn))
        out[(p.get("Caption") or "").strip()] = items
    return out


def _cmp_vc(a, b) -> dict:
    s = _sec()
    va, vb = _vc_items(a), _vc_items(b)
    kb = {k.lower(): k for k in vb}
    seen = set()
    for page, items in va.items():
        k = kb.get(page.lower())
        if k is None:
            s["only_a"].append(f"page '{page}' ({len(items)} widgets)")
            continue
        seen.add(k)
        ia = sorted(i for i in items if i[0] != "Slider" or i[2])
        ib = sorted(i for i in vb[k] if i[0] != "Slider" or i[2])
        if ia == ib:
            s["same"] += 1
            continue
        miss = [i for i in ib if i not in ia]
        extra = [i for i in ia if i not in ib]
        bits = []
        if miss:
            bits.append(f"{len(miss)} not here (e.g. {miss[0][0]} '{miss[0][1] or miss[0][2]}')")
        if extra:
            bits.append(f"{len(extra)} only here (e.g. {extra[0][0]} '{extra[0][1] or extra[0][2]}')")
        s["different"].append(f"page '{page}': " + "; ".join(bits))
    s["only_b"] = [f"page '{k}' ({len(v)} widgets)" for k, v in vb.items() if k not in seen]
    return s


def _cuelists(root) -> dict[str, list[str]]:
    vc = root.find("VirtualConsole")
    fn = {f.get("ID"): f for f in _functions(root)}
    names = {i: f.get("Name", "") for i, f in fn.items()}
    out = {}
    for cl in (vc.iter("CueList") if vc is not None else []):
        cid = (cl.findtext("Chaser") or "").strip()
        ch = fn.get(cid)
        steps = [_norm(names.get((st.text or "").strip(), "?")) for st in ch.findall("Step")] if ch is not None else None
        out[(cl.get("Caption") or "").strip()] = steps
    return out


def _overlap(x, y) -> float:
    if not x or not y:
        return 0.0
    sx, sy = set(x), set(y)
    return len(sx & sy) / len(sx | sy)


def _cmp_setlist(a, b) -> dict:
    """Pair the cue lists by caption; the rest by their songs (the most
    songs in common, at least half), or the only one left on each side."""
    s = _sec()
    ca, cb = _cuelists(a), _cuelists(b)
    kb = {k.lower(): k for k in cb}
    pairs, left_a = {}, []
    for cap in ca:
        k = kb.get(cap.lower())
        if k is not None and k not in pairs.values():
            pairs[cap] = k
        else:
            left_a.append(cap)
    left_b = [k for k in cb if k not in pairs.values()]
    cands = sorted(((_overlap(ca[x], cb[y]), x, y) for x in left_a for y in left_b), reverse=True)
    for sc, x, y in cands:
        if sc >= 0.5 and x in left_a and y in left_b:
            pairs[x] = y
            left_a.remove(x)
            left_b.remove(y)
    if len(left_a) == 1 and len(left_b) == 1:
        pairs[left_a.pop()] = left_b.pop()
    for cap, steps in ca.items():
        k = pairs.get(cap)
        if k is None:
            s["only_a"].append(cap)
            continue
        name = cap if k.lower() == cap.lower() else f"{cap}' ↔ '{k}"
        if steps is None:
            s["different"].append(f"'{name}': no chaser wired")
        elif cb[k] is None:
            s["different"].append(f"'{name}': the other has no chaser wired")
        elif steps == cb[k]:
            s["same"] += 1
        else:
            s["different"].append(f"'{name}': {len(steps)} vs {len(cb[k])} songs"
                                  + ("" if len(steps) != len(cb[k]) else ", other order or songs"))
    s["only_b"] = list(left_b)
    return s


# ── all together ────────────────────────────────────────────────────────────

def compare(a: ET.Element, b: ET.Element, defs: dict | None = None) -> dict:
    """Compare show *a* (this show) with *b* (the other).  Both roots
    un-namespaced."""
    fmap = match_fixtures(a, b)
    funcs, maps = _cmp_functions(a, b, defs)
    res = {"fixtures": _cmp_fixtures(a, b, fmap), "groups": _cmp_groups(a, b, fmap),
           **funcs, "vc": _cmp_vc(a, b), "setlist": _cmp_setlist(a, b)}
    tot = {"same": 0, "different": 0, "only_a": 0, "only_b": 0, "unused_a": 0, "unused_b": 0}
    for k, _l in SECTIONS:
        s = res[k]
        tot["same"] += s["same"]
        for x in ("different", "only_a", "only_b", "unused_a", "unused_b"):
            tot[x] += len(s.get(x, []))
    res["total"] = tot
    res["identical"] = not (tot["different"] or tot["only_a"] or tot["only_b"])
    return res


def report(res: dict, a_name: str = "this show", b_name: str = "the other file") -> str:
    lines = ["═══ Compare — what the two shows do ═══", "",
             f"This show:  {a_name}", f"Other file: {b_name}", ""]
    t = res["total"]
    lines.append("RESULT: functionally the same." if res["identical"] else
                 f"RESULT: {t['same']} the same · {t['different']} different · "
                 f"{t['only_a']} only in this show · {t['only_b']} only in the other file")
    lines.append("")
    for k, lab in SECTIONS:
        s = res[k]
        lines.append(f"── {lab}: {s['same']} same, {len(s['different'])} different, "
                     f"{len(s['only_a'])} only here, {len(s['only_b'])} only in the other ──")
        for x in s["different"]:
            lines.append(f"  ≠ {x}")
        for x in s["only_a"]:
            lines.append(f"  + {x}   (only in this show)")
        for x in s["only_b"]:
            lines.append(f"  − {x}   (only in the other file)")
        for key, where in (("unused_a", "this show"), ("unused_b", "the other file")):
            if s.get(key):
                lines.append(f"  · {len(s[key])} unused, only in {where}: " + ", ".join(s[key][:12])
                             + (" …" if len(s[key]) > 12 else ""))
        lines.append("")
    if t.get("unused_a") or t.get("unused_b"):
        lines.append(f"Not counted above: {t.get('unused_a', 0)} unused function(s) only in this show and "
                     f"{t.get('unused_b', 0)} only in the other file — nothing plays them (no button, not in "
                     "another function); the Doctor can remove them.")
    lines.append(f"Looks are compared by what they light (level and colour, ±{int(TOL * 100)} %) when the "
                 "fixture definitions are known, else channel by channel.")
    return "\n".join(lines) + "\n"
