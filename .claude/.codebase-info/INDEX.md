# Codebase Map — QLC+ Swiss Knife

*Last Updated: 2026-09-14*

Desktop tool for managing QLC+ v5.x.x lighting show files. Python/Flask backend serves a single-page web UI (vanilla JS + Jinja2 template) on `localhost:5731`, optionally wrapped in a pywebview native window. Parses and manipulates QXW workspace XML, QXF fixture definitions, and companion text files (setlists, dictionaries).

**Stack:** Python 3 · Flask · pywebview (optional) · vanilla JavaScript · Grid.js (CDN)
**Shape:** Layered monolith — `core/` (pure logic) → `routes/` (Flask blueprints) → `static/` + `templates/` (SPA frontend)

## Documents

| Document | What's inside |
|----------|---------------|
| [architecture.md](./architecture.md) | Three-layer design, component diagram, request flow |
| [tech-landscape.md](./tech-landscape.md) | Languages, frameworks, source-of-truth files |
| [directory-structure.md](./directory-structure.md) | Annotated folder tree |
| [entry-points.md](./entry-points.md) | `app.py` bootstrap, all API route groups |
| [modules.md](./modules.md) | Every `core/` and `routes/` module: purpose, deps, exports |
| [communication.md](./communication.md) | REST API surface, GitHub QXF integration |
| [patterns.md](./patterns.md) | XML handling, state management, error handling, testing |
| [coding-style.md](./coding-style.md) | Naming conventions derived from existing code |
| [onboarding.md](./onboarding.md) | Quick start, common dev tasks, project conventions |

## How to use this map

- New here? Read `onboarding.md` then `architecture.md`.
- Before touching code, skim the doc(s) for the area you're changing.
- These docs hold concrete file paths — use them to navigate straight to the relevant code.

## Keeping this map current

After a change that affects architecture, directory structure, dependencies, the data model, entry
points, APIs/events, or conventions, refresh the affected docs with the `update-codebase-map` skill
(`/codebase-mapper:update-codebase-map`). Small, internal-only changes don't need an update.
