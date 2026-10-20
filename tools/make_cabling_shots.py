#!/usr/bin/env python3
"""Pictures of Cabling: the plan, My kit, the checks, and cabling.gif.

Easier: python3 tools/shots.py cabling (starts the app, compares, contact sheet).

    python3 tools/make_cabling_shots.py [OUT_DIR]

Writes OUT_DIR/22-cabling-plan.png, 23-cabling-kit.png, 24-cabling-check.png
(1440 x 900) and cabling.gif (the kit, the stage, the alternatives one after
the other, the checks).  Uses a copy of the scrubbed corpus show Festival_14fix
in a scratch folder (the plan file is written there, not in tests/corpus) and a
demo kit: the app must run with QSK_CABLING_KIT pointing to a scratch file
(tools/shots.py does that), so your own kit is never touched.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.request

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.cabling import kit as kit_mod  # noqa: E402
from core.workspace import VERSION  # noqa: E402

CORPUS = os.path.join(ROOT, "tests", "corpus")
BASE = os.environ.get("SWK_URL", "http://127.0.0.1:5731")
LANG = os.environ.get("SWK_LANG", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "screenshots")
W, H = 1440, 900


def api(path, body=None):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")


def demo_kit():
    P = kit_mod.PRESETS
    items = [P["enttec_usb_pro"], P["lixada_1x8"], P["adapter_5m_3f"], dict(P["terminator_3"], count=5),
             dict(P["cable_3_1.5"], count=2), dict(P["cable_3_3"], count=12), dict(P["cable_3_5"], count=4),
             dict(P["cable_3_10"], count=3), dict(P["cable_3_20"], count=1),
             kit_mod.fixture_item("Generic", "7-Ch RGB LED PAR", count=8, termination="none")]
    return {"items": items, "units": "m"}


def main():
    kit_path = os.environ.get("QSK_CABLING_KIT", "")
    if not kit_path or kit_path.startswith(os.path.expanduser("~/.qlc_swiss_knife")):
        sys.exit("make_cabling_shots: run it through tools/shots.py cabling (the app needs a scratch kit)")
    show_dir = tempfile.mkdtemp(prefix="sk-cabling-")
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), show_dir)
    show = os.path.join(show_dir, "Festival_14fix.qxw")
    shutil.copy(os.path.join(CORPUS, "Festival_14fix.qxw"), show)
    api("/api/load", {"path": show})
    api("/api/cabling/kit", {"kit": demo_kit()})
    os.makedirs(OUT, exist_ok=True)
    frames = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.route("**/api/update/**", lambda r: r.fulfill(json={
            "current": VERSION, "latest": VERSION, "enabled": True, "frozen": False,
            "can_install": False, "platform": "x", "error": "", "newer": False}))
        pg.on("dialog", lambda d: d.accept())
        if LANG:
            pg.add_init_script(f"try {{ localStorage.setItem('sk-lang', '{LANG}') }} catch (e) {{}}")
        pg.goto(BASE + "/")
        pg.wait_for_timeout(1500)

        def step(js, wait=1500, name=None, frame=True):
            pg.evaluate(f"async () => {{ {js} }}")
            pg.wait_for_timeout(wait)
            pg.mouse.move(W - 20, H - 20)
            png = pg.screenshot()
            if name:
                with open(os.path.join(OUT, name), "wb") as fh:
                    fh.write(png)
                print("  ✓", name)
            if frame:
                frames.append(Image.open(io.BytesIO(png)).convert("RGB"))

        step("go('cabling')", 2000, frame=False)
        # the venue's six spots on the truss: house fixtures, cabled and labelled, never packed
        step("['0','1','2','3','4','5'].forEach(i => { _cb.plan.owners[i] = 'venue'; }); "
             "_cb.plan.tonight.items.forEach(x => { if (x.kind === 'splitter') x.termination = 'none'; }); "
             "_cbChanged(); cablingKitMode('tonight')", 2000)
        # the scratch kit's path would show: the picture shows where yours is kept
        step("cablingKitMode('mine'); document.getElementById('cb-kit-path').textContent = "
             "_cbT('Kept in {0}, saved as you change it. Share it as a file through the Library (Cabling kit).', "
             "'~/.qlc_swiss_knife/cabling_kit.json')", 1200, name="23-cabling-kit.png")
        step("cablingGoStep(1)", 1500)
        step("_cbAlts = null; cablingGoStep(2); await cablingPropose()", 6000, name="22-cabling-plan.png")
        for k in (1, 2, 0):
            step(f"cablingPickAlt({k})", 2000)
        step("cablingGoStep(3)", 2000, name="24-cabling-check.png")
        b.close()
    small = [f.resize((960, 600), Image.LANCZOS) for f in frames]
    pal = [im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for im in small]
    pal[0].save(os.path.join(OUT, "cabling.gif"), save_all=True, append_images=pal[1:],
                duration=[1600] * (len(pal) - 1) + [3500], loop=0, optimize=True)
    print("  ✓ cabling.gif", len(pal), "frames")
    shutil.rmtree(show_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
