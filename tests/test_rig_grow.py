"""2.7 Grow a rig — copied fixtures wired into the show's own looks
("plays like"): core.rig_grow and the Function Porter's plan key ``wire``."""
import copy
import os
import shutil

import pytest

import app
from core import porter, qxw_io, rig_grow
from core.doctor import check, load_qxf_defs

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
CEILING = ["0", "1", "2", "3", "4", "5"]          # Festival_14fix: the 6 ceiling spots


@pytest.fixture(scope="module")
def defs():
    return load_qxf_defs([CORPUS])


@pytest.fixture
def grown():
    """Pub_6fix (6 PARs) with Festival's 6 ceiling spots copied in."""
    porter.clear()
    porter.load_source(os.path.join(CORPUS, "Festival_14fix.qxw"))
    porter.load_target(os.path.join(CORPUS, "Pub_6fix.qxw"))
    root = copy.deepcopy(porter._tgt["root"])
    cmap = porter.copy_fixtures_into(porter._src["root"], root, CEILING, [], {})["map"]
    return root, list(cmap.values())


def _scenes(root):
    return [f for f in root.find("Engine").findall("Function") if f.get("Type") == "Scene"]


def _ids(fn):
    return [fv.get("ID") for fv in fn.findall("FixtureVal")]


def test_suggest_follows_a_fixture_at_the_same_level(grown):
    root, new = grown
    pos = porter._positions(root)
    sug = rig_grow.suggest(root, new)
    for n in new:
        t = sug[n]["template"]
        assert t and t not in new
        # ceiling spots follow a hanging fixture when the show has one
        hanging = [i for i in pos if i not in new and pos[i][1] >= rig_grow.HIGH_MM]
        if hanging:
            assert t in hanging, (n, t)
        assert "same side" in sug[n]["why"]


def test_wire_adds_the_new_fixture_wherever_the_template_plays(grown, defs):
    root, new = grown
    plan = {n: rig_grow.suggest(root, new)[n]["template"] for n in new}
    with_tmpl = {n: [s.get("ID") for s in _scenes(root) if plan[n] in _ids(s)] for n in new}
    rep = rig_grow.wire(root, plan, defs)
    assert not rep["problems"]
    for n in new:
        hit = [s.get("ID") for s in _scenes(root) if n in _ids(s)]
        assert hit == with_tmpl[n]
        assert rep["fixtures"][n]["scenes"] == len(hit) > 0
    # every channel of the spot (9 ch) is declared, values translated by capability
    s = next(s for s in _scenes(root) if new[0] in _ids(s))
    vals = next(fv.text for fv in s.findall("FixtureVal") if fv.get("ID") == new[0])
    assert len(vals.split(",")) == 18


def test_translation_keeps_the_colour(grown, defs):
    """A red PAR look makes the spot red: dimmer and colour go through the
    capability map, not channel by channel (the spot has strobe on ch 1)."""
    root, new = grown
    t = rig_grow.suggest(root, new)[new[0]]["template"]
    rig_grow.wire(root, {new[0]: t}, defs)
    from core.capability_map import decode
    from core.porter import _fixture_infos
    inf = _fixture_infos(root)
    d_t = defs[(inf[t]["manufacturer"].lower(), inf[t]["model"].lower())]
    d_n = defs[(inf[new[0]]["manufacturer"].lower(), inf[new[0]]["model"].lower())]
    checked = 0
    for s in _scenes(root):
        fv = {f.get("ID"): f.text for f in s.findall("FixtureVal")}
        if t in fv and new[0] in fv:
            a = decode(d_t, inf[t]["mode"], rig_grow._pairs(fv[t]))
            b = decode(d_n, inf[new[0]]["mode"], rig_grow._pairs(fv[new[0]]))
            la, lb = (a.level if a.level is not None else 1.0), (b.level if b.level is not None else 1.0)
            assert abs(la - lb) < 0.02, s.get("Name")
            if la > 0.05 and a.colour and b.colour and max(a.colour) > 0.05:
                assert all(abs(x - y) < 0.05 for x, y in zip(a.colour, b.colour)), s.get("Name")
            checked += 1
    assert checked > 50


def test_nothing_else_changes_and_wiring_twice_is_a_no_op(grown, defs):
    root, new = grown
    plan = {n: rig_grow.suggest(root, new)[n]["template"] for n in new}
    before = copy.deepcopy(root)
    rig_grow.wire(root, plan, defs)
    once = qxw_io.qxw_bytes(root)
    assert rig_grow.wire(root, plan, defs)["total"] == 0
    assert qxw_io.qxw_bytes(root) == once
    # without the added values, every function is exactly as before
    eng_b = {f.get("ID"): f for f in before.find("Engine").findall("Function")}
    for fn in root.find("Engine").findall("Function"):
        old = eng_b[fn.get("ID")]
        kept = [fv for fv in fn.findall("FixtureVal")
                if not (fv.get("ID") in new and fv.get("ID") not in _ids(old))]
        assert [(f.get("ID"), f.text) for f in kept] == [(f.get("ID"), f.text) for f in old.findall("FixtureVal")]


def test_no_new_doctor_errors(grown, defs):
    root, new = grown
    errs = len(check(root, list(defs.values())).errors)
    rig_grow.wire(root, {n: rig_grow.suggest(root, new)[n]["template"] for n in new}, defs)
    assert len(check(root, list(defs.values())).errors) <= errs


def test_only_the_given_functions_and_empty_template_means_dark(grown, defs):
    root, new = grown
    t = rig_grow.suggest(root, new)[new[0]]["template"]
    first = next(s for s in _scenes(root) if t in _ids(s))
    rep = rig_grow.wire(root, {new[0]: t, new[1]: ""}, defs, functions={first.get("ID")})
    assert rep["fixtures"][new[0]]["scenes"] == 1 and new[1] not in rep["fixtures"]
    assert sum(new[1] in _ids(s) for s in _scenes(root)) == 0


def test_matrices_are_reported_not_changed():
    """Festival: an RGB matrix on a group of floor PARs; a new fixture that
    follows one of them is not added to the group — the report says so."""
    porter.clear()
    porter.load_target(os.path.join(CORPUS, "Festival_14fix.qxw"))
    root = copy.deepcopy(porter._tgt["root"])
    eng = root.find("Engine")
    mats = [f for f in eng.findall("Function") if f.get("Type") == "RGBMatrix"]
    groups = {g.get("ID"): {h.get("Fixture") for h in g.findall("Head")} for g in eng.findall("FixtureGroup")}
    gid = next((m.findtext("FixtureGroup") for m in mats if groups.get(m.findtext("FixtureGroup"))), None)
    assert gid is not None
    tmpl = sorted(groups[gid])[0]
    lines = rig_grow.not_wired(root, {"999": tmpl})
    assert any("RGB matrices on group" in x for x in lines)
    # a fixture not in any matrix group: nothing to report about matrices
    in_groups = set().union(*groups.values())
    other = next(f.findtext("ID") for f in eng.findall("Fixture") if f.findtext("ID") not in in_groups) \
        if any(f.findtext("ID") not in in_groups for f in eng.findall("Fixture")) else None
    if other:
        assert not any("RGB matrices" in x for x in rig_grow.not_wired(root, {"999": other}))


def test_usage_counts_looks(grown):
    root, _new = grown
    u = rig_grow.usage(root)
    assert u and all(v > 0 for v in u.values())


# ── through the Function Porter ────────────────────────────────────────────

@pytest.fixture
def c(tmp_path):
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), tmp_path)
    for f in ("Festival_14fix.qxw", "Pub_6fix.qxw"):
        shutil.copy(os.path.join(CORPUS, f), tmp_path / f)
    client = app.create_app().test_client()
    porter.clear()
    client.tmp = tmp_path
    return client


def _ok(r):
    assert r.status_code < 300, r.get_data(as_text=True)[:400]
    return r


def test_porter_wire_options_and_apply(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    d = _ok(c.post("/api/porter/wire/options", json={"copy_fixtures": CEILING})).get_json()
    assert [r["src"] for r in d["rows"]] == CEILING
    assert all(r["template"] for r in d["rows"])
    assert d["targets"] and all(t["id"] not in {r["new"] for r in d["rows"]} for t in d["targets"])
    wire = {r["src"]: r["template"] for r in d["rows"]}
    plan = {"closure": {"function_ids": [], "fixture_ids": []}, "fixture_mapping": {},
            "copy_fixtures": CEILING, "wire": wire}
    v = _ok(c.post("/api/porter/validate", json=plan)).get_json()
    assert any("plays like" in x for x in v["info"]), v["info"]
    _ok(c.post("/api/porter/apply", json=plan))
    root = qxw_io.loads_qxw(c.get("/api/show/file").data)
    qxw_io.strip_ns(root)
    new = {r["new"] for r in d["rows"]}
    lit = [s for s in _scenes(root) if new & set(_ids(s))]
    assert len(lit) > 50
    assert "WIRED INTO THE SHOW'S OWN LOOKS" in c.get("/api/show/report").get_data(as_text=True)


def test_porter_without_wire_leaves_the_show_looks_alone(c):
    _ok(c.post("/api/load", json={"path": str(c.tmp / "Pub_6fix.qxw")}))
    _ok(c.post("/api/porter/source/load", json={"path": str(c.tmp / "Festival_14fix.qxw")}))
    _ok(c.post("/api/porter/target/show", json={}))
    d = _ok(c.post("/api/porter/wire/options", json={"copy_fixtures": CEILING})).get_json()
    plan = {"closure": {"function_ids": [], "fixture_ids": []}, "fixture_mapping": {},
            "copy_fixtures": CEILING}
    _ok(c.post("/api/porter/apply", json=plan))
    root = qxw_io.loads_qxw(c.get("/api/show/file").data)
    qxw_io.strip_ns(root)
    new = {r["new"] for r in d["rows"]}
    assert not [s for s in _scenes(root) if new & set(_ids(s))]
