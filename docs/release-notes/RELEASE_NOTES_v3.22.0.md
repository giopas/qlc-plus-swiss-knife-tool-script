### Added — the same job on many shows, faster, just as predictable

- **Claude's `batch` tool.** One call does the same steps on many shows: `shows` (paths) or `query` (part of their path), and `steps`, the tools Claude would call after `open_show` (Doctor, upgrade, Wizard Repair, looks, Virtual Console, setlist, …). Swiss Knife opens each show in turn, runs the steps and answers with one short table, one line per show, instead of every answer in the chat. Shows run in path order, at most 50. `save` is off by default, so a first call writes nothing; with `save` on, each show that changed is saved as a new file with its report and recipe, next to it or in `where`. A step that fails stops that show only, nothing is saved for it, and the others go on. A batch step cannot open, save, undo, make a new show or write a side file: only the tools that change the show in progress.
- **The tools as a Python API for scripts** (`core/sk_api.py`). `SwissKnife()` gives every Claude tool as a method with the same name and arguments, answers as Python data that are never cut short, `SwissKnife.help(tool)` for the guide, and `SwissKnifeError` for a refusal. For Claude Code (or you) when a job needs a loop or a filter that `batch` cannot describe. Run from the sources.
- **One door for every call.** `Server.call_raw` is now the only way into the tools: Claude over MCP, `batch` and the Python API all go through it, so the shared folders, new files only, the Doctor before a save and the recipe are the same for each. Every saved file still replays to the same bytes with `python -m core.recipe replay`.
- **A Claude Code skill**, `docs/claude-code/SKILL.md`: when to use a tool, `batch` or a script, and the rules a script keeps.
- **Pitch video:** the slide *Undo It, or Ask Claude* says Claude can also do one job on many shows (bullet and voice-over).
- Guide entry and a *Usual sequences* line for `batch`; wiki *Claude Tools* regenerated, *Connect Claude to Swiss Knife* gets *Many shows at once* and *Scripts with Claude Code*.
- Tests: `tests/test_batch_api_3220.py` (nothing written without `save`; saved files replay byte for byte and the originals are untouched; the same batch twice gives the same files; a show with no change is not saved; refused steps, paths outside the folders, the cap; one failing show does not stop the others; the API has every tool, keeps the same rules and is never cut; MCP, batch and the API go through `call_raw`). No screen text changed, so no translations.

### Fixed — pictures that change on every computer

- **The Start page in the pictures says "Welcome".** It greets the login name of the computer, with the hour ("Good morning, …"), so `tools/shots.py` run on a Mac put the login name in the README pictures and changed them with the time of day. The app it starts now gets `SK_NO_USER_NAME`, and `/api/settings` then gives no name. The window you use is unchanged. Test: `tests/test_shots_greeting_3220.py`.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
