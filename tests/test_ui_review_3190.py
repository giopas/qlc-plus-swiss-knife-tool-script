"""The UI review of 3.19.0: what each finding changed stays changed.

The review looked at every tool rendered (1440 x 900 and 1024 x 700, dark, grey
and light) and listed thirteen findings.  These checks read the template, the
styles and the scripts; the rendered check is `tools/shots.py`.
"""
import os
import re
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
KIT = (ROOT / "static" / "css" / "kit.css").read_text(encoding="utf-8")


def _js(name):
    return (ROOT / "static" / "js" / name).read_text(encoding="utf-8")


def _button(id_):
    m = re.search(r'<button[^>]*\bid="%s"[^>]*>(.*?)</button>' % re.escape(id_), HTML, re.S)
    assert m, id_
    return m.group(0)


# 1 · the header keeps Open and Save on screen
def test_header_actions_never_shrink_and_save_has_a_short_label():
    save = _button("sb-save")
    assert 'class="ms-long"' in save and 'class="ms-short"' in save
    assert re.search(r"\.ms-actions\s*\{\s*flex:\s*none", CSS)
    assert re.search(r"@media \(max-width: 1280px\)\s*\{[^}]*\.ms-tl, \.ms-long \{ display: none; \}", CSS)
    assert 'aria-label="Undo"' in _button("sb-undo")


# 2 · the side menu gives its height to the tools
def test_settings_fold_holds_the_side_panel_rows():
    m = re.search(r'<details class="fp-settings" id="fp-settings">(.*?)</details>', HTML, re.S)
    assert m
    body = m.group(1)
    for id_ in ("fp-workspace", "lang-select", "upd-enabled", "fp-mcp", "fp-theme", "session-badge"):
        assert 'id="%s"' % id_ in body, id_
    assert 'id="sn-recent"' not in HTML                      # recent tools moved to Go to…
    assert "skRecentTools" in _js("palette.js") and "Recent tools" in _js("palette.js")


def test_theme_is_one_setting_not_a_button_per_tool():
    assert 'class="theme-btn"' not in HTML
    assert 'onclick="cycleTheme()"' in HTML                  # the Colours row under Settings
    assert "fp-theme-name" in _js("app.js")


# 4 · Workspace Doctor
def test_doctor_toggle_keeps_one_line_and_footer_has_room():
    assert re.search(r"\.doc-caret \{ width: auto; flex: none; white-space: nowrap;", CSS)
    foot = re.search(r'<section class="screen" id="scr-doctor">.*?<div class="out-footer">(.*?)</div>\s*</section>', HTML, re.S).group(1)
    assert "doctorCopyReport" not in foot and "showTravel" not in foot
    assert re.search(r"\.out-footer > \.btn-accent:last-child \{ margin-left: auto; \}", CSS)


# 5 · one footer shape: chip, outcome, main button that says why it waits
def test_song_builder_has_the_footer_of_the_other_tools():
    sec = re.search(r'<section class="screen" id="scr-songbuilder">(.*?)</section>', HTML, re.S).group(1)
    assert 'class="tool-foot"' not in sec
    assert re.search(r'<div class="out-footer">\s*<span class="out-note kit-chip kit-chip-apply"', sec)
    b = _button("sbd-build-btn")
    assert "disabled" in b and 'data-needs="Give the song a name in step 1."' in b
    assert "_sbdBuildState" in _js("songbuilder.js")


def test_main_buttons_wait_until_there_is_something_to_do():
    for id_, needs in (("vce-apply-btn", "Move, resize or recolour a widget first."),
                       ("cmp-run-btn", "Pick the other show first (Other show…).")):
        b = _button(id_)
        assert " disabled " in b and 'data-needs="%s"' % needs in b, id_
    assert "_vceSyncApply" in _js("vc_editor.js")
    assert "✓ Apply to the show" in _button("lb-go")


# 6 · selects follow the theme
def test_plain_selects_wear_the_theme():
    assert re.search(r"select:not\(\[class\]\) \{[^}]*background: var\(--surface-1\)", CSS)


# 7 · stage plots
def test_stage_labels_are_placed_and_cut_to_fit():
    js = _js("fixture.js")
    assert "function _placeLabel(" in js and "function _fitLabel(" in js
    assert "substring(0, 12)" not in _js("porter.js")


# 8 · one filled button per screen in the Setlist Manager
def test_setlist_assign_is_not_a_second_filled_button():
    assert "btn-accent" not in _button("btn-pool-assign")
    assert re.search(r"#btn-pool-toggle \{ background: transparent;", CSS)


# 9 · empty states with their next step
def test_empty_states_offer_the_next_step():
    assert 'id="porter-src-empty"' in HTML and "porterBrowseSrc()" in HTML
    wz = _js("wizard.js")
    assert "skEmpty(" in wz and "go('doctor')" in wz
    assert ".kit-empty-wide" in KIT


# 10, 13 · targets and labels
def test_icon_only_buttons_have_a_name():
    bad = []
    for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", HTML, re.S):
        attrs, inner = m.group(1), m.group(2)
        text = re.sub(r"<[^>]+>", "", re.sub(r"<svg.*?</svg>", "", inner, flags=re.S)).strip()
        if text in ("", "✕", "?", "↺", "−", "+") and "aria-label" not in attrs \
                and not re.search(r'id="(sb-changes|sb-doctor|update-badge)"', attrs):
            bad.append(HTML.count("\n", 0, m.start()) + 1)
    assert not bad, bad
    sb = _js("songbuilder.js")
    assert sb.count("aria-label=") >= 7                      # ⋯ ↑ ↓ ⧉ × and both ⇥


def test_small_targets_reach_24px():
    for sel in (r"\.sc-link \{ min-height: 24px;", r"\.btn-sm \{ min-height: 24px; \}", r"\.sbd-ibtn \{ min-width: 26px; min-height: 26px; \}"):
        assert re.search(sel, CSS), sel


# 3 · no text under 11 px from a bare <small>
def test_bare_small_keeps_the_floor():
    assert re.search(r"small \{ font-size: max\(var\(--fs-small\), \.85em\); \}", CSS)
