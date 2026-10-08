# QLC+ Swiss Knife v2.9.0: Claude can use the same tools you do

Connect Claude Desktop or Claude Code to Swiss Knife and ask for the work in plain language. Claude can open a show, run the Doctor, shrink a rig, port functions, build looks and chasers, edit the Virtual Console, turn a setlist into a chaser, compare two shows and undo. It can also draft the Dictionary descriptions for your functions.

## What Claude can reach

Claude gets the folders you list and the Swiss Knife tools. Nothing else on your computer is reachable through this connection: no disk browsing, no commands, no other programs, no network. Paths outside your folders are refused. Claude only ever writes new files, never overwrites or deletes one, and every change is a History step you can undo. The Doctor refuses a result with new errors, as it does in the window.

## Added

- An MCP server with 23 tools, built into the app (`QLC Swiss Knife --mcp`).
- A one-click setup for Claude Desktop. Open *🔌 Connect to Claude* in the menu and click *Connect Claude Desktop*, or double-click the `…-claude.mcpb` file attached to this release. Claude Desktop asks which folders to share and installs the connection. Start Swiss Knife once from where you installed it, so Claude can find it.
- Dictionary descriptions drafted by Claude from names, types, buttons and contents. You review a table first, then it saves a new dictionary `.txt` that you load with *Browse TXT*.
- Read-only and changing tools are marked, so Claude Desktop asks fewer questions if you allow the reading group once.
- On Windows, `QLC Swiss Knife MCP.exe` next to the app. It is the console program Claude talks to.
- A wiki page, *Connect Claude to Swiss Knife*, with examples and troubleshooting.

## Status

Tested with a scripted client (the Pub route gives the same file as the recipe replay), smoke-tested by the release build on every platform, and installed in Claude Desktop on macOS from the source version. The packaged apps and the Windows console program have not been tried with Claude Desktop yet. Please report anything odd.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
