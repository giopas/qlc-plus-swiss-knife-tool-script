# Directory Structure

*Last Updated: 2026-09-14*

## Root Layout

```
qlc-plus-swiss-knife-tool-script/
├── app.py                    # Flask app factory + main entry point
├── run.sh                    # Unix launcher (auto-creates venv)
├── requirements.txt          # Flask + optional pywebview
├── core/                     # Pure logic layer (no Flask imports)
│   ├── __init__.py
│   ├── workspace.py          # Central state singleton + QXW parser (1620 lines)
│   ├── showbook.py           # Show Book document generator
│   ├── porter.py             # Cross-workspace function import engine
│   ├── brightness.py         # Per-fixture dimmer scaling
│   ├── fixture.py            # Fixture configurator + QXW generation
│   ├── qxf_parser.py         # Deep QXF fixture definition parser
│   ├── merger.py             # QXW file merge engine
│   ├── pdf.py                # Raw PDF builder (stdlib only)
│   ├── session.py            # .qsk project file I/O
│   ├── gh_fetch.py           # GitHub API helpers for QXF repo
│   └── quick_start/          # Quick Start wizard sub-package
│       ├── __init__.py
│       ├── fixture_analyzer.py   # QXF capability scanner
│       ├── qxw_builder.py       # Full QXW XML generation from scratch
│       ├── template_library.py  # Pre-built templates for generation
│       └── vc_generator.py      # Virtual Console layout generator
├── routes/                   # Flask Blueprints (one per feature tab)
│   ├── __init__.py
│   ├── workspace_routes.py   # /api/workspace/* — load, info, save
│   ├── setlist_routes.py     # /api/setlist/*   — song management, export
│   ├── session_routes.py     # /api/session/*   — .qsk project files
│   ├── quick_start_routes.py # /api/quickstart/* — wizard endpoints
│   ├── fixture_routes.py     # /api/fixture/*   — rig configuration
│   ├── brightness_routes.py  # /api/brightness/* — dimmer scaling
│   ├── porter_routes.py      # /api/porter/*    — function import
│   ├── merger_routes.py      # /api/merger/*     — QXW merge
│   ├── id_browser_routes.py  # /api/functions, /api/vc-widgets
│   ├── dictionary_routes.py  # /api/dict/*      — descriptions
│   ├── checklist_routes.py   # /api/checklist/* — setup checklist
│   ├── techrider_routes.py   # /api/techrider/* — tech rider
│   ├── triggers_routes.py    # /api/triggers/*  — trigger management
│   ├── showbook_routes.py    # /api/showbook/*  — show documentation
│   └── native_picker_routes.py # /api/picker/* — OS file/folder dialogs
├── static/
│   ├── css/
│   │   ├── style.css         # Main stylesheet (3340 lines, 3 themes)
│   │   └── tokens.css        # CSS custom properties / design tokens
│   ├── js/
│   │   ├── app.js            # SPA core: navigation, workspace loading, ID Browser
│   │   ├── setlist.js        # Setlist Manager tab logic
│   │   ├── quickstart.js     # Quick Start wizard tab
│   │   ├── vc_editor.js      # VC Visual Editor
│   │   ├── fixture.js        # Fixture Configurator tab
│   │   ├── session.js        # Session management UI
│   │   ├── porter.js         # Function Porter tab
│   │   ├── brightness.js     # Brightness tool tab
│   │   ├── merger.js         # QXW Merger tab
│   │   ├── triggers.js       # Trigger Manager tab
│   │   ├── dictionary.js     # Dictionary Manager tab
│   │   ├── showbook.js       # Show Book tab
│   │   ├── checklist.js      # Setup Checklist tab
│   │   └── techrider.js      # Tech Rider tab
│   └── icons.svg             # SVG sprite sheet
├── templates/
│   └── index.html            # Single Jinja2 template (1900 lines, all tabs)
├── launchers/                # Platform-specific launchers
│   ├── create-macos-app.sh   # Creates .app bundle
│   ├── QLC_Swiss_Knife.bat   # Windows launcher
│   └── qlc-swiss-knife.desktop  # Linux .desktop file
├── tests/fixtures/           # Sample QXF files for testing
├── tests/                    # Pytest test files
├── screenshots/              # App screenshots for README
├── wiki/                     # GitHub wiki pages (gitignored, separate git repo)
├── mockups/                  # HTML mockups
├── Old and tests/            # Historical versions (gitignored)
├── .github/ISSUE_TEMPLATE/   # Bug report + feature request templates
├── CHANGELOG.md
├── README.md
├── CONTRIBUTING.md
├── DEVELOPMENT.md
├── LICENSE                   # MIT
└── ROADMAP.md
```

## Organizing Principle

**Layer-based with feature-aligned modules.** The `core/` directory holds all business logic (no Flask imports). The `routes/` directory maps 1:1 to UI feature tabs. The frontend is a monolithic SPA in one HTML template with per-tab JS files.
