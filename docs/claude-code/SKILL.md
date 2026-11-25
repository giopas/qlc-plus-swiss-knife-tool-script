---
name: swiss-knife
description: Change or check QLC+ show files (.qxw) with QLC+ Swiss Knife's own tools, from a Python script or the batch tool, when a job repeats over many shows or needs a filtered answer. Use instead of editing .qxw XML by hand.
---

# QLC+ Swiss Knife from Claude Code

Swiss Knife's Claude tools are also a Python API: `core.sk_api.SwissKnife`. Use it from the
Swiss Knife repository folder (run from the sources). The same rules hold as over MCP: only
the folders shared in Settings › Connect to Claude, a show is only written as a NEW file, the
Doctor checks before a save, every saved file has a recipe that rebuilds it byte for byte.

## Pick the smallest way

1. One show, a few steps: the MCP tools directly (`open_show`, `doctor_check`, `save_show`, …).
2. The same steps on many shows: the `batch` MCP tool, or `sk.batch(...)`. It answers with one
   short table. Run it with `save=False` first, show the table, then `save=True`.
3. Anything `batch` cannot describe (a filter across shows, a report, a choice per show):
   a short script with `SwissKnife`.

Never edit a `.qxw` directly, and never write to a show except through `save_show` (or
`batch` with `save=True`). A script reads and decides; the tools change the shows.

## The API

```python
from core.sk_api import SwissKnife, SwissKnifeError
sk = SwissKnife()                 # or SwissKnife(folders=["/path/to/shows"])
sk.tools()                        # the tool names
print(SwissKnife.help("batch"))   # arguments, answers and an example of a tool
sk.open_show(path="/path/to/shows/Pub.qxw")
sk.doctor_fix()                   # each tool is a method with keyword arguments
saved = sk.save_show()            # {"saved": ..., "recipe": ..., "doctor": ...}
```

- Answers are Python data and are never cut short.
- A refusal raises `SwissKnifeError`; `.message` is the text Claude would read.
- One show in progress per `SwissKnife()`, like one Claude connection.

## Batch

```python
out = sk.batch(query="Venues/",
               steps=[{"tool": "upgrade_show", "args": {"steps": ["crossuniverse"]}},
                      {"tool": "doctor_fix"},
                      {"tool": "doctor_check"}],
               save=False)
for r in out["rows"]:
    print(r["show"], r["ok"], r.get("error") or r["steps"][-1]["answer"])
```

Shows run in path order, at most 50. A failing step stops that show only. IDs differ between
shows, so prefer steps without IDs.

## Keep it predictable

- Show the user what a script will change before it saves, as with `preview=true` on a tool.
- After saving, the recipes are the record: `python -m core.recipe replay <recipe>` must say
  identical. Report the saved paths, not a summary from memory.
- Ask before any script that would save more than a handful of files.
