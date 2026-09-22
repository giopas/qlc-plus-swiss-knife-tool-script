# Entry Points

*Last Updated: 2026-09-14*

## Application Bootstrap

| Entry point | Purpose | File |
|-------------|---------|------|
| `python3 app.py` | Main entry — creates Flask app, starts server on `:5731` | `app.py` |
| `python3 app.py --browser` | Force browser mode (skip pywebview) | `app.py` |
| `bash run.sh` | Auto-creates venv, installs Flask, launches app | `run.sh` |
| `launchers/QLC_Swiss_Knife.bat` | Windows launcher | `launchers/` |
| `launchers/create-macos-app.sh` | Creates macOS .app bundle | `launchers/` |

## Bootstrap Sequence

1. `app.py` self-bootstraps: if Flask is not importable, re-execs under `.venv/` Python.
2. `create_app()` registers 15 Flask Blueprints + CSRF middleware + security headers.
3. If pywebview is available (and `--browser` not passed): starts Flask in a daemon thread, opens a native window via `webview.create_window()`.
4. Otherwise: opens browser to `http://localhost:5731`, runs Flask in the main thread.

## API Route Groups

All routes are JSON APIs under `/api/`:

| Blueprint | Prefix | Key endpoints | Routes file |
|-----------|--------|---------------|-------------|
| workspace | `/api/workspace` | `load`, `info`, `save`, `functions`, `vc-widgets` | `routes/workspace_routes.py` |
| setlist | `/api/setlist` | `songs`, `load-txt`, `export-pdf`, `export-csv`, `generate` | `routes/setlist_routes.py` |
| session | `/api/session` | `save`, `load`, `recent`, `extend` | `routes/session_routes.py` |
| quickstart | `/api/quickstart` | `templates`, `analyze`, `generate`, `effects` | `routes/quick_start_routes.py` |
| fixture | `/api/fixture` | `rig`, `add`, `update`, `remove`, `load-qxf`, `stage` | `routes/fixture_routes.py` |
| brightness | `/api/brightness` | `scan`, `apply`, `preview`, `github-search` | `routes/brightness_routes.py` |
| porter | `/api/porter` | `load-source`, `load-target`, `resolve`, `execute` | `routes/porter_routes.py` |
| merger | `/api/merger` | `load-src`, `load-dst`, `copy`, `export` | `routes/merger_routes.py` |
| id_browser | `/api/functions`, `/api/vc-widgets` | List all functions / VC widgets | `routes/id_browser_routes.py` |
| dictionary | `/api/dict` | `load`, `save`, `apply` | `routes/dictionary_routes.py` |
| checklist | `/api/checklist` | `scan`, `items` | `routes/checklist_routes.py` |
| techrider | `/api/techrider` | `generate` | `routes/techrider_routes.py` |
| triggers | `/api/triggers` | `list`, `save` | `routes/triggers_routes.py` |
| showbook | `/api/showbook` | `generate`, `export-pdf`, `export-csv` | `routes/showbook_routes.py` |
| picker | `/api/picker` | `file`, `folder`, `save` | `routes/native_picker_routes.py` |

## App-Level Endpoints (in `app.py`)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/settings` | Returns user_name from `settings.json` or OS username |
| `POST /api/quit` | Shuts down server (and native window if applicable) |
