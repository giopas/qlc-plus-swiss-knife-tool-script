# Changelog

All notable changes to QLC+ Swiss Knife are documented here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) conventions.

---

## [0.7.2] — 2026-05-26

### Security hardening release
*Fixes 9 security issues identified in a full static + manual audit of v0.7.1. No functional changes; all existing behaviour is preserved.*

**Fixed — MEDIUM: XML injection in "Export XML Code" (`export_txt`)**
The chaser name was embedded raw into an f-string XML template. A workspace with a specially crafted function name could produce an injected, malformed exported XML block. `xml.sax.saxutils.escape` (stdlib, zero new dependencies) is now applied to the name before embedding.

**Fixed — MEDIUM: Denial-of-service via oversized XML ("billion laughs")**
All four `ET.parse()` call sites (`load_qxw()`, `_parse_qxf()`, `_load_template_dialog()`, `_get_template_root()`) are replaced by a new `_safe_parse_xml()` helper that enforces a 50 MB file-size cap before handing off to the parser. Community-shared QXW/QXF files are a realistic delivery vector.

**Fixed — LOW: XPath injection via f-string query construction (6 sites)**
XPath predicates in `rename_chaser_to_cuelist()`, `SetlistSlot.save_qxw()`, `save_all_slots()`, and `DictionaryManagerTab.update_inspector()` were built by interpolating XML attribute values into f-strings. A new `_find_by_id()` helper iterates child elements directly instead, eliminating any possibility of XPath metacharacter injection.

**Fixed — LOW: Negative-index bypass in QXW generation (`_build_qxw`)**
Unassigned fixture slots stored `-1` in `_func_assignments`. The guard only blocked values ≥ `new_count`, so `-1` passed through and produced `<FixtureVal ID="-1">` — an invalid reference that silently breaks functions in QLC+. Guard changed to `0 <= idx < new_count`.

**Fixed — LOW: Unbounded file reads into memory (3 sites)**
`SetlistSlot.load_txt()`, `SetlistManagerTab.load_desc()`, and `DictionaryManagerTab.load_txt()` called `readlines()` with no size guard. A new `_safe_read_txt()` helper enforces a 5 MB cap before reading.

**Fixed — LOW: Unbounded integer parsing for DMX values (7 sites)**
Universe, address, and channel numbers from XML were converted with bare `int()` and no range validation. All sites now clamp to valid DMX ranges on parse (universe 0–255, address 0–511, channels 1–512).

**Fixed — LOW: TOCTOU race condition in file save (3 sites)**
`SetlistSlot.save_qxw()`, `SetlistManagerTab.save_all_slots()`, and `TriggerManagerTab.save_qxw()` checked `os.path.exists()` then opened with `open("w")`, creating a race window. Fixed by using Python's `'x'` (exclusive-create) open mode for new files.

**Fixed — INFORMATIONAL: Silent exception swallowing (2 sites)**
Two `except Exception: pass` clauses in `FixtureConfiguratorTab` now log a `[warn]` line to stderr instead of silently discarding errors.

**Fixed — INFORMATIONAL: Missing namespace validation in QXF parser**
If a non-QXF XML file was opened accidentally, `findtext()` calls would silently return `"Unknown"` for every field. A namespace check is now performed immediately after parsing and raises a clear `ValueError` if the root element is wrong.

**Added**
- `_safe_parse_xml(path)` — central XML parsing entry point with 50 MB size guard (replaces 4 direct `ET.parse()` call sites)
- `_safe_read_txt(path)` — central text-file reader with 5 MB size guard (replaces 3 direct `open()/readlines()` call sites)
- `_find_by_id(parent, tag_local, fid)` — safe XPath-free element lookup by ID attribute (replaces 6 f-string XPath constructions)
- `_findall_by_id(parent, tag_local, fid)` — as above, returns all matching children as a list

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
