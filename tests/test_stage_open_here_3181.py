"""3.18.1: the companion opens the page on this computer; the page has a light theme and a colours button."""

import re

import pytest

from core import stage_monitor as sm
from stage_app import control
from tests.test_stage_app import exported, _free_port  # noqa: F401 — the fixture


def test_open_here_opens_localhost(exported):
    app = control.App(folder=exported, probe=lambda **k: {"state": "off"})
    opened = []
    app.browser = lambda u: opened.append(u) or True
    with pytest.raises(ValueError):
        app.open_here()                              # nothing served yet
    port = _free_port()
    app.start(port)
    try:
        assert app.open_here()["url"] == f"http://localhost:{port}/"
        role = app.state()["page"]["views"][0]["id"]
        assert app.open_here(role)["url"] == f"http://localhost:{port}/?role={role}"
        with pytest.raises(ValueError):
            app.open_here("../../etc")              # only the page's own views
        assert opened == [f"http://localhost:{port}/", f"http://localhost:{port}/?role={role}"]
    finally:
        app.stop()


def test_light_theme_and_colours_button():
    assert sm.clean_config({"theme": "light"})["theme"] == "light"
    html = open(sm.PAGE_TEMPLATE, encoding="utf-8").read()
    assert ':root[data-theme="light"]' in html and '<button id="th"' in html
    js_themes = re.findall(r'\["(\w+)", T\(', html)
    assert tuple(js_themes) == sm.THEMES             # the button cycles every theme the export knows


def test_no_empty_space_above_the_first_song():
    html = open(sm.PAGE_TEMPLATE, encoding="utf-8").read()
    assert "#list::before" not in html and "#list::after" in html


def test_the_page_follows_the_list_that_starts_playing():
    html = open(sm.PAGE_TEMPLATE, encoding="utf-8").read()
    assert "function started(id, was)" in html and html.count("started(") >= 3
    assert "#tabs button.play::before" in html


def test_add_the_new_cue_lists_and_a_red_stop():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, "static", "js", "stagemon.js"), encoding="utf-8").read()
    assert "function stagemonAddNew()" in js and "stagemonAddNew()" in js
    ui = open(os.path.join(root, "stage_app", "ui", "index.html"), encoding="utf-8").read()
    assert 'class="btn btn-danger" id="stop"' in ui
