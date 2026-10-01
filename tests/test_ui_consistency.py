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


# ── 2.6 screen pattern ──────────────────────────────────────────────────────

WIKI_PAGES = {
    "Home", "Quick-Start", "Fixture-Configurator", "Rig-Reducer", "Function-Porter",
    "Brightness", "Look-Builder", "VC-Visual-Editor", "Stage-and-Meshes",
    "Setlist-Manager", "Trigger-Manager", "Dictionary-Manager", "Workspace-Doctor",
    "ID-Browser", "Show-Paperwork", "Show-in-Progress",
}


def _screens():
    for m in re.finditer(r'<section class="screen[^"]*" id="scr-(\w+)">(.*?)</section>', HTML, re.S):
        yield m.group(1), m.group(2)


def test_every_tool_header_has_a_wiki_help_button():
    """Each tool says what it does and links its wiki page ("?")."""
    seen = 0
    for screen, body in _screens():
        if screen == "start":
            continue
        pages = re.findall(r'openHelp\(\'([\w-]+)\'\)', body)
        assert pages, f"{screen}: no ? help button"
        assert pages[0] in WIKI_PAGES, (screen, pages[0])
        assert 'class="p-desc"' in body, screen
        seen += 1
    assert seen >= 14


def test_help_route_opens_only_wiki_pages():
    import app as appmod
    a = appmod.create_app()
    a.config["TESTING"] = True
    c = a.test_client()
    r = c.post("/api/help", json={"page": "Function-Porter"}, headers={"Origin": "http://127.0.0.1:5731"})
    assert r.status_code == 200 and r.get_json()["url"].endswith("/wiki/Function-Porter")
    r = c.post("/api/help", json={"page": "../../evil"}, headers={"Origin": "http://127.0.0.1:5731"})
    assert r.status_code == 400


def test_one_save_verb_for_new_files():
    """Writers of a new .qxw say "Save as new file…"; the old verbs are gone."""
    visible = re.sub(r'<!--.*?-->', '', HTML, flags=re.S)
    for old in ("Generate QXW", "Save new version", "Apply &amp; Save", "Build → new file", "Save → new file"):
        assert old not in visible, old
    js = Path(os.path.dirname(HERE), "static", "js")
    for f in js.glob("*.js"):
        code = "\n".join(l for l in f.read_text(encoding="utf-8").splitlines()
                         if not l.lstrip().startswith(("//", "*", "/*")))
        assert "'💾 Generate QXW'" not in code and "Generate QXW to" not in code, f.name


def test_porter_steps_end_in_a_footer_with_the_primary_on_the_right():
    body = dict(_screens())["porter"]
    bars = re.findall(r'<div class="porter-nav-bar out-footer"[^>]*>(.*?)\n      </div>', body, re.S)
    assert len(bars) == 5
    for bar in bars:
        assert 'class="out-note' in bar
        classes = re.findall(r'<button[^>]*class="([^"]*)"', bar)
        prim = [c for c in classes if "btn-accent" in c]
        assert len(prim) == 1 and "btn-accent" in classes[-1], classes


def test_empty_states_say_the_next_step():
    """No blank panes: the tools that fill in on load have a placeholder text."""
    js = Path(os.path.dirname(HERE), "static", "js")
    app_js = (js / "app.js").read_text(encoding="utf-8")
    assert "to list its functions and Virtual Console widgets" in app_js     # ID Browser
    assert "_plainTable" in app_js                                           # offline ID Browser
    looks = (js / "looks.js").read_text(encoding="utf-8")
    assert "Open a workspace to build looks" in looks


def test_inspector_tabs_in_look_builder_and_stage():
    js = Path(os.path.dirname(HERE), "static", "js")
    looks = (js / "looks.js").read_text(encoding="utf-8")
    stage = (js / "stage3d.js").read_text(encoding="utf-8")
    assert set(re.findall(r'data-lbpane="(\w+)"', looks)) == {"looks", "chaser"}
    assert set(re.findall(r'data-stpane="(\w+)"', stage)) == {"select", "place", "add", "stage"}


def test_route_steps_open_real_tools():
    js = (Path(os.path.dirname(HERE), "static", "js") / "route.js").read_text(encoding="utf-8")
    screens = {s for s, _ in _screens()}
    tools = re.findall(r"tool: '(\w+)'", js)
    assert len(tools) >= 10
    assert set(tools) <= screens, set(tools) - screens
    for rid in re.findall(r"routeStart\('(\w+)'\)", HTML):
        assert f"\n  {rid}: {{" in js, rid


def test_no_beta_badge_left_on_the_vc_editor():
    assert 'class="b beta"' not in HTML
