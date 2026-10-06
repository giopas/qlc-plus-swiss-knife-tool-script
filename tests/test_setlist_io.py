"""v2.6.0 — setlist import and the tablet page."""
import app
from core import setlist_io as sio, workspace


def names(res, i=0):
    return [s["txt_name"] for s in res["sets"][i]["songs"]]


def test_plain_and_numbered():
    t = "1. Intro\n2) Smoke on the Water\n03 - Whole Lotta Love\n\n# a comment\n- Back in Black\n99 Luftballons\n1999\n"
    r = sio.parse(t)
    assert names(r) == ["Intro", "Smoke on the Water", "Whole Lotta Love", "Back in Black", "99 Luftballons", "1999"]
    assert r["sets"][0]["songs"][0]["hold"] == sio.HOLD_INFINITE and r["format"] == "list"


def test_set_breaks_and_song_titles_that_look_like_them():
    t = "--- Set 1 ---\nSong A\nSong B\n--- Set 2 ---\nSong C\nEncore\nSet Fire to the Rain\nBreak on Through\n"
    r = sio.parse(t)
    assert [s["name"] for s in r["sets"]] == ["Set 1", "Set 2", "Encore"]
    assert names(r, 2) == ["Set Fire to the Rain", "Break on Through"]   # not set breaks
    assert any("3 sets" in n for n in r["notes"])


def test_csv_with_header_set_and_times():
    t = "Song;Set;Fade in;Hold;Fade out\nOne;A;1;3:30;2\nTwo;A;;;\nThree;B;0,5;45;0\n"
    r = sio.parse(t, "show.csv")
    assert [s["name"] for s in r["sets"]] == ["A", "B"] and r["format"] == "table"
    one = r["sets"][0]["songs"][0]
    assert (one["in"], one["hold"], one["out"]) == ("1000", "210000", "2000")
    two = r["sets"][0]["songs"][1]
    assert two["hold"] == sio.HOLD_INFINITE and two["in"] == "0"
    assert r["sets"][1]["songs"][0]["in"] == "500" and r["sets"][1]["songs"][0]["hold"] == "45000"


def test_csv_without_header_and_tab():
    r = sio.parse("1\tOne\n2\tTwo\n")
    assert names(r) == ["One", "Two"]
    r = sio.parse("Hello, Goodbye\nCome Together, Right Now\n")        # commas in titles stay a list
    assert names(r) == ["Hello, Goodbye", "Come Together, Right Now"] and r["format"] == "list"


def test_duplicates_noted_and_empty():
    r = sio.parse("A\nB\na\n")
    assert any("more than once" in n for n in r["notes"])
    assert sio.parse("\n# nothing\n")["songs"] == 0
    assert names(sio.parse("﻿BOM Song\n")) == ["BOM Song"]


def test_tablet_page():
    page = sio.tablet_page("Show <1>", [{"name": "Set 1", "songs": [{"name": "A & B", "note": "Red"}]},
                                        {"name": "Empty", "songs": []},
                                        {"name": "Set 2", "songs": [{"name": "C", "note": ""}]}],
                           notes=True, generated="2026-10-06")
    assert page.startswith("<!doctype html>") and "Show &lt;1&gt;" in page and "A &amp; B" in page
    assert page.count('class="set"') == 2 and "Empty" not in page
    assert "<small class=\"note\">Red</small>" in page and 'id="notes"' in page
    assert "http://" not in page and "https://" not in page          # self-contained, no network
    assert 'id="notes"' not in sio.tablet_page("x", [{"name": "s", "songs": [{"name": "a"}]}])


def test_routes(tmp_path):
    c = app.create_app().test_client()
    r = c.post("/api/setlist/parse", json={"text": "1. A\n2. B\n"})
    assert r.status_code == 200 and r.get_json()["songs"] == 2
    assert c.post("/api/setlist/parse", json={"text": "  \n"}).status_code == 400
    assert c.post("/api/setlist/parse", json={"text": "# only a comment"}).status_code == 400
    p = tmp_path / "s.qxw"
    p.write_text('<?xml version="1.0"?>\n<!DOCTYPE Workspace>\n<Workspace xmlns="http://www.qlcplus.org/Workspace"><Engine>'
                 '<Function ID="0" Type="Chaser" Name="Setlist"><Speed FadeIn="0" FadeOut="0" Duration="0"/></Function></Engine>'
                 '<VirtualConsole><Frame Caption="P" ID="0"><CueList Caption="Set 1" ID="1"><Chaser>0</Chaser></CueList></Frame></VirtualConsole>'
                 '</Workspace>', encoding="utf-8")
    workspace.load_qxw(str(p))
    slot = c.get("/api/setlist/slots").get_json()[0]["id"]
    assert c.post("/api/setlist/tablet", json={"title": "T"}).status_code == 400      # no songs yet
    c.post(f"/api/setlist/{slot}/details", json={"rows": [{"txt_name": "Opener", "qxw_id": "", "qxw_name": "",
                                                           "in": "0", "hold": "4294967294", "out": "0"}]})
    r = c.post("/api/setlist/tablet", json={"title": "T"})
    assert r.status_code == 200 and r.mimetype == "text/html" and b"Opener" in r.data
