# Key Modules

*Last Updated: 2026-09-25*

## Core Layer (`core/`)

### core/workspace.py (1673 lines)
- **Purpose:** Central state singleton and QXW workspace parser. THE source of truth for loaded workspace data.
- **Key exports:** `_state` dict, `load_workspace()`, `save_workspace()`, `NS`, `QLC_NS_URI`, `VERSION`
- **State holds:** `xml_tree`, `qxw_root`, `fixture_map`, `group_map`, `func_by_name`, `func_by_id`, `clone_base_map`, VC widget data, and more.
- **Depends on:** stdlib only (`xml.etree.ElementTree`, `copy`, `difflib`, `re`)

### core/fixture.py (668 lines)
- **Purpose:** Fixture Configurator — manage a rig of fixtures, load QXF definitions, generate QXW fixture XML.
- **Key exports:** `get_rig()`, `add_fixture()`, `load_qxf()`, `clear_rig()`, `get_qxf_defs()`
- **Depends on:** `core.qxf_parser`

### core/qxf_parser.py (621 lines)
- **Purpose:** Deep QXF fixture definition parser. Extracts per-channel groups, presets, capability ranges, modes, physical data, 16-bit pairing.
- **Key exports:** `parse_qxf()`, `decode_value()` (raw DMX → human label)
- **Depends on:** stdlib only

### core/brightness.py (780 lines)
- **Purpose:** Per-fixture brightness scaling. Scales Master Dimmer channel in Scenes, preserving colour ratios.
- **Key exports:** `scan_fixtures()`, `apply_brightness()`, `preview()`
- **Depends on:** `core.workspace`, `core.gh_fetch`

### core/merger.py (423 lines)
- **Purpose:** QXW file merger. Loads two workspaces independently, copies Fixtures/Groups/Functions from source to destination with safe ID remapping.
- **Key exports:** `load_src()`, `load_dst()`, `copy_elements()`, `export_dst()`
- **State:** Own `_src` / `_dst` dicts — independent of `workspace._state`

### core/porter.py (943 lines)
- **Purpose:** Cross-workspace function import with dependency resolution, ID rebasing, fixture remapping.
- **Key exports:** `load_source()`, `load_target()`, `resolve_closure()`, `execute()`
- **State:** Own `_src` / `_tgt` dicts
- **See also:** `porter_vc.py` for Virtual Console widget porting

### core/porter_vc.py (505 lines)
- **Purpose:** Virtual Console porting for the Function Porter. Brings VC widgets of ported functions into the target workspace with ID remapping, pruning, and automatic placement.
- **Key exports:** VC widget copy/remap logic integrated with porter execution
- **Depends on:** `core.vc_ops`, `core.qxw_io`

### core/qxw_io.py (179 lines)
- **Purpose:** Single centralised QXW reader/writer. ALL workspace file I/O goes through here.
- **Key exports:** `load_qxw()`, `save_qxw()`, `next_version_path()`, `OverwriteError`
- **Rules:** Preserves `<!DOCTYPE Workspace>` (QLC+ requires it), never overwrites source files, deterministic output, 50 MB size cap.
- **Depends on:** stdlib only

### core/vc_ops.py (358 lines)
- **Purpose:** Structural Virtual Console edits for the VC Visual Editor: copy/move widgets between frames and pages, duplicate pages, create empty pages.
- **Key exports:** `copy_widgets()`, `move_widgets()`, `duplicate_page()`, `VcOpError`
- **Rules:** Copies get fresh widget IDs (deterministic), moves keep IDs. Refuses when duplicate widget IDs exist (points to Doctor D002).
- **Depends on:** `core.qxw_io`

### core/showbook.py (1142 lines)
- **Purpose:** Show Book document generator. Produces structured show documentation (patch lists, function details, chaser timings, VC layout, stats). Exports as PDF or CSV ZIP.
- **Key exports:** `generate()`, `export_pdf()`, `export_csv()`
- **Depends on:** `core.workspace`, `core.fixture`, `core.qxf_parser`, `core.pdf`

### core/pdf.py (556 lines)
- **Purpose:** Raw PDF builder using only stdlib (`zlib`, `datetime`). No external PDF library.
- **Key exports:** `assemble_pdf()`, `build_blueprint_pdf()`, `build_setlist_pdf()`, `build_table_pdf()`

### core/session.py (167 lines)
- **Purpose:** `.qsk` project file I/O. Saves/loads which workspace, dictionary, and setlist files are part of a session.
- **Key exports:** `save_session()`, `load_session()`, `get_recent()`

### core/gh_fetch.py
- **Purpose:** Shared GitHub API helpers for fetching QXF fixture definitions from the official QLC+ repository.
- **Key exports:** `gh_get()`, `gh_get_raw()`, `norm_name()`, `GH_API_BASE`, `GH_RAW_BASE`
- **External:** Makes HTTP requests to `api.github.com` and `raw.githubusercontent.com`

### core/doctor/ (sub-package)
- **Purpose:** Workspace Doctor — read-only check engine for QXW files. Detects common problems (duplicate widget IDs, unassigned channels, risky strobe/shutter values, orphan functions, etc.) with severity levels (error/warning/info).
- **checks.py** (627 lines) — All check functions. Works on namespace-stripped deep copy, never mutates input.
- **report.py** — `Finding` and `Report` data classes, text/JSON formatting.
- **__main__.py** — CLI: `python -m core.doctor FILE.qxw [--qxf PATH] [--json]`. Exit 0=clean, 1=errors, 2=usage.
- **Key exports:** `check_file()`, `load_qxf_defs()`, `Report`, `Finding`
- **Depends on:** `core.qxw_io`

### core/quick_start/ (sub-package)
- **Purpose:** Quick Start wizard — analyzes fixtures, generates a complete QXW workspace from scratch with mode-aware channels, neutral values, naming profiles, and VC style cloning.
- **fixture_analyzer.py** (235 lines) — Scans QXF definitions for capability flags (RGB, pan/tilt, strobe, dimmer, gobo).
- **channel_model.py** (100 lines) — Mode-aware channel lists; computes per-channel "neutral" DMX values from QXF capabilities (e.g. shutter open ≠ 0).
- **nomenclature.py** (141 lines) — Function-naming convention profiles loaded from JSON. Supports custom letter-pair prefixes per fixture group and effect kind.
- **qlc_library.py** (135 lines) — Detects installed QLC+ fixture definitions on macOS/Linux/Windows. Writes `.qxf` next to exported workspace only for fixtures the library lacks.
- **qxw_builder.py** (246 lines) — Builds complete QXW XML skeleton from a rig definition.
- **vc_generator.py** (909 lines) — Generates Virtual Console layout (buttons, sliders, frames, SHOW frame, fixture groups, matrix effects, PANIC RESET).
- **vc_style.py** (173 lines) — Extracts VC style (button size, gaps, fonts, page size) from a reference workspace for style cloning.
- **template_library.py** (38 lines) — Pre-built skeleton templates for generation.
- **profiles/** — JSON naming-convention profiles (e.g. `prefix.json`, `plain.json`).

## Route Layer (`routes/`)

Each file is a Flask Blueprint, one per feature tab. Pattern: imports core module → exposes REST endpoints → returns JSON or file bytes. See [entry-points.md](./entry-points.md) for the full route table.

## Frontend (`static/js/`)

Each JS file corresponds to one UI tab. `app.js` is the SPA core (navigation, workspace loading, ID Browser). No build step — files are served directly by Flask.
