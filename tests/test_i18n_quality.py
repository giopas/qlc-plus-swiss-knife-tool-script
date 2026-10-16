"""3.4.0: the translations of the newer screens, checked the way the review found them wanting.

Each check is a mistake that was really in the files: a Look Builder word shown in
English, a Doctor fix with no translation, a one-word pattern that left half a
sentence in English, "il show" in Italian, Brazilian words in the European
Portuguese file, "la show" in Spanish, and an escape helper that broke tooltips
with quotes in them."""
import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("it", "fr", "de", "es", "pt", "ja", "zh")


def _load(lang):
    return json.loads((ROOT / "static" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))


D = {lang: _load(lang) for lang in LANGS}


@pytest.mark.parametrize("lang", LANGS)
def test_look_builder_roles_places_and_groups(lang):
    from core.look_families import ROLES
    for word in list(ROLES) + ["Centre", "Audience", "All fixtures"]:
        assert D[lang].get("lb|" + word), f"{lang}: lb|{word}"


@pytest.mark.parametrize("lang", LANGS)
def test_doctor_fix_hints_are_translated(lang):
    src = (ROOT / "core" / "doctor" / "fixes.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "fix_hint")
    hints = {n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and " " in n.value and not n.value.startswith("One line") and n.value != "no PANIC"}
    assert len(hints) >= 15
    missing = sorted(h for h in hints if h not in D[lang])
    assert not missing, f"{lang}: {missing[:3]}"


REPORT = [
    "look {0} '{1}' — {2} fixture(s), {3}",
    "look {0} '{1}' — {2} fixture(s), {3}, aimed at {4}",
    "chaser {0} '{1}' — {2}, {3} step(s), {4} scene(s), {5} ms, fade {6} ms",
    "movement effect {0} '{1}' — {2} on {3} moving head(s), rides on the aim of the look playing",
    "VC: page '{0}' with a {1}-page frame, one page per group",
    "VC: page '{0}': intensity slider, {1} look(s), {2} effect(s)",
    "✓ Applied to the show — step {0}: {1}.",
    "Doctor: {0} errors, {1} warnings.",
    "✓ Fix {0} selected in the show",
    "The meshes and fixtures on the stage; click one to edit it",
]


@pytest.mark.parametrize("lang", LANGS)
def test_reports_and_messages_of_the_new_tools(lang):
    for k in REPORT:
        assert D[lang].get(k), f"{lang}: {k}"


def test_italian_says_lo_show():
    bad = [v for v in D["it"].values() if re.search(r"\b(il|al|del|nel|dal|sul|un) [Ss]how\b", v)]
    assert not bad, bad[:3]


def test_spanish_show_is_masculine():
    bad = [v for v in D["es"].values() if re.search(r"\b(la|una|esta|otra|de la) show\b", v, re.I)]
    assert not bad, bad[:3]


def test_portuguese_stays_european():
    bad = [v for v in D["pt"].values() if re.search(r"\b(arquivo(?! (CSV|ZIP))|Salvar|você|roteiro|Pular)\b", v)]
    assert not bad, bad[:3]


def test_route_words_match_the_route_titles():
    """The route strip and its footer use the word the route titles use."""
    assert "Weg" in D["de"]["Finish the route"] and "Weg" in D["de"]["▶ Route: start a new show"]
    assert "流程" in D["zh"]["Finish the route"] and "流程" in D["zh"]["▶ Route: start a new show"]
    assert "percurso" in D["pt"]["Finish the route"]


def test_the_global_escape_helper_is_safe_in_attributes():
    """Every tool's _esc is one global (the last script loaded wins): it must escape quotes."""
    js = (ROOT / "static" / "js" / "quickstart.js").read_text(encoding="utf-8")
    body = js[js.index("function _esc(s)"):]
    body = body[:body.index("\n}") + 2]
    assert "&quot;" in body


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_a_one_word_pattern_never_half_translates_a_sentence():
    """'{0} scene{1}' is meant for '3 scenes', not for 'merge it into its scene'."""
    engine = (ROOT / "static" / "js" / "i18n.js").read_text(encoding="utf-8")
    dict_ = {"{0} scene{1}": "{0} シーン", "Next: {0} →": "次へ：{0} →", "Function {0} '{1}'": "ファンクション {0} '{1}'"}
    script = """
    global.window = { alert(){}, confirm(){}, prompt(){} };
    global.localStorage = { getItem: () => 'ja', setItem(){} };
    global.document = { readyState: 'complete', getElementById: () => null,
      dispatchEvent(){}, createTreeWalker: () => ({ nextNode: () => null }), body: {}, documentElement: {} };
    global.MutationObserver = class { observe(){} };
    global.NodeFilter = { SHOW_ELEMENT: 1, SHOW_TEXT: 4 };
    global.CustomEvent = class { constructor(n){ this.type = n; } };
    global.XMLHttpRequest = class { open(){} send(){ this.status = 200; this.responseText = JSON.stringify(%s); } };
    %s
    I18N.init();
    console.log(JSON.stringify([t('3 scenes'), t('merge it into its scene'), t('Next: Placement →'), t("Function 7 '🚨 PANIC RESET (kill auto modes)'")]));
    """ % (json.dumps(dict_), engine)
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr[-500:]
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got == ["3 シーン", "merge it into its scene", "次へ：Placement →",
                   "ファンクション 7 '🚨 PANIC RESET (kill auto modes)'"]
