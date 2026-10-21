"""Song cards, the Next song banner and role views of the Tablet page (3.9.0)."""
import json
import re

import pytest

from core import stage_monitor as sm
from tests.test_stage_monitor import _client, _inlined, _small

CARD = {"tuning": "Drop D", "starts": "Drums, 4 bars", "note": "Capo 2", "bpm": 128,
        "players": [{"who": "Guitar", "note": "delay on, boost off"}]}


def _cfg_with(cards):
    """List 21 ('Set one': Intro, Song A, Song B) with a card on some steps: {index: card}."""
    return {"lists": [{"id": "21", "label": "", "mode": "read",
                       "steps": {str(i): {"card": c} for i, c in cards.items()}}]}


def test_a_card_keeps_only_what_is_set_and_checks_it():
    assert sm.clean_card({}) == {} and sm.clean_card(None) == {} and sm.clean_card("x") == {}
    c = sm.clean_card({"tuning": "  Drop D ", "bpm": "128.4", "junk": 1, "note": "",
                       "players": [{"who": "Guitar", "note": "delay"}, {}, {"who": "", "note": ""}, "x"]})
    assert c == {"tuning": "Drop D", "bpm": 128, "players": [{"who": "Guitar", "note": "delay"}]}
    assert "bpm" not in sm.clean_card({"bpm": 5}) and "bpm" not in sm.clean_card({"bpm": 900})
    assert "bpm" not in sm.clean_card({"bpm": "fast"})
    assert len(sm.clean_card({"players": [{"who": str(i)} for i in range(20)]})["players"]) == sm.MAX_PLAYERS
    assert len(sm.clean_card({"note": "x" * 999})["note"]) == 200


def test_the_tempo_in_a_step_name():
    assert sm.tempo_from_name("Song 34 · 128 BPM") == 128
    assert sm.tempo_from_name("Song | 96bpm") == 96
    assert sm.tempo_from_name("99 Luftballons") is None          # a title is not a tempo
    assert sm.tempo_from_name("Song · 900 BPM") is None
    assert sm.tempo_from_name("") is None


def test_cards_live_in_the_config_with_the_steps():
    cfg = sm.clean_config(_cfg_with({1: CARD}))
    assert cfg["lists"][0]["steps"]["1"]["card"] == CARD
    assert sm.clean_config(json.loads(json.dumps(cfg))) == cfg            # survives the sidecar file
    assert sm.clean_config(_cfg_with({1: {"junk": 1}}))["lists"][0]["steps"] == {}   # an empty card is no card


def test_a_card_of_a_step_that_is_gone_is_dropped():
    cfg = _cfg_with({1: CARD, 9: CARD})
    kept = sm.reconcile(cfg, sm.cuelists(_small()))["config"]["lists"][0]["steps"]
    assert list(kept) == ["1"]


def test_the_page_gets_cards_and_a_tuning_change():
    cards = {0: {"tuning": "E standard"}, 1: {"tuning": "E standard", "bpm": 96}, 2: {"tuning": "Drop D"}}
    d = sm.page_data(_cfg_with(cards), sm.cuelists(_small()))
    steps = d["lists"][0]["steps"]
    assert "tc" not in steps[0] and "tc" not in steps[1]
    assert steps[2]["tc"] == {"from": "E standard", "to": "Drop D"}
    assert steps[1]["card"]["bpm"] == 96


def test_a_tuning_change_skips_hidden_songs_and_songs_without_a_tuning():
    cfg = _cfg_with({0: {"tuning": "E standard"}, 1: {"note": "no tuning here"}, 2: {"tuning": "E standard"}})
    steps = sm.page_data(cfg, sm.cuelists(_small()))["lists"][0]["steps"]
    assert not any("tc" in s for s in steps)                   # E to E: no change, whatever sits between
    cfg["lists"][0]["steps"]["1"]["card"] = {"tuning": "Drop D"}
    cfg["lists"][0]["steps"]["1"]["hide"] = True               # hidden: not played, not a change
    steps = sm.page_data(cfg, sm.cuelists(_small()))["lists"][0]["steps"]
    assert not any("tc" in s for s in steps)


def test_the_tempo_of_a_step_name_reaches_the_page():
    lists = sm.cuelists(_small())
    lists[0]["steps"][0]["name"] = "Intro · 120 BPM"
    steps = sm.page_data(_cfg_with({}), lists)["lists"][0]["steps"]
    assert steps[0]["card"] == {"bpm": 120}
    own = sm.page_data(_cfg_with({0: {"bpm": 100}}), lists)["lists"][0]["steps"]
    assert own[0]["card"]["bpm"] == 100                        # the card's own tempo wins


def test_a_show_without_cards_builds_the_same_page_data_as_before():
    d = sm.page_data(_cfg_with({}), sm.cuelists(_small()))
    assert all(set(s) == {"i", "name", "note", "hide"} for s in d["lists"][0]["steps"])


def test_the_page_has_its_roles_banner_and_stage_rules():
    html = open(sm.PAGE_TEMPLATE, encoding="utf-8").read()
    assert "CFG.views" in html                                          # the views come from the settings
    assert {v["layout"] for v in sm.DEFAULT_VIEWS} == set(sm.ROLES)     # the three layouts come with the page
    assert "if (ROLE) document.body.dataset.role = ROLE" in html       # data-role="" would match the role CSS
    assert 'id="nextup"' in html and 'id="cardpane"' in html and "▲ ${esc(T(\"TUNING CHANGE\"))}" in html
    assert "scroll-behavior: smooth" not in html.replace("/* no smooth scrolling", "")        # no motion on the stage
    assert "min-height: 56px" in html                                                          # 56 px targets
    assert 'ROLE !== "vocals" && ROLE !== "band"' in html                                      # only the pedal player controls
    assert "https://" not in html.replace("http://", "") and "src=\"http" not in html          # offline


def _lum(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _themes(html):
    """{theme: {variable: hex}} from the page's :root blocks, later blocks over earlier ones."""
    css = html[html.index("<style>"):html.index("</style>")]
    themes = {t: {} for t in ("dark", "contrast", "black", "dim")}
    for sel, body in re.findall(r"([^{}]*:root[^{}]*)\{([^}]*)\}", css):
        named = re.findall(r'data-theme="(\w+)"', sel)
        vals = {k: ("#" + "".join(ch * 2 for ch in h) if len(h) == 3 else "#" + h)
                for k, h in re.findall(r"--([\w-]+):\s*#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", body)}
        for t in (named or ["dark"]):
            themes[t].update(vals)
    # contrast and black start from the dark theme's values, dim from black's
    for t, parent in (("contrast", "dark"), ("black", "dark"), ("dim", "black")):
        themes[t] = {**themes[parent], **themes[t]}
    return themes


def test_card_colours_pass_the_stage_contrast_rules():
    """Tuning change 7:1, card text 4.5:1, on the page's background in every theme."""
    for name, v in _themes(open(sm.PAGE_TEMPLATE, encoding="utf-8").read()).items():
        assert _ratio(v["tune"], v["bg"]) >= 7, (name, "tuning change", _ratio(v["tune"], v["bg"]))
        assert _ratio(v["tune"], v["card-bg"]) >= 7, (name, "tuning change on the card")
        assert _ratio(v["card-fg"], v["card-bg"]) >= 4.5, (name, "card text", _ratio(v["card-fg"], v["card-bg"]))


def test_routes_keep_cards_in_the_settings_file(tmp_path):
    c, p = _client(tmp_path, "Festival_14fix.qxw")
    d = c.get("/api/stagemon/lists").get_json()
    cfg = d["config"]
    cfg["lists"][0]["steps"]["0"] = {"card": CARD, "label": "Opener"}
    assert c.post("/api/stagemon/config", json={"config": cfg}).get_json()["saved"]
    side = json.loads((tmp_path / "Festival_14fix.stage.json").read_text(encoding="utf-8"))
    assert side["lists"][0]["steps"]["0"]["card"] == CARD
    again = c.get("/api/stagemon/lists").get_json()["config"]
    assert again["lists"][0]["steps"]["0"]["card"] == CARD
    html = c.post("/api/stagemon/preview", json={"config": again}) and c.get("/api/stagemon/preview").get_data(as_text=True)
    page = _inlined(html)
    assert page["lists"][0]["steps"][0]["card"]["tuning"] == "Drop D"
