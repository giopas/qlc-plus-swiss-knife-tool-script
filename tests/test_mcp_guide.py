"""Claude's tools are documented, readable by Claude, and the wiki matches (v3.0.1)."""
import io
import json
import os

from core import mcp_guide, mcp_server

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rpc(method, params=None):
    out = io.StringIO()
    msg = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    mcp_server.serve(io.StringIO(json.dumps(msg) + "\n"), out, mcp_server.Server(None))
    return json.loads(out.getvalue())


def test_every_tool_has_a_guide_and_a_title():
    names = [t["name"] for t in mcp_server.TOOLS]
    assert set(names) == set(mcp_guide.GUIDE)
    assert all(n in mcp_server.TITLES for n in names)
    for n in names:
        text = mcp_guide.answer(n, mcp_server.TOOLS, mcp_server.TITLES, mcp_server.READ_ONLY)
        assert text.startswith(n) and mcp_guide.GUIDE[n]["use"] in text


def test_every_edit_vc_operation_is_documented():
    from routes.id_browser_routes import _BUILDER_ARGS
    ops = set(_BUILDER_ARGS) | {"copy", "move", "new_page", "fix_ids", "copy_page"}
    assert ops == set(mcp_guide.EDIT_VC_OPS)
    for op in ops:
        assert op in next(t for t in mcp_server.TOOLS if t["name"] == "edit_vc")["description"]


def test_the_wiki_page_is_up_to_date():
    import importlib.util
    import pytest
    page = os.path.join(HERE, "wiki", "Claude-Tools.md")
    if not os.path.isfile(page):          # the wiki is its own repository, not in a CI checkout
        pytest.skip("wiki/ not checked out")
    spec = importlib.util.spec_from_file_location("mk", os.path.join(HERE, "tools", "make_claude_tools_wiki.py"))
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    with open(page, encoding="utf-8") as fh:
        assert fh.read() == mk.render(), "run: python tools/make_claude_tools_wiki.py"


def test_guide_tool_resources_and_prompts():
    r = _rpc("tools/call", {"name": "guide", "arguments": {"topic": "edit_vc:create"}})["result"]
    assert "parent_id" in r["content"][0]["text"]
    idx = _rpc("tools/call", {"name": "guide", "arguments": {}})["result"]["content"][0]["text"]
    assert all(t["name"] in idx for t in mcp_server.TOOLS)
    res = _rpc("resources/list")["result"]["resources"]
    assert res[0]["uri"] == "swissknife://guide" and len(res) == len(mcp_server.TOOLS) + 1
    read = _rpc("resources/read", {"uri": "swissknife://guide/save_show"})["result"]["contents"][0]["text"]
    assert "NEW .qxw" in read
    prompts = _rpc("prompts/list")["result"]["prompts"]
    assert [p["name"] for p in prompts][0] == "write_dictionary"
    got = _rpc("prompts/get", {"name": "write_dictionary", "arguments": {"show": "/x/Club.qxw"}})["result"]
    assert '"/x/Club.qxw"' in got["messages"][0]["content"]["text"]
    init = _rpc("initialize", {"protocolVersion": "2025-06-18"})["result"]
    assert {"tools", "prompts", "resources"} <= set(init["capabilities"])


def test_the_claude_desktop_bundle_lists_the_prompts():
    from core import mcpb
    m = mcpb.manifest("3.0.1")
    assert m["prompts"][0]["name"] == "write_dictionary"
    assert "${arguments.show}" in m["prompts"][0]["text"]
