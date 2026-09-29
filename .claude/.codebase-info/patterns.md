# Patterns

*Last Updated: 2026-09-27*

## XML Handling

- **Namespace:** QLC+ workspace XML uses namespace `http://www.qlcplus.org/Workspace`. Registered globally in `core/workspace.py` via `ET.register_namespace('', QLC_NS_URI)`. All XPath queries use `NS = {'q': QLC_NS_URI}`.
- **QXF namespace:** Fixture definitions use `http://www.qlcplus.org/FixtureDefinition`, handled separately in `core/qxf_parser.py` and `core/brightness.py`.
- **Safety limits:** `_MAX_XML_BYTES = 50 MB`, `_MAX_TXT_BYTES = 5 MB` (in `workspace.py`).
- **Centralised I/O:** `core/qxw_io.py` is the single place where QXW files are read (`load_qxw()`) and written (`save_qxw()`). Preserves `<!DOCTYPE Workspace>` (QLC+ refuses files without it). Never overwrites source files — callers pass protected paths and new files get versioned names (`_v2`, `_v3`…). Output is deterministic.
- **Namespace stripping:** `load_qxw(path, strip_namespace=True)` returns plain tags (`"Engine"` instead of `"{http://…}Engine"`). Used by Doctor and VC operations for simpler XPath.
- **Parse pattern:** `ET.parse()` → keep `xml_tree` and `qxw_root` alive in state for save-back. Never use `ET.fromstring()` for workspace files (need the tree for writing).

## State Management

- **Singleton dicts:** Each domain has its own module-level state dict:
  - `workspace._state` — main loaded workspace
  - `merger._src` / `merger._dst` — merger's two independent workspaces
  - `porter._src` / `porter._tgt` — porter's source and target
  - `fixture._qxf_defs` / `fixture._rig` — fixture configurator
- **VC operations** (`vc_ops.py`) work on the in-memory tree (`_state['qxw_root']`) and never touch disk; the user saves via "Apply & Save QXW…" which writes through `qxw_io`.
- **No shared mutable state** between core modules (except `workspace._state` which brightness, showbook, setlist etc. read from).
- **Thread safety:** Not a concern — single-user, Flask runs with `use_reloader=False`.

## Error Handling

- **Route-level pattern:** Routes wrap core calls in try/except, use `_safe_err()` to strip filesystem paths from error messages before returning to client.
  ```python
  def _safe_err(exc):
      return re.sub(r'(/[\w/.\- ]+|[A-Za-z]:\\[\w\\.\- ]+)', '<path>', str(exc))
  ```
- **HTTP errors:** Routes return `jsonify({'error': message}), 4xx/5xx`. Frontend checks `response.ok` and shows error toasts.
- **No global exception handler** — each route handles its own errors.

## ID Remapping (Merger & Porter)

When copying elements between workspaces, IDs must be remapped to avoid collisions:
- Find the maximum existing ID in the target workspace.
- Rebase all source IDs by adding the max + 1 offset.
- Update all internal cross-references (fixture refs in functions, function refs in collections/chasers).
- Pattern used in `core/merger.py`, `core/porter.py`, `core/porter_vc.py`, and `core/porter_input.py`.
- **Porter VC porting:** `porter_vc.py` extends the pattern for Virtual Console widgets — copies widget units, remaps function and fixture IDs, prunes widgets whose functions weren't ported, and places units on the target page without overlapping existing widgets.

## PDF Generation

`core/pdf.py` builds PDF files from raw bytes — no external library. Pattern:
1. Build page content as a list of PDF stream operations (text positioning, fonts, lines).
2. `assemble_pdf(pages, W, H)` wraps them in a valid PDF structure with cross-reference table.
3. Uses `zlib.compress()` for stream compression.

## Capability-Based Value Translation

`core/capability_map.py` translates scene values between **different fixture types** (e.g. RGB PAR → moving head with colour wheel):
- Source values are decoded into an abstract `LookState` (dimmer level, colour, pan/tilt degrees, shutter state, gobo slot).
- The `LookState` is re-encoded onto the target fixture's channels using its QXF definition and selected mode.
- Colour matching: RGB mixing emitters → RGB, or nearest colour-wheel slot by normalised colour distance.
- Pan/tilt: centre-relative degrees via QXF `PanMax`/`TiltMax`, clamped to target range; 16-bit when the mode has fine channels.
- Unmapped capabilities (prism, macros, zoom) → neutral values from `channel_model`.

## Workspace Doctor

`core/doctor/` is a read-only check engine for QXW files:
- Works on a namespace-stripped deep copy — never mutates the input tree.
- Findings have three severities: `ERROR`, `WARNING`, `INFO`.
- Checks include: duplicate widget IDs (D002), unassigned channels, risky shutter/strobe values at DMX 0, orphan functions, input bindings saved as UID only, and more.
- CLI: `python -m core.doctor Show.qxw --qxf fixtures/ [--json]` (exit 0=clean, 1=errors).
- Can gate other operations (e.g. Porter refuses if Doctor finds critical issues).

## Testing

- **Framework:** pytest
- **CI:** GitHub Actions runs pytest on push and PR (Python 3.11 + 3.12).
- **Test suite:** 20 test files under `tests/` covering porter, porter fan-in, qxf_parser, quick_start (golden output, modes, profiles), doctor, vc_ops, qxw_io, session tools, triggers, corpus baselines, UI consistency, and live QLC+ checks.
- **Test corpus:** `tests/corpus/` contains real-show QXW/QXF files with `expected_baseline.json` for regression testing.
- **Sample fixtures:** `tests/fixtures/` (Chauvet and generic QXF files).
- **Developer tools:** `tools/qlc_check.py` — opens a generated QXW in a live QLC+ instance and checks it responds (used in test_qlc_live.py).

## Configuration

- **No .env files.** Configuration is minimal and hardcoded:
  - `PORT = 5731` in `app.py`
  - `VERSION = "1.4.0"` in `core/workspace.py`
- **User settings:** `settings.json` (gitignored) stores `user_name` only.
- **Session persistence:** `.qsk` JSON files store which workspace + companion files were loaded.
