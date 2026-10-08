"""Localisation (v2.7.0): the interface in English, Italian and French."""
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import i18n_extract as ex  # noqa: E402

LANGS = ("it", "fr", "de", "es", "pt", "ja", "zh")
_PH = re.compile(r"\{\d+\}")


def _load(lang):
    with open(os.path.join(ROOT, "static", "i18n", f"{lang}.json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("lang", LANGS)
def test_file_is_valid_and_named(lang):
    d = _load(lang)
    assert d["_language"]
    assert len(d) > 2000


@pytest.mark.parametrize("lang", LANGS)
def test_no_empty_values(lang):
    bad = [k for k, v in _load(lang).items() if not isinstance(v, str) or not v.strip()]
    assert not bad, bad[:5]


@pytest.mark.parametrize("lang", LANGS)
def test_translation_keeps_the_placeholders(lang):
    """A translation may reorder {0} {1} but never invent one (it would show as nothing)."""
    bad = []
    for k, v in _load(lang).items():
        if k.startswith("_"):
            continue
        if not set(_PH.findall(v)) <= set(_PH.findall(k)):
            bad.append(k)
    assert not bad, bad[:5]


@pytest.mark.parametrize("lang", LANGS)
def test_a_pattern_is_not_only_parts(lang):
    """'{0}' alone would match every string on the page."""
    for k in _load(lang):
        if _PH.search(k):
            assert _PH.sub("", k).strip(), k


@pytest.mark.parametrize("lang", LANGS)
def test_static_page_is_mostly_translated(lang):
    d = _load(lang)
    html = ex.html_strings()
    assert html
    have = sum(1 for k in html if d.get(k) or k in d)
    assert have / len(html) >= 0.85, f"{have}/{len(html)} of the page text has a {lang} entry"


def test_extractor_runs():
    assert ex.main(["--keys"]) == 0
    assert len(ex.all_keys()) > 2000


def test_the_page_loads_the_engine_before_the_app():
    with open(os.path.join(ROOT, "templates", "index.html"), encoding="utf-8") as f:
        html = f.read()
    assert "lang-select" in html
    assert html.index("i18n.js") < html.index("js/app.js")
    for code in ("en",) + LANGS:
        assert f'<option value="{code}"' in html or code in open(
            os.path.join(ROOT, "static", "js", "i18n.js"), encoding="utf-8").read()
