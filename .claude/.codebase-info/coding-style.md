# Coding Style

*Last Updated: 2026-09-14*

## Conventions (derived from existing code)

### Python
- **No linter/formatter config files** in the repo. Style is informal but consistent.
- **Docstrings:** Module-level docstrings describe purpose and public API. Google/numpy style for functions when present.
- **Naming:** `snake_case` for functions, variables, files. `_private` prefix for internal helpers. `UPPER_CASE` for constants.
- **Imports:** stdlib first, then Flask, then `core.*` modules. `from core import workspace as ws` is a common alias.
- **Type hints:** Sparse — `from __future__ import annotations` used in newer modules (`porter.py`, `merger.py`, `showbook.py`). Older modules have no type hints.
- **Line length:** ~90–100 chars typical, no hard enforcement.
- **Comments:** Liberal use of section-divider comments with box-drawing chars:
  ```python
  # ── Section name ────────────────────────────────────────────────────────
  ```
- **String formatting:** f-strings preferred throughout.

### JavaScript
- **`'use strict'`** at top of every JS file.
- **Module-level variables:** `let _camelCase` for cached data, `const UPPER_CASE` for constants.
- **No modules/imports:** All JS files loaded via `<script>` tags in `index.html`. Global scope.
- **DOM interaction:** `document.getElementById()` / `querySelector()` — no framework.
- **Fetch pattern:** `fetch('/api/...').then(r => r.json()).then(data => ...)` with error toast on failure.

### File Organization
- **One Blueprint per feature tab** in `routes/`.
- **One JS file per feature tab** in `static/js/`.
- **Core modules are Flask-free** — they import only stdlib and other `core.*` modules.
- **Blueprint variable** always named `bp` in routes files.

### Git
- **Commit message prefix:** `feat:`, `fix:`, `docs:`, `security:` (conventional-ish).
- **No branch strategy documented** — appears to be trunk-based on `main`.
