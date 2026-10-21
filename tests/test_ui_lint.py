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
