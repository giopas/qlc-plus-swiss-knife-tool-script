# Patterns

*Last Updated: 2026-09-14*

## XML Handling

- **Namespace:** QLC+ workspace XML uses namespace `http://www.qlcplus.org/Workspace`. Registered globally in `core/workspace.py` via `ET.register_namespace('', QLC_NS_URI)`. All XPath queries use `NS = {'q': QLC_NS_URI}`.
- **QXF namespace:** Fixture definitions use `http://www.qlcplus.org/FixtureDefinition`, handled separately in `core/qxf_parser.py` and `core/brightness.py`.
- **Safety limits:** `_MAX_XML_BYTES = 50 MB`, `_MAX_TXT_BYTES = 5 MB` (in `workspace.py`).
- **Parse pattern:** `ET.parse()` → keep `xml_tree` and `qxw_root` alive in state for save-back. Never use `ET.fromstring()` for workspace files (need the tree for writing).

## State Management

- **Singleton dicts:** Each domain has its own module-level state dict:
  - `workspace._state` — main loaded workspace
  - `merger._src` / `merger._dst` — merger's two independent workspaces
  - `porter._src` / `porter._tgt` — porter's source and target
  - `fixture._qxf_defs` / `fixture._rig` — fixture configurator
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
- Pattern used in both `core/merger.py` and `core/porter.py`.

## PDF Generation

`core/pdf.py` builds PDF files from raw bytes — no external library. Pattern:
1. Build page content as a list of PDF stream operations (text positioning, fonts, lines).
2. `assemble_pdf(pages, W, H)` wraps them in a valid PDF structure with cross-reference table.
3. Uses `zlib.compress()` for stream compression.

## Testing

- **Framework:** pytest
- **Test files:** `test_porter.py`, `test_qxf_parser.py` (root), `tests/test_quick_start.py`
- **Fixtures:** Sample QXF files in `tests/fixtures/` (Chauvet models)
- **Coverage:** Focused on core logic (porter, qxf_parser, quick_start). Routes and UI are not unit-tested.

## Configuration

- **No .env files.** Configuration is minimal and hardcoded:
  - `PORT = 5731` in `app.py`
  - `VERSION = "1.3.0"` in `core/workspace.py`
- **User settings:** `settings.json` (gitignored) stores `user_name` only.
- **Session persistence:** `.qsk` JSON files store which workspace + companion files were loaded.
