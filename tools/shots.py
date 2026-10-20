#!/usr/bin/env python3
"""Screenshots and the route GIF in one command: starts the app, takes the
pictures, says which ones changed and makes a contact sheet to look at them all
at once.

    python3 tools/shots.py readme                 # screenshots/01..18 (README and wiki)
    python3 tools/shots.py gif                    # screenshots/route.gif + screenshots/tutorial/*
    python3 tools/shots.py stage                  # screenshots/19..21 + stage-monitor.gif (the tablet page)
    python3 tools/shots.py cabling                # screenshots/22..24 + cabling.gif (a demo kit, never yours)
    python3 tools/shots.py stage --lang it --dry  # the Stage Monitor pictures in Italian, to look at
    python3 tools/shots.py all                    # all three
    python3 tools/shots.py readme --only 07 13    # keep only these (the others are still taken, not written)
    python3 tools/shots.py all --dry              # into a scratch folder: compare, do not replace
    python3 tools/shots.py state looks "go('looks')" "looksType('Concert')" --lang it --show Wizard530_video.qxw
                                                  # any screen: one picture per JavaScript step

After a run it prints, for each picture, whether it changed and by how much, and
writes contact.png (every new picture, small) next to them, so a reviewer opens
one image instead of twenty.

Options: --out DIR (where the pictures go), --lang it|fr|de|es|pt|ja|zh (state and stage),
--width/--height (default 1440 x 900), --url (use an app that is already running).
Needs Playwright with a Chromium and Pillow.  The app it starts uses the scrubbed
corpus shows in tests/corpus, so nothing private is shown.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "tests", "corpus")
SHOTS = os.path.join(ROOT, "screenshots")


# ── the app ──────────────────────────────────────────────────────────────────

class App:
    """The Swiss Knife server on a free port, for the time of the run."""

    def __init__(self, url=None):
        self.url, self.proc, self.kit = url, None, None

    def __enter__(self):
        if self.url:
            return self
        # the app's own port: it only accepts changes from a page on that port
        from app import PORT as port
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            raise SystemExit(f"Swiss Knife is already running on port {port}: quit it, or pass --url http://127.0.0.1:{port}")
        except OSError:
            pass
        # a scratch cabling kit: the pictures never read or change yours
        kit = os.path.join(tempfile.mkdtemp(prefix="sk-kit-"), "cabling_kit.json")
        self.kit = kit
        env = dict(os.environ, SK_NO_BROWSER="1", QLCPLUS_FIXTURES="", QSK_CABLING_KIT=kit)
        code = f"import app; a = app.create_app(); a.run(port={port}, threaded=True)"
        self.proc = subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.url = f"http://127.0.0.1:{port}"
        for _ in range(60):
            try:
                urllib.request.urlopen(self.url + "/", timeout=1)
                return self
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        self.__exit__()
        raise SystemExit("the app did not start")

    def __exit__(self, *_a):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ── comparing and the contact sheet ─────────────────────────────────────────

def _changed(new: str, old: str) -> str:
    from PIL import Image, ImageChops
    if not os.path.exists(old):
        return "new"
    a, b = Image.open(new).convert("RGB"), Image.open(old).convert("RGB")
    if a.size != b.size:
        return f"size {b.size[0]}×{b.size[1]} → {a.size[0]}×{a.size[1]}"
    diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 24 else 0)
    n = diff.histogram()[255]
    pct = 100 * n / (a.size[0] * a.size[1])
    return "same" if pct < 0.05 else f"{pct:.1f} % changed"


def contact_sheet(paths, out, cols=3, w=720):
    from PIL import Image, ImageDraw
    paths = [p for p in paths if p.lower().endswith(".png")]
    if not paths:
        return None
    h = int(w * 900 / 1440)
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + 22)), (13, 17, 23))
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(paths):
        x, y = (i % cols) * w, (i // cols) * (h + 22)
        im = Image.open(p).convert("RGB")
        im.thumbnail((w, h))                 # keeps the shape: a tablet page in portrait stays upright
        sheet.paste(im, (x + (w - im.width) // 2, y + 22))
        d.text((x + 6, y + 5), os.path.basename(p), fill=(232, 236, 245))
    sheet.save(out)
    return out


def report(new_dir, ref_dir, names):
    print("\n  picture                         vs the repo")
    for n in names:
        print(f"  {n:<31} {_changed(os.path.join(new_dir, n), os.path.join(ref_dir, n))}")


# ── the runs ─────────────────────────────────────────────────────────────────

def run_script(script, out, url, lang=None, kit=None):
    env = dict(os.environ, SWK_URL=url)
    if kit:
        env["QSK_CABLING_KIT"] = kit
    if os.environ.get("QSK_CABLING_KIT") is None and script == "make_cabling_shots.py":
        env["QSK_CABLING_KIT"] = os.path.join(tempfile.mkdtemp(prefix="sk-kit-"), "cabling_kit.json")
    if lang:
        env["SWK_LANG"] = lang
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", script), out], cwd=ROOT, env=env)
    if r.returncode:
        raise SystemExit(f"{script} failed")


def run_states(url, out, steps, lang, show, width, height, name):
    """One picture per JavaScript step: <name>-1.png, <name>-2.png …"""
    import json
    from playwright.sync_api import sync_playwright
    from core.workspace import VERSION
    if show:
        path = show if os.path.isabs(show) else os.path.join(CORPUS, show)
        req = urllib.request.Request(url + "/api/load", json.dumps({"path": path}).encode(),
                                     {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=60).read()
    made = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": width, "height": height})
        pg.route("**/api/update/**", lambda r: r.fulfill(json={
            "current": VERSION, "latest": VERSION, "enabled": True, "frozen": False,
            "can_install": False, "platform": "x", "error": "", "newer": False}))
        pg.on("dialog", lambda d: d.dismiss())
        if lang:
            pg.add_init_script(f"try {{ localStorage.setItem('sk-lang', '{lang}') }} catch (e) {{}}")
        pg.goto(url + "/")
        pg.wait_for_timeout(1500)
        for i, js in enumerate(steps, 1):
            try:
                pg.evaluate(f"async () => {{ {js} }}")
            except Exception as e:  # noqa: BLE001
                print(f"  ! step {i}: {str(e).splitlines()[0][:160]}")
            pg.wait_for_timeout(1800)
            pg.mouse.move(width - 20, height - 20)
            f = os.path.join(out, f"{name}-{i}.png")
            pg.screenshot(path=f)
            made.append(f)
            print("  ✓", os.path.basename(f))
        b.close()
    return made


def main(argv=None) -> int:
    sys.path.insert(0, ROOT)
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("what", choices=["readme", "gif", "stage", "cabling", "all", "state"])
    ap.add_argument("steps", nargs="*", help="state: a name, then one JavaScript step per picture")
    ap.add_argument("--only", nargs="*", default=None, help="readme/gif: keep only pictures starting with these")
    ap.add_argument("--dry", action="store_true", help="into a scratch folder; the repo is not touched")
    ap.add_argument("--out", help="folder for the pictures")
    ap.add_argument("--lang", help="interface language for state")
    ap.add_argument("--show", help="state: a show to open first (a file in tests/corpus, or a path)")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--url", help="an app already running (default: start one)")
    a = ap.parse_args(argv)

    if a.what == "state":
        with App(a.url) as app:
            if not a.steps:
                ap.error("state needs a name and at least one JavaScript step")
            out = a.out or tempfile.mkdtemp(prefix="sk-shots-")
            os.makedirs(out, exist_ok=True)
            made = run_states(app.url, out, a.steps[1:] or ["0"], a.lang, a.show, a.width, a.height, a.steps[0])
            sheet = contact_sheet(made, os.path.join(out, "contact.png"))
            print(f"\n  pictures in {out}" + (f"\n  all of them: {sheet}" if sheet else ""))
            return 0


    # each script gets a fresh app: one leaves the show changed for the next
    scratch = tempfile.mkdtemp(prefix="sk-shots-")
    jobs = [("readme", "make_screenshots.py"), ("gif", "make_route_gif.py"), ("stage", "make_stage_shots.py"),
            ("cabling", "make_cabling_shots.py")]
    for kind, script in jobs:
        if a.what in (kind, "all"):
            print(f"── {script}")
            with App(a.url) as app:
                run_script(script, scratch, app.url, a.lang if kind in ("stage", "cabling") else None,
                           kit=app.kit)

    # what was made, compared with the repo, then written (unless --dry or --out)
    made = []
    for dp, _dn, fns in os.walk(scratch):
        for fn in sorted(fns):
            rel = os.path.relpath(os.path.join(dp, fn), scratch)
            if a.only and not any(os.path.basename(rel).startswith(o) or rel.startswith(o) for o in a.only):
                continue
            made.append(rel)
    report(scratch, SHOTS, made)
    dest = a.out or (scratch if a.dry else SHOTS)
    if dest != scratch:
        for rel in made:
            os.makedirs(os.path.dirname(os.path.join(dest, rel)), exist_ok=True)
            shutil.copy2(os.path.join(scratch, rel), os.path.join(dest, rel))
    sheet = contact_sheet([os.path.join(scratch, r) for r in made], os.path.join(scratch, "contact.png"))
    print(f"\n  written to {dest}" + (f"\n  all of them, small: {sheet}" if sheet else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
