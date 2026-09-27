"""
Show Book (WORKPLAN Phase 1.3)
==============================
Section builders, DMX decoding against the corpus QXFs, the VC Layout
section against Pub_6fix's real pages and frames, the Doctor section, the
CSV zip and the PDF text layer — all on the corpus files.
"""
import csv
import io
import os
import re
import sys
import tempfile
import unittest
import zipfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import fixture, showbook, workspace                 # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
FIXT = os.path.join(HERE, "fixtures")
DATE = "2026-09-27"


def book(name, sections=None, qxf_dir=None, path=None):
    fixture.clear_rig()
    workspace.load_qxw(path or os.path.join(CORPUS, name))
    return showbook.generate(sections, qxf_dir, date=DATE)


def pdf_text(data: bytes) -> str:
    """Text layer of our PDFs: every (…) Tj string of every Flate stream."""
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            content = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        for t in re.finditer(rb"\((.*?)(?<!\\)\) Tj", content, re.S):
            out.append(t.group(1).replace(rb"\(", b"(").replace(rb"\)", b")")
                       .replace(rb"\\\\", b"\\").decode("latin-1"))
    return "\n".join(out)


def scene(doc, name):
    return next(s for s in doc["sections"]["scenes"] if s["name"] == name)


class TestSections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = book("Pub_6fix.qxw")
        cls.S = cls.doc["sections"]

    def test_all_sections_present(self):
        self.assertEqual(set(self.S), set(showbook.ALL_SECTIONS))
        self.assertEqual(self.doc["show_name"], "Pub_6fix")
        self.assertEqual(self.doc["date"], DATE)

    def test_summary(self):
        s = self.S["summary"]
        self.assertEqual((s["fixture_count"], s["function_count"]), (6, 207))
        self.assertEqual(s["function_types"], {"Chaser": 38, "Scene": 133, "Collection": 36})
        self.assertEqual((s["vc_page_count"], s["vc_widget_count"]), (2, 98))
        self.assertEqual(s["universes"], [1])

    def test_patch_sorted_and_model_without_manufacturer(self):
        p = self.S["patch"]
        self.assertEqual(len(p), 6)
        self.assertEqual([r["address"] for r in p], sorted(r["address"] for r in p))
        self.assertEqual(p[0]["patch"], "U1.001")
        self.assertEqual({r["model"] for r in p}, {"7-Ch RGB LED PAR"})
        self.assertEqual({r["manufacturer"] for r in p}, {"Generic"})

    def test_function_index(self):
        f = self.S["functions"]
        self.assertEqual(len(f), 207)
        self.assertEqual([int(r["id"]) for r in f], sorted(int(r["id"]) for r in f))

    def test_chaser_steps_and_times(self):
        ch = next(c for c in self.S["chasers"] if c["name"] == "Rock Loop")
        self.assertEqual(len(ch["steps"]), 3)
        self.assertEqual(ch["steps"][0]["hold"], "1.0s")
        self.assertEqual(ch["steps"][0]["function_name"], "Rock Loop Step 130")

    def test_empty_sections_are_lists(self):
        self.assertEqual((self.S["efx"], self.S["shows"], self.S["scripts"]), ([], [], []))


class TestDecoding(unittest.TestCase):
    """Values decoded with the fixture definitions (found next to the file)."""

    def test_par_dimmer_percent_and_strobe_capability(self):
        doc = book("Pub_6fix.qxw")
        ch = scene(doc, "PRE-SHOW Logo/Drums White")["fixtures"][0]["channels"]
        by = {c["channel_name"]: c for c in ch}
        self.assertEqual(by["Master Dimmer"]["decoded"], "78% (200)")
        self.assertEqual(by["Strobe"]["decoded"], "No flash (0)")
        self.assertTrue(by["Mode"]["decoded"].startswith("DMX Mode"), by["Mode"]["decoded"])

    def test_spot_rgbw(self):
        doc = book("Festival_14fix.qxw")
        sc = next(s for s in doc["sections"]["scenes"]
                  if s["fixtures"] and s["fixtures"][0]["fixture_model"].endswith("Slim Spot"))
        names = [c["channel_name"] for c in sc["fixtures"][0]["channels"]]
        self.assertIn("White", names)
        self.assertNotIn("Ch 1", names)        # every index resolved by name

    def test_pan_tilt_degrees_with_qxf_dir(self):
        doc = book("QuickStart_club.qxw", ["scenes"], qxf_dir=FIXT)
        vals = [c["decoded"] for s in doc["sections"]["scenes"] for f in s["fixtures"]
                for c in f["channels"] if c["channel_name"] == "Pan"]
        self.assertTrue(vals)
        self.assertTrue(all("°" in v for v in vals), vals[:3])
        self.assertIn("268.9° (127)", vals)                # 127/255 × 540

    def test_unknown_fixture_stays_raw(self):
        doc = book("QuickStart_club.qxw", ["scenes"])     # no qxf_dir, not next to the file
        chans = [c for s in doc["sections"]["scenes"] for f in s["fixtures"] for c in f["channels"]]
        self.assertTrue(chans)
        self.assertTrue(all(c["decoded"] == str(c["raw_value"]) for c in chans
                            if c["channel_name"].startswith("Ch ")))


class TestVcLayout(unittest.TestCase):
    """The VC Layout section matches Pub_6fix's pages and frames."""

    @classmethod
    def setUpClass(cls):
        cls.L = book("Pub_6fix.qxw", ["vc_layout"])["sections"]["vc_layout"]
        cls.w = {w["caption"]: w for pg in cls.L["pages"] for w in pg["widgets"]}

    def test_pages(self):
        self.assertEqual([(p["caption"], p["size"]) for p in self.L["pages"]],
                         [("1. SETLIST", "1650×884"), ("2. EFFECTS", "1650×884")])

    def test_first_page_widgets(self):
        caps = [w["caption"] for w in self.L["pages"][0]["widgets"]]
        self.assertEqual(caps, ["⛔ PANIC / BLACKOUT", "▪ STAGE PATTER", "☀ ALL WHITE (Changeover)",
                                "🚨 PANIC RESET", "Master Dim", "Pub Setlist"])

    def test_frame_paths_and_depth(self):
        w = self.w["AS · Emerald City"]
        self.assertEqual(w["frame"], "◆ SHOW — one look at a time › ◼ LOOKS")
        self.assertEqual(w["depth"], 2)
        self.assertEqual(self.w["◼ LOOKS"]["type"], "Frame")

    def test_ids_positions_functions(self):
        w = self.w["▪ STAGE PATTER"]
        self.assertEqual((w["id"], w["x"], w["y"], w["w"], w["h"]), ("9505", "1130", "126", "260", "90"))
        self.assertEqual((w["function_id"], w["function_name"]), ("211", "Patter Warm Low (was Dark Red)"))
        self.assertEqual(self.w["⛔ PANIC / BLACKOUT"]["function_name"], "(stop all functions)")

    def test_bindings(self):
        self.assertEqual(self.w["Pub Setlist"]["bindings"],
                         "Next: key Space, Prev: key Backspace, Stop: key Esc")
        self.assertEqual(self.w["AS · Emerald City"]["bindings"][:4], "key ")

    def test_midi_bindings(self):
        from tests.test_porter_input import make_source
        path = make_source(tempfile.mkdtemp())
        L = book(None, ["vc_layout"], path=path)["sections"]["vc_layout"]
        w = {x["caption"]: x for pg in L["pages"] for x in pg["widgets"]}
        self.assertEqual(w["🚨 PANIC RESET"]["bindings"], "MIDI U2 ch 40")
        self.assertIn("Next: key Space, Next: MIDI U2 ch 20", w["Pub Setlist"]["bindings"])

    def test_count_matches_xml(self):
        from core import qxw_io, vc_ops
        root = qxw_io.load_qxw(os.path.join(CORPUS, "Pub_6fix.qxw"), strip_namespace=True).getroot()
        vc = root.find("VirtualConsole")
        n = sum(1 for e in vc.iter() if vc_ops._is_widget(e)) - len(self.L["pages"])
        self.assertEqual(self.L["widget_count"], n)


class TestDoctorSection(unittest.TestCase):
    def test_clean_file(self):
        d = book("Pub_6fix.qxw", ["doctor"])["sections"]["doctor"]
        self.assertEqual((d["errors"], d["warnings"], d["findings"]), (0, 0, []))

    def test_file_with_errors(self):
        d = book("Festival_14fix.qxw", ["doctor"])["sections"]["doctor"]
        self.assertEqual(d["errors"], 1)
        self.assertEqual(d["findings"][0]["code"], "D002")


class TestExports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = book("Pub_6fix.qxw")
        cls.zip = showbook.export_csv(cls.doc)
        cls.pdf = showbook.export_pdf(cls.doc)

    def test_zip_contents(self):
        with zipfile.ZipFile(io.BytesIO(self.zip)) as z:
            names = sorted(z.namelist())
            self.assertEqual(names, sorted(["patch.csv", "functions.csv", "scenes.csv",
                                            "chasers.csv", "collections.csv", "efx.csv",
                                            "shows.csv", "scripts.csv", "vc_layout.csv",
                                            "doctor.csv", "summary.txt"]))
            rows = list(csv.reader(io.StringIO(z.read("vc_layout.csv").decode("utf-8"))))
            self.assertEqual(rows[0][:5], ["Page", "Frame Path", "Widget ID", "Type", "Caption"])
            self.assertEqual(len(rows), 1 + 2 + 98)            # header + pages + widgets
            patch = list(csv.reader(io.StringIO(z.read("patch.csv").decode("utf-8"))))
            self.assertEqual(len(patch), 7)
            summ = z.read("summary.txt").decode("utf-8")
            self.assertIn("VC Widgets: 98 on 2 page(s)", summ)
            self.assertIn("Doctor: 0 error(s), 0 warning(s)", summ)

    def test_zip_deterministic(self):
        self.assertEqual(self.zip, showbook.export_csv(self.doc))

    def test_pdf_text_layer(self):
        self.assertTrue(self.pdf.startswith(b"%PDF"))
        t = pdf_text(self.pdf)
        for s in ("Pub_6fix", "Fixture Patch List", "FLS: Front Left (Singer)",
                  "Page: 1. SETLIST", "Page: 2. EFFECTS", "PANIC / BLACKOUT",
                  "Workspace Doctor", "0 error(s), 0 warning(s)", DATE):
            self.assertIn(s, t)
        self.assertNotIn("?", "".join(re.findall(r"^.*PANIC.*$", t, re.M)))   # emoji dropped, not "?"
        self.assertIn("(stop all functions)", t)
        self.assertIn("» » AS · Emerald City", t)                              # frame depth
        self.assertIn("SHOW - one look at a time", t)                          # "—" mapped to "-"

    def test_pdf_deterministic(self):
        self.assertEqual(self.pdf, showbook.export_pdf(self.doc))


if __name__ == "__main__":
    unittest.main()
