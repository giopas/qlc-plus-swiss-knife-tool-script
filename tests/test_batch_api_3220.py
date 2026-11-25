"""3.22.0 — the `batch` tool and the Python API (core/sk_api.py): faster, and just as predictable."""
import hashlib
import json
import os
import shutil

import pytest

from core import mcp_config, mcp_guide, mcp_server, porter, recipe, show
from core.sk_api import SwissKnife, SwissKnifeError

from test_mcp import CORPUS, LOOKS, Client


def _sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _files(folder):
    return sorted(os.listdir(folder))


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("QSK_LOOK_PRESETS", str(tmp_path / "p.json"))
    monkeypatch.setenv("QSK_MESH_DIRS", str(tmp_path / "dirs.json"))
    monkeypatch.delenv("QSK_MCP_FOLDERS", raising=False)
    folder = tmp_path / "shows"
    folder.mkdir()
    for f in os.listdir(CORPUS):
        if f.endswith(".qxf"):
            shutil.copy(os.path.join(CORPUS, f), folder)
    for f in ("Festival_14fix.qxw", "Pub_6fix.qxw"):
        shutil.copy(os.path.join(CORPUS, f), folder / f)
    porter.clear()
    show._show.clear()
    c = Client([str(folder)])
    c.folder = folder
    c.tmp = tmp_path
    return c


STEPS = [{"tool": "looks_options"}, {"tool": "build_looks", "args": LOOKS}, {"tool": "doctor_check"}]


# ── batch ────────────────────────────────────────────────────────────────────

def test_batch_with_save_false_writes_nothing(work):
    before = {f: _sha(work.folder / f) for f in _files(work.folder)}
    out = work.ok("batch", query="shows", steps=STEPS)
    assert out["shows"] == 2 and out["ok"] == 2 and out["saved"] == 0
    assert [os.path.basename(r["show"]) for r in out["rows"]] == ["Festival_14fix.qxw", "Pub_6fix.qxw"]
    for r in out["rows"]:
        assert r["changed"] is True and [s["tool"] for s in r["steps"]] == ["looks_options", "build_looks", "doctor_check"]
        assert set(r["steps"][2]["answer"]) == {"total", "by_code"}
        assert "saved" not in r
    assert {f: _sha(work.folder / f) for f in _files(work.folder)} == before
    assert "Nothing was written" in out["note"]


def test_batch_saves_new_files_that_replay_byte_for_byte(work):
    before = {f: _sha(work.folder / f) for f in _files(work.folder)}
    out = work.ok("batch", shows=[str(work.folder / "Pub_6fix.qxw"), str(work.folder / "Festival_14fix.qxw")],
                  steps=STEPS, save=True)
    assert out["saved"] == 2
    for f, h in before.items():                              # the originals are untouched
        assert _sha(work.folder / f) == h
    for r in out["rows"]:
        assert r["saved"] != r["show"] and os.path.isfile(r["saved"]) and os.path.isfile(r["recipe"])
        rec = json.load(open(r["recipe"], encoding="utf-8"))
        res = recipe.replay(rec, recipe_dir=str(work.folder))
        assert res["identical"], res


def test_the_same_batch_gives_the_same_files(work):
    a, b = work.tmp / "out_a", work.tmp / "out_b"
    a.mkdir()
    b.mkdir()
    work2 = Client([str(work.folder), str(a), str(b)])
    r1 = work2.ok("batch", query="shows/", steps=STEPS, save=True, where=str(a))
    r2 = work2.ok("batch", query="shows/", steps=STEPS, save=True, where=str(b))
    n1 = sorted(os.path.basename(r["saved"]) for r in r1["rows"])
    n2 = sorted(os.path.basename(r["saved"]) for r in r2["rows"])
    assert n1 == n2
    for n in n1:
        assert _sha(a / n) == _sha(b / n)


def test_a_show_with_no_change_is_not_saved(work):
    out = work.ok("batch", query="Pub_6fix", steps=[{"tool": "doctor_check"}], save=True)
    assert out["rows"][0]["changed"] is False and "saved" not in out["rows"][0] and out["saved"] == 0


def test_batch_refuses_what_it_should(work, tmp_path, monkeypatch):
    for bad in ("save_show", "open_show", "new_show", "undo", "batch", "dictionary_save", "cabling"):
        err, msg = work.tool("batch", query="shows", steps=[{"tool": bad}])
        assert err and "cannot be a batch step" in msg
    err, msg = work.tool("batch", query="shows", steps=[])
    assert err
    err, msg = work.tool("batch", steps=[{"tool": "doctor_check"}])
    assert err and "query" in msg
    err, msg = work.tool("batch", query="no-such-show", steps=[{"tool": "doctor_check"}])
    assert err and "No show matches" in msg
    other = tmp_path / "elsewhere"
    other.mkdir()
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), other / "Pub.qxw")
    err, msg = work.tool("batch", shows=[str(other / "Pub.qxw")], steps=[{"tool": "doctor_check"}])
    assert err and "outside the folders" in msg
    err, msg = work.tool("batch", query="shows", steps=[{"tool": "doctor_check"}], where=str(other))
    assert err and "outside the folders" in msg
    monkeypatch.setattr(mcp_server, "BATCH_MAX", 1)
    err, msg = work.tool("batch", query="shows", steps=[{"tool": "doctor_check"}])
    assert err and "at most 1" in msg


def test_a_failing_show_does_not_stop_the_others(work, monkeypatch):
    real = mcp_server.Server.t_doctor_check

    def flaky(self, a):
        if self.opened_path.endswith("Festival_14fix.qxw"):
            raise mcp_server.ToolError("boom")
        return real(self, a)

    monkeypatch.setattr(mcp_server.Server, "t_doctor_check", flaky)
    out = work.ok("batch", query="shows", steps=STEPS, save=True)
    fest, pub = out["rows"]
    assert not fest["ok"] and fest["error"] == "doctor_check: boom" and "saved" not in fest
    assert pub["ok"] and pub["saved"]
    assert out["failed"] == 1 and out["saved"] == 1


def test_the_guide_lists_the_batch_steps():
    text = dict(mcp_guide.GUIDE["batch"]["args"])["steps"]
    named = {w.strip(" .") for w in text.split("can be:")[1].split(",")}
    assert named == mcp_server.BATCH_STEPS
    assert "batch" in mcp_guide.WORKFLOWS


# ── the Python API ───────────────────────────────────────────────────────────

def test_the_api_has_every_tool_and_their_guide(work):
    sk = SwissKnife([str(work.folder)])
    assert sk.tools() == [t["name"] for t in mcp_server.TOOLS]
    assert set(sk.tools()) <= set(dir(sk))
    assert sk.batch.__doc__.startswith("batch") and "steps" in SwissKnife.help("batch")
    with pytest.raises(AttributeError):
        sk.no_such_tool
    with pytest.raises(SwissKnifeError):
        sk.call("no_such_tool")


def test_the_api_keeps_the_same_rules(work, tmp_path):
    sk = SwissKnife([str(work.folder)])
    with pytest.raises(SwissKnifeError) as e:
        sk.doctor_check()
    assert "open_show" in e.value.message
    other = tmp_path / "elsewhere"
    other.mkdir()
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), other / "Pub.qxw")
    with pytest.raises(SwissKnifeError) as e:
        sk.open_show(path=str(other / "Pub.qxw"))
    assert "outside the folders" in e.value.message
    sk.open_show(path=str(work.folder / "Pub_6fix.qxw"))
    sk.looks_options()
    sk.build_looks(**LOOKS)
    saved = sk.save_show()
    assert saved["saved"] != str(work.folder / "Pub_6fix.qxw")
    assert recipe.replay(json.load(open(saved["recipe"], encoding="utf-8")), recipe_dir=str(work.folder))["identical"]


def test_api_answers_are_data_and_never_cut(work, monkeypatch):
    monkeypatch.setattr(mcp_server, "MAX_TEXT", 20)
    sk = SwissKnife([str(work.folder)])
    s = sk.open_show(path=str(work.folder / "Festival_14fix.qxw"))
    assert isinstance(s, dict) and s["open"]
    fx = sk.rig_fixtures()
    assert len(json.dumps(fx)) > 20                         # the MCP answer would be cut here


def test_mcp_and_api_go_through_one_door(work, monkeypatch):
    seen = []
    real = mcp_server.Server.call_raw

    def spy(self, name, args=None):
        seen.append(name)
        return real(self, name, args)

    monkeypatch.setattr(mcp_server.Server, "call_raw", spy)
    work.ok("list_shows")
    SwissKnife([str(work.folder)]).list_shows()
    work.ok("batch", query="Pub_6fix", steps=[{"tool": "doctor_check"}])
    assert seen[:2] == ["list_shows", "list_shows"]
    assert seen[2:] == ["batch", "open_show", "doctor_check"]
