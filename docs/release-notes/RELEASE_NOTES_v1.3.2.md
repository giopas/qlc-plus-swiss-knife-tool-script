## v1.3.2 — clean the bench

First step of the new [work plan](WORKPLAN.md): making Swiss Knife a safe, predictable show-file builder.

### Your files are safe
- **No tool ever overwrites your workspace.** Trigger Manager now saves `Show_v42.qxw` next to `Show_v41.qxw`. Every tool writes through one safe writer that always keeps QLC+'s `<!DOCTYPE Workspace>` line.

### New
- **VC Visual Editor**: copy or move buttons and frames to another page, duplicate a page, add a new page; **Undo** (↶ / ⌘Z); pinch or ⌘-scroll to zoom; box-select and ⌘-click; one-click fix for duplicated widget IDs.
- **Sessions (.qsk) remember every tool**: show name and date, Brightness sliders, Porter and Merger files, Show Book settings, PDF paper sizes.
- **Quick Start aims fixtures at the stage** (truss 45°, floor uplight 45°, mid-height horizontal).

### Fixed
- QXW Merger and Function Porter showed 0 fixtures / 0 functions for real QLC+ files.
- Function Porter wizard stuck on "Loading…"; VC Visual Editor ignored clicks; Brightness "Fetch from GitHub" failed.
- macOS native window crash (`KeyError: 'text_select'`) when the Python environment lives in an iCloud folder.

### Changed
- Files are opened the same way everywhere: **📂 Open…** in the header, **📂 Browse…** in every tool, no more paste-a-path fields.
- One primary button per screen, bottom right; the *Triggers* tab is now **Trigger Manager**.
- Tests run automatically on GitHub for every push.

Full details: [CHANGELOG](CHANGELOG.md).
