"""3.17.1: the Stage Monitor page keeps the tablet's screen on with a tiny silent video."""
import base64
import re

from core import stage_monitor as sm


def _page():
    return open(sm.PAGE_TEMPLATE, encoding="utf-8").read()


def test_the_page_carries_its_own_silent_looping_video():
    html = _page()
    tag = re.search(r'<video id="nosleep"[^>]*>', html, re.S).group(0)
    for attr in ("muted", "loop", "playsinline", 'aria-hidden="true"'):
        assert attr in tag, attr
    data = re.search(r'src="data:video/mp4;base64,([A-Za-z0-9+/=]+)"', tag).group(1)
    mp4 = base64.b64decode(data, validate=True)
    assert mp4[4:8] == b"ftyp" and len(mp4) < 4096          # a real MP4, and small


def test_a_button_turns_it_off_and_on_and_a_tap_starts_it():
    html = _page()
    assert '<button id="wk"' in html
    js = html[html.index("<script>"):]
    assert 'T("Keep screen on")' in js and 'T("Screen stays on")' in js
    assert "nosleep.play()" in js and "nosleep.pause()" in js
    assert 'addEventListener("pointerdown"' in js           # the first tap anywhere starts it
    assert "keepAwake()" in js[js.index('"visibilitychange"'):]   # and again when the tablet wakes


def test_every_server_lets_the_page_play_its_video():
    for p in (sm.SERVE_SCRIPT, sm.__file__):
        src = open(p, encoding="utf-8").read()
        assert "media-src data:" in src, p
