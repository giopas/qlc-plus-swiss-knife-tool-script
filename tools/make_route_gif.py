#!/usr/bin/env python3
"""Run the guided route 'Adapt a show to a new venue' in the app and keep the pictures.

    python3 app.py --browser &
    python3 tools/make_route_gif.py [OUT_DIR]

Festival_14fix (scrubbed corpus) becomes a pub show: the nine steps of the wiki
tutorial.  Writes OUT_DIR/tutorial/01..09-*.png and OUT_DIR/route.gif (needs Pillow).
"""
import io
import json
import os
import sys
import urllib.request

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.workspace import VERSION  # noqa: E402

CORPUS = os.path.join(ROOT, "tests", "corpus")
BASE = os.environ.get("SWK_URL", "http://127.0.0.1:5731")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "screenshots")
TUT = os.path.join(OUT, "tutorial")
SONGS = [f"Song {n:02d}" for n in range(1, 38) if n not in (17, 25, 33)]      # 34 songs, Song 12 among them
NAMES = {6: "DR: Drums Floor", 7: "FLB: Front Left (Band)", 8: "FRB: Front Right (Band)",
         9: "LG: Logo / Banner", 10: "FLS: Front Left (Singer)", 13: "FRS: Front Right (Singer)"}
DROP = [0, 1, 2, 3, 4, 5, 11, 12]
GROUPS = [("Singer Pair", ["FLS", "FRS"]), ("Band Pair", ["FLB", "FRB"]),
          ("Front Band", ["FLB", "FRB", "DR"]), ("Logo", ["LG"]), ("All 6", [""])]


def main():
    os.makedirs(TUT, exist_ok=True)
    frames = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        pg.set_default_timeout(6000)
        pg.route("**/api/update/**", lambda r: r.fulfill(json={
            "current": VERSION, "latest": VERSION, "enabled": True, "frozen": False,
            "can_install": False, "platform": "x", "error": "", "newer": False}))
        pg.on("dialog", lambda d: d.accept(pg._dlg_text if hasattr(pg, "_dlg_text") else ""))

        def prompt(text):
            pg._dlg_text = text

        def frame(name=None, wait=600):
            pg.wait_for_timeout(wait)
            pg.mouse.move(1420, 890)
            png = pg.screenshot()
            frames.append(png)
            if name:
                with open(os.path.join(TUT, name), "wb") as f:
                    f.write(png)
                print("  ✓", name)

        def step(label, fn):
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                print(f"  ! {label}: {str(e)[:200]}")

        pg.goto(BASE + "/")
        pg.wait_for_timeout(800)
        pg.evaluate("p=>fetch('/api/load',{method:'POST',headers:{'Content-Type':'application/json'},"
                    "body:JSON.stringify({path:p})})", os.path.join(CORPUS, "Festival_14fix.qxw"))
        pg.reload()
        pg.wait_for_timeout(1500)
        frame()                                                       # the Start screen
        pg.locator(".route-card, .rc-card, [class*=card]").filter(has_text="Adapt a show to a new venue") \
            .get_by_role("button", name="Start the route").click()
        pg.wait_for_timeout(800)

        def done():
            pg.evaluate("document.getElementById('show-history').classList.remove('open')")
            pg.wait_for_timeout(300)
            pg.get_by_role("button", name="Done, next").click()
            pg.wait_for_timeout(700)

        # 1 · Rig Reducer
        def s1():
            rows = pg.locator("#scr-reducer tbody tr")
            for i in DROP:
                rows.nth(i).locator("input[type=checkbox]").uncheck()
            for i, nm in NAMES.items():
                inp = rows.nth(i).locator("input:not([type=checkbox])").first
                inp.fill(nm)
                inp.dispatch_event("change")
            frame("01-rig-reducer.png", 900)
            pg.get_by_role("button", name="Apply to the show").click()
            frame(None, 1500)
            done()
        step("reducer", s1)

        # 2 · Doctor
        def s2():
            pg.locator("#scr-doctor").get_by_role("button", name="Check").first.click()
            pg.wait_for_timeout(1500)
            pg.get_by_role("button", name="Recommended").click()
            frame("02-doctor.png", 800)
            pg.get_by_role("button", name="Fix").last.click()
            frame(None, 1500)
            done()
        step("doctor", s2)

        # 3 · skipped
        step("skip", done)

        # 4 · Groups
        def s4():
            pg.locator("#scr-stage button", has_text="Groups").first.click()
            pg.wait_for_timeout(600)
            for name, tags in GROUPS:
                pg.fill("#st-grp-name", name)
                pg.get_by_role("button", name="None").first.click()
                if tags == [""]:
                    pg.get_by_role("button", name="All").first.click()
                else:
                    for t in tags:
                        pg.locator("label").filter(has_text=f"{t}:").first.locator("input").check()
                pg.get_by_role("button", name="Create group").click()
                pg.wait_for_timeout(700)
            pg.evaluate("document.getElementById('show-history').classList.remove('open')")
            frame("03-groups.png", 800)
            done()
        step("groups", s4)

        # 5 · Look Builder
        def s5():
            lk = pg.locator("#scr-looks")
            lk.locator("label").filter(has_text="Singer Pair").first.locator("input").check()
            lk.locator("label").filter(has_text="Band Pair").first.locator("input").check()
            for c in ("Warm White", "Amber", "Orange", "Red", "Pink"):
                lk.get_by_text(c, exact=True).first.click()
            lk.get_by_role("button", name="Add looks").click()
            frame("04-looks.png", 900)
            lk.get_by_role("button", name="Chasers").first.click()
            pg.wait_for_timeout(500)
            frame(None, 400)
            lk.get_by_role("button", name="Check").first.click()
            frame("05-looks-to-build.png", 900)
            lk.get_by_role("button", name="Add to the show").click()
            frame(None, 1800)
            done()
        step("looks", s5)

        # 6 · VC editor pages
        def s6():
            pg.locator("#scr-vceditor").get_by_role("button", name="Pages").first.click()
            frame("06-vc-pages.png", 1500)
            done()
        step("vc", s6)

        # 7 · stage: skipped here
        step("stage", done)

        # 8 · Setlist
        def s8():
            pg.wait_for_timeout(1500)
            pg.locator("#slot-list > *").first.click()
            pg.get_by_role("button", name="Import").first.click()
            pg.wait_for_timeout(500)
            pg.fill("#sl-imp-text", "\n".join(SONGS))
            pg.dispatch_event("#sl-imp-text", "input")
            pg.wait_for_timeout(1200)
            pg.click("#sl-imp-go")
            pg.wait_for_timeout(800)
            pg.click("#btn-auto-match")
            frame("07-setlist.png", 1500)
            done()
        step("setlist", s8)

        # 9 · Final check
        def s9():
            pg.locator("#scr-doctor").get_by_role("button", name="Check").first.click()
            frame("08-final-check.png", 1800)
        step("final", s9)

        # Compare with the hand-made pub show
        def s10():
            pg.click("#sn-compare")
            pg.fill("input[placeholder*='paste the .qxw']", os.path.join(CORPUS, "Pub_6fix.qxw"))
            pg.keyboard.press("Enter")
            pg.get_by_role("button", name="Compare").last.click()
            frame("09-compare.png", 2500)
        step("compare", s10)
        b.close()

    # the GIF: Start, then one picture per step (taken at 960 px wide)
    pick = frames[:: max(1, len(frames) // 12)][:12] if len(frames) > 12 else frames
    imgs = [Image.open(io.BytesIO(f)).convert("RGB").resize((960, 600), Image.LANCZOS) for f in pick]
    imgs = [im.convert("P", palette=Image.ADAPTIVE, colors=128) for im in imgs]
    imgs[0].save(os.path.join(OUT, "route.gif"), save_all=True, append_images=imgs[1:],
                 duration=1800, loop=0, optimize=True)
    print("  ✓ route.gif", len(imgs), "frames")


if __name__ == "__main__":
    main()
