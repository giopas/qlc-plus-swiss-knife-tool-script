"""Write wiki/Claude-Tools.md from core/mcp_guide.py (the text Claude reads).

    python tools/make_claude_tools_wiki.py
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from core import mcp_guide, mcp_server  # noqa: E402

PATH = os.path.join(HERE, "wiki", "Claude-Tools.md")


def render() -> str:
    return mcp_guide.wiki_page(mcp_server.TOOLS, mcp_server.TITLES, mcp_server.READ_ONLY)


if __name__ == "__main__":
    with open(PATH, "w", encoding="utf-8") as fh:
        fh.write(render())
    print("written:", PATH)
