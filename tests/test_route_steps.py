"""3.4.0: one way forward in a guided route (claude/UX_REVIEW_STEPS.md, option C).

The route strip only shows where you are; the footer's route button is the one
way forward.  These checks keep the pieces that make that work in place."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTE_JS = (ROOT / 'static/js/route.js').read_text(encoding='utf-8')
INDEX = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
LANGS = ['it', 'fr', 'de', 'es', 'pt', 'ja', 'zh']


def _route_tools():
    return sorted(set(re.findall(r"\{ tool: '(\w+)'", ROUTE_JS)))


def _screen(tool):
    m = re.search(r'<section class="screen[^"]*" id="scr-%s">' % tool, INDEX)
    assert m, tool
    end = INDEX.find('<section class="screen', m.end())
    return INDEX[m.start():end if end > 0 else len(INDEX)]


def test_every_route_tool_has_a_footer_for_the_route_button():
    for tool in _route_tools():
        assert 'out-footer' in _screen(tool), f'{tool}: the route button goes in its .out-footer'


def test_the_strip_has_no_second_forward_button():
    assert 'Done, next' not in ROUTE_JS.split('function routeRender')[1].split('function routeCards')[0]
    assert 'routeForward' in ROUTE_JS and 'routeSkip' in ROUTE_JS


def test_tools_with_steps_use_the_shared_stepper():
    assert 'id="route-sub"' in INDEX
    for tool in ('quickstart', 'porter'):
        assert f'class="tool-stepper" data-tool="{tool}"' in INDEX
        js = (ROOT / f'static/js/{tool}.js').read_text(encoding='utf-8')
        assert f"toolPosition('{tool}'" in js
    assert 'qs-dot-1' not in INDEX and 'porter-step-1' not in INDEX


def test_quick_start_finishes_its_route_step():
    js = (ROOT / 'static/js/quickstart.js').read_text(encoding='utf-8')
    assert 'finish:' in js and 'qsOpenAsShow' in js.split('finish:')[1][:600]


def test_the_effect_panel_has_one_way_back():
    js = (ROOT / 'static/js/looks.js').read_text(encoding='utf-8')
    assert "'Done'" not in js
    assert 'Keep these settings ›' in js and "modal: true" in js


def test_the_new_words_are_translated():
    strings = re.findall(r"_rTr\('([^']+)'", ROUTE_JS) + ['Skip this step', 'Not needed? Skip it',
                                                           'Keep these settings ›', 'Nothing is added to the show yet.']
    for lang in LANGS:
        d = json.loads((ROOT / f'static/i18n/{lang}.json').read_text(encoding='utf-8'))
        missing = [s for s in strings if s not in d]
        assert not missing, (lang, missing)
