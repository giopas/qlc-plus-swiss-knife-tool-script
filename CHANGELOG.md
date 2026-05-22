# Changelog

All notable changes to QLC+ Swiss Knife are documented here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) conventions.

---

## [0.7.1] — 2026-05-22

### Setlist Manager — Chaser Step Hold Time Fix

**Fixed**
- Chaser steps with `Hold="0"` in the QXW XML were being misread as zero-duration holds. In QLC+, a value of `0` means "defer to the Chaser's Common speed setting" (effectively infinite). The parser now normalises `0` → `4294967294` (the explicit infinite sentinel) on load, so the UI displays and saves hold times correctly.
- When generating cloned Chasers, the `Speed` and `SpeedModes` blocks are now explicitly written with `Duration=4294967294`, `FadeIn=PerStep`, `FadeOut=PerStep`, and `Duration=Common`, ensuring per-step infinite hold is preserved correctly in the exported workspace.

---

## [0.7] — 2026-05-22

### Setlist Manager — Major Refactor: Multi-Slot Architecture

The Setlist Manager has been redesigned from a single-cue-list view into a **multi-slot system** where each slot corresponds to one QLC+ CueList / Chaser pair. This allows managing an entire show with multiple cue lists in a single session.

**Added**
- Inner notebook: each CueList detected in the loaded workspace gets its own dedicated tab (slot) inside the Setlist Manager.
- `+ Add Slot` and `× Remove Slot` buttons to manually add or delete slots at any time.
- Each slot shows the linked VC CueList caption for instant orientation.
- **"✎ Rename to CueList"** button: renames the underlying Chaser in the QXW XML to match its CueList caption — keeps the show file clean without manual XML editing.
- **"Unassign All"** button: clears all function assignments in the active slot in one click, with a confirmation prompt.
- Auto-link on workspace load: each slot automatically links to the CueList that matches its position.
- Per-slot PDF and TXT export, with slot label and CueList caption shown in the document header.

### Trigger Manager — VC Frame Parsing Fix

**Fixed**
- Virtual Console frame ancestry is now tracked correctly for **nested frames**. Previously, a button inside a sub-frame reported only its direct parent; it now correctly reports all enclosing frame names at every nesting level.
- The Frame filter in the Trigger Manager now works reliably regardless of how deeply buttons are nested.

---

## [0.6] — 2025

### Fixture Configurator — Function Assignment Panel

**Added**
- New collapsible **Function Assignment Panel** at the bottom of the Fixture Configurator tab.
- Displays all functions parsed from the template workspace, with their type, fixture slot count, and linked description (read from the Dictionary if loaded).
- **Intelligent auto-assignment**: when a template workspace is loaded, functions are automatically matched to rig fixtures using a multi-strategy algorithm:
  1. Name-role matching (e.g. "Front", "Back", "Wash")
  2. Spatial proximity (closest fixture to the template slot's position)
  3. Sequential fallback
- Manual override: per-function assignment can be edited directly in the panel.
- Assignment reads from the shared Dictionary when available, enriching function labels with human-readable descriptions.

---

## [0.5] — 2025

### New Tab: Fixture Configurator

**Added**
- Brand-new **Tab 5 — Fixture Configurator**: a visual stage design tool.
- Load one or more `.qxf` fixture definition files to populate a fixture library.
- Add fixture instances to the rig, set names and assign height roles (5 fixed tiers).
- **Interactive 2D top-down stage canvas**: drag fixtures to set X/Z positions visually.
- Configurable stage dimensions (width, depth, height in metres) via toolbar fields.
- **Auto-DMX**: automatically assigns consecutive universe/address values to all fixtures with one click.
- Load a `.qxw` template workspace (or reuse the one already loaded in the main shell).
- **Generate QXW**: produces a new `.qxw` file where the template's Engine/Fixture blocks are expanded to match the new rig, and 3D Monitor positions (`FxItem`) are updated from the canvas layout.
- Separate template path support: use a different workspace as a template without replacing the active working file.

---

## [0.4] — 2025

### Initial Unified Release

**Added**
- First release of QLC+ Swiss Knife as a unified single-file application.
- **Tab 1 — Setlist Manager**: build show cue lists from plain-text setlists, map to QLC+ functions, generate pristine clones, export PDF.
- **Tab 2 — Dictionary Manager**: create and edit ID→description mapping files to annotate the QLC+ function pool; shared across all tabs.
- **Tab 3 — Setup Checklist**: parse fixture patches, 3D positions, and groups from the workspace; export printable blueprint PDFs and text checklists.
- **Tab 4 — Trigger Manager**: audit and edit all Virtual Console keyboard and MIDI bindings in a spreadsheet-style table; write changes back to the workspace.
- Unified shell with shared workspace state: loading a `.qxw` file once populates all tabs simultaneously.
- Dark / light theme engine (Catppuccin-inspired palette) with per-session toggle.
- Zero external dependencies — pure Python 3 stdlib + tkinter.
- Cross-platform: Windows, macOS, Linux.
