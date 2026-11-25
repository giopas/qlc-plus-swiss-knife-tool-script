"""core/sk_api.py — Swiss Knife's Claude tools as a Python API, for scripts (3.22.0).

The same tools Claude calls over MCP, as Python functions.  Meant for Claude Code (or you)
writing a short script for a job that repeats: a loop over many shows, a filter on a long
Doctor report, a table of what changed.  The script talks to the tools, the tools change
the shows.  Nothing here edits a file by itself.

    from core.sk_api import SwissKnife
    sk = SwissKnife()                      # the folders of Settings › Connect to Claude
    for s in sk.list_shows(query="Venues/", limit=200)["shows"]:
        sk.open_show(path=s["path"])
        print(s["name"], sk.doctor_check()["by_code"])

Rules, the same as for Claude over MCP, because every call goes through
``mcp_server.Server.call_raw``:

* only the shared folders (plus any given to ``SwissKnife(folders=…)``) can be read or written;
* a show is only ever written as a NEW file (``save_show``), with its report and its recipe;
* the Doctor checks a show before it is saved, every change is a History step.

So a script is as predictable as the tools: each saved file comes with a recipe, and
``python -m core.recipe replay <recipe>`` rebuilds it byte for byte, whatever script made it.

Answers are Python data, never cut short (MCP answers are cut at ``MAX_TEXT``).
A tool that refuses raises ``SwissKnifeError`` with the same message Claude would read.
Run from the sources (``python3 my_script.py`` in the repository folder).
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from core import mcp_config, mcp_server

__all__ = ["SwissKnife", "SwissKnifeError"]


class SwissKnifeError(RuntimeError):
    """A tool said no (a path outside the folders, no show open, the Doctor found errors, …)."""

    def __init__(self, tool: str, message: str):
        super().__init__(f"{tool}: {message}")
        self.tool = tool
        self.message = message


class SwissKnife:
    """One session with one show in progress, like one Claude connection.

    Every tool is a method with keyword arguments: ``sk.doctor_fix(keys=[...])``,
    ``sk.save_show(where="/shows/out")``.  ``sk.call("doctor_fix", keys=[...])`` does the same.
    """

    def __init__(self, folders: Optional[Iterable[str]] = None):
        self._srv = mcp_server.Server(mcp_config.Allowlist(list(folders or [])))
        self._names = [t["name"] for t in mcp_server.TOOLS]

    # ── calling the tools ───────────────────────────────────────────────────
    def call(self, tool: str, **args: Any) -> Any:
        if tool not in self._names:
            raise SwissKnifeError(tool, "no such tool. SwissKnife().tools() lists them.")
        try:
            return self._srv.call_raw(tool, args)
        except (mcp_server.ToolError, mcp_config.NotAllowed) as e:
            raise SwissKnifeError(tool, str(e)) from None

    def __getattr__(self, name: str):
        if name.startswith("_") or name not in self.__dict__.get("_names", ()):
            raise AttributeError(name)

        def tool(**args: Any) -> Any:
            return self.call(name, **args)

        tool.__name__ = name
        tool.__doc__ = self.help(name)
        return tool

    def __dir__(self) -> List[str]:
        return sorted(set(super().__dir__()) | set(self._names))

    # ── reading about them ──────────────────────────────────────────────────
    def tools(self) -> List[str]:
        """The tool names, in the order Claude sees them."""
        return list(self._names)

    def folders(self) -> List[str]:
        """The folders this session may read and write."""
        return self._srv.allow.folders()

    @staticmethod
    def help(tool: str = "") -> str:
        """The guide Claude reads: a tool's arguments, answers and an example ("" lists them all)."""
        from core import mcp_guide
        return mcp_guide.answer(tool, mcp_server.TOOLS, mcp_server.TITLES, mcp_server.READ_ONLY)


def main(argv: Optional[List[str]] = None) -> int:
    """``python -m core.sk_api [tool]``: print the guide (for a quick look from a terminal)."""
    import sys
    args = sys.argv[1:] if argv is None else argv
    print(SwissKnife.help(args[0] if args else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
