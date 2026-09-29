"""
Port MIDI / input control (WORKPLAN Phase 1.6)
==============================================
Source: Pub_6fix with the MIDI setup of giopas's show rebuilt (the real
file is not committed): universe 2 (ID 1) ← MIDI device "SINCO", and three
bindings on page *1. SETLIST*: PANIC RESET ← ch 40, CueList Next ← ch 20,
Previous ← ch 10.

* Target A: QuickStart_6fix — no input device at all.
* Target B: QuickStart_6fix with the same controller (saved QLC+ 5.2.1
  style, ``UID="SINCO"``) and its *ALL ON* button already on ch 40.
"""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import porter, porter_input, porter_vc, qxw_io     # noqa: E402
from core.doctor import check                                  # noqa: E402

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")


def _load(name):
    return qxw_io.load_qxw(os.path.join(CORPUS, name), strip_namespace=True).getroot()


def _caption(root, cap, tag=None):
    vc = root.find("VirtualConsole")
    return next(w for w in vc.iter() if w.get("Caption") == cap and (tag is None or w.tag == tag))


def _patch(root, uid, name=None, profile=None):
    iom = root.find("Engine").find("InputOutputMap")
    u = next((x for x in iom.findall("Universe") if x.get("ID") == "1"), None)
    if u is None:
        u = ET.SubElement(iom, "Universe", {"Name": "Universe 2", "ID": "1"})
    old = u.find("Input")
    if old is not None:
        u.remove(old)
    attrs = {"Plugin": "MIDI", "UID": uid, "Line": "0"}
    if name:
        attrs["Name"] = name
    if profile:
        attrs["Profile"] = profile
    u.insert(0, ET.Element("Input", attrs))


def make_source(folder):
    root = _load("Pub_6fix.qxw")
    _patch(root, "528145425", "SINCO", "SINCO Program Change")
    ET.SubElement(_caption(root, "🚨 PANIC RESET"), "Input", {"Universe": "1", "Channel": "40"})
    cl = _caption(root, "Pub Setlist", "CueList")
    ET.SubElement(cl.find("Next"), "Input", {"Universe": "1", "Channel": "20"})
    ET.SubElement(cl.find("Previous"), "Input", {"Universe": "1", "Channel": "10"})
    path = os.path.join(folder, "PubMidi.qxw")
    qxw_io.write_qxw(root, path)
    return path


def make_target_b(folder):
    root = _load("QuickStart_6fix.qxw")
    _patch(root, "SINCO")
    ET.SubElement(_caption(root, "ALL ON"), "Input", {"Universe": "1", "Channel": "40"})
    path = os.path.join(folder, "QS6_midi.qxw")
    qxw_io.write_qxw(root, path)
    return path


def run_port(src, tgt, **vc):
    porter.load_source(src)
    porter.load_target(tgt)
    keys = porter_vc.list_source_vc(porter.source_root())
    scope = [w["key"] for w in keys if w["caption"] == "1. SETLIST"]
    cl = porter.resolve_closure(porter_vc.seeds_from_widgets(porter.source_root(), scope))
    opts = dict(enabled=True, scope=scope)
    opts.update(vc)
    plan = dict(closure=cl, fixture_mapping=porter.auto_map(cl["fixture_ids"], "fan_in"),
                fanout_mode="fan_in", drop_unmapped=True, qxf_paths=[CORPUS], vc=opts)
    res = porter.port(plan)
    return plan, res, qxw_io.strip_ns(ET.fromstring(res["bytes"]))


def _inputs(root):
    vc = root.find("VirtualConsole")
    out = {}
    for w in vc.iter():
        if porter_vc._is_widget(w):
            for slot, _p, el in porter_input.widget_bindings(w):
                if el.tag == "Input":
                    out.setdefault(el.get("Channel"), []).append((w.get("Caption"), slot, el.get("Universe")))
    return out


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.src = make_source(cls.tmp)
        cls.tgt_a = os.path.join(CORPUS, "QuickStart_6fix.qxw")
        cls.tgt_b = make_target_b(cls.tmp)


class TestNoInputInTarget(_Base):
    def test_patch_copied_and_bindings_kept(self):
        _plan, res, root = run_port(self.src, self.tgt_a)
        patch = porter_input.read_patch(root)
        self.assertEqual(patch["1"]["device"], "SINCO")
        self.assertEqual(patch["1"]["profile"], "SINCO Program Change")
        self.assertEqual(res["input_patch"][0]["action"], "copied")
        ins = _inputs(root)
        self.assertEqual(ins["40"], [("🚨 PANIC RESET", "", "1")])
        self.assertEqual(ins["20"], [("Pub Setlist", "Next", "1")])
        self.assertEqual(ins["10"], [("Pub Setlist", "Previous", "1")])
        self.assertIn("── INPUT / MIDI ──", res["report"])
        self.assertIn("input patch copied from the source (SINCO)", res["report"])

    def test_doctor_d012_clean(self):
        _plan, res, root = run_port(self.src, self.tgt_a)
        d012 = [f for f in check(root, []).findings if f.code == "D012"]
        self.assertEqual(d012, [])

    def test_copy_off_leaves_warning(self):
        _plan, res, root = run_port(self.src, self.tgt_a, copy_input=False)
        self.assertEqual(res["input_patch"][0]["action"], "skipped")
        self.assertTrue(any(f.code == "D012" for f in check(root, []).findings))

    def test_universe_mapping(self):
        _plan, res, root = run_port(self.src, self.tgt_a, universe_map={"1": "2"})
        ins = _inputs(root)
        self.assertEqual({u for v in ins.values() for (_c, _s, u) in v}, {"2"})
        patch = porter_input.read_patch(root)
        self.assertEqual(patch["2"]["device"], "SINCO")
        iom = root.find("Engine").find("InputOutputMap")
        self.assertEqual([u.get("ID") for u in iom.findall("Universe")], ["0", "2"])
        self.assertIn("moved to another universe", " ".join(res["vc"]["summary"]))

    def test_deterministic(self):
        a = run_port(self.src, self.tgt_a)[1]["bytes"]
        self.assertEqual(a, run_port(self.src, self.tgt_a)[1]["bytes"])


class TestSameController(_Base):
    def test_keep_free_drops_conflict_and_names_it(self):
        _plan, res, root = run_port(self.src, self.tgt_b)
        ins = _inputs(root)
        self.assertEqual([c for c, _s, _u in ins["40"]], ["ALL ON"])        # target keeps it
        self.assertEqual(ins["20"][0][0], "Pub Setlist")
        self.assertEqual(res["input_patch"][0]["action"], "ok")            # same device
        self.assertIn("dropped: already used by the target's Button 'ALL ON'", res["report"])

    def test_source_wins_moves_binding(self):
        _plan, res, root = run_port(self.src, self.tgt_b, bindings="source_wins")
        ins = _inputs(root)
        self.assertEqual([c for c, _s, _u in ins["40"]], ["🚨 PANIC RESET"])
        self.assertIn("removed from the target's Button 'ALL ON'", res["report"])
        self.assertEqual(res["vc"]["bindings_moved"], 1)

    def test_other_device_warns(self):
        root = _load("QuickStart_6fix.qxw")
        _patch(root, "Other", "APC mini")
        path = os.path.join(self.tmp, "QS6_apc.qxw")
        qxw_io.write_qxw(root, path)
        _plan, res, _root = run_port(self.src, path)
        self.assertEqual(res["input_patch"][0]["action"], "other_device")
        self.assertIn("another device (APC mini)", res["report"])


class TestBindingsOnly(_Base):
    """VC not ported; the bindings go onto matching target widgets."""

    def test_copied_by_caption(self):
        # Quick Start's "PANIC\nRESET" matches the source's "🚨 PANIC RESET"
        _plan, res, root = run_port(self.src, self.tgt_a, enabled=False, bindings_only=True)
        ins = _inputs(root)
        self.assertEqual(ins["40"], [("PANIC\nRESET", "", "1")])
        self.assertNotIn("20", ins)                         # no CueList in the target
        self.assertEqual(porter_input.read_patch(root)["1"]["device"], "SINCO")
        acts = {e["binding"]: e["action"] for e in res["copied_bindings"]}
        self.assertEqual(acts["MIDI/input U2 ch 40"], "copied")
        self.assertEqual(acts["MIDI/input U2 ch 20"], "not copied: no matching target widget")


class TestHelpers(unittest.TestCase):
    def test_device_name_formats(self):
        self.assertEqual(porter_input.device_name(ET.Element("Input", Plugin="MIDI", UID="SINCO")), "SINCO")
        self.assertEqual(porter_input.device_name(
            ET.Element("Input", Plugin="MIDI", UID="528145425", Name="SINCO")), "SINCO")
        self.assertEqual(porter_input.device_name(
            ET.Element("Input", Plugin="MIDI", UID="None", Name="None")), "")

    def test_slots(self):
        w = ET.fromstring('<CueList><Next><Input Universe="1" Channel="20"/><Key>Space</Key></Next>'
                          '<Button><Key>A</Key></Button></CueList>')
        slots = [(s, e.tag) for s, _p, e in porter_input.widget_bindings(w)]
        self.assertEqual(slots, [("Next", "Input"), ("Next", "Key")])


if __name__ == "__main__":
    unittest.main()


class TestValidationPreview(_Base):
    """Step 4 says which bindings clash with the target, per policy."""

    def _plan(self, **vc):
        porter.load_source(self.src)
        porter.load_target(self.tgt_b)
        keys = porter_vc.list_source_vc(porter.source_root())
        scope = [w["key"] for w in keys if w["caption"] == "1. SETLIST"]
        cl = porter.resolve_closure(porter_vc.seeds_from_widgets(porter.source_root(), scope))
        opts = dict(enabled=True, scope=scope)
        opts.update(vc)
        return dict(closure=cl, fixture_mapping=porter.auto_map(cl["fixture_ids"], "fan_in"),
                    fanout_mode="fan_in", drop_unmapped=True, qxf_paths=[CORPUS], vc=opts)

    def test_keep_free_warns(self):
        w = porter.validate(self._plan())["warnings"]
        hit = [x for x in w if "will be DROPPED" in x]
        self.assertEqual(len(hit), 1)
        self.assertIn("MIDI/input U2 ch 40 on Button '🚨 PANIC RESET'", hit[0])
        self.assertIn("target: Button 'ALL ON'", hit[0])
        self.assertIn("Source wins", hit[0])

    def test_source_wins_is_info(self):
        v = porter.validate(self._plan(bindings="source_wins"))
        self.assertFalse(any("DROPPED" in x for x in v["warnings"]))
        self.assertTrue(any("move from the target widgets" in x for x in v["info"]))

    def test_no_conflict_on_other_universe(self):
        w = porter.validate(self._plan(universe_map={"1": "3"}))["warnings"]
        self.assertFalse(any("DROPPED" in x for x in w))


class TestThroughTheApi(_Base):
    """The same options through the Flask routes the UI uses — the route
    used to drop 'source_wins', the universe map, copy_input and
    bindings_only (giopas's test on the real show, 29 Sep)."""

    def _post(self, client, url, body):
        r = client.post(url, json=body)
        self.assertLess(r.status_code, 300, r.get_data(as_text=True)[:300])
        return r

    def test_source_wins_and_universe_map_reach_the_porter(self):
        import app
        c = app.create_app().test_client()
        self._post(c, "/api/porter/source/load", {"path": self.src})
        self._post(c, "/api/porter/target/load", {"path": self.tgt_b})
        keys = porter_vc.list_source_vc(porter.source_root())
        scope = [w["key"] for w in keys if w["caption"] == "1. SETLIST"]
        cl = porter.resolve_closure(porter_vc.seeds_from_widgets(porter.source_root(), scope))
        plan = dict(closure=cl, fixture_mapping=porter.auto_map(cl["fixture_ids"], "fan_in"),
                    fanout_mode="fan_in", drop_unmapped=True,
                    vc=dict(enabled=True, scope=scope, bindings="source_wins",
                            universe_map={}, copy_input=True, bindings_only=False))
        self._post(c, "/api/porter/execute", plan)
        res = c.get("/api/porter/last-result").get_json()
        self.assertEqual(res["vc"]["bindings_moved"], 1)
        self.assertTrue(any("removed from the target's Button 'ALL ON'" in e["action"]
                            for e in res["vc"]["binding_log"]))
        plan["vc"].update(bindings="keep_free", universe_map={"1": "2"})
        r = self._post(c, "/api/porter/execute", plan)
        root = qxw_io.strip_ns(ET.fromstring(r.data))
        self.assertEqual(porter_input.read_patch(root)["2"]["device"], "SINCO")
