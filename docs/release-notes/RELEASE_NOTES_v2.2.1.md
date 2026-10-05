# QLC+ Swiss Knife v2.2.1 — the UI polish, finished

The three items 2.2.0 left open, and the fix for the white window.

### Changed
- **Function Porter says what Apply will do** in steps 2–5, in the same form as the other tools: functions and VC widgets to port, fixtures mapped (amber when some have no target), the plan's errors and warnings, and whether the result is one History step or a new file.
- **Porter step 3 shows the mapping first.** The stage maps are folded under *🗺 Stage maps*; open them to check the mapping on the stage (hover or click a row to ring its fixtures).
- **One type scale.** The odd font sizes (8–10.5, 11.5, 12.5, 13.5 px) now sit on the scale, and the scale is a set of tokens (`--fs-micro` … `--fs-title`). The VC Editor widgets, fixture chips and the stage-plot SVG keep their small sizes on purpose.

### Fixed
- **The native window opened white** on some starts: it loaded the page before the server was listening. It now waits for the server, and says so if port 5731 is already taken. `QSK_DEBUG=1 python3 app.py` enables *Inspect Element*.

Your original files are never changed.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Function Porter](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Function-Porter).
