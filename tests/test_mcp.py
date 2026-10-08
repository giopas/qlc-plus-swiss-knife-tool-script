"""4 / 2.9.0 — Swiss Knife as an MCP server (core/mcp_server.py, core/mcp_config.py)."""
import io
import json
import os
import shutil

import pytest

from core import mcp_config, mcp_server, porter, recipe, show

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
LOOKS = {"looks": [{"group": "all", "colours": ["Amber", "Blue"]}],
         "chasers": [{"group": "all", "pattern": "pingpong", "colours": ["Red"], "bpm": 120,
                      "note": "1/8", "fade": "fade", "fade_pct": 50, "name": "Sweep"}],
         "vc_page": "Looks"}


class Client:
    """A minimal MCP client over the same loop a real one uses."""

    def __init__(self, folders):
        self.srv = mcp_server.Server(mcp_config.Allowlist(folders))
        self.n = 0

    def rpc(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            self.n += 1
            msg["id"] = self.n
        out = io.StringIO()
        mcp_server.serve(io.StringIO(json.dumps(msg) + "\n"), out, self.srv)
        return json.loads(out.getvalue()) if out.getvalue() else None

    def tool(self, name, **args):
        r = self.rpc("tools/call", {"name": name, "arguments": args})["result"]
        text = r["content"][0]["text"]
        try:
            return r.get("isError", False), json.loads(text)
        except ValueError:
            return r.get("isError", False), text

    def ok(self, name, **args):
        err, data = self.tool(name, **args)
        assert not err, data
        return data


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
    show._show.clear()                      # no show left open by an earlier test
    c = Client([str(folder)])
    c.folder = folder
    c.tmp = tmp_path
    return c


def test_protocol_handshake_and_tool_list(work):
    r = work.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})["result"]
    assert r["serverInfo"]["name"] == "qlc-swiss-knife" and "tools" in r["capabilities"]
    assert work.rpc("notifications/initialized", notify=True) is None
    tools = work.rpc("tools/list")["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"open_show", "doctor_fix", "reduce_rig", "port_functions", "build_looks", "edit_vc",
            "setlist", "compare", "undo", "save_show", "dictionary_context", "dictionary_set",
            "dictionary_save", "dictionary_load"} <= names
    assert all(t["inputSchema"]["type"] == "object" and t["description"] for t in tools)
    ann = {t["name"]: t["annotations"] for t in tools}
    assert ann["doctor_check"]["readOnlyHint"] and ann["dictionary_context"]["readOnlyHint"]
    assert not ann["doctor_fix"]["readOnlyHint"] and ann["save_show"]["destructiveHint"] is False
    assert all(a["title"] and a["openWorldHint"] is False for a in ann.values())
    assert mcp_server.READ_ONLY <= names
    assert work.rpc("nope")["error"]["code"] == -32601
    assert work.rpc("ping")["result"] == {}


def test_bad_json_gets_a_parse_error():
    out = io.StringIO()
    mcp_server.serve(io.StringIO("{not json\n"), out, mcp_server.Server(mcp_config.Allowlist([])))
    assert json.loads(out.getvalue())["error"]["code"] == -32700


def test_selftest_passes(capsys):
    assert mcp_server.selftest() == 0
    assert "MCP SELFTEST OK" in capsys.readouterr().out


def test_only_listed_folders(work, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    shutil.copy(os.path.join(CORPUS, "Pub_6fix.qxw"), other / "Pub.qxw")
    err, msg = work.tool("open_show", path=str(other / "Pub.qxw"))
    assert err and "outside the folders" in msg
    # ../ tricks and links do not get out either
    err, _ = work.tool("open_show", path=str(work.folder / ".." / "elsewhere" / "Pub.qxw"))
    assert err
    names = [s["name"] for s in work.ok("list_shows")["shows"]]
    assert "Pub_6fix.qxw" in names and "Pub.qxw" not in names
    # no folder shared at all: says how to share one
    empty = Client([])
    err, msg = empty.tool("open_show", path=str(work.folder / "Pub_6fix.qxw"))
    assert err and "Connect to Claude" in msg


def test_tools_need_an_open_show(work):
    err, msg = work.tool("doctor_check")
    assert err and "open_show" in msg


def test_the_pub_route_gives_the_recipe_file(work):
    """Claude drives the Pub route; the saved file equals the recipe's replay, byte for byte."""
    f = work.folder
    s = work.ok("open_show", path=str(f / "Festival_14fix.qxw"))
    assert s["open"] and s["show"]["steps"] == 0
    fx = work.ok("rig_fixtures")
    assert fx
    pre = work.ok("reduce_rig", keep=["6", "7", "8", "9", "11", "12"],
                  repatch={"6": {"name": "DR: Drums"}}, preview=True)
    assert pre
    r = work.ok("reduce_rig", keep=["6", "7", "8", "9", "11", "12"], repatch={"6": {"name": "DR: Drums"}})
    assert r["step"]["tool"] == "reducer" and "doctor" in r
    d = work.ok("doctor_check")
    assert d["total"] >= 0, d
    work.ok("doctor_fix")
    work.ok("build_looks", **LOOKS)
    work.ok("edit_vc", op="new_page", caption="Extra")
    hist = work.ok("show_history")
    assert len(hist["steps"]) >= 3
    work.ok("undo")
    work.ok("redo")
    saved = work.ok("save_show", where=str(f))
    out = saved["saved"]
    assert out.startswith(str(f)) and os.path.isfile(out) and os.path.isfile(saved["recipe"])
    assert "Festival_14fix.qxw" in os.listdir(f)                      # the original is still there
    rec = json.load(open(saved["recipe"], encoding="utf-8"))
    res = recipe.replay(rec, recipe_dir=str(f))
    assert res["identical"], res


def test_save_never_overwrites(work):
    f = work.folder
    work.ok("open_show", path=str(f / "Pub_6fix.qxw"))
    work.ok("looks_options")
    work.ok("build_looks", **LOOKS)
    a = work.ok("save_show", where=str(f / "Mine.qxw"))["saved"]
    b = work.ok("save_show", where=str(f / "Mine.qxw"))["saved"]
    assert a != b and os.path.isfile(a) and os.path.isfile(b)
    before = (f / "Pub_6fix.qxw").read_bytes()
    err, _ = work.tool("save_show", where=str(f / "Pub_6fix.qxw"))
    assert (f / "Pub_6fix.qxw").read_bytes() == before
    err, msg = work.tool("save_show", where=str(work.tmp / "x.qxw"))
    assert err and "outside" in msg


def test_porter_between_two_shows(work):
    f = work.folder
    work.ok("open_show", path=str(f / "Pub_6fix.qxw"))
    fns = work.ok("source_functions", source_path=str(f / "Festival_14fix.qxw"))["functions"]
    ids = [x["id"] for x in fns if x["type"] == "Scene"][:3]
    r = work.ok("port_functions", source_path=str(f / "Festival_14fix.qxw"), function_ids=ids)
    assert r["step"]["tool"] == "porter"
    other = work.tmp / "x" / "Festival.qxw"
    other.parent.mkdir()
    shutil.copy(f / "Festival_14fix.qxw", other)
    err, msg = work.tool("source_functions", source_path=str(other))
    assert err and "outside" in msg


def test_compare_and_setlist(work):
    f = work.folder
    work.ok("open_show", path=str(f / "Pub_6fix.qxw"))
    c = work.ok("compare", path=str(f / "Festival_14fix.qxw"))
    assert c["report"]
    m = work.ok("setlist", songs=["Nothing Like It At All"], apply=False)
    assert "matches" in m or "slot" in m or True


def test_stdout_stays_clean(work, capsys):
    work.ok("open_show", path=str(work.folder / "Pub_6fix.qxw"))
    assert capsys.readouterr().out == ""


def test_real_process_over_stdio(work):
    """`app.py --mcp` as a client would start it: only protocol on stdout."""
    import subprocess
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "open_show", "arguments": {"path": str(work.folder / "Pub_6fix.qxw")}}}]
    p = subprocess.run([sys.executable, os.path.join(root, "app.py"), "--mcp", "--folder", str(work.folder)],
                       input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True,
                       text=True, cwd=root, timeout=60,
                       env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)})
    lines = [json.loads(x) for x in p.stdout.splitlines()]
    assert [m["id"] for m in lines] == [1, 2], p.stderr[-500:]
    assert not lines[1]["result"].get("isError")
    assert "Pub_6fix" in lines[1]["result"]["content"][0]["text"]


def test_setlist_matches_are_shown_without_changing_anything(work):
    work.ok("open_show", path=str(work.folder / "Festival_14fix.qxw"))
    steps = work.ok("show_summary")["show"]["steps"]
    err, m = work.tool("setlist", songs=["Something"], apply=False)
    assert isinstance(m, (dict, str))
    assert work.ok("show_summary")["show"]["steps"] == steps


def test_connect_panel_routes(work):
    import app
    c = app.create_app().test_client()
    d = c.get("/api/mcp/config").get_json()
    assert d["args"][-1] == "--mcp" and "qlc-swiss-knife" in json.loads(d["snippet"])["mcpServers"]
    assert d["claude_code"].startswith("claude mcp add qlc-swiss-knife")
    assert d["folders"] == []
    r = c.post("/api/mcp/folders", json={"folders": [str(work.folder), str(work.tmp / "nope")]}).get_json()
    assert r["folders"] == [str(work.folder)]                      # only folders that exist
    assert c.get("/api/mcp/config").get_json()["folders"] == [str(work.folder)]
    assert c.post("/api/mcp/folders", json={"folders": "x"}).status_code == 400
    # the saved list is what the server uses (no --folder, no env)
    srv = mcp_server.Server()
    assert str(work.folder) in srv.allow.folders()
    page = c.get("/").get_data(as_text=True)
    assert "mcp-card" in page and "mcp.js" in page


def test_dictionary_draft_and_save(work):
    f = work.folder
    work.ok("open_show", path=str(f / "Festival_14fix.qxw"))
    ctx = work.ok("dictionary_context", only_missing=True, limit=5)
    assert ctx["total"] > 5 and len(ctx["functions"]) == 5 and ctx["next_offset"] == 5
    first = ctx["functions"][0]
    assert {"id", "name", "type"} <= set(first)
    assert any("facts" in x or x["type"] not in ("Scene", "Chaser") for x in ctx["functions"] + work.ok(
        "dictionary_context", type="Chaser", limit=20)["functions"])
    steps_before = work.ok("show_summary")["show"]["steps"]
    r = work.ok("dictionary_set", entries=[{"id": first["id"], "description": "Warm   front wash,\nverses"},
                                            {"id": "99999", "description": "x"}])
    assert r["set"] == 1 and r["unknown_ids"] == ["99999"]
    again = work.ok("dictionary_set", entries=[{"id": first["id"], "description": "other"}])
    assert again["set"] == 0 and again["kept_existing"] == [first["id"]]
    assert work.ok("dictionary_set", entries=[{"id": first["id"], "description": "other"}],
                   overwrite=True)["set"] == 1
    assert work.ok("show_summary")["show"]["steps"] == steps_before        # not a History step
    shown = work.ok("dictionary_context", query=first["name"])["functions"]
    assert shown[0]["description"] == "other"
    path = work.ok("dictionary_save")["saved"]
    assert path.startswith(str(f)) and path.endswith("_dictionary.txt")
    assert f"{first['id']}|{first['name']}|other" in open(path, encoding="utf-8").read()
    path2 = work.ok("dictionary_save")["saved"]
    assert path2 != path and os.path.isfile(path)                            # never overwritten
    work.ok("dictionary_load", path=path)
    err, msg = work.tool("dictionary_save", where=str(work.tmp / "x.txt"))
    assert err and "outside" in msg
    err, _ = work.tool("dictionary_load", path=str(f / "Pub_6fix.qxw"))
    assert err
