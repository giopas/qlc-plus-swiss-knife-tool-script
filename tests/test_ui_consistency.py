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
    "ID-Browser", "Show-Paperwork", "Show-in-Progress", "Compare",
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
    assert set(re.findall(r'data-stpane="(\w+)"', stage)) == {"select", "place", "add", "stage", "groups"}


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


def test_ui_polish_v22():
    """v2.2 UI review: guided routes first on Start, a footer that says what
    Apply will do, the ⌘K palette, labelled header cards, semantic tokens."""
    start = HTML[HTML.index('id="scr-start"'):]
    assert start.index('class="start-routes"') < start.index('class="start-workflow"')
    for sid in ("reducer", "brightness", "doctor", "looks", "setlist"):
        sec = HTML[HTML.index(f'id="scr-{sid}"'):]
        foot = sec[sec.index('<div class="out-footer">'):]
        assert f'id="oc-{sid}"' in foot[:foot.index('</div>')], sid
    assert 'id="cp"' in HTML and "palette.js?v={{ asset_v }}" in HTML
    assert 'class="ms-l"' in HTML
    tokens = (Path(os.path.dirname(HERE), "static", "css", "tokens.css")).read_text(encoding="utf-8")
    for t in ("--success", "--warning", "--error", "--shadow-1", "--fs-title", "--sp-3"):
        assert tokens.count(t + ":") >= (3 if t in ("--success", "--warning", "--error") else 1), t


def test_porter_footers_and_folded_maps_v221():
    """v2.2.1: the Porter footers (steps 2-5) carry the "Apply will" slot, the
    step-3 stage maps are folded, the type scale is a set of tokens."""
    porter = HTML[HTML.index('id="porter-panel-2"'):HTML.index('id="porter-status"')]
    for n in (2, 3, 4, 5):
        assert f'id="oc-porter{n}"' in porter, n
    p3 = HTML[HTML.index('id="porter-panel-3"'):]
    assert p3.index('id="porter-maps-fold"') < p3.index('id="porter-fixture-map"')
    root = Path(os.path.dirname(HERE))
    tokens = (root / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    for t in ("--fs-micro", "--fs-small", "--fs-ui", "--fs-body", "--fs-lead", "--fs-section", "--fs-title"):
        assert t + ":" in tokens, t
    css = (root / "static" / "css" / "style.css").read_text(encoding="utf-8")
    assert not re.search(r"font-size:\s*(?:10\.5|11\.5|12\.5|13\.5)px", css)


def test_new_show_flow_v230():
    """v2.3: Fixtures open as the show, a guided New-show route, the Setlist's
    function list as a drawer, profiles that start a show and the step editor."""
    fx = HTML[HTML.index('id="scr-fixtures"'):HTML.index('id="scr-brightness"')]
    assert 'id="fix-btn-open"' in fx and 'fixOpenAsShow()' in fx
    js = (Path(os.path.dirname(HERE), "static", "js", "route.js")).read_text(encoding="utf-8")
    assert "\n  new: {" in js and "routeStart('new')" in HTML
    sl = HTML[HTML.index('id="scr-setlist"'):]
    assert 'id="sl-split"' in sl and 'id="btn-pool-toggle"' in sl and 'slTogglePool(false)' in sl
    css = (Path(os.path.dirname(HERE), "static", "css", "style.css")).read_text(encoding="utf-8")
    assert ".sl-fb-split.pool-closed .fn-pool-pane" in css
    for hook in ('id="sh-prof-start"', 'showEditProfile()', 'id="sh-prof-rig"', 'qsSaveRigProfile()'):
        assert hook in HTML, hook
