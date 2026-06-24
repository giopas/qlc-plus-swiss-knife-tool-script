# Changelog

All notable changes to QLC+ Swiss Knife are documented here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) conventions.

---

## [1.0.4] — 2026-06-25

### Added — Setlist tab: multi-select songs for bulk assignment

- **Ctrl+click** (or ⌘+click on macOS) toggles individual song rows in the selection; **Shift+click** range-selects from the last anchor.
- All selected rows are highlighted. Clicking a pool function (or pressing ◀ Assign) assigns it to **all selected songs at once**.
- ✕ Clear Song also clears all selected songs in one operation.
- The timing panel shows "— N songs selected —" and disables when multiple rows are active.

### Added — Setlist tab: 🧹 Purge Clones button

- New button in the Assign section unassigns all songs currently linked to `(Setlist)` clones, clearing the slate for fresh matching. Clone function definitions remain in the workspace.

### Added — Setlist tab: 🗑 Delete Clones from WS button

- New **Workspace** section in the Actions pane with a "Delete Clones from WS" button. Unlike Purge Clones (which only unassigns songs), this **removes the `(Setlist)` clone function definitions entirely** from the in-memory XML tree and all state maps. Any songs still assigned to those clones are also unassigned. Use Generate QXW afterwards to save a clean output file without old clones — ideal for starting fresh with a different set of functions without bloating the workspace.

### Fixed — Setlist tab: auto-match prefers base functions over clones

- When both a base function (e.g. `"Stage Patter"`) and its clone (`"Stage Patter (Setlist)"`) exist in the pool, the four-stage auto-matcher now always picks the base function. Clones are still returned when they are the only candidate (e.g. in a gig-ready file where the originals have been removed).

### Fixed — Setlist tab: parent name always shown for (Setlist) clones

- Previously, the `↑ [ID] Parent Name` line below a clone assignment was silently omitted when the base function had been removed from the workspace (e.g. in a gig-ready file). It now always shows the derived base name in dimmed italic so the clone's origin is always traceable regardless of which file is loaded.

---

## [1.0.3] — 2026-06-21

### Added — Dictionary tab: VC button name & frame filters

- **VC Button name filter**: a dedicated text input next to the existing filters lets you search within the VC button caption column specifically (independent of the general search box). Useful for quickly isolating all functions assigned to a button whose caption contains a known keyword.
- **Frame filter dropdown**: a new dropdown is auto-populated from every VC frame (container) found in the loaded workspace. Selecting a frame shows only the functions whose VC buttons live inside that frame. Nested ancestry is supported — a button inside a sub-frame matches its entire ancestor chain.
- **Backend — `vc_frames` field**: `/api/dictionary/` now includes a `vc_frames` array for each entry, listing the deduplicated ancestry of VC frames for that function's button(s). The general search box also searches within frame names.

### Added — Setlist tab: VC button & description in song list

- **Inline VC button name**: each assigned song in the song list now shows the 🎛 VC button caption (in blue monospace) below the function name, pulled live from the function pool.
- **Inline description**: if a description exists for the assigned function, it is shown below the VC button line in italic grey — matching the display style already used in the function pool panel on the right.
- Both lines are only shown when the corresponding data is available; unassigned songs and functions without VC buttons or descriptions are unaffected.

### Added — Setlist tab: show parent function for (Setlist) clones

- Assigned songs that map to a `(Setlist)` clone now show a **↑ [ID] Parent Name** line below the clone name, making it immediately clear which base function the clone was generated from. This helps when re-matching a setlist that was already used once, since auto-match correctly finds the existing clone but the original function wasn't obvious.

### Fixed — Setlist tab: function pool descriptions always up-to-date

- The function pool (right panel) now re-fetches functions every time the Setlist tab is visited, instead of only on the first load. This ensures that descriptions entered or loaded in the Dictionary tab are immediately visible in the pool — which is the primary place descriptions help: identifying the right function to assign to each song.
- Added **↺ refresh button** to the QLC+ Functions panel header to manually re-fetch functions with the latest descriptions without switching tabs.
- **Browse TXT** in the Dictionary tab now syncs all imported descriptions to the server immediately (via new `/api/dictionary/bulk-update` endpoint), so the Setlist pool reflects them as soon as you hit ↺. Previously, Browse TXT was client-side only and descriptions never reached the server's shared state.

---

## [1.0.2] — 2026-06-11

### Added — Trigger Manager enhancements

- **Conflict detector — inline highlighting**: clicking 🔍 Duplicates now highlights conflicting rows directly in the table with a red left border, in addition to reporting the summary in the status bar. Hovering a highlighted row shows a tooltip. Conflict state clears automatically after a Bulk MIDI Shift or when data is reloaded.
- **Bulk MIDI Shift modal**: new ⇄ MIDI Shift button opens a dialog where you can enter a source universe + channel and a target universe + channel. All triggers bound to the source address are reassigned in one operation; the table reloads automatically and reports how many triggers were updated.
- **Assignment Matrix panel**: new ⊞ Matrix button toggles an inline grid panel showing every assigned widget (rows) against every unique key name (columns). Duplicate keys are flagged in red with a ⚠ marker in the column header. Clicking a ✓ cell or a widget row selects that trigger for editing in the side panel.

---

## [1.0.1] — 2026-06-05

### Fixed

- **Blueprint PDF — top-view Z orientation**: downstage/audience was rendered at the top of the plot and upstage/backstage at the bottom, the opposite of both the Swiss Knife canvas and the QLC+ 3D monitor. The Z axis mapping in `core/pdf.py` is now consistent with the canvas (`z = 0` → upstage/top, `z = max` → downstage/audience/bottom).
- **QXW Merger — source and destination loading**: path-only input made it impossible to load files on most systems. Both panels now have a **Browse…** button that opens a native file picker; selecting a file loads it immediately. Path entry still works as before.

---

## [1.0.0] — 2026-05-28

### Full rewrite: Tkinter → Flask web application

v1.0.0 is a ground-up rewrite of the application stack. The seven original tabs are fully ported to a browser-based single-page application (SPA) backed by a local Flask server. The user experience, feature set, and file formats are fully preserved; the delivery mechanism and architecture are new.

### Added — Flask / SPA architecture
- `app.py` — self-bootstrapping Flask entry point: auto-detects `.venv`, installs Flask guidance on first run, opens `http://localhost:5731` automatically.
- `templates/index.html` — single HTML shell with a tab bar, header, and status footer.
- `static/css/style.css` — full Catppuccin theme system: **Dark** (Mocha), **Grey** (Frappé), **Light** (Latte), toggled live with no page reload.
- `static/js/app.js` — tab switching, workspace loading (path mode + upload mode + drag-and-drop), ID Browser (Grid.js tables), CSV export.
- Per-tab JS modules: `setlist.js`, `dictionary.js`, `checklist.js`, `triggers.js`, `fixture.js`, `merger.js`.
- Blueprint-per-tab Flask routes: `workspace_routes.py`, `setlist_routes.py`, `dictionary_routes.py`, `checklist_routes.py`, `triggers_routes.py`, `fixture_routes.py`, `id_browser_routes.py`, `merger_routes.py`.
- `core/workspace.py` — QXW parser, function pool (with `find_best_match` four-stage fuzzy matching), setlist slot engine, slot-details CRUD, `generate_slot_qxw_content()` (returns bytes, not a file path).
- `core/pdf.py` — pure-Python PDF builder (no reportlab): blueprint PDF, setlist PDF, generic table PDF.
- `core/fixture.py` — rig state, QXF definition parsing, DMX auto-assign, canvas-to-workspace QXW generation.

### Added — QXW Merger tab (🔀)
- Load any two `.qxw` files independently of the main workspace via `core/merger.py`.
- Browse Fixtures, Fixture Groups, and Functions from the source file; filter by name or function type.
- Tick elements to copy; the merger assigns new IDs above the destination's highest existing ID and rewrites all internal cross-references (scene fixture vals, chaser step targets, etc.).
- Name-clash warnings displayed inline (⚠) — elements are still copied; user decides.
- Export the merged destination as a new `.qxw` via the native OS Save dialog (`showSaveFilePicker`) with `<a download>` fallback.

### Added — Setlist tab improvements
- FileBot-style three-column layout: Slot list | Song table | Function pool.
- Function pool: usage count (★N), setlist-clone indicator (✦ orange star), Used/Unused filter.
- Auto-match: maps all songs to QLC+ functions in one click using the four-stage fuzzy matcher.
- Per-song timing fields: Fade In, Hold, Fade Out (QLC+ ms values).
- QXW generation: no file written server-side — bytes streamed to browser, saved via `showSaveFilePicker`.
- PDF export: per-slot setlist PDF (paper size selector).

### Added — Header & UI
- Hover tooltips on all major buttons (`[data-tooltip]` CSS pseudo-element system).
- Theme toggle button cycles Dark → Grey → Light.
- Drag-and-drop `.qxw` anywhere on the window.

### Changed — Security hardening
- Upload handler: `.qxw` extension enforced; other extensions rejected with a clear error.
- CSRF protection: all `POST/PATCH/PUT/DELETE` requests validate `Origin` / `Host` against `localhost:5731`.
- Response headers: `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
- Exception messages: filesystem paths stripped via regex before being returned to the browser.
- Server binds to `127.0.0.1` only (localhost; never reachable from the network).

### Removed
- Tkinter desktop UI (`qlc_swiss_knife_0.7.3.py`) — superseded by the web UI. The file is kept in the repository for reference but is no longer the primary entry point.
- Output-directory input box in the header — replaced by the native OS Save dialog.

### Dependencies
- **Added:** `flask` (install once with `pip install flask` or via the provided `.venv` bootstrap).
- **Removed:** `tkinter` (no longer needed).
- Everything else (PDF generation, XML parsing, fuzzy matching) uses Python's standard library only.

---

## [0.7.3] — 2026-05-26

### New Tab: ID Browser — Functions & VC Widgets inspector

**Extended parser — `_parse_vc_node`**
The Virtual Console walker now captures every VC widget type: `Button`, `Frame`, `SoloFrame`, `Slider`, `Knob`, `SpeedDial`, `XYPad`, `Label`, `Clock`, `VUMeter`, `AudioTrigger`, `Animation`, and `CueList`. For each widget the parser stores: widget ID, type, caption, geometry (X / Y / W / H), linked function ID + name, and the full frame ancestry path. Results accumulate in a new shared list `app.vc_widgets`. The existing `vc_buttons` dict is still populated exactly as before — nothing in the other tabs is affected.

**Added — Tab 6: 🔍 ID Browser**

Two inner sub-tabs:

- **⚙ Functions** — all Engine functions from `func_detailed`. Columns: `ID`, icon, `Name`, `Type`, `Contains / Steps`.
- **🖥 VC Widgets** — all Virtual Console widgets from `vc_widgets`. Columns: `Widget ID`, icon, `Type`, `Caption`, `Func ID`, `Func Name`, `Frame Path`, `X`, `Y`, `W`, `H`.

Features shared by both sub-tabs:
- **Sortable columns**: click any column header to sort ascending; click again to reverse. Active sort column shows a ▲ / ▼ arrow.
- **Live filter**: search bar in the toolbar — filters across all visible columns simultaneously.
- **Export CSV**: dumps the currently visible view (with active filter and sort applied) to a UTF-8 CSV file via Python's built-in `csv` module — no extra dependencies.
- **Export PDF**: same raw-PDF renderer used by the Setlist tab, with a paper-size / font-size dialog. Landscape A4 default suits the wider VC Widgets table.

**Updated — status bar**
The status bar now shows `VC Widgets: N` alongside the existing workspace counts.

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
