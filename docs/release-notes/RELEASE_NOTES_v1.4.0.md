# QLC+ Swiss Knife v1.4.0 — build the next show with the tool

Phase 1 of the [work plan](../../WORKPLAN.md): **Quick Start, Function Porter and Show Book leave Alpha.** Every workspace they write is checked by the new Workspace Doctor, tested against real show files, and identical run to run. Your original files are never changed.

### New
- **Workspace Doctor** — a health check for any `.qxw`: duplicate IDs, broken references, looks that leak into each other (LTP bleed), strobe or auto-programs left on, missing PANIC RESET, MIDI buttons with no controller patched, unused functions. It runs before every Quick Start and Function Porter export (errors block, warnings are reported) and from the command line: `python -m core.doctor show.qxw`.
- **Start a new rig from an existing show** — build the rig in Quick Start, then **➜ Port from an existing show**: your looks, effects and their buttons come across, even to **other fixture types** (dimmer, RGB ↔ colour wheel, pan/tilt angles, strobe, gobo are translated, not copied by channel number).
- **Function Porter brings the Virtual Console** — pick pages, frames or buttons of the old show; they are placed on a new page without overlapping. **Fan-in** for smaller rigs (14 → 6 fixtures), stage plans of both rigs coloured by the mapping, untick fixtures you don't need, remove old pages from the result, and a **port report** next to the new file.
- **MIDI / key control comes along** — ported buttons and CueLists keep their bindings; the controller's input patch (device + input profile) is copied into the new file; bindings can move to another universe; *Source wins* moves a binding off the widget that already used it.
- **Show Book** — the Virtual Console page by page with frames, positions and key/MIDI bindings; an optional Doctor summary; Shows and Scripts in the PDF and CSV.

### Quick Start
- Scenes follow each fixture's selected mode and leave unused channels at safe neutral values (shutter open, no programs, pan/tilt centred).
- A **PANIC RESET** that really resets (tested in QLC+ 5.2.2), a MASTER dimmer, fixture groups with their own frame, dimmer, looks and effects; pressing a look switches the previous one off.
- Naming profiles and a VC style cloned from any show; the fixture `.qxf` files QLC+ lacks are saved next to the workspace.

### Fixed
- Function Porter: non-deterministic IDs, EFX and scripts not recognised in real files, values of unmapped fixtures left behind, ported looks surviving the PANIC RESET, Sequence steps pointing at the old fixtures.
- Show Book: VC widget IDs were empty; emoji printed as `?`; overlapping titles in the PDF.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Quick Start](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Quick-Start) · [Function Porter](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Function-Porter) · [Show Book](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Book) · [Workspace Doctor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Workspace-Doctor).
