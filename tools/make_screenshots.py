#!/usr/bin/env python3
"""Retake the README screenshots (screenshots/01..18) with Playwright.

    python3 app.py --browser &            # the app on http://127.0.0.1:5731
    python3 tools/make_screenshots.py [OUT_DIR]

Uses the scrubbed corpus shows (tests/corpus) and the Chauvet test fixtures, so
nothing private is shown.  Dark theme, 1440 x 900.  Needs: pip install playwright
and a Chromium.  The route GIF and the tutorial pictures are made by
tools/make_route_gif.py.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "tests", "corpus")
FIX = os.path.join(ROOT, "tests", "fixtures")
BASE = os.environ.get("SWK_URL", "http://127.0.0.1:5731")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "screenshots")


def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")
    except Exception as e:  # noqa: BLE001
        print("  ! POST", path, e)
        return {}


def main():
    os.makedirs(OUT, exist_ok=True)
    # Quick Start rig (server side): two spots in 6-channel mode + four PARs
    post("/api/quickstart/clear", {})
    for f in ("Chauvet-Intimidator-Spot-110", "Chauvet-SlimPAR-56"):
        post("/api/quickstart/load-qxf", {"path": os.path.join(FIX, f + ".qxf")})
    post("/api/quickstart/add-fixture", {"key": "Chauvet::Intimidator Spot 110", "mode": "6 Channel",
                                         "quantity": 2, "name": "Spot"})
    post("/api/quickstart/add-fixture", {"key": "Chauvet::SlimPAR 56", "quantity": 4, "name": "Par"})

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        from core.workspace import VERSION
        # the update check needs the internet; the pictures should not show an error
        pg.route("**/api/update/**", lambda r: r.fulfill(json={
            "current": VERSION, "latest": VERSION, "enabled": True, "frozen": False,
            "can_install": False, "platform": "x", "error": "", "newer": False}))
        pg.goto(BASE + "/")
        pg.wait_for_timeout(800)
        def load(path):
            pg.evaluate("p=>fetch('/api/load',{method:'POST',headers:{'Content-Type':'application/json'},"
                        "body:JSON.stringify({path:p})})", path)
            pg.reload()
            pg.wait_for_timeout(1500)

        load(os.path.join(CORPUS, "Festival_14fix.qxw"))

        def shot(name, nav=None, wait=900):
            if nav:
                pg.click("#sn-" + nav)
            pg.wait_for_timeout(wait)
            pg.evaluate("document.activeElement && document.activeElement.blur()")
            pg.mouse.move(1400, 880)
            pg.screenshot(path=os.path.join(OUT, name))
            print("  ✓", name)

        shot("01-start.png")
        shot("02-quick-start.png", "quickstart", 1200)
        shot("03-fixtures.png", "fixtures")
        # 04 · Rig Reducer: the six ceiling spots unticked
        pg.click("#sn-reducer")
        pg.wait_for_timeout(900)
        boxes = pg.locator("#scr-reducer input[type=checkbox]")
        for i in range(6):
            boxes.nth(i).uncheck()
        shot("04-rig-reducer.png", None, 700)
        pg.reload()
        pg.wait_for_timeout(1500)
        # 05 · Function Porter: the pub show as the source
        pg.click("#sn-porter")
        pg.wait_for_timeout(600)
        post("/api/porter/source/load", {"path": os.path.join(CORPUS, "Pub_6fix.qxw")})
        pg.reload()
        pg.wait_for_timeout(1200)
        shot("05-function-porter.png", "porter", 1200)
        shot("06-brightness.png", "brightness")
        # 07 · Look Builder: two groups, the warm palette, added to the batch
        pg.click("#sn-looks")
        pg.wait_for_timeout(900)
        try:
            pg.get_by_label("Ceiling").first.check()
            pg.get_by_label("Floor", exact=False).first.check()
            pg.get_by_text("Warm White").first.click()
            pg.get_by_text("Amber").first.click()
            pg.get_by_role("button", name="+ Add looks").click()
        except Exception as e:  # noqa: BLE001
            print("  ! looks:", str(e)[:120])
        shot("07-look-builder.png", None, 900)
        shot("08-vc-editor.png", "vceditor", 1500)
        shot("09-stage-meshes.png", "stage", 1200)
        # 10 · Setlist: a night's songs pasted into the first slot and matched
        pg.click("#sn-setlist")
        pg.wait_for_timeout(1200)
        try:
            pg.locator("#slot-list > *").first.click()
            pg.click("#btn-import-paste")
            pg.fill("#sl-imp-text", "\n".join(f"Song {n:02d}" for n in range(1, 38) if n not in (17, 25, 33)))
            pg.dispatch_event("#sl-imp-text", "input")
            pg.wait_for_timeout(1200)
            pg.click("#sl-imp-go")
            pg.wait_for_timeout(800)
            pg.click("#btn-auto-match")
        except Exception as e:  # noqa: BLE001
            print("  ! setlist:", str(e)[:120])
        shot("10-setlist.png", None, 1500)
        load(os.path.join(CORPUS, "Festival_14fix.qxw"))
        shot("11-trigger-manager.png", "triggers")
        shot("12-dictionary.png", "dictionary")
        shot("13-workspace-doctor.png", "doctor", 1200)
        shot("14-id-browser.png", "idbrowser")
        shot("15-show-paperwork.png", "showbook", 1200)
        shot("18-library.png", "library")
        # 16 · History and 17 · Compare: after a real change (the ceiling spots removed)
        pg.click("#sn-reducer")
        pg.wait_for_timeout(800)
        boxes = pg.locator("#scr-reducer input[type=checkbox]")
        for i in range(6):
            boxes.nth(i).uncheck()
        pg.get_by_role("button", name="Apply to the show").click()
        pg.wait_for_timeout(2500)
        pg.get_by_role("button", name="History").first.click()
        shot("16-show-in-progress.png", None, 1200)
        pg.locator("#show-history button[title=Close]").click()
        pg.click("#sn-compare")
        pg.wait_for_timeout(500)
        pg.get_by_role("button", name="Opened file").first.click()
        shot("17-compare.png", None, 2500)
        b.close()


if __name__ == "__main__":
    main()
