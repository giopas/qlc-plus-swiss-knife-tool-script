# Architecture

*Last Updated: 2026-09-14*

## Summary

QLC+ Swiss Knife is a local-only desktop tool that reads, manipulates, and generates QLC+ v5 workspace files (`.qxw`) and fixture definitions (`.qxf`). It runs a Flask HTTP server on `localhost:5731` serving a single-page application. The UI is vanilla JavaScript communicating with the backend via a REST-style JSON API.

The application has three layers: **core logic** (pure Python — XML parsing, state, generation), **route layer** (Flask blueprints that expose the core as HTTP endpoints), and **frontend** (one Jinja2 template + modular JS files + CSS). An optional pywebview wrapper provides a native OS window; without it, the app opens in the default browser.

All state lives in module-level Python dicts (singletons). There is no database — the QXW/QXF XML files are the persistent store. The tool is single-user, single-process, localhost-only.

## High-Level Diagram

```
┌─────────────────────────────────────────────────────┐
│                     Frontend (SPA)                   │
│  templates/index.html  ·  static/js/*.js  ·  CSS     │
│  Grid.js (CDN) for tables  ·  vanilla JS fetch()     │
└──────────────────────────┬──────────────────────────┘
                           │ HTTP  localhost:5731
┌──────────────────────────┴──────────────────────────┐
│                  Flask Route Layer                    │
│  routes/*.py  — one Blueprint per feature tab         │
│  CSRF origin check  ·  security headers               │
└──────────────────────────┬──────────────────────────┘
                           │ Python imports
┌──────────────────────────┴──────────────────────────┐
│                   Core Logic Layer                    │
│  core/workspace.py  — singleton state + QXW parser    │
│  core/fixture.py    — fixture configurator            │
│  core/qxf_parser.py — deep QXF parser                 │
│  core/brightness.py — dimmer scaling                  │
│  core/merger.py     — QXW merge engine                │
│  core/porter.py     — cross-workspace function import │
│  core/showbook.py   — show doc generator (PDF/CSV)    │
│  core/pdf.py        — raw PDF builder (stdlib only)   │
│  core/session.py    — .qsk project file I/O           │
│  core/gh_fetch.py   — GitHub QXF repo helpers         │
│  core/quick_start/  — wizard: analyze→generate QXW    │
└─────────────────────────────────────────────────────┘
         │                          │
    QXW / QXF / TXT            GitHub API
    (local files)         (fixture definitions)
```

## Data Flow

**Typical request flow — loading a workspace:**

1. User drops a `.qxw` file or clicks "Open" → JS sends `POST /api/workspace/load` with path or file upload.
2. `workspace_routes.py` calls `core.workspace.load_workspace(path)`.
3. `workspace.py` parses the QXW XML via `xml.etree.ElementTree`, populates `_state` dict (fixture map, function map, group map, VC widgets, etc.).
4. Route returns a JSON summary to the frontend.
5. Subsequent feature tabs (Setlist, Triggers, Brightness, etc.) read from `workspace._state` and return tab-specific data.

**Generating output (e.g. setlist PDF):**

1. JS sends `POST /api/setlist/export-pdf` with song data.
2. `setlist_routes.py` calls `core.pdf.build_setlist_pdf(...)`.
3. `pdf.py` builds raw PDF bytes using only stdlib (`zlib`, `datetime`) — no external PDF library.
4. Route returns the PDF as `application/pdf`.

## Key Decisions & Constraints

- **Zero mandatory external deps beyond Flask.** pywebview is optional. PDF generation uses raw PDF construction (no reportlab/weasyprint). This keeps installation trivial.
- **Module-level singleton state** (`workspace._state`, `merger._src/_dst`, `porter._src/_tgt`). Safe because the tool is single-user, localhost-only.
- **QLC+ XML namespace handling** is critical: `QLC_NS_URI = 'http://www.qlcplus.org/Workspace'` registered globally; all XPath queries use `NS = {'q': QLC_NS_URI}`.
- **No database.** The `.qxw` XML file IS the data store. `.qsk` JSON files save session state (which files were loaded).
- **GitHub API** is the only external network call — used to fetch fixture definitions from the official QLC+ repo. Always disclosed to the user before calling.
