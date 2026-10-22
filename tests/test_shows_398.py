"""Show awareness (3.9.8): Shows in the Doctor, the Setlist and the travel zip."""
import os
import xml.etree.ElementTree as ET

from core import definitions, media, qxw_io, workspace
from core.doctor import check
from tests.test_doctor import FULL, scene, ws

INF = "4294967294"


def show(fid, items, name="Song show", tracks=1):
    """items: [(function id, start ms, duration ms)] all on one track."""
    body = "".join(f'<ShowFunction ID="{i}" StartTime="{a}" Duration="{d}" Color="#ff0000"/>' for i, a, d in items)
    return (f'<Function ID="{fid}" Type="Show" Name="{name}"><TimeDivision Type="Time" BPM="120"/>'
            f'<Track ID="0" Name="Track 1" SceneID="4294967295" isMute="0">{body}</Track></Function>')


def audio(fid, src, name="Click"):
    return (f'<Function ID="{fid}" Type="Audio" Name="{name}"><Speed FadeIn="0" FadeOut="0" Duration="60000"/>'
            f'<Source>{src}</Source></Function>')


def cuelist(chaser_id, holds, steps):
    st = "".join(f'<Step Number="{n}" FadeIn="0" Hold="{h}" FadeOut="0">{s}</Step>'
                 for n, (s, h) in enumerate(zip(steps, holds)))
    fn = (f'<Function ID="800" Type="Chaser" Name="Setlist"><Speed FadeIn="0" FadeOut="0" Duration="{INF}"/>'
          f'<Direction>Forward</Direction><RunOrder>Loop</RunOrder>{st}</Function>')
    vc = f'<CueList Caption="Setlist" ID="50"><Chaser>{chaser_id}</Chaser></CueList>'
    return fn, vc


def codes(root, **kw):
    return [f.code for f in check(root, **kw).findings]


def test_empty_show_is_flagged():
    assert "D004" in codes(ws(show("10", [])))


def test_show_with_a_lit_scene_is_fine():
    root = ws(scene("5") + show("10", [("5", 0, 5000)]))
    assert "D004" not in codes(root)


def test_sound_only_show_in_a_cuelist_lights_nothing():
    fn, vc = cuelist("800", [INF], ["10"])
    root = ws(audio("6", "/x/a.wav") + show("10", [("6", 0, 5000)]) + fn, vc)
    assert "D018" in codes(root)


def test_show_with_light_and_sound_is_not_dark():
    fn, vc = cuelist("800", [INF], ["10"])
    root = ws(scene("5") + audio("6", "/x/a.wav") + show("10", [("5", 0, 5000), ("6", 0, 5000)]) + fn, vc)
    assert "D018" not in codes(root)


def test_missing_media_file(tmp_path):
    f = tmp_path / "there.wav"
    f.write_bytes(b"RIFF")
    root = ws(audio("6", str(f), "Here") + audio("7", str(tmp_path / "gone.wav"), "Gone") + audio("8", "", "Blank"))
    fs = [x for x in check(root).findings if x.code == "D024"]
    assert len(fs) == 2
    assert any("gone.wav" in x.message for x in fs) and any("no file set" in x.message for x in fs)


def test_relative_path_is_looked_up_next_to_the_show(tmp_path):
    (tmp_path / "song.wav").write_bytes(b"RIFF")
    root = ws(audio("6", "song.wav") + audio("7", "other.wav"))
    fs = [x for x in check(root, base_dir=str(tmp_path)).findings if x.code == "D024"]
    assert [x.ref["source"] for x in fs] == ["other.wav"]
    assert "D024" not in codes(root)          # no folder to look in: not guessed


def test_urls_are_not_checked():
    assert media.media_status("http://example.com/a.mp3") == "url"
    assert "D024" not in codes(ws(audio("6", "http://example.com/a.mp3")))


def test_finite_hold_shorter_than_the_show_is_flagged():
    fn, vc = cuelist("800", ["3000"], ["10"])
    root = ws(scene("5") + show("10", [("5", 0, 10000)]) + fn, vc)
    f = [x for x in check(root).findings if x.code == "D025"]
    assert len(f) == 1 and f[0].ref["show_ms"] == 10000 and f[0].ref["lasts_ms"] == 3000


def test_waiting_for_the_pedal_or_a_long_enough_hold_is_fine():
    for hold in (INF, "10000", "12000"):
        fn, vc = cuelist("800", [hold], ["10"])
        root = ws(scene("5") + show("10", [("5", 0, 10000)]) + fn, vc)
        assert "D025" not in codes(root), hold


def test_show_length_and_items():
    f = ET.fromstring(show("10", [("5", 1000, 4000), ("6", 0, 2000)]))
    assert media.show_length_ms(f) == 5000
    assert len(media.show_items(f)) == 2
    assert media.show_length_ms(ET.fromstring(show("11", []))) == 0


def test_contained_ids_of_a_show():
    f = ET.fromstring(show("10", [("5", 0, 1000), ("6", 0, 1000), ("5", 2000, 1000)])
                      .replace("<Function ", '<Function xmlns="http://www.qlcplus.org/Workspace" ', 1))
    assert workspace._contained_ids(f) == ["5", "6"]


def test_edited_show_copy_is_noticed():
    ns = "http://www.qlcplus.org/Workspace"
    eng = ET.fromstring(f'<Engine xmlns="{ns}">'
                        + show("10", [("5", 0, 1000)], "Orig")
                        + show("11", [("5", 0, 1000), ("6", 0, 500)], "Copy").replace('Type="Show"', 'Type="Show" SwissKnifeClone="10"')
                        + f'<Function ID="800" Type="Chaser" Name="S"><Step Number="0">11</Step></Function></Engine>')
    master = eng.findall(f"{{{ns}}}Function")[2]
    workspace._state['setlist_edited_copies'] = []
    workspace._note_edited_show_copies(master, eng)
    assert workspace._state['setlist_edited_copies'] == ["Copy"]
    # an untouched copy is not reported
    eng.findall(f"{{{ns}}}Function")[1].find(f"{{{ns}}}Track").remove(
        eng.findall(f"{{{ns}}}Function")[1].find(f"{{{ns}}}Track")[1])
    workspace._state['setlist_edited_copies'] = []
    workspace._note_edited_show_copies(master, eng)
    assert workspace._state['setlist_edited_copies'] == []


def test_travel_readme_lists_the_media(tmp_path):
    root = ws(audio("6", "/nowhere/click.wav"))
    text = definitions._media_text(qxw_io.qxw_bytes(root), str(tmp_path))
    assert "NOT in this zip" in text and "/nowhere/click.wav" in text and "NOT FOUND here" in text
    assert definitions._media_text(qxw_io.qxw_bytes(ws(scene("5"))), "") == ""


# ── split a Show into sections ───────────────────────────────────────────────

import pytest
from core import show_split


@pytest.mark.parametrize("text,ms", [
    ("0:32", 32000), ("1:32.5", 92500), ("92.5s", 92500), ("1500ms", 1500), ("12", 12000),
    ("bar 9", 16000), ("bar 9.3", 17000), ("beat 65", 32000)])
def test_cut_positions(text, ms):
    assert show_split.parse_position(text, 120, 4) == ms


@pytest.mark.parametrize("text", ["", "abc", "1:75", "bar 0", "bar 2.5"])
def test_bad_positions_say_why(text):
    with pytest.raises(ValueError):
        show_split.parse_position(text, 120, 4)


def test_bars_need_a_tempo():
    with pytest.raises(ValueError, match="BPM"):
        show_split.parse_position("bar 5", 0, 4)


SPLIT_ITEMS = [("5", 0, 10000), ("6", 10000, 10000), ("7", 20000, 5000), ("8", 28000, 12000)]


def _show_el():
    return ET.fromstring(show("10", SPLIT_ITEMS, "Song").replace(
        "<Function ", '<Function xmlns="http://www.qlcplus.org/Workspace" ', 1))


def test_split_gives_one_show_per_section_with_shifted_items():
    made, p = show_split.build(_show_el(), [{"name": "Verse", "at": "0:00"}, {"name": "Chorus", "at": "0:20"}], 100)
    assert [m.get("ID") for m in made] == ["100", "101"]
    assert [m.get("Name") for m in made] == ["Song - Verse", "Song - Chorus"]
    assert [(i["function"], i["start"]) for i in media.show_items(made[0])] == [("5", 0), ("6", 10000)]
    assert [(i["function"], i["start"]) for i in media.show_items(made[1])] == [("7", 0), ("8", 8000)]
    assert p["warnings"] == []


def test_an_item_across_a_cut_is_kept_whole_and_warned():
    made, p = show_split.build(_show_el(), [{"name": "A", "at": "0"}, {"name": "B", "at": "0:15"}, {"name": "C", "at": "0:30"}], 100)
    assert len(media.show_items(made[0])) == 2                 # 5, 6 (6 runs to 20 s, past the cut at 15 s)
    assert any("past the cut" in w and "'6'" in w for w in p["warnings"])
    assert media.show_length_ms(made[0]) == 20000              # nothing was shortened
    # no item is lost or doubled
    assert sum(len(media.show_items(m)) for m in made) == len(SPLIT_ITEMS)


def test_the_sections_must_be_valid():
    s = _show_el()
    with pytest.raises(ValueError, match="at least two"):
        show_split.plan(s, [{"name": "A", "at": "0"}])
    with pytest.raises(ValueError, match="start at 0"):
        show_split.plan(s, [{"name": "A", "at": "0:05"}, {"name": "B", "at": "0:20"}])
    with pytest.raises(ValueError, match="after"):
        show_split.plan(s, [{"name": "A", "at": "0"}, {"name": "B", "at": "0:20"}, {"name": "C", "at": "0:10"}])


def test_bars_at_a_tempo_cut_the_same_as_times():
    a = show_split.plan(_show_el(), [{"name": "A", "at": "0"}, {"name": "B", "at": "bar 11"}], 120)   # 10 bars x 2 s = 20 s
    b = show_split.plan(_show_el(), [{"name": "A", "at": "0"}, {"name": "B", "at": "0:20"}], 0)
    assert a == b


def test_split_in_the_workspace_adds_shows_and_keeps_the_original(tmp_path):
    root = ws(scene("5") + scene("6") + scene("7") + scene("8") + show("10", SPLIT_ITEMS, "Song"))
    p = tmp_path / "s.qxw"
    p.write_bytes(qxw_io.qxw_bytes(root))
    workspace.load_qxw(str(p))
    before = workspace._find_by_id(workspace._state["qxw_root"].find("q:Engine", workspace.NS), "Function", "10")
    sig = workspace._show_signature(before)
    info = workspace.split_show_info("10")
    assert info["length_ms"] == 40000 and info["name"] == "Song"
    out = workspace.split_show_apply("10", [{"name": "Verse", "at": "0"}, {"name": "Chorus", "at": "0:20"}])
    assert len(out["ids"]) == 2 and out["warnings"] == []
    eng = workspace._state["qxw_root"].find("q:Engine", workspace.NS)
    assert workspace._show_signature(workspace._find_by_id(eng, "Function", "10")) == sig
    names = [f["name"] for f in workspace.get_functions()]
    assert "Song - Verse" in names and "Song - Chorus" in names
    with pytest.raises(ValueError):
        workspace.split_show_apply("5", [{"name": "A", "at": "0"}, {"name": "B", "at": "1"}])   # a Scene
