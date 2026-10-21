"""Views by role of your own, and song cards in the Simple page (3.9.0)."""
import json
import re

import pytest

from core import setlist_io
from core import stage_monitor as sm
from tests.test_stage_monitor import _client, _inlined, _small


def test_a_view_is_cleaned():
    v = sm.clean_views([
        {"label": "  Drummer & FX ", "layout": "nope", "fields": ["note", "tuning", "junk"], "who": " Drums "},
        {"id": "Drummer & FX", "label": "again"},        # the same address: dropped
        {"id": "", "label": ""}, "x", None,               # nothing to name it by: dropped
        {"id": "lead", "label": "Lead", "layout": "commander", "fields": [], "who": "G" * 99},
    ])
    assert [x["id"] for x in v] == ["drummer-fx", "lead"]
    assert v[0] == {"id": "drummer-fx", "label": "Drummer & FX", "layout": "band",
                    "fields": ["tuning", "note"], "who": "Drums"}      # fields in card order, bad layout falls back
    assert v[1]["fields"] == [] and len(v[1]["who"]) == 30 and v[1]["layout"] == "commander"
    assert len(sm.clean_views([{"label": f"v{i}"} for i in range(40)])) == sm.MAX_VIEWS
    assert sm.clean_views("x") == [] and sm.clean_views(None) == []


def test_the_three_views_come_with_the_page_until_you_change_them():
    assert [v["id"] for v in sm.views_of({})] == ["commander", "band", "vocals"]
    assert sm.views_of({"views": []}) == []                    # none on purpose
    assert "views" not in sm.clean_config({})                  # an old settings file is left as it is
    assert sm.clean_config({"views": []})["views"] == []
    mine = [{"id": "keys", "label": "Keys", "layout": "band", "fields": ["tuning"], "who": ""}]
    cfg = sm.clean_config({"views": mine})
    assert cfg["views"] == mine and sm.views_of(cfg) == mine


def test_the_page_gets_the_views():
    cfg = {"lists": [{"id": "21", "label": "", "mode": "read", "steps": {}}],
           "views": [{"id": "keys", "label": "Keys", "layout": "vocals", "fields": ["bpm"], "who": "keys"}]}
    d = sm.page_data(cfg, sm.cuelists(_small()))
    assert d["views"][0]["id"] == "keys" and d["views"][0]["fields"] == ["bpm"]
    assert [v["id"] for v in sm.page_data({"lists": cfg["lists"]}, sm.cuelists(_small()))["views"]] == ["commander", "band", "vocals"]


def test_songs_are_matched_to_steps():
    steps = [{"name": "Intro"}, {"name": "Song A · 128 BPM"}, {"name": "Song B"}]
    got = sm.match_steps([["song a", ""], ["Song B", "x"], ["Other", "Intro"]], steps)
    assert [g["name"] if g else None for g in got] == ["Song A · 128 BPM", "Song B", "Intro"]
    assert sm.match_steps([["x"], ["y"], ["z"]], steps) == steps            # no name fits, same length: by position
    assert sm.match_steps([["x"], ["y"]], steps) == [None, None]            # no name fits, other length: no guess
    twice = sm.match_steps([["A"], ["A"]], [{"name": "A"}, {"name": "A"}])
    assert twice[0] is not twice[1]                                         # each step once


SETS = [{"name": "Set <1>", "songs": [
    {"name": "Song A", "note": "", "card": {"tuning": "Drop D", "bpm": 120, "players": [{"who": "Guitar", "note": "Delay on"}]},
     "tc": {"from": "E standard", "to": "Drop D"}},
    {"name": "Song B", "note": ""}]}]
VIEWS = [{"id": "vocals", "label": "Vocals", "layout": "vocals", "fields": ["bpm", "note"], "who": ""}]


def test_the_simple_page_folds_the_card_under_the_song():
    page = setlist_io.tablet_page("T", SETS, views=VIEWS)
    assert page.count('class="hascard"') == 1 and page.count('class="cbtn"') == 1       # only the song with a card
    assert 'data-f="tuning"' in page and 'data-f="players" data-who="Guitar"' in page
    assert "TUNING CHANGE E standard → Drop D" in page                                  # the words come first
    assert 'id="view"' in page and '<option value="vocals">Vocals</option>' in page
    assert json.loads(re.search(r'id="views">(.*?)</script>', page, re.S).group(1)) == VIEWS


def test_no_cards_means_the_simple_page_is_as_before():
    plain = [{"name": "S", "songs": [{"name": "A", "note": ""}]}]
    page = setlist_io.tablet_page("T", plain, views=VIEWS)
    assert 'class="hascard"' not in page and 'id="view"' not in page and 'id="cards"' not in page
    assert json.loads(re.search(r'id="views">(.*?)</script>', page, re.S).group(1)) == []      # a view means nothing without a card


def test_a_card_cannot_break_out_of_the_page():
    bad = [{"name": "S", "songs": [{"name": "A", "note": "", "card": {"note": "</script><b>x</b>", "tuning": '"><i>'}}]}]
    page = setlist_io.tablet_page("T", bad, views=[{"id": "x", "label": "</script>", "fields": [], "who": ""}])
    assert "<b>x</b>" not in page and "<i>" not in page
    assert page.count("</script>") == 2                        # the two of the page itself, none from the data


def test_the_screen_and_the_simple_page_have_no_stray_markup():
    js = open("static/js/stagemon.js", encoding="utf-8").read()
    assert "stagemonView(" in js and "_smViews().map(v =>" in js        # role links follow your views
    page = open("core/setlist_io.py", encoding="utf-8").read()
    assert "innerHTML" not in page.split("_JS")[1]                       # the page's script writes no markup


def test_route_puts_the_cards_on_the_simple_page(tmp_path):
    from core import workspace as ws
    c, _p = _client(tmp_path, "Festival_14fix.qxw")
    for slot, names in (("4001", ("Song 34", "Song 30")), ("4101", ("Song 37",))):
        ws.set_slot_details(slot, [{"txt_name": f"My {n}", "qxw_id": "", "qxw_name": n, "in": "0", "hold": "4294967294", "out": "0"}
                                   for n in names])
    cfg = c.get("/api/stagemon/lists").get_json()["config"]
    cfg["lists"] = [{"id": "4001", "label": "", "mode": "read", "steps": {
        "2": {"card": {"tuning": "Drop D", "bpm": 120}}, "3": {"card": {"tuning": "E standard"}}}}]
    cfg["views"] = [{"id": "keys", "label": "Keys", "layout": "band", "fields": ["bpm"], "who": ""}]
    assert c.post("/api/stagemon/config", json={"config": cfg}).get_json()["saved"]
    plain = c.post("/api/setlist/tablet", json={"title": "T"}).get_data(as_text=True)
    assert 'class="hascard"' not in plain                                   # cards only when asked for
    page = c.post("/api/setlist/tablet", json={"title": "T", "cards": True}).get_data(as_text=True)
    assert page.count('class="hascard"') == 2 and "Drop D" in page
    assert "TUNING CHANGE Drop D → E standard" in page
    assert '<option value="keys">Keys</option>' in page
    other = c.post("/api/setlist/tablet", json={"title": "T", "cards": True, "slots": ["4101"]}).get_data(as_text=True)
    assert 'class="hascard"' not in other                                   # another cue list has no cards

