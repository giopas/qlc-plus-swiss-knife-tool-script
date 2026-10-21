"""The page kit (3.9.0 step 0, DESIGN_v2.md section 8): kit.css and skActionBar().

The kit is additive: it is loaded by the shell, defines only kit- classes, uses the
tokens as they are, and no screen uses it yet.  These checks keep it that way.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/css/kit.css").read_text(encoding="utf-8")
JS = (ROOT / "static/js/kit.js").read_text(encoding="utf-8")
HTML = (ROOT / "templates/index.html").read_text(encoding="utf-8")


def test_shell_loads_the_kit_after_tokens_and_style():
    css = [m.group(1) for m in re.finditer(r'href="/static/css/([\w.]+)\?v=\{\{ asset_v \}\}"', HTML)]
    assert css.index("tokens.css") < css.index("style.css") < css.index("kit.css")
    assert re.search(r'<script src="/static/js/kit\.js\?v=\{\{ asset_v \}\}"></script>', HTML)
    assert HTML.index("static/js/kit.js") < HTML.index("static/js/app.js")


def test_every_selector_is_a_kit_class():
    body = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    body = re.sub(r"@media[^{]*\{", "", body)                      # keep the rules, drop the wrapper
    selectors = [s for blk in re.findall(r"([^{}]+)\{", body) for s in blk.split(",")]
    for s in (x.strip() for x in selectors):
        if not s or s == ":root":
            continue
        assert re.search(r"\.kit-", s), s


def test_css_uses_tokens_not_literals():
    body = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body), "colours come from tokens.css"
    for px in re.findall(r"font-size:\s*(\d+)px", body):
        assert int(px) >= 11, "type floor is 11 px"
    assert "!important" not in body
    assert ":focus-visible" in body


def test_js_never_builds_html_from_text():
    assert "innerHTML" not in JS and "insertAdjacentHTML" not in JS and "document.write" not in JS
    assert "style.cssText" not in JS and ".style." not in JS, "no inline style: classes only"


def test_the_four_verbs_have_their_chips():
    for kind, text in (("apply", "Changes the show in progress"), ("new", "Writes a new file"),
                       ("export", "Does not change the show"), ("settings", "Saved in your settings")):
        assert re.search(rf"{kind}:\s*\{{\s*text: '{text}'", JS), kind


def test_a_disabled_primary_says_why():
    assert "data-why" in JS and "aria-live" in JS


def test_no_existing_screen_uses_the_kit_yet():
    """3.9.0 step 0 changes no existing screen; the Tablet screen is the kit's only user."""
    own = re.compile(r"(?<![\w-])kit-(head|toolbar|body|work|panel|actionbar|chip|summary|why|empty|done|seg|page|spacer|loading)")
    assert not own.search(re.sub(r'href="/static/css/kit\.css[^"]*"', "", HTML))
    api = re.compile(r"skActionBar|skSegmented|skEmpty|skDone|SK_CHIPS")
    for p in (ROOT / "static/js").glob("*.js"):
        if p.name != "kit.js":
            text = p.read_text(encoding="utf-8")
            assert not api.search(text) and not own.search(text), p.name
    assert not own.search((ROOT / "static/css/style.css").read_text(encoding="utf-8"))
