# Key Modules

*Last Updated: 2026-09-14*

## Core Layer (`core/`)

### core/workspace.py (1620 lines)
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

### core/quick_start/ (sub-package)
- **Purpose:** Quick Start wizard — analyzes fixtures, generates a complete QXW workspace from scratch.
- **fixture_analyzer.py** — Scans QXF definitions for capability flags (RGB, pan/tilt, strobe, dimmer, gobo).
- **qxw_builder.py** — Builds complete QXW XML skeleton from a rig definition.
- **vc_generator.py** (893 lines) — Generates Virtual Console layout (buttons, sliders, frames).
- **template_library.py** — Pre-built skeleton templates for generation.

## Route Layer (`routes/`)

Each file is a Flask Blueprint, one per feature tab. Pattern: imports core module → exposes REST endpoints → returns JSON or file bytes. See [entry-points.md](./entry-points.md) for the full route table.

## Frontend (`static/js/`)

Each JS file corresponds to one UI tab. `app.js` is the SPA core (navigation, workspace loading, ID Browser). No build step — files are served directly by Flask.
