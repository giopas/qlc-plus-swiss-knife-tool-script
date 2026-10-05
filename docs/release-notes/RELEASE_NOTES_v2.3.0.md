# QLC+ Swiss Knife v2.3.0 — the new-show flow

Starting a show from nothing is now one path.

### Added
- **Fixtures → 🎛 Open it as the show** after *Save as new file…*.
- **Guided route *New show*** (Start page and ⌘K): rig → groups → looks → VC Editor → stage → setlist → Show Book → Doctor.
- **Profiles that start a show from nothing**: save the Quick Start rig as a profile, then *Start a show from a profile*. Also `python -m core.profile rig` / `build` without `--show`.
- **Profile step editor**: drop, reorder and rename steps; left-out reasons stay visible.
- **Setlist with the QLC+ function list in a drawer**: fewer columns, remembered open/closed.

### Changed / removed
- Checklist and Tech Rider routes are thin wrappers over the Show Book. The old Merger code is gone (the Function Porter replaces it).

Your original files are never changed.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Show Profiles](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Profiles).
