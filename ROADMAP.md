# Roadmap

This document outlines potential directions for future development of QLC+ Swiss Knife. Items are loosely grouped by theme and are **not** in a fixed priority order — the roadmap is intentionally open-ended and will be shaped by real-world feedback and contributions.

> **Note:** This project is maintained in spare time. There are no committed release dates. If you have ideas or would like to help implement any of these items, please open a [Feature Request](../../issues/new?template=feature_request.md) or a Pull Request.

---

## Version 0.x — Stabilisation & Polish

These are near-term improvements focused on robustness and usability of existing features.

- [ ] Improve error messages when a malformed or unsupported `.qxw` file is loaded
- [ ] Add keyboard shortcuts for common actions (load workspace, switch tabs, save)
- [ ] Persist window size and last-opened file path between sessions
- [ ] Add a "dark/light theme" preference that survives restarts
- [ ] Improve PDF export layout and typography across all tabs
- [ ] Unit tests for the XML parsing and data transformation logic
- [ ] Bundled executable builds (PyInstaller) for Windows and macOS — so users without Python can run it directly

---

## Setlist Manager — Future Ideas

- [ ] Support for importing setlists from plain `.txt`, `.csv`, or clipboard paste
- [ ] Drag-and-drop reordering of cue entries in the setlist view
- [ ] Automatic detection and warning of duplicate function assignments
- [ ] Export setlist as an HTML page (for tablet use on stage)
- [ ] "Quick clone" mode: create an entire parallel cue sequence in one click

---

## Dictionary Manager — Future Ideas

- [ ] Bulk import of descriptions from a CSV file
- [ ] Export dictionary as a formatted PDF or HTML reference sheet
- [ ] Auto-suggest descriptions based on function names (fuzzy matching)
- [ ] Sync dictionary entries with function names detected in the workspace

---

## Setup Checklist — Future Ideas

- [ ] Interactive 2D stage plot view (click a fixture to highlight it in the checklist)
- [ ] Export checklist as an editable spreadsheet (`.xlsx` / `.csv`)
- [ ] Comparison mode: diff two `.qxw` workspaces to spot changes in the patch
- [ ] Support for QLC+ fixture definition files (`.qxf`) to enrich fixture metadata

---

## Trigger Manager — Future Ideas

- [ ] Conflict detection: flag duplicate keyboard/MIDI bindings automatically
- [ ] Filter/search bar for large trigger tables
- [ ] Bulk reassignment: change a binding for multiple buttons at once
- [ ] Export trigger map as a printable cheat sheet (PDF/HTML)
- [ ] MIDI learn simulation: visually map MIDI channels to VC widgets

---

## Long-Term / Exploratory

- [ ] Support for QLC+ network API (if/when available) for live interaction without reloading `.qxw`
- [ ] Plugin architecture: allow community-contributed tabs or panels
- [ ] Localisation / translations (UI strings extracted to a separate resource file)
- [ ] Web-based companion view (read-only, for a tablet on a lighting desk)

---

## Completed

| Version | Feature |
|---|---|
| v0.1 | Initial Setlist Manager |
| v0.2 | Dictionary Manager added |
| v0.3 | Setup Checklist added |
| v0.4 | Trigger Manager added; unified shell with shared workspace state; dark/light theme engine |

---

*Last updated: March 2026*
