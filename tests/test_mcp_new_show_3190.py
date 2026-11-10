"""3.19.0 — Claude creates a show from nothing: find_fixtures and new_show (core/mcp_server.py)."""
import json
import os
import shutil

import pytest

from core import mcp_config, mcp_server, porter, show
from core.quick_start import qlc_library

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
PAR = "Generic-7Ch-RGB-PAR.qxf"
SPOT = "Eurolite-LED-4C-12-Silent-Slim-Spot.qxf"


class C:
    def __init__(self, folders):
        self.srv = mcp_server.Server(mcp_config.Allowlist(folders))

    def tool(self, _tool, **args):
        r = self.srv.call_tool(_tool, args)
        text = r["content"][0]["text"]
        try:
            return r.get("isError", False), json.loads(text)
        except ValueError:
            return r.get("isError", False), text

    def ok(self, _tool, **args):
        err, data = self.tool(_tool, **args)
        assert not err, data
        return data

    def err(self, _tool, **args):
        err, data = self.tool(_tool, **args)
        assert err, data
        return data


@pytest.fixture
def empty(tmp_path, monkeypatch):
    """A shared folder with nothing in it, and a QLC+ library outside it."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    monkeypatch.delenv("QSK_MCP_FOLDERS", raising=False)
    lib = tmp_path / "qlc" / "Fixtures"
    (lib / "Generic").mkdir(parents=True)
    shutil.copy(os.path.join(CORPUS, PAR), lib / "Generic" / PAR)
    monkeypatch.setenv("QLCPLUS_FIXTURES", str(lib))
    qlc_library.clear_cache()
    shows = tmp_path / "shows"
    shows.mkdir()
    porter.clear()
    show._show.clear()
    c = C([str(shows)])
    c.shows, c.lib, c.tmp = shows, lib, tmp_path
    yield c
    qlc_library.clear_cache()


PARS = {"manufacturer": "Generic", "model": "7-Ch RGB LED PAR", "quantity": 4, "name": "PAR"}


def test_empty_folder_says_what_to_do(empty):
    out = empty.ok("list_shows")
    assert out["total"] == 0 and "new_show" in out["hint"]


def test_find_fixtures_in_the_library_and_the_shared_folders(empty):
    shutil.copy(os.path.join(CORPUS, SPOT), empty.shows / SPOT)
    assert empty.ok("find_fixtures")["manufacturers"] == ["Eurolite", "Generic"]
    hit = empty.ok("find_fixtures", query="7ch")["fixtures"]
    assert len(hit) == 1 and hit[0]["model"] == "7-Ch RGB LED PAR" and hit[0]["library"] == "stock"
    assert hit[0]["modes"] == [{"name": "7 Channel", "channels": 7}]
    spot = empty.ok("find_fixtures", query="slim spot", manufacturer="euro")["fixtures"][0]
    assert spot["library"] == "shared"
    assert empty.ok("find_fixtures", query="nothing like this")["total"] == 0


def test_preview_writes_nothing(empty):
    out = empty.ok("new_show", name="Club", fixtures=[PARS], stage_m=[8, 5], preview=True)
    assert out["preview"] and len(out["patch"]) == 4
    assert out["patch"][1].startswith("PAR 2 · Generic 7-Ch RGB LED PAR · 7 Channel · universe 1 ch 8-14")
    assert out["will_make"]["scenes"] > 0 and "builtin:full_band" in out["choices"]["stage_layout"]
    assert os.listdir(empty.shows) == []


def test_new_show_in_a_folder_that_does_not_exist_yet(empty):
    out = empty.ok("new_show", name="Club night", folder=str(empty.shows / "Club"), fixtures=[PARS])
    path = out["created"]
    assert path == str(empty.shows / "Club" / "Club_night_v1.qxw") and os.path.isfile(path)
    assert out["doctor"]["error"] == 0 and out["definitions_written"] == []   # QLC+ has the PAR
    first = open(path, "rb").read()
    # it is the show in progress: the other tools go on from it, and saving writes a NEW file
    assert empty.ok("show_summary")["show"]["source_name"] == "Club_night_v1.qxw"
    empty.ok("build_looks", looks=[{"group": "all", "colours": ["Red"]}])
    saved = empty.ok("save_show")["saved"]
    assert saved.endswith("Club_night_v2.qxw") and open(path, "rb").read() == first
    # the same again never writes over a file
    again = empty.ok("new_show", name="Club night", folder=str(empty.shows / "Club"), fixtures=[PARS])
    assert again["created"].endswith("Club_night_v3.qxw") and open(path, "rb").read() == first


def test_only_shared_folder_is_the_default_and_two_need_a_choice(empty):
    assert empty.ok("new_show", name="A", fixtures=[PARS])["created"].startswith(str(empty.shows))
    other = empty.tmp / "other"
    other.mkdir()
    two = C([str(empty.shows), str(other)])
    assert "folder" in two.err("new_show", name="A", fixtures=[PARS])


def test_definition_from_a_shared_folder_goes_next_to_the_show(empty):
    own = empty.tmp / "shows" / "defs"
    own.mkdir()
    shutil.copy(os.path.join(CORPUS, SPOT), own / SPOT)
    dest = empty.shows / "Gig"
    dest.mkdir()
    (dest / "Eurolite-LED-4C-12-Silent-Slim-Spot.qxf").write_text("mine")     # a different file: left alone
    out = empty.ok("new_show", name="Gig", folder=str(dest),
                   fixtures=[{"qxf": str(own / SPOT), "quantity": 2}, PARS])
    assert (dest / "Eurolite-LED-4C-12-Silent-Slim-Spot.qxf").read_text() == "mine"
    assert out["definitions_left"][0]["file"] == "Eurolite-LED-4C-12-Silent-Slim-Spot.qxf"
    dest2 = empty.shows / "Gig2"
    out = empty.ok("new_show", name="Gig", folder=str(dest2), fixtures=[{"qxf": str(own / SPOT)}])
    assert out["definitions_written"] == ["Eurolite-LED-4C-12-Silent-Slim-Spot.qxf"]


def test_patch_fixed_addresses_first_then_free_channels(empty):
    out = empty.ok("new_show", name="P", preview=True, fixtures=[
        dict(PARS, quantity=2),
        {"manufacturer": "Generic", "model": "7-Ch RGB LED PAR", "name": "Back", "quantity": 2, "address": 1},
        {"manufacturer": "Generic", "model": "7-Ch RGB LED PAR", "name": "Floor", "universe": 3}])
    p = out["patch"]
    assert "universe 1 ch 15-21" in p[0] and "universe 1 ch 22-28" in p[1]      # after the fixed ones
    assert "universe 1 ch 1-7" in p[2] and "universe 1 ch 8-14" in p[3]
    assert "universe 3 ch 1-7" in p[4]


def test_a_full_universe_rolls_over(empty):
    out = empty.ok("new_show", name="Big", preview=True, fixtures=[dict(PARS, quantity=74)])
    assert "universe 1 ch 505-511" in out["patch"][72] and "universe 2 ch 1-7" in out["patch"][73]


def test_groups_by_fixture_or_line_name(empty):
    out = empty.ok("new_show", name="G", preview=True,
                   fixtures=[PARS, {"manufacturer": "Generic", "model": "7-Ch RGB LED PAR", "name": "Wash"}],
                   groups=[{"name": "Front", "fixtures": ["PAR 1", "PAR 4", "Wash"]}])
    assert out["groups"] == [{"name": "Front", "fixtures": ["PAR 1", "PAR 4", "Wash"]}]
    assert "no fixture or line" in empty.err("new_show", name="G", preview=True, fixtures=[PARS],
                                             groups=[{"name": "X", "fixtures": ["Nope"]}])


def test_positions(empty):
    out = empty.ok("new_show", name="Pos", preview=True, stage_m=[8, 4], fixtures=[
        dict(PARS, quantity=2),
        {"manufacturer": "Generic", "model": "7-Ch RGB LED PAR", "name": "Top", "quantity": 2,
         "at": {"x_m": 1, "z_m": 0.5, "height_m": 3, "spacing_m": 2}}])
    assert out["patch"][0].endswith("at 2.0, 2.0 m") and out["patch"][1].endswith("at 6.0, 2.0 m")
    assert out["patch"][2].endswith("at 1.0, 0.5, 3.0 m") and out["patch"][3].endswith("at 3.0, 0.5, 3.0 m")


def test_clear_errors(empty):
    assert "outside the folders" in empty.err("new_show", name="X", folder=str(empty.tmp / "elsewhere"), fixtures=[PARS])
    msg = empty.err("new_show", name="X", fixtures=[{"manufacturer": "Generic", "model": "RGB PAR 7"}])
    assert "Closest: Generic / 7-Ch RGB LED PAR" in msg
    assert "Its modes: 7 Channel (7 ch)" in empty.err("new_show", name="X", fixtures=[dict(PARS, mode="12ch")])
    assert empty.ok("new_show", name="X", preview=True, fixtures=[dict(PARS, mode="7")])["patch"]
    assert "overlap" in empty.err("new_show", name="X", fixtures=[dict(PARS, address=510)])
    assert "own `name`" in empty.err("new_show", name="X", fixtures=[dict(PARS, quantity=1, name="A"),
                                                                     dict(PARS, quantity=1, name="A")])
    assert "`name`" in empty.err("new_show", fixtures=[PARS])
    assert "List the fixtures" in empty.err("new_show", name="X", fixtures=[])
    assert "outside the folders" in empty.err("new_show", name="X", fixtures=[{"qxf": str(empty.lib / "Generic" / PAR)}])
    assert os.listdir(empty.shows) == []


def test_new_show_is_a_tool_that_changes_and_find_fixtures_only_reads():
    assert "find_fixtures" in mcp_server.READ_ONLY and "new_show" not in mcp_server.READ_ONLY
    assert mcp_server._annotations("new_show")["destructiveHint"] is False
