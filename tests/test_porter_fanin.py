"""
Function Porter on the real corpus (WORKPLAN §5, Phase 1.2)
===========================================================
* Fan-in: Festival_14fix (6 ceiling spots + 8 floor PARs) → QuickStart_6fix
  (2 spots + 4 PARs).
* Reduced rig: Festival_14fix → the bare Pub rig (Pub_6fix's six PARs, same
  fixture IDs, no functions) with ``same_id`` mapping.
* VC porting: widgets of ported functions, new IDs, free placement.
Every result must pass Doctor with no new errors, and be byte-identical
when repeated.
"""

import os
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import porter, porter_vc, qxw_io                    # noqa: E402
from core.doctor import check, load_qxf_defs                   # noqa: E402

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
FESTIVAL = os.path.join(CORPUS, "Festival_14fix.qxw")
QS6 = os.path.join(CORPUS, "QuickStart_6fix.qxw")
PUB = os.path.join(CORPUS, "Pub_6fix.qxw")
DEFS = load_qxf_defs([CORPUS])
NS = "{" + qxw_io.QLC_NS_URI + "}"


def bare_pub_rig(folder: str) -> str:
    """Pub_6fix's patch (6 PARs, IDs 6–12) with no functions and one empty page."""
    root = qxw_io.load_qxw(PUB).getroot()
    eng = root.find(NS + "Engine")
    for f in eng.findall(NS + "Function"):
        eng.remove(f)
    vc = root.find(NS + "VirtualConsole")
    pages = [p for p in vc if p.tag in (NS + "Frame", NS + "SoloFrame")]
    for p in pages[1:]:
        vc.remove(p)
    for c in list(pages[0]):
        if c.tag[len(NS):] in porter_vc.vc_ops.WIDGET_TYPES:
            pages[0].remove(c)
    pages[0].set("Caption", "Main")
    path = os.path.join(folder, "PubRig.qxw")
    qxw_io.write_qxw(root, path)
    return path


def _keys_by_caption(root, *captions):
    tree = porter_vc.list_source_vc(root)
    return [next(w["key"] for w in tree if w["caption"] == c) for c in captions]


def _plan(scope, strategy, mode, **extra):
    cl = porter.resolve_closure(porter_vc.seeds_from_widgets(porter.source_root(), scope))
    plan = dict(closure=cl, fixture_mapping=porter.auto_map(cl["fixture_ids"], strategy),
                fanout_mode=mode, drop_unmapped=True, qxf_paths=[CORPUS],
                vc=dict(enabled=True, scope=scope))
    plan.update(extra)
    return plan


def _parse(res):
    return qxw_io.strip_ns(ET.fromstring(res["bytes"]))


class TestFanInFestivalToQuickStart(unittest.TestCase):
    """14 → 6 fixtures, looks + effects + their VC frames."""

    @classmethod
    def setUpClass(cls):
        porter.load_source(FESTIVAL)
        porter.load_target(QS6)
        cls.scope = _keys_by_caption(porter.source_root(), "FLOOR", "CEILING", "COMBINED FX")
        cls.plan = _plan(cls.scope, "fan_in", "fan_in")
        cls.res = porter.port(cls.plan)
        cls.root = _parse(cls.res)

    @classmethod
    def tearDownClass(cls):
        porter.clear()

    def test_fan_in_blocks_by_type_and_stage_order(self):
        m = self.plan["fixture_mapping"]
        # 6 ceiling spots → 2 target spots (3 each), 8 PARs → 4 PARs (2 each)
        self.assertEqual({s: m[s] for s in "012345"},
                         {"0": ["0"], "1": ["0"], "2": ["0"], "3": ["1"], "4": ["1"], "5": ["1"]})
        par_targets = [t for s in ("6", "7", "8", "9", "10", "11", "12", "13") for t in m[s]]
        self.assertEqual(sorted(par_targets), ["2", "2", "3", "3", "4", "4", "5", "5"])
        v = porter.validate(self.plan)
        self.assertTrue(v["ok"], v["errors"])

    def test_doctor_clean(self):
        self.assertEqual(self.res["doctor"]["errors"], [])
        self.assertEqual(self.res["doctor"]["warnings"], [])
        rep = check(self.root, list(DEFS.values()))
        self.assertEqual(rep.errors, [])

    def test_deterministic(self):
        again = porter.port(self.plan)
        self.assertEqual(again["bytes"], self.res["bytes"])

    def test_scene_values_only_on_target_fixtures_and_complete(self):
        eng = self.root.find("Engine")
        fixtures = {f.findtext("ID"): int(f.findtext("Channels")) for f in eng.findall("Fixture")}
        new_ids = set(self.res["func_id_map"].values())
        for fn in eng.findall("Function"):
            if fn.get("ID") not in new_ids or fn.get("Type") != "Scene":
                continue
            for fv in fn.findall("FixtureVal"):
                self.assertIn(fv.get("ID"), fixtures)
                chans = [int(x) for x in (fv.text or "").split(",")[0::2] if x != ""]
                self.assertEqual(sorted(chans), list(range(fixtures[fv.get("ID")])),
                                 f"scene {fn.get('Name')} fixture {fv.get('ID')}")

    def test_vc_page_added_with_unique_ids_and_no_overlap(self):
        vc = self.root.find("VirtualConsole")
        pages = [p for p in vc if p.tag in ("Frame", "SoloFrame")]
        self.assertEqual(pages[-1].get("Caption"), "Ported from Festival_14fix")
        ids = [w.get("ID") for w in vc.iter() if porter_vc._is_widget(w)]
        self.assertEqual(len(ids), len(set(ids)))
        page = pages[-1]
        _, _, pw, ph = porter_vc._rect(page)
        rects = [porter_vc._rect(c) for c in page if porter_vc._is_widget(c)]
        self.assertEqual(len(rects), 3)
        for i, a in enumerate(rects):
            self.assertLessEqual(a[0] + a[2], pw)
            self.assertLessEqual(a[1] + a[3], ph)
            for b in rects[i + 1:]:
                self.assertFalse(porter_vc._overlaps(a, b), (a, b))

    def test_buttons_point_at_ported_functions(self):
        new_ids = set(self.res["func_id_map"].values())
        page = [p for p in self.root.find("VirtualConsole") if p.tag == "Frame"][-1]
        refs = [r for w in page.iter() if porter_vc._is_widget(w)
                for r in porter_vc.widget_function_refs(w)]
        self.assertGreater(len(refs), 50)
        self.assertTrue(set(refs) <= new_ids)

    def test_panic_reset_stops_ported_functions(self):
        eng = self.root.find("Engine")
        script = next(f for f in eng.findall("Function")
                      if f.get("Type") == "Script" and f.get("Name") == "PANIC RESET")
        cmds = [c.text for c in script.findall("Command")]
        for fid in self.res["func_id_map"].values():
            self.assertIn(f"stopfunction%3A{fid}", cmds)
        start = next(i for i, c in enumerate(cmds) if c.startswith("startfunction"))
        for fid in self.res["func_id_map"].values():
            self.assertLess(cmds.index(f"stopfunction%3A{fid}"), start)
        self.assertEqual(cmds[-1], f"stopfunction%3A{script.get('ID')}")

    def test_level_slider_starts_at_zero(self):
        page = [p for p in self.root.find("VirtualConsole") if p.tag == "Frame"][-1]
        for sl in page.iter("Slider"):
            if (sl.findtext("SliderMode") or "").strip() == "Level":
                self.assertEqual(sl.find("Level").get("Value"), "0")
                for ch in sl.iter("Channel"):
                    self.assertIn(ch.get("Fixture"), {"0", "1", "2", "3", "4", "5"})

    def test_rgb_matrix_group(self):
        eng = self.root.find("Engine")
        groups = {g.get("ID"): g for g in eng.findall("FixtureGroup")}
        for fn in eng.findall("Function"):
            if fn.get("Type") == "RGBMatrix" and fn.get("ID") in set(self.res["func_id_map"].values()):
                g = groups[fn.findtext("FixtureGroup")]
                heads = {h.get("Fixture") for h in g.findall("Head")}
                self.assertEqual(heads, {"0", "1"})     # the two target spots

    def test_report(self):
        rep = self.res["report"]
        for s in ("Fan-out mode: fan_in", "Target 0 'Ceiling 1' ←", "VIRTUAL CONSOLE",
                  "PANIC RESET", "DOCTOR", "0 new error(s)"):
            self.assertIn(s, rep)
        self.assertEqual(porter.report_path("/x/Show_v3.qxw"), "/x/Show_v3_port_report.txt")


class TestReducedRigFestivalToPub(unittest.TestCase):
    """The Pub case: same physical PARs (IDs 6–12), spots dropped."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        porter.load_source(FESTIVAL)
        porter.load_target(bare_pub_rig(cls.tmp))
        cls.scope = _keys_by_caption(porter.source_root(), "COMBINED FX")
        page_id = porter_vc.list_target_pages(porter.target_root())[0]["id"]
        cls.plan = _plan(cls.scope, "same_id", "manual",
                         vc=dict(enabled=True, scope=cls.scope, target_page=page_id))
        cls.res = porter.port(cls.plan)
        cls.root = _parse(cls.res)

    @classmethod
    def tearDownClass(cls):
        porter.clear()

    def test_same_id_mapping(self):
        m = self.plan["fixture_mapping"]
        self.assertEqual({s: t for s, t in m.items() if t},
                         {"6": ["6"], "7": ["7"], "8": ["8"], "9": ["9"], "11": ["11"], "12": ["12"]})
        plan = dict(self.plan, drop_unmapped=False)
        self.assertFalse(porter.validate(plan)["ok"])      # unmapped spots are an error…
        v = porter.validate(self.plan)                      # …unless left out on purpose
        self.assertTrue(v["ok"])
        self.assertTrue(any("left out" in w for w in v["warnings"]))

    def test_values_copied_unchanged(self):
        src = {f.get("ID"): f for f in porter.source_root().find("Engine").findall("Function")}
        out = {f.get("ID"): f for f in self.root.find("Engine").findall("Function")}
        checked = 0
        for s, n in self.res["func_id_map"].items():
            if src[s].get("Type") != "Scene":
                continue
            want = {fv.get("ID"): porter._pairs(fv.text) for fv in src[s].findall("FixtureVal")
                    if fv.get("ID") in {"6", "7", "8", "9", "11", "12"}}
            got = {fv.get("ID"): porter._pairs(fv.text) for fv in out[n].findall("FixtureVal")}
            self.assertEqual(set(got), set(want))
            for fx, vals in want.items():
                for ch, v in vals.items():
                    self.assertEqual(got[fx][ch], v)
                self.assertEqual(sorted(got[fx]), list(range(7)))   # completed
            checked += 1
        self.assertGreater(checked, 50)

    def test_spot_only_functions_removed_with_their_steps(self):
        pruned = {p["id"]: p["reason"] for p in self.res["pruned"]}
        self.assertIn("140", pruned)            # Rock Loop Ceil 140: spots only
        self.assertIn("145", pruned)            # Rock Loop Ceiling: all steps gone
        self.assertIn("821", pruned)            # RGB matrix on the ceiling group
        out_ids = {f.get("ID") for f in self.root.find("Engine").findall("Function")}
        for fn in self.root.find("Engine").findall("Function"):
            for st in fn.findall("Step"):
                self.assertIn(st.text.strip(), out_ids)

    def test_placed_on_chosen_page_and_doctor_clean(self):
        pages = [p for p in self.root.find("VirtualConsole") if p.tag in ("Frame", "SoloFrame")]
        self.assertEqual(len(pages), 1)
        self.assertEqual(self.res["vc"]["pages"], [])
        self.assertEqual(self.res["doctor"]["errors"], [])
        self.assertEqual(check(self.root, list(DEFS.values())).errors, [])


class TestVcPortingRules(unittest.TestCase):
    """Pruning, bindings and placement on small hand-made trees."""

    def _tree(self, xml):
        return ET.fromstring(xml)

    def test_pruning_and_bindings(self):
        src = self._tree("""<Workspace><VirtualConsole>
          <Frame Caption="P" ID="0"><WindowState X="0" Y="0" Width="800" Height="600"/>
            <Frame Caption="F" ID="1"><WindowState X="10" Y="10" Width="300" Height="200"/>
              <Button Caption="A" ID="2"><WindowState X="5" Y="5" Width="50" Height="50"/>
                <Function ID="10"/><Key>A</Key></Button>
              <Button Caption="B" ID="3"><WindowState X="60" Y="5" Width="50" Height="50"/>
                <Function ID="11"/><Key>B</Key></Button>
              <Button Caption="label" ID="4"><WindowState X="5" Y="60" Width="50" Height="20"/>
                <Function ID="4294967295"/></Button>
            </Frame>
            <Frame Caption="Labels only" ID="5"><WindowState X="400" Y="10" Width="100" Height="100"/>
              <Button Caption="x" ID="6"><WindowState X="5" Y="5" Width="50" Height="20"/>
                <Function ID="4294967295"/></Button></Frame>
          </Frame></VirtualConsole></Workspace>""")
        tgt = self._tree("""<Workspace><VirtualConsole>
          <Frame Caption="T" ID="7"><WindowState X="0" Y="0" Width="800" Height="600"/>
            <Button Caption="old" ID="8"><WindowState X="10" Y="10" Width="100" Height="100"/>
              <Function ID="1"/><Key>A</Key></Button>
          </Frame></VirtualConsole></Workspace>""")
        res = porter_vc.port_vc(src, tgt, {"10": "50"}, {}, {"target_page": "7"})
        page = tgt.find("VirtualConsole/Frame")
        frames = page.findall("Frame")
        self.assertEqual([f.get("Caption") for f in frames], ["F"])      # labels-only frame not in auto
        caps = [b.get("Caption") for b in frames[0].findall("Button")]
        self.assertEqual(caps, ["A", "label"])                          # B: function not ported
        a = frames[0].find("Button")
        self.assertEqual(a.find("Function").get("ID"), "50")
        self.assertIsNone(a.find("Key"))                                 # 'A' already used
        self.assertEqual(res["bindings_dropped"], 1)
        self.assertEqual(frames[0].get("ID"), "9")                       # max(8) + 1
        x, y, _, _ = porter_vc._rect(frames[0])
        self.assertFalse(porter_vc._overlaps((x, y, 300, 200), (10, 10, 100, 100)))
        self.assertTrue(any("B'" in d for d in res["dropped"]))

    def test_full_page_gets_continuation_page(self):
        src = self._tree("""<Workspace><VirtualConsole>
          <Frame Caption="P" ID="0"><WindowState X="0" Y="0" Width="400" Height="300"/>
            <Button Caption="A" ID="1"><WindowState X="0" Y="0" Width="380" Height="250"/><Function ID="1"/></Button>
            <Button Caption="B" ID="2"><WindowState X="0" Y="0" Width="380" Height="250"/><Function ID="2"/></Button>
          </Frame></VirtualConsole></Workspace>""")
        tgt = self._tree("<Workspace><VirtualConsole/></Workspace>")
        res = porter_vc.port_vc(src, tgt, {"1": "1", "2": "2"}, {}, {"page_caption": "New"})
        pages = tgt.find("VirtualConsole").findall("Frame")
        self.assertEqual([p.get("Caption") for p in pages], ["New", "New (2)"])
        self.assertEqual(len(res["pages"]), 2)
        ids = [w.get("ID") for w in tgt.iter() if porter_vc._is_widget(w)]
        self.assertEqual(len(ids), len(set(ids)))


class TestFanInRepresentative(unittest.TestCase):
    """In a fan-in block the target takes the first *lit* source."""

    def test_first_lit_source_wins(self):
        fn = ET.fromstring('<Function ID="1" Type="Scene" Name="s">'
                           '<FixtureVal ID="0">0,0,1,0</FixtureVal>'
                           '<FixtureVal ID="1">0,255,1,40</FixtureVal>'
                           '<FixtureVal ID="2">0,100,1,0</FixtureVal></Function>')
        before, after = porter._remap_fixture_refs(fn, {"9": ["0", "1", "2"]}, set(), {},
                                                   {"0": {0}, "1": {0}, "2": {0}})
        self.assertEqual((before, after), (3, 1))
        fv = fn.findall("FixtureVal")
        self.assertEqual([(f.get("ID"), f.text) for f in fv], [("9", "0,255,1,40")])

    def test_dark_scene_uses_first_declared(self):
        fn = ET.fromstring('<Function ID="1" Type="Scene" Name="s">'
                           '<FixtureVal ID="1">0,0</FixtureVal><FixtureVal ID="0">0,0</FixtureVal></Function>')
        porter._remap_fixture_refs(fn, {"9": ["0", "1"]}, set(), {})
        self.assertEqual([f.get("ID") for f in fn.findall("FixtureVal")], ["9"])
        self.assertEqual(fn.find("FixtureVal").text, "0,0")

    def test_complete_channels_neutral(self):
        self.assertEqual(porter._complete("0,255,9,1", {0: 0, 1: 0, 2: 127}), "0,255,1,0,2,127")


if __name__ == "__main__":
    unittest.main()


class TestPorterRoutes(unittest.TestCase):
    """HTTP flow used by the Porter tab: VC seeds → auto-map → export → report."""

    def test_end_to_end(self):
        import app
        c = app.create_app().test_client()
        tmp = tempfile.mkdtemp()
        self.assertTrue(c.post("/api/porter/source/load", json={"path": FESTIVAL}).get_json()["ok"])
        self.assertTrue(c.post("/api/porter/target/load", json={"path": QS6}).get_json()["ok"])
        tree = c.get("/api/porter/source/vc").get_json()
        key = next(w["key"] for w in tree if w["caption"] == "CEILING")
        seeds = c.post("/api/porter/vc/seeds", json={"keys": [key]}).get_json()["seed_ids"]
        self.assertTrue(seeds)
        closure = c.post("/api/porter/resolve", json={"seed_ids": seeds}).get_json()
        mapping = c.post("/api/porter/auto-map", json={"fixture_ids": closure["fixture_ids"],
                                                       "strategy": "fan_in"}).get_json()
        pages = c.get("/api/porter/target/pages").get_json()
        self.assertEqual(len(pages), 1)
        plan = {"closure": closure, "fixture_mapping": mapping, "fanout_mode": "fan_in",
                "drop_unmapped": True, "vc": {"enabled": True, "scope": [key]}}
        r = c.post("/api/porter/execute", json=plan)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:500])
        self.assertEqual(r.headers["X-Suggested-Filename"], "QuickStart_6fix_v2.qxw")
        out = os.path.join(tmp, "QuickStart_6fix_v2.qxw")
        with open(out, "wb") as fh:
            fh.write(r.get_data())
        d = c.post("/api/porter/save-report", json={"qxw_path": out}).get_json()
        self.assertEqual(d["name"], "QuickStart_6fix_v2_port_report.txt")
        with open(d["path"], encoding="utf-8") as fh:
            self.assertIn("Function Porter", fh.read())
        s = c.get("/api/porter/last-result").get_json()
        self.assertEqual(s["doctor"]["errors"], [])
        self.assertTrue(s["vc"]["widgets"] > 0)
        self.assertEqual(c.post("/api/porter/auto-map", json={"fixture_ids": ["0"],
                                                              "strategy": "nope"}).status_code, 400)
        c.post("/api/porter/clear")


class TestStagePlan(unittest.TestCase):
    """Stage plans for the Porter's step 1/3 (Fixtures-tab reading code)."""

    def test_plan_from_positions(self):
        from core import fixture as fx
        plan = fx.stage_plan(qxw_io.load_qxw(FESTIVAL).getroot())
        self.assertTrue(plan["has_positions"])
        self.assertEqual(len(plan["fixtures"]), 14)
        f0 = plan["fixtures"][0]
        self.assertEqual((f0["id"], f0["x_mm"], f0["z_mm"]), ("0", 750, 90))
        colors = {f["model"]: f["color"] for f in plan["fixtures"]}
        self.assertEqual(len(set(colors.values())), 2)          # one colour per model
        for f in plan["fixtures"]:
            self.assertLessEqual(f["x_mm"], plan["stage"]["w_mm"])
            self.assertLessEqual(f["z_mm"], plan["stage"]["d_mm"])

    def test_no_positions_and_state_untouched(self):
        from core import fixture as fx
        before = fx.get_stage_dims()
        root = ET.fromstring('<Workspace xmlns="http://www.qlcplus.org/Workspace"><Engine>'
                             '<Fixture><ID>0</ID><Name>A</Name></Fixture></Engine></Workspace>')
        plan = fx.stage_plan(root)
        self.assertFalse(plan["has_positions"])
        self.assertEqual(plan["fixtures"], [])
        self.assertEqual(fx.get_stage_dims(), before)

    def test_route(self):
        import app
        c = app.create_app().test_client()
        c.post("/api/porter/clear")
        self.assertFalse(c.get("/api/porter/stage/source").get_json()["has_positions"])
        c.post("/api/porter/source/load", json={"path": FESTIVAL})
        d = c.get("/api/porter/stage/source").get_json()
        self.assertEqual(len(d["fixtures"]), 14)
        self.assertEqual(c.get("/api/porter/stage/nope").status_code, 400)
        c.post("/api/porter/clear")


class TestLitFixtureMap(unittest.TestCase):
    """resolve_closure reports which fixtures a function actually lights
    (used by step 3's "Port this fixture" to untick functions)."""

    def test_zero_declared_fixtures_are_not_lit(self):
        porter.load_source(PUB)
        try:
            fns = {f["name"]: f["id"] for f in porter.list_source_functions()}
            cl = porter.resolve_closure([fns["AS · Stage Patter"]] if "AS · Stage Patter" in fns
                                        else [next(iter(fns.values()))])
            lit = cl["lit_fixture_map"]
            self.assertTrue(set(lit) <= set(cl["function_ids"]))
            for fid, fx in lit.items():
                self.assertTrue(set(fx) <= set(cl["fixture_ids"]))
            src = {f.get("ID"): f for f in porter.source_root().find("Engine").findall("Function")}
            for fid, fx in lit.items():
                f = src[fid]
                if f.get("Type") == "Scene":
                    want = {fv.get("ID") for fv in f.findall("FixtureVal")
                            if any(v > 0 for v in porter._pairs(fv.text).values())}
                    self.assertEqual(set(fx), want)
        finally:
            porter.clear()


class TestRemoveTargetVc(unittest.TestCase):
    """Step 4: leave existing target VC items out of the output."""

    def test_remove_page_and_place_in_freed_space(self):
        tmp = tempfile.mkdtemp()
        porter.load_source(FESTIVAL)
        porter.load_target(QS6)
        try:
            tgt_tree = porter_vc.list_source_vc(porter.target_root(), include_all=True)
            page = next(w for w in tgt_tree if w["depth"] == 0)
            # every widget is listed (labels and function-less buttons too)
            self.assertGreater(len(tgt_tree), len(porter_vc.list_source_vc(porter.target_root())))
            scope = _keys_by_caption(porter.source_root(), "CEILING")
            plan = _plan(scope, "fan_in", "fan_in",
                         vc=dict(enabled=True, scope=scope, remove=[page["key"]]))
            res = porter.port(plan)
            root = _parse(res)
            pages = [p.get("Caption") for p in root.find("VirtualConsole")
                     if p.tag in ("Frame", "SoloFrame")]
            self.assertNotIn(page["caption"], pages)
            self.assertEqual(pages, ["Ported from Festival_14fix"])
            self.assertTrue(res["removed_vc"][0].startswith(f"page '{page['caption']}'"))
            self.assertIn("REMOVED FROM THE TARGET VC", res["report"])
            self.assertEqual(res["doctor"]["errors"], [])
            # the target as loaded is untouched
            self.assertIn(page["caption"], [p["caption"] for p in
                                            porter_vc.list_target_pages(porter.target_root())])
        finally:
            porter.clear()

    def test_nested_selection_removed_once(self):
        root = ET.fromstring("""<Workspace><VirtualConsole>
          <Frame Caption="P" ID="0"><WindowState X="0" Y="0" Width="800" Height="600"/>
            <Frame Caption="F" ID="1"><WindowState X="0" Y="0" Width="100" Height="100"/>
              <Button Caption="B" ID="2"><WindowState X="0" Y="0" Width="50" Height="50"/></Button>
            </Frame>
            <Button Caption="C" ID="3"><WindowState X="200" Y="0" Width="50" Height="50"/></Button>
          </Frame></VirtualConsole></Workspace>""")
        keys = {w["caption"]: w["key"] for w in porter_vc.list_source_vc(root, include_all=True)}
        removed = porter_vc.remove_widgets(root, [keys["F"], keys["B"]])
        self.assertEqual(removed, ["Frame 'F' (2 widgets)"])
        self.assertEqual([c.get("Caption") for c in root.find("VirtualConsole/Frame")
                          if c.tag in ("Frame", "Button")], ["C"])
