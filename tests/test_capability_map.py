"""
Capability translation between fixture types (WORKPLAN Phase 1.5)
=================================================================
Unit tests for ``core.capability_map`` on real QXFs (corpus + test
fixtures), and the Porter end-to-end: Festival_14fix (Eurolite RGBW spots +
generic 7-ch PARs) → QuickStart_club (Intimidator Spot 110 + SlimPAR 56),
a rig of **different** fixture types.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import capability_map as cm                         # noqa: E402
from core import porter, porter_vc                            # noqa: E402
from core.qxf_parser import parse_qxf                         # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
FIXT = os.path.join(HERE, "fixtures")

G7 = parse_qxf(os.path.join(CORPUS, "Generic-7Ch-RGB-PAR.qxf"))           # Dim R G B Strobe Mode Speed
EURO = parse_qxf(os.path.join(CORPUS, "Eurolite-LED-4C-12-Silent-Slim-Spot.qxf"))  # Dim Strobe R G B W …
SPOT = parse_qxf(os.path.join(FIXT, "Chauvet-Intimidator-Spot-110.qxf"))  # 6ch: Pan Tilt Wheel Strobe Dim Gobo
SPOT375 = parse_qxf(os.path.join(FIXT, "Chauvet-Intimidator-Spot-375Z-IRC.qxf"))
SLIM = parse_qxf(os.path.join(FIXT, "Chauvet-SlimPAR-56.qxf"))            # 7-Ch: R G B Macro Strobe Mode Dim


def tr(src, sm, tgt, tm, text, **kw):
    return cm.translate_text(src, sm, tgt, tm, text, **kw)


class TestIntensityAndColour(unittest.TestCase):
    def test_par_to_par_keeps_colour_and_level(self):
        out, notes = tr(G7, "7 Channel", SLIM, "7-Ch", "0,200,1,255,2,0,3,128,4,0,5,0,6,0")
        self.assertEqual(out, "0,255,1,0,2,128,3,0,4,0,5,0,6,200")
        self.assertEqual(notes, [])

    def test_level_baked_into_rgb_when_target_has_no_dimmer(self):
        out, _ = tr(G7, "7 Channel", SLIM, "3-Ch", "0,128,1,255,2,128,3,0")
        self.assertEqual(out, "0,128,1,64,2,0")

    def test_rgb_to_wheel_picks_nearest_colour(self):
        out, _ = tr(G7, "7 Channel", SPOT, "6 Channel", "0,200,1,0,2,0,3,255,4,0")
        vals = cm._pairs(out)
        self.assertEqual(vals[2], 96)          # Color 3 (Blue)
        self.assertEqual(vals[4], 200)         # dimmer = level × peak
        self.assertEqual((vals[0], vals[1]), (127, 127))   # pan/tilt neutral (centre)

    def test_wheel_to_rgb(self):
        out, _ = tr(SPOT, "6 Channel", SLIM, "7-Ch", "0,127,1,127,2,32,3,0,4,255,5,0")
        v = cm._pairs(out)
        self.assertEqual((v[0], v[1], v[2], v[6]), (255, 0, 0, 255))

    def test_open_wheel_is_white(self):
        out, _ = tr(SPOT, "6 Channel", SLIM, "7-Ch", "2,0,4,100")
        v = cm._pairs(out)
        self.assertEqual((v[0], v[1], v[2], v[6]), (255, 255, 255, 100))

    def test_rgbw_white_emitter_carried(self):
        out, _ = tr(EURO, "9 Channel", EURO, "9 Channel", "0,255,2,255,3,255,4,255,5,255")
        v = cm._pairs(out)
        self.assertEqual((v[2], v[3], v[4], v[5]), (0, 0, 0, 255))

    def test_rgb_to_rgbw_no_white(self):
        out, _ = tr(G7, "7 Channel", EURO, "9 Channel", "0,255,1,255,2,255,3,255")
        v = cm._pairs(out)
        self.assertEqual((v[0], v[2], v[3], v[4], v[5]), (255, 255, 255, 255, 0))

    def test_dark_source_stays_dark(self):
        out, _ = tr(G7, "7 Channel", SPOT, "6 Channel", "0,255,1,0,2,0,3,0")
        self.assertEqual(cm._pairs(out)[4], 0)

    def test_every_target_channel_declared(self):
        out, _ = tr(G7, "7 Channel", SPOT375, "15 channel", "0,255,1,255")
        self.assertEqual(sorted(cm._pairs(out)), list(range(15)))


class TestPositionAndShutter(unittest.TestCase):
    def test_pan_tilt_16bit_same_range(self):
        out, _ = tr(SPOT, "12 Channel", SPOT375, "15 channel", "0,127,1,0,2,200,3,0,7,255")
        v = cm._pairs(out)
        self.assertEqual((v[0], v[1], v[2], v[3]), (127, 0, 200, 0))

    def test_pan_centre_relative_degrees(self):
        # 90° right of centre on a 540° head → 0.5 + 90/540
        st = cm.LookState(pan=90.0, pan_is_deg=True, level=1.0)
        out, _ = cm.encode(SPOT, "6 Channel", st)
        self.assertEqual(out[0], round((0.5 + 90 / 540) * 255))

    def test_position_dropped_on_par_is_reported_only_off_centre(self):
        _, notes = tr(SPOT, "6 Channel", SLIM, "7-Ch", "0,127,1,127,4,255")
        self.assertEqual(notes, [])
        _, notes = tr(SPOT, "6 Channel", SLIM, "7-Ch", "0,0,1,127,4,255")
        self.assertIn("target has no pan; position dropped", notes)

    def test_strobe_speed_mapped_into_target_range(self):
        out, _ = tr(G7, "7 Channel", EURO, "9 Channel", "0,255,1,255,4,100")
        self.assertEqual(cm._pairs(out)[1], 1 + round((100 - 8) / 247 * 254))

    def test_strobe_drop_gives_open(self):
        out, notes = tr(G7, "7 Channel", SPOT, "6 Channel", "0,255,1,255,4,100", strobe="drop")
        self.assertEqual(cm._pairs(out)[3], 0)
        self.assertIn("strobe dropped", notes)

    def test_closed_shutter(self):
        st = cm.LookState(level=1.0, shutter="closed")
        out, _ = cm.encode(SPOT375, "9 channel", st)
        self.assertEqual(out[7], 0)                 # Shutter Closed
        out, _ = cm.encode(SLIM, "7-Ch", st)        # no closed position → dark
        self.assertEqual(out[6], 0)

    def test_everything_else_neutral(self):
        out, _ = tr(G7, "7 Channel", SPOT375, "9 channel", "0,255,1,255,5,200")
        v = cm._pairs(out)
        self.assertEqual((v[3], v[4], v[5]), (0, 0, 0))   # gobo open, no rotation, no prism

    def test_deterministic(self):
        a = tr(EURO, "9 Channel", SPOT, "12 Channel", "0,90,2,255,3,180,5,30")
        self.assertEqual(a, tr(EURO, "9 Channel", SPOT, "12 Channel", "0,90,2,255,3,180,5,30"))


class TestKind(unittest.TestCase):
    def test_families(self):
        self.assertEqual(cm.kind(SPOT, "6 Channel"), "moving")
        self.assertEqual(cm.kind(SLIM, "7-Ch"), "colour")
        self.assertEqual(cm.kind(EURO, "9 Channel"), "colour")
        self.assertEqual(cm.kind(None, "x"), "unknown")
        self.assertEqual(cm.kind(SLIM, "no such mode"), "unknown")


class TestPorterDifferentTypes(unittest.TestCase):
    """Festival_14fix → QuickStart_club: every fixture type differs."""

    @classmethod
    def setUpClass(cls):
        porter.load_source(os.path.join(CORPUS, "Festival_14fix.qxw"))
        porter.load_target(os.path.join(CORPUS, "QuickStart_club.qxw"))
        tree = porter_vc.list_source_vc(porter.source_root())
        scope = [w["key"] for w in tree if w["caption"] in ("FLOOR", "CEILING")]
        cl = porter.resolve_closure(porter_vc.seeds_from_widgets(porter.source_root(), scope))
        q = [CORPUS, FIXT]
        cls.mapping = porter.auto_map(cl["fixture_ids"], "fan_in", q)
        cls.plan = dict(closure=cl, fixture_mapping=cls.mapping, fanout_mode="fan_in",
                        drop_unmapped=True, qxf_paths=q, vc=dict(enabled=True, scope=scope))
        cls.validation = porter.validate(cls.plan)
        cls.res = porter.port(cls.plan)
        cls.xml = cls.res["bytes"].decode("utf-8")

    def test_fan_in_pairs_types_by_family(self):
        # 6 ceiling spots → the 2 moving heads, 8 floor PARs → the 4 SlimPARs
        for s in map(str, range(6)):
            self.assertIn(self.mapping[s][0], ("0", "1"))
        for s in map(str, range(6, 14)):
            self.assertIn(self.mapping[s][0], ("2", "3", "4", "5"))

    def test_validation_says_translated(self):
        self.assertEqual(self.validation["errors"], [])
        self.assertFalse(any("channel by channel" in w for w in self.validation["warnings"]))
        self.assertTrue(any("translated by capability" in i for i in self.validation["info"]))

    def test_doctor_clean(self):
        self.assertEqual(self.res["doctor"]["errors"], [])
        self.assertEqual(self.res["doctor"]["warnings"], [])

    def test_dark_red_on_spot_uses_red_slot(self):
        m = re.search(r'<Function [^>]*Name="Dark Red"[^>]*>(.*?)</Function>', self.xml, re.S)
        vals = dict(re.findall(r'<FixtureVal ID="(\d+)">([^<]*)', m.group(1)))
        spot = cm._pairs(vals["0"])
        self.assertEqual(spot[2], 32)          # Color 1 (Red)
        self.assertGreater(spot[4], 0)         # dimmer open

    def test_report_lists_translation(self):
        self.assertIn("TRANSLATED BETWEEN FIXTURE TYPES", self.res["report"])

    def test_byte_identical(self):
        self.assertEqual(self.res["bytes"], porter.port(self.plan)["bytes"])

    def test_translation_can_be_switched_off(self):
        plan = dict(self.plan, translate_types=False)
        v = porter.validate(plan)
        self.assertTrue(any("channel by channel" in w for w in v["warnings"]))


if __name__ == "__main__":
    unittest.main()


class TestPorterEfxAndSequence(unittest.TestCase):
    """EFX and Sequence steps on different fixture types (1.5 part 2).

    An EFX and a Sequence are added to Festival_14fix (the corpus has none):
    * EFX 9001: fixture 0 (spot, Position), 6 (PAR, Position), 7 (PAR, Dimmer)
    * Sequence 9002 bound to scene 100, two steps on fixtures 0 and 6.
    Ported into QuickStart_club (Spot 110 ×2 + SlimPAR 56 ×4)."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from xml.etree import ElementTree as ET
        from core import qxw_io
        ns = "{" + qxw_io.QLC_NS_URI + "}"
        tree = qxw_io.load_qxw(os.path.join(CORPUS, "Festival_14fix.qxw"))
        eng = tree.getroot().find(ns + "Engine")

        def sub(parent, tag, text=None, **attrs):
            el = ET.SubElement(parent, ns + tag, attrs)
            if text is not None:
                el.text = text
            return el
        efx = sub(eng, "Function", ID="9001", Type="EFX", Name="Test EFX")
        sub(efx, "Algorithm", "Circle")
        for fid, mode in (("0", "0"), ("6", "0"), ("7", "1")):
            fx = sub(efx, "Fixture")
            sub(fx, "ID", fid)
            sub(fx, "Head", "0")
            sub(fx, "Mode", mode)
        seq = sub(eng, "Function", ID="9002", Type="Sequence", Name="Test Seq", BoundScene="100")
        sub(seq, "Step", "0:0,255,2,255:6:0,255,1,255", Number="0", Values="4")
        sub(seq, "Step", "0:0,0:6:0,255,3,255", Number="1", Values="3")
        cls.tmp = tempfile.mkdtemp()
        src = os.path.join(cls.tmp, "Festival_efx.qxw")
        qxw_io.write_qxw(tree.getroot(), src)

        porter.load_source(src)
        porter.load_target(os.path.join(CORPUS, "QuickStart_club.qxw"))
        cl = porter.resolve_closure(["9001", "9002"])
        q = [CORPUS, FIXT]
        cls.mapping = porter.auto_map(cl["fixture_ids"], "fan_in", q)
        cls.plan = dict(closure=cl, fixture_mapping=cls.mapping, fanout_mode="fan_in",
                        drop_unmapped=True, qxf_paths=q)
        cls.res = porter.port(cls.plan)
        cls.xml = cls.res["bytes"].decode("utf-8")

    def _fn(self, name):
        m = re.search(r'<Function [^>]*Name="%s"[^>]*>(.*?)</Function>' % name, self.xml, re.S)
        self.assertIsNotNone(m, name)
        return m.group(1)

    def test_sequence_fixture_collected(self):
        self.assertIn("6", self.plan["closure"]["fixture_ids"])

    def test_efx_drops_position_on_par(self):
        body = self._fn("Test EFX")
        ids = re.findall(r"<Fixture>\s*<ID>(\d+)</ID>\s*<Head>0</Head>\s*<Mode>(\d)</Mode>", body)
        self.assertIn((self.mapping["0"][0], "0"), ids)       # spot keeps the movement
        self.assertIn((self.mapping["7"][0], "1"), ids)       # PAR keeps the dimmer EFX
        self.assertNotIn((self.mapping["6"][0], "0"), ids)    # PAR can't move
        self.assertTrue(any(x.get("efx") for x in self.res["translated"]))
        self.assertIn("EFX needs position", self.res["report"])

    def test_sequence_steps_remapped_and_translated(self):
        body = self._fn("Test Seq")
        steps = re.findall(r'<Step Number="(\d)"[^>]*Values="(\d+)"[^>]*>([^<]*)</Step>', body)
        self.assertEqual(len(steps), 2)
        spot, par = self.mapping["0"][0], self.mapping["6"][0]
        for _n, count, text in steps:
            parts = text.split(":")
            fids = parts[0::2]
            # the one spot source fans out to both spots; the PAR feeds its SlimPAR
            self.assertEqual(fids, self.mapping["0"] + [par])
            self.assertEqual(int(count), sum(len(cm._pairs(v)) for v in parts[1::2]))
        first = dict(zip(steps[0][2].split(":")[0::2], steps[0][2].split(":")[1::2]))
        self.assertEqual(sorted(cm._pairs(first[par])), list(range(7)))   # SlimPAR 7-Ch
        self.assertEqual(cm._pairs(first[par])[0], 255)                   # red stays red
        self.assertEqual(cm._pairs(first[spot])[2], 32)                   # Eurolite ch 2 = red → red slot

    def test_doctor_clean(self):
        self.assertEqual(self.res["doctor"]["errors"], [])

    def test_byte_identical(self):
        self.assertEqual(self.res["bytes"], porter.port(self.plan)["bytes"])


class TestGobo(unittest.TestCase):
    def test_same_slot_number(self):
        # Spot 110 gobo wheel: Open 0, Gobo 1 = 32 …; 375Z: Open 0, Gobo 1 = 8, Gobo 2 = 16 …
        out, notes = tr(SPOT, "6 Channel", SPOT375, "9 channel", "4,255,5,64")   # Gobo 2
        self.assertEqual(cm._pairs(out)[3], 16)
        self.assertEqual(notes, [])

    def test_open_stays_open(self):
        out, _ = tr(SPOT, "6 Channel", SPOT375, "9 channel", "4,255,5,0")
        self.assertEqual(cm._pairs(out)[3], 0)

    def test_gobo_dropped_on_par(self):
        _, notes = tr(SPOT, "6 Channel", SLIM, "7-Ch", "4,255,5,64")
        self.assertIn("target has no gobo wheel; gobo dropped", notes)

    def test_rotation_channel_is_not_a_wheel(self):
        chdef = SPOT375["channel_defs"]["Gobo Rotation"]
        self.assertEqual(cm._gobo_slots(chdef), [])
