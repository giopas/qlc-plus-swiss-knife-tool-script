# Roadmap

This document outlines potential directions for future development of QLC+ Swiss Knife. Items are loosely grouped by theme and are **not** in a fixed priority order — the roadmap is intentionally open-ended and will be shaped by real-world feedback and contributions.

> **Note:** This project is maintained in spare time. There are no committed release dates. If you have ideas or would like to help implement any of these items, please open a [Feature Request](../../issues/new?template=feature_request.md) or a Pull Request.

---

## Version 1.0 — Flask / Web UI  *(dev branch: `web-ui`)*

The next major version replaces the tkinter desktop app with a **Flask + SPA** architecture that runs entirely in the browser (`http://localhost:5731`). No GUI toolkit required — just Python 3 and `flask`.

### What is already working on `web-ui`

- [x] File load via path input, drag-and-drop, and Browse button
- [x] Reload from disk; workspace state shared across all tabs
- [x] Status bar (function / fixture / VC widget counts)
- [x] **ID Browser** — sortable/filterable Functions + VC Widgets tables, CSV export
- [x] **Setlist Manager** — CueList slot list, per-slot song editor, load/save TXT
- [x] **Dictionary Manager** — editable function-description table, load/save TXT
- [x] **Setup Checklist** — sortable fixture table, export TXT
- [x] **Trigger Manager** — Key/MIDI edit panel, duplicates check, save to QXW
- [x] **Fixture tab** — read-only workspace fixture view

### Still to do before v1.0 ships

- [ ] Fixture Configurator canvas — HTML5 `<canvas>` drag-and-drop, `.qxf` loading, auto-DMX, QXW generation *(planned for v1.1)*
- [ ] PDF export for Checklist and Setlist (port raw-PDF writer from tkinter version)
- [ ] Setlist chaser-clone generation (port `_generate_chaser()`)
- [ ] Unit tests for Flask routes and `core/workspace.py`
- [ ] Merge `web-ui` → `main` as **v1.0.0** and retire `qlc_swiss_knife_0.7.3.py`

---

## Version 0.x — Stabilisation & Polish  *(tkinter, stable branch: `main`)*

Near-term improvements to the stable tkinter release. Most of these become irrelevant once v1.0 ships, but are noted for completeness.

- [ ] Improve error messages when a malformed or unsupported `.qxw` file is loaded
- [ ] Add keyboard shortcuts for common actions (load workspace, switch tabs, save)
- [ ] Persist window size and last-opened file path between sessions
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
- [x] Support for QLC+ fixture definition files (`.qxf`) to enrich fixture metadata — *(implemented in Fixture Configurator, v0.5)*

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
| v0.5 | Fixture Configurator tab: 2D stage canvas, `.qxf` loading, DMX auto-assign, QXW generation from template |
| v0.6 | Function Assignment Panel in Fixture Configurator: intelligent auto-mapping with name-role and spatial proximity strategies |
| v0.7 | Setlist Manager multi-slot architecture (one slot per CueList); "Rename to CueList" and "Unassign All" actions; nested VC frame ancestry fix in Trigger Manager |
| v0.7.1 | Bugfix: Chaser step `Hold="0"` now correctly parsed as infinite; generated Chasers write explicit per-step Speed/SpeedModes blocks |
| v0.7.2 | Security hardening: 9 fixes (XML injection, DoS via oversized files, XPath injection, negative-index bypass, unbounded reads, DMX range validation, TOCTOU race, silent exceptions, missing namespace check) |
| v0.7.3 | ID Browser tab (Tab 6): sortable/filterable Functions table + VC Widgets table; CSV and PDF export; status bar updated with VC widget count |

---

*Last updated: May 2026 — v0.7.3 released on `main`; v1.0 web UI in active development on `web-ui`*
