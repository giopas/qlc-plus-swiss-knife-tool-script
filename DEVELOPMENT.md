# Development Guide — QLC+ Swiss Knife

`main` is the active line: a Flask server plus a single-page web UI (the old tkinter app lives on the `legacy-tkinter` branch).
The plan of record is [WORKPLAN.md](WORKPLAN.md); [ROADMAP.md](ROADMAP.md) is the short version.

---

## Engineering principles (apply to every change)

1. **Never overwrite.** Every write produces a new file: `<name>_v<N+1>.qxw` for edits, `<name>_doctor.qxw` for Doctor fixes. The original is never touched.
2. **One writer.** All QXW output goes through `core/qxw_io` (`qxw_bytes()`, `write_qxw()`, `next_version_path()`). Never call `ElementTree.write()` or build the `<!DOCTYPE Workspace>` header by hand — `tests/test_qxw_io.py` fails if you do. Load with `qxw_io.load_qxw()` (pass `strip_namespace=True` if you want plain tag names).
3. **Deterministic IDs and ordering.** New IDs are `max(existing) + 1` in a stable order; no timestamps or random values in generated XML; golden-file tests compare bytes.
4. **Doctor gates every export** (from v1.4). Errors block the export; warnings are shown.
5. **Safe-by-default show content.** Generated scenes declare every channel of every fixture they touch, keep strobe/program channels at 0 unless asked, and there is always a PANIC RESET. VC buttons and chaser steps never share a scene.
6. **QLC+ is the reference.** Run the manual QLC+ open-check (WORKPLAN §6) before every release.
7. **Conventions are data, not code** — JSON profiles, not hard-coded names.
8. **Tests and CI green before merge.**
9. **One way to open files.** Tools that use the open workspace rely on the header **📂 Open…** (and the `.need-ws` banner, see `_WS_SCREENS` in `app.js`); every *Browse…* goes through `nativePick()` / `pickQxwInto()` and falls back to `<input type=file>` only when `nativePick.unavailable`. Uploads must keep the original file name.
10. **Every VC edit is undoable.** Client-side edits go through the wrapped `vce*` functions (local snapshots); anything that changes the server's XML must call `ws.vc_snapshot()` first (see `vc_structural_edit`, `/api/vc/patch`).

## Tests

```bash
pip install flask pytest
python -m pytest -q          # whole suite (pytest.ini sets testpaths = tests)
```

* Tests live in `tests/`; sample fixture definitions in `tests/fixtures/`, real show files in `tests/corpus/` (do not edit them).
* `tests/manual/tilt_check.qxw` (regenerate with `python tools/make_tilt_check.py`) is for checking fixture tilt in the QLC+ 5 3D view.
* CI runs the suite on Python 3.11 and 3.12 for every push and PR (`.github/workflows/tests.yml`).

## Git workflow

* One branch per phase (`chore/phase0-cleanup`, `feat/doctor`, …); merge to `main` when CI is green; tag releases `vX.Y.Z`.
* [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:` — small, one logical change each.
* Every change adds a `CHANGELOG.md` entry under `## [Unreleased]`. At release, bump `VERSION` in `core/workspace.py` (single source of truth) and move `[Unreleased]` to `[X.Y.Z] — date`.

---

## Architecture overview

```
Browser (SPA)  ←→  Flask (localhost:5731)  ←→  .qxw file on disk
```

* **Flask** is the server.  It holds the parsed workspace in memory (`core/workspace.py`), serves the HTML shell once, and answers JSON API calls from the browser.
* **The browser** renders everything.  Tab switches, filter input, table sorting — all happen client-side with no page reloads.
* **One file, one source of truth.**  Load a `.qxw` once; every tab reads the same parsed state.

---

## How to run

```bash
# Install the dependency (pywebview is optional, for a native window)
pip install flask          # or: pip3 install flask

# Start the server (opens browser automatically)
python3 app.py
```

The app opens at `http://localhost:5731`.  Press `Ctrl+C` to quit.

---

## Project structure

*Partial and historical — see `.claude/.codebase-info/directory-structure.md` for the current map. Key additions since: `core/qxw_io.py` (the single QXW reader/writer), `core/porter.py`, `core/qxf_parser.py`, `core/showbook.py`, `core/quick_start/`.*

```
app.py                  Flask entry point — registers blueprints, auto-opens browser
requirements.txt        Single dependency: flask>=3.0

core/
  workspace.py          Shared state + ALL parsing logic.
                        Public API: load_qxw(), get_state(), get_functions(),
                                    get_vc_widgets(), get_fixtures(),
                                    get_triggers(), update_trigger(), save_triggers(),
                                    get_dictionary(), update_description(),
                                    load_dictionary(), save_dictionary(),
                                    get_cuelist_slots(), get_slot_songs(), set_slot_songs()

routes/
  workspace_routes.py   GET /          → SPA shell
                        POST /api/load → load a .qxw (path or file upload)
                        GET  /api/status
                        POST /api/reload
  id_browser_routes.py  GET /api/functions      ✅
                        GET /api/vc-widgets     ✅
  setlist_routes.py     GET  /api/setlist/slots           ✅
                        GET  /api/setlist/<id>/songs      ✅
                        POST /api/setlist/<id>/songs      ✅
                        POST /api/setlist/load            ✅
                        POST /api/setlist/save            ✅
  dictionary_routes.py  GET  /api/dictionary/             ✅
                        PATCH /api/dictionary/<fid>       ✅
                        POST /api/dictionary/load         ✅
                        POST /api/dictionary/save         ✅
  checklist_routes.py   GET  /api/checklist/fixtures      ✅
                        POST /api/checklist/export-txt    ✅
  triggers_routes.py    GET  /api/triggers/               ✅
                        GET  /api/triggers/duplicates     ✅
                        PATCH /api/triggers/<uid>         ✅
                        POST /api/triggers/save           ✅
  fixture_routes.py     GET  /api/fixture/rig             ✅

templates/
  index.html            Single-page app shell — all 6 tabs fully implemented

static/
  css/style.css         Catppuccin Mocha theme (CSS custom properties)
  js/app.js             Tab switching, file loading, ID Browser, invalidation
  js/setlist.js         Setlist Manager tab logic
  js/dictionary.js      Dictionary Manager tab logic
  js/checklist.js       Setup Checklist tab logic
  js/triggers.js        Trigger Manager tab logic
  js/fixture.js         Fixture tab logic
```

---

## What works today

| Feature | Status |
|---|---|
| File load — path input | ✅ |
| File load — drag & drop | ✅ |
| File load — browse button | ✅ |
| Reload from disk | ✅ |
| Status bar counts | ✅ |
| **ID Browser — Functions** | ✅ sortable, filterable, CSV export |
| **ID Browser — VC Widgets** | ✅ sortable, filterable, CSV export |
| **Setlist Manager** | ✅ slot list, song editor, load/save TXT |
| **Dictionary Manager** | ✅ editable table, load/save TXT |
| **Setup Checklist** | ✅ sortable fixture table, export TXT |
| **Trigger Manager** | ✅ editable table, MIDI/key edit, save to QXW, duplicates check |
| **Fixture tab** | ✅ read-only workspace fixture table |
| Fixture Configurator (canvas / QXF / QXW generation) | 🔲 planned for v1.1 |

---

## Porting guide — tab by tab *(historical: the tkinter → web port is complete)*

Each tab follows the same three-step pattern:

1. **Extract logic into `core/`** — move the parsing/mutation Python from the old monolith.
2. **Add routes** — write Flask endpoints that call the core functions and return JSON.
3. **Build the UI** — add a new `<section>` in `index.html` and a matching JS module in `static/js/`.

### Tab 1 — Setlist Manager
- **Core logic location:** `SetlistSlot` + `SetlistManagerTab` in `qlc_swiss_knife_0.7.3.py`
- **Key data:** cuelist slots, per-slot song lists, chaser cloning
- **Frontend:** slot tabs (JS `<ul>/<li>` nav), song list editor (editable grid or textarea), generate/export buttons
- **New file:** `core/setlist.py`, `static/js/setlist.js`
- **Routes:** `routes/setlist_routes.py` (stubs already in place with endpoint plan)

### Tab 2 — Dictionary Manager
- **Core logic location:** `DictionaryManagerTab`
- **Key data:** `shared_descriptions` dict (already in `ws._state`)
- **Frontend:** editable two-column table (ID / description), load/save buttons
- **New file:** `core/dictionary.py`, `static/js/dictionary.js`

### Tab 3 — Setup Checklist
- **Core logic location:** `SetupChecklistTab`
- **Key data:** `ws.get_fixtures()` already works — just needs the UI + PDF export
- **Frontend:** read-only fixture table (can reuse Grid.js), export buttons
- **PDF export:** port `_export_blueprint_pdf()` to write bytes → `Response(bytes, mimetype='application/pdf')`
- **New file:** `static/js/checklist.js`

### Tab 4 — Trigger Manager
- **Core logic location:** `TriggerManagerTab`
- **Key data:** vc_widgets + KeySequence/Input nodes from raw XML (need a second pass in `_parse_vc_node`)
- **Frontend:** editable Grid.js table (key, MIDI, function assignment per row), save-back button
- **Save-back:** writes `<name>_v<N+1>.qxw` next to the loaded file via `core/qxw_io.write_qxw()` — never in place
- **New file:** `core/triggers.py`, `static/js/triggers.js`

### Tab 5 — Fixture Configurator
- **Core logic location:** `FixtureConfiguratorTab`
- **Canvas:** replace tkinter `Canvas` with HTML5 `<canvas>` — drag-and-drop positioning is **easier** in the browser than in tkinter
  - `mousedown` → `mousemove` → `mouseup` for drag
  - `PATCH /api/fixture/rig/<id>` updates position in `ws._state`
- **QXF parser:** port `_parse_qxf()` → `core/fixture.py`
- **Generate QXW:** port `_build_qxw()` → server returns a downloadable file
- **New file:** `core/fixture.py`, `static/js/fixture.js`

---

## API conventions

All endpoints return JSON.  Error responses always include an `error` key:

```json
{ "error": "No workspace loaded." }
```

Success responses return the relevant data array or dict.  A successful load returns the full `get_state()` dict so the frontend can update the header and status bar in one round-trip.

For endpoints that write files (save triggers, generate QXW), return `{"ok": true, "path": "..."}` on success.

---

## Dependencies

| Package | Why | Version |
|---|---|---|
| `flask` | HTTP server + routing | ≥ 3.0 |
| Grid.js | Sortable/filterable tables | loaded from CDN (no install) |

No other runtime dependencies.  All QXW/QXF parsing uses Python stdlib (`xml.etree.ElementTree`).  PDF export will use Python stdlib too (same raw-PDF writer from the tkinter version, no reportlab).
