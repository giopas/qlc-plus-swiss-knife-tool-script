"""UI conventions for the tool footers (WORKPLAN: uniform action buttons).

Every tool screen ends with an ``.out-footer``: an ``out-note`` saying what the
tool writes, secondary buttons (``btn-surface``), and at most ONE primary
action (``btn-accent``) as the right-most button. Local CSS/JS carry ``?v=``.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(os.path.dirname(HERE), "templates", "index.html"), encoding="utf-8").read()


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
