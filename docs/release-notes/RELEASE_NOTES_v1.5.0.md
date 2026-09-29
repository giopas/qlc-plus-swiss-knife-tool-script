# QLC+ Swiss Knife v1.5.0 — fix it, then make it smaller

### New
- **Workspace Doctor tab** (sidebar → Workspace tools) — 🔍 Check the open show, tick what to fix (the recommended fixes are pre-ticked; removing functions has to be asked for), **💾 Fix selected → new file…**. Fixes: broken references, scenes that don't set every channel (LTP bleed), strobe / auto programs left on, a scene shared by a button and a chaser, duplicate IDs, widgets outside their page, a missing PANIC RESET — and a **PANIC RESET that can't reset**: a plain scene can't darken a look that is still running, so the fix turns it into a script that stops everything first, then resets. A fix report is saved next to the new file. Also on the command line: `python -m core.doctor show.qxw --fix`.
- **Rig Reducer** (sidebar → Build the rig) — keep the fixtures of a smaller rig; scene values, groups, EFX / matrix fixtures, 3D positions, functions left empty and the buttons, CueLists and faders that used them are cleaned up. Re-patch names, universes and addresses; **Preview** shows every change and what the Doctor says; save as a new file with a report.
- New Doctor checks: PANIC RESET is a plain scene (D017), setlist page isn't page 1 (D010), widget outside its page or frame (D011), chaser steps that last 0 ms (D013), CueList running an empty chaser (D014).

Your original files are never changed: every result is a new `<name>_v<N+1>.qxw`.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Workspace Doctor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Workspace-Doctor) · [Rig Reducer](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Rig-Reducer).
