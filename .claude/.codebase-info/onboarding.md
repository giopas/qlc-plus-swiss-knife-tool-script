# Onboarding

*Last Updated: 2026-09-25*

## Quick Start

```bash
# Clone
git clone https://github.com/giopas/qlc-plus-swiss-knife-tool-script.git
cd qlc-plus-swiss-knife-tool-script

# Option A: one-command launch (creates venv, installs Flask automatically)
bash run.sh

# Option B: manual setup
python3 -m venv .venv
source .venv/bin/activate
pip install flask
python3 app.py

# Optional: native window mode (instead of browser)
pip install pywebview
python3 app.py
```

The app opens at `http://localhost:5731`. Use `--browser` flag to force browser mode even with pywebview installed.

## What You Need to Know

1. **The workspace file (`.qxw`) is everything.** Load one to unlock all features. It's a QLC+ XML file containing fixtures, functions, and virtual console layout.
2. **Core logic is in `core/`, UI wiring is in `routes/`.** To change business logic, edit `core/*.py`. To change API shape, edit `routes/*.py`. To change the UI, edit `templates/index.html` and `static/js/*.js`.
3. **`core/workspace.py` is the heart.** It holds `_state` — the parsed workspace data that every other module reads from.
4. **No database.** All data comes from XML files. State lives in Python dicts, persisted only when the user saves.
5. **One HTML file for the entire UI.** `templates/index.html` (1900 lines) contains all tabs. Each tab's logic is in a matching JS file.

## Common Dev Tasks

### Add a new feature tab

1. Create `core/new_feature.py` — pure logic, no Flask imports.
2. Create `routes/new_feature_routes.py` — Flask Blueprint with `bp = Blueprint('new_feature', __name__, url_prefix='/api/new-feature')`.
3. Register in `app.py`: `from routes.new_feature_routes import bp as new_feature_bp` + `app.register_blueprint(new_feature_bp)`.
4. Add tab markup to `templates/index.html`.
5. Create `static/js/new_feature.js` for tab logic.
6. Add `<script>` tag to `index.html`.

### Add a new API endpoint to an existing tab

1. Add the route function to the relevant `routes/*_routes.py` file.
2. Wire it to core logic — call functions from the matching `core/*.py` module.
3. Call it from the matching `static/js/*.js` file.

### Run tests

```bash
source .venv/bin/activate
pip install pytest   # if not installed
pytest               # runs all tests (17 test files)
pytest tests/test_porter.py -v   # specific test file
pytest tests/test_doctor.py -v   # workspace doctor checks
```

CI runs automatically on push and PR (GitHub Actions, Python 3.11 + 3.12).

### Run the Workspace Doctor

```bash
python -m core.doctor path/to/Show.qxw --qxf fixtures/
python -m core.doctor Show.qxw --json          # JSON output
python -m core.doctor Show.qxw --min-severity warning  # skip info
```

### Modify QXW parsing

QXW file I/O is centralised in `core/qxw_io.py` — always use `load_qxw()` / `save_qxw()`. The namespace `NS = {'q': 'http://www.qlcplus.org/Workspace'}` must be used in all XPath queries:
```python
root.findall('.//q:Function', NS)
```
For checks and VC operations, use `load_qxw(path, strip_namespace=True)` for plain tags.

### Build a macOS .app bundle

```bash
bash launchers/create-macos-app.sh
```

## Project Links

- **GitHub:** https://github.com/giopas/qlc-plus-swiss-knife-tool-script
- **Wiki:** https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki
- **Issues:** https://github.com/giopas/qlc-plus-swiss-knife-tool-script/issues
