#!/usr/bin/env python3
"""A poisoned show through every screen: does any name run as HTML? (3.9.7, advisory)

    python3 tools/xss_probe.py                      # starts the app, opens a poisoned copy of a corpus show
    python3 tools/xss_probe.py --url http://127.0.0.1:5731   # an app that is already running
    python3 tools/xss_probe.py --show tests/corpus/Pub_6fix.qxw

Every name, caption, path, model and author in the show is replaced by an <img onerror> that
records its own field in ``window.__xss``.  The probe opens the show the way the page does, visits
every screen, presses the buttons that only read (Preview, Check, Scan…), and fails when a payload
ran or an injected <img> is in the page.  The show lives in a scratch folder; yours are never touched.

Needs Playwright with a Chromium (like tools/shots.py).  Exit 0: nothing ran.  1: something ran.
"""
import argparse
import asyncio
import os
import re
import sys
import tempfile
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)                      # shots.py imports app from the repo folder

SCREENS = ["start", "quickstart", "fixtures", "reducer", "porter", "brightness", "looks", "vceditor", "stage",
           "setlist", "songbuilder", "triggers", "dictionary", "stagemon", "cabling", "doctor", "wizard", "upgrade", "compare",
           "idbrowser", "library", "showbook"]
# buttons that only read; anything that writes, deletes, quits or leaves is never pressed
SKIP = r"save|export|apply|delete|remove|quit|write|install|replace|discard|clear|reset|stop|download|kill|travel|undo|redo"


def poison(src_path: str, out_path: str) -> int:
    """A copy of the show where every name-like field is a payload that says which field it was."""
    src = open(src_path, encoding="utf-8").read()
    n = [0]

    def pay(tag):
        return escape("<img src=x onerror='(window.__xss=window.__xss||[]).push(\"%s\")'>" % tag, {'"': "&quot;"})

    def attr(m):
        n[0] += 1
        return '%s="%s"' % (m.group(1), pay(m.group(1) + str(n[0])))

    def el(m):
        n[0] += 1
        return "<%s>%s</%s>" % (m.group(1), pay(m.group(1) + str(n[0])), m.group(1))
    out = re.sub(r'\b(Name|Caption|Path)="[^"]*"', attr, src)
    out = re.sub(r"<(Manufacturer|Model|Mode|Author|Name)>[^<]*</\1>", el, out)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(out)
    return n[0]


async def probe(url: str, show: str) -> int:
    from playwright.async_api import async_playwright
    bad = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
        await page.goto(url + "/")
        await page.evaluate("p => _doLoad({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p})})", show)
        await page.wait_for_timeout(2500)
        for s in SCREENS:
            await page.evaluate(f"go('{s}')")
            await page.wait_for_timeout(700)
            await page.evaluate("""skip => { const sc = document.querySelector('.screen.active'); if (!sc) return;
                const rx = new RegExp(skip, 'i');
                sc.querySelectorAll('button[onclick]').forEach(b => { const o = b.getAttribute('onclick') || '';
                  if (rx.test(o + b.textContent) || /^(go|open|cycle)/.test(o) || /Help|Theme/.test(o)) return;
                  try { b.click(); } catch (e) {} }); }""", SKIP)
            await page.wait_for_timeout(1000)
            ran, live = await page.evaluate("[(window.__xss || []).length, document.querySelectorAll('img[src=x]').length]")
            shown = await page.evaluate("document.body.innerText.split('onerror').length - 1")
            flag = "FAIL" if ran or live else "ok"
            bad += 1 if ran or live else 0
            print(f"  {s:<11} {flag:<4} ran={ran} injected={live} payload text shown={shown}")
        await page.evaluate("go('showbook'); sbSelectAll(); sbGenerate()")
        await page.wait_for_timeout(5000)
        ran, live = await page.evaluate("[(window.__xss || []).length, document.querySelectorAll('img[src=x]').length]")
        print(f"  {'preview':<11} {'FAIL' if ran or live else 'ok':<4} ran={ran} injected={live}")
        bad += 1 if ran or live else 0
        await browser.close()
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", help="an app that is already running (default: start one)")
    ap.add_argument("--show", default=os.path.join(ROOT, "tests", "corpus", "Festival_14fix.qxw"))
    a = ap.parse_args()
    out = os.path.join(tempfile.mkdtemp(prefix="sk-xss-"), "poison.qxw")
    print(f"poisoned fields: {poison(a.show, out)}")
    if a.url:
        bad = asyncio.run(probe(a.url, out))
    else:
        from shots import App
        with App() as app:
            bad = asyncio.run(probe(app.url, out))
    print("\nNothing ran." if not bad else f"\n{bad} screen(s) ran injected HTML.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
