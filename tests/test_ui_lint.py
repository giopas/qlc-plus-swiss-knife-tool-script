"""Automatic checks on the look of the app (3.9.5, DESIGN_v2.md section 5).

The rules start with what stage A made true and grow with the later stages:

* no emoji used as an icon: the sprite (static/icons.svg) draws every icon, and
  no translation key starts with a picture;
* no literal font size below 11 px;
* no inline ``style`` in the shell (everything outside a tool's own screen) or
  in the page kit;
* every ``<symbol>`` a template or script asks for exists in the sprite;
* the button classes are the four kinds (btn-accent, btn-surface, btn-ghost,
  btn-danger), plus btn-overwrite for the Stage Monitor's *replace a page*.
"""
import glob
import json
import os
import re
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
KIT = (ROOT / "static" / "css" / "kit.css").read_text(encoding="utf-8")
SPRITE = (ROOT / "static" / "icons.svg").read_text(encoding="utf-8")
JS = {Path(f).name: Path(f).read_text(encoding="utf-8") for f in glob.glob(str(ROOT / "static" / "js" / "*.js"))}

# pictures, not the text signs (arrows, ✓ ✕ ⚠ ★ ⌘ ♂ ♀) the interface keeps
PICT = "[\U0001F000-\U0001FFFF⚙⚡⛔⏳✅⬇⬆⬛⬜➕✨⏩]"
# two messages the server sends (routes/*.py) still name a button by its old emoji
SERVER_SENT = {"No show open — open one first (📂 Open…).", "Open a show first (📂 Open… top right)."}


def _shell(html):
    """The page without the ``<section class="screen">`` blocks."""
    return re.sub(r'<section class="screen.*?</section>', "", html, flags=re.S)


def test_no_emoji_in_the_template_and_scripts():
    bad = [("index.html", m.group()) for m in re.finditer(PICT, HTML)]
    for name, text in JS.items():
        bad += [(name, m.group()) for m in re.finditer(PICT, text)]
    assert not bad, bad[:10]


def test_no_translation_key_starts_with_an_emoji():
    for f in glob.glob(str(ROOT / "static" / "i18n" / "*.json")):
        keys = [k for k in json.load(open(f, encoding="utf-8")) if re.match(r"\s*" + PICT, k) and k not in SERVER_SENT]
        assert not keys, (os.path.basename(f), keys[:5])


def test_no_literal_font_size_below_11px():
    for name, text in (("style.css", CSS), ("kit.css", KIT)):
        for m in re.finditer(r"font-size:\s*([0-9.]+)px", text):
            assert float(m.group(1)) >= 11, "%s:%d %s" % (name, text.count("\n", 0, m.start()) + 1, m.group(0))


def test_no_inline_style_in_the_shell_and_the_kit():
    left = re.findall(r'<[^>]*\sstyle="[^"]*"', _shell(HTML))
    assert not left, left[:5]
    assert "style=" not in KIT
    kit_js = JS["kit.js"]
    assert not re.search(r"""style=["']""", kit_js)


def test_every_icon_asked_for_is_in_the_sprite():
    have = set(re.findall(r'<symbol id="([\w-]+)"', SPRITE))
    asked = set(re.findall(r"icons\.svg#([\w-]+)", HTML))
    for text in JS.values():
        asked |= set(re.findall(r"icons\.svg#([\w-]+)", text))
    maps = re.findall(r"const (?:_FN_)?TYPE_ICON = \{(.*?)\};", JS["app.js"] + JS["setlist.js"], flags=re.S)
    for body in maps:
        asked |= set(re.findall(r":\s*'([\w-]+)'", body))
    asked |= set(re.findall(r"icon: '([\w-]+)'", JS["showbook.js"]))
    assert not asked - have, sorted(asked - have)


def test_button_classes_are_the_four_kinds():
    used = set(re.findall(r"\bbtn-(accent|surface|ghost|danger|overwrite|primary|secondary|success|green|red)\b", HTML))
    for text in JS.values():
        used |= set(re.findall(r"\bbtn-(accent|surface|ghost|danger|overwrite|primary|secondary|success|green|red)\b", text))
    assert not used & {"primary", "secondary", "success", "green", "red"}, used


def test_inter_is_bundled_with_its_licence():
    fonts = ROOT / "static" / "fonts"
    tokens = (ROOT / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    for name in ("inter-latin-wght-normal.woff2", "inter-latin-ext-wght-normal.woff2"):
        assert (fonts / name).stat().st_size > 10000, name
        assert "/static/fonts/" + name in tokens
    assert "SIL OPEN FONT LICENSE" in (fonts / "Inter-OFL.txt").read_text(encoding="utf-8").upper()
    assert '--font: "Inter"' in tokens
    assert "http" not in re.sub(r"/\*.*?\*/", "", tokens, flags=re.S).split("--font:")[0].split("@font-face")[1]


# ── stage C: the footers ────────────────────────────────────────────────────

CHIP_TEXT = {"apply": "Changes the show in progress", "new": "Writes a new file", "export": "Does not change the show",
             "settings": "Saved in your settings", "beside": "Saved next to the show"}


def _footers():
    return re.findall(r'<div class="[^"]*out-footer[^"]*"[^>]*>.*?\n\s*</div>(?=\n)', HTML, flags=re.S)


def test_footer_chips_use_the_words_of_the_kit():
    kit = JS["kit.js"]
    for verb, text in CHIP_TEXT.items():
        assert "'%s'" % text in kit, (verb, text)
    seen = 0
    for f in _footers():
        m = re.search(r'<span class="out-note kit-chip kit-chip-(\w+)" data-verb="(\w+)"[^>]*>([^<]*)</span>', f)
        if not m:
            continue
        seen += 1
        verb = m.group(2)
        assert verb in CHIP_TEXT, verb
        assert m.group(3).strip() == CHIP_TEXT[verb] or (verb == "beside" and m.group(3).strip().startswith("Reads the show")), m.group(3)
    assert seen >= 20, seen


def test_a_footer_that_can_be_disabled_says_why():
    """Every main button that starts disabled has its reason in words (stage C)."""
    for f in _footers():
        for b in re.findall(r'<button[^>]*\bbtn-accent\b[^>]*>', f):
            if re.search(r"\sdisabled(?:\s|>|=)", b):
                assert "data-needs=" in b, b[:120]


def test_every_footer_has_one_main_button_at_most():
    for f in _footers():
        assert len(re.findall(r'<button[^>]*\bbtn-accent\b', f)) <= 2, f[:80]   # qs-btn-next / qs-btn-export swap


def test_the_apply_verbs_say_what_happens_in_one_line():
    css = CSS
    assert re.search(r"\.out-footer \.out-note\s*\{[^}]*white-space:\s*nowrap", css)


def test_a_step_added_to_the_history_is_announced():
    show = JS["show.js"]
    assert "_skAnnounce" in show and "skDone(" in show and "sh-new" in show
    assert "showUndo(" in show.split("_skAnnounce", 1)[1][:1800]


# ── stage D: key screens ────────────────────────────────────────────────────

def test_the_doctor_counts_kinds_and_filters():
    doc = JS["doctor.js"]
    assert "doctorFilter" in doc and "kinds of warning" in doc and 'aria-pressed' in doc
    assert 'id="doc-show-info"' not in HTML


def test_the_setlist_rail_folds_and_songs_carry_a_match_pill():
    assert len(re.findall(r'<details class="fb-fold">', HTML)) == 2
    sl = JS["setlist.js"]
    assert "_slMatchKind" in sl and "fb-pill-" in sl and "badge-${" in sl


def test_the_porter_remembers_whether_both_stages_were_shown():
    assert "sk-porter-both-stages" in JS["porter.js"]


def test_no_inline_font_size_below_11px_in_the_template():
    assert not re.findall(r"font-size:\s*(?:[0-9]|10)(?:\.\d+)?px", HTML)


# ── stage E: the words in the app (DESIGN_v2.md section 11.1) ───────────────

def _words(s):
    return len(re.sub(r"<[^>]+>", "", s).split())


def test_every_tool_header_is_one_short_outcome_sentence():
    heads = re.findall(r'<h2>[^<]*</h2><div class="p-desc">(.*?)</div>', HTML, re.S)
    assert len(heads) >= 19
    for h in heads:
        text = re.sub(r"\s+", " ", h).strip()
        assert _words(text) <= 20, text
        assert " — " not in text and " – " not in text, text


def test_tooltips_are_one_sentence_of_at_most_20_words():
    bad = [t for t in re.findall(r'data-tooltip="([^"]*)"', HTML) if _words(t) > 20]
    assert not bad, bad[:3]


def test_every_doctor_rule_has_its_plain_meaning():
    import sys
    sys.path.insert(0, str(ROOT))
    from core.doctor.report import TITLES
    plain = set(re.findall(r"^  ([DI]\d{3}): '", JS["doctor.js"], re.M))
    assert plain == set(TITLES), sorted(plain ^ set(TITLES))


def test_the_stage_e_sentences_are_translated_in_all_seven_languages():
    heads = [re.sub(r"\s+", " ", h).replace("&amp;", "&").strip()
             for h in re.findall(r'<h2>[^<]*</h2><div class="p-desc">(.*?)</div>', HTML, re.S)]
    plain = re.findall(r"^  [DI]\d{3}: '(.*)',$", JS["doctor.js"], re.M)
    for f in glob.glob(str(ROOT / "static" / "i18n" / "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        miss = [s for s in heads + plain if s not in d and "Tablet" not in s]
        assert not miss, (os.path.basename(f), miss[:3])


# ── the footer summary chips are translated (3.9.5) ─────────────────────────

def test_summary_chips_use_skplural_not_english_suffixes():
    for name in ("porter.js", "reducer.js", "brightness.js", "setlist.js"):
        bad = [l.strip() for l in JS[name].splitlines()
               if ("chips.push" in l or "setOutcome(" in l) and re.search(r"\$\{[^}]*\?\s*'(?:s|es)'\s*:\s*''\}", l)]
        assert not bad, (name, bad[:2])


def test_every_skplural_pair_is_translated_in_all_seven_languages():
    keys = set()
    for text in JS.values():
        for m in re.finditer(r"skPlural\([^,]+,\s*'([^']+)',\s*'([^']+)'", text):
            keys.update(m.groups())
    assert len(keys) >= 40, len(keys)
    for f in glob.glob(str(ROOT / "static" / "i18n" / "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        miss = sorted(k for k in keys if k not in d)
        assert not miss, (os.path.basename(f), miss[:4])
