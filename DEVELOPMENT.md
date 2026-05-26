# Development Guide — QLC+ Swiss Knife Web UI (v1.0)

This branch (`web-ui`) is the active development line for the Flask/SPA rewrite of QLC+ Swiss Knife.  
The tkinter version lives on `main` and remains the stable release until v1.0 ships.

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
# Install the single dependency
pip install flask          # or: pip3 install flask

# Start the server (opens browser automatically)
python3 app.py
```

The app opens at `http://localhost:5731`.  Press `Ctrl+C` to quit.

---

## Project structure

```
app.py                  Flask entry point — registers blueprints, auto-opens browser
requirements.txt        Single dependency: flask>=3.0

core/
  workspace.py          Shared state + ALL parsing logic (extracted from 0.7.3)
                        Public API: load_qxw(), get_state(), get_functions(),
                                    get_vc_widgets(), get_fixtures()

routes/
  workspace_routes.py   GET /          → SPA shell
                        POST /api/load → load a .qxw (path or file upload)
                        GET  /api/status
                        POST /api/reload
  id_browser_routes.py  GET /api/functions   ✅ fully wired
                        GET /api/vc-widgets  ✅ fully wired
  setlist_routes.py     stubs — see porting guide below
  dictionary_routes.py  stubs — see porting guide below
  checklist_routes.py   stubs (GET /api/checklist/fixtures already works)
  triggers_routes.py    stubs — see porting guide below
  fixture_routes.py     stubs — see porting guide below

templates/
  index.html            Single-page app shell (all 6 tab panels, ID Browser wired)

static/
  css/style.css         Catppuccin Mocha theme (CSS custom properties)
  js/app.js             Tab switching, file loading, ID Browser, CSV export
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
| Checklist fixtures data (`/api/checklist/fixtures`) | ✅ |
| Setlist Manager | 🔲 stub |
| Dictionary Manager | 🔲 stub |
| Setup Checklist (UI) | 🔲 stub |
| Trigger Manager | 🔲 stub |
| Fixture Configurator | 🔲 stub |

---

## Porting guide — tab by tab

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
- **Important:** the save-back writes directly to the `.qxw` file — use `ET.ElementTree.write()` with the same namespace handling as the original
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

## Branching & release plan

```
main       stable tkinter releases (0.7.x)
web-ui     this branch — Flask/SPA development
```

When every tab is ported and tested:

1. Merge `web-ui` → `main` as **v1.0.0**
2. The `qlc_swiss_knife_0.7.3.py` file is removed (it lives in git history)
3. Tag `v1.0.0`, publish GitHub Release
4. From v1.0 onwards only one codebase to maintain

---

## Dependencies

| Package | Why | Version |
|---|---|---|
| `flask` | HTTP server + routing | ≥ 3.0 |
| Grid.js | Sortable/filterable tables | loaded from CDN (no install) |

No other runtime dependencies.  All QXW/QXF parsing uses Python stdlib (`xml.etree.ElementTree`).  PDF export will use Python stdlib too (same raw-PDF writer from the tkinter version, no reportlab).
