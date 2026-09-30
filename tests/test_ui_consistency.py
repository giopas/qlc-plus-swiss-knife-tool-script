"""UI conventions for the tool footers (WORKPLAN: uniform action buttons).

Every tool screen ends with an ``.out-footer``: an ``out-note`` saying what the
tool writes, secondary buttons (``btn-surface``), and at most ONE primary
action (``btn-accent``) as the right-most button. Local CSS/JS carry ``?v=``.
"""
import os
from pathlib import Path
import re

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = Path(os.path.dirname(HERE), "templates", "index.html").read_text(encoding="utf-8")


def _footers():
    for m in re.finditer(r'<div class="out-footer">(.*?)\n    </div>', HTML, re.S):
        sec = HTML.rfind('id="scr-', 0, m.start())
        yield HTML[sec + 8:HTML.index('"', sec + 8)], m.group(1)


def test_every_footer_has_one_primary_on_the_right():
    seen = 0
    for screen, body in _footers():
        seen += 1
        buttons = re.findall(r'<button[^>]*class="([^"]*)"', body)
        primaries = [c for c in buttons if "btn-accent" in c or "btn-primary" in c]
        assert len(primaries) <= 1 or screen == "quickstart", screen   # QS: Next / Generate swap
        if primaries:
            assert "btn-accent" in buttons[-1] or "btn-primary" in buttons[-1], screen
        assert "vce-xb" not in body and "btn-success" not in body, screen
    assert seen >= 12


def test_output_notes_present():
    for screen, body in _footers():
        if screen != "quickstart":
            assert 'class="out-note' in body, screen


def test_local_assets_are_cache_busted():
    for url in re.findall(r'(?:href|src)="(/static/(?:css|js)/[^"]+)"', HTML):
        assert "?v={{ asset_v }}" in url, url


def test_start_cards_match_side_menu_groups():
    """Start cards 1-6 and the side-menu groups 1-6: same numbers, names and tools."""
    nav = HTML[HTML.index('<div class="side-nav">'):HTML.index('<!-- Files panel -->')]
    groups = {}
    for m in re.finditer(r'id="sn-grp-(\d)"><span class="sn-gnum">(\d)</span><span class="sn-gtxt">(.*?)</span>(.*?)(?=<div class="sn-group-label"|$)', nav, re.S):
        assert m.group(1) == m.group(2)
        groups[m.group(1)] = (m.group(3), re.findall(r'id="sn-(\w+)"', m.group(4)))
    assert sorted(groups) == list("123456")
    start = HTML[HTML.index('id="scr-start"'):]
    start = start[:start.index('</section>')]
    cards = re.findall(r'<div class="wf-card" data-grp="(\d)">\s*<div class="wf-head"><div class="wf-num">(\d)</div><div class="wf-title">(.*?)</div>.*?<div class="wf-chips">(.*?)</div>', start, re.S)
    assert len(cards) == 6
    for grp, num, title, chips in cards:
        assert grp == num and groups[grp][0] == title, (grp, title)
        assert list(dict.fromkeys(re.findall(r"go\('(\w+)'\)", chips))) == groups[grp][1], title
    every = [t for _, tools in groups.values() for t in tools]
    assert len(every) == len(set(every)) == len(re.findall(r'<button class="sn-item" id="sn-', nav))


def test_javascript_parses():
    """A syntax error in one file silently kills a whole tool (30 Sep: a name
    clash in porter.js) — every static JS file must parse."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node not installed")
    js = Path(os.path.dirname(HERE), "static", "js")
    for f in sorted(js.glob("*.js")):
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{f.name}: {r.stderr[:300]}"
