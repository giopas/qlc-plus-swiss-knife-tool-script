# Release v1.0.7

## 📋 New: Session / Project File (.qsk)

Adds the ability to save and restore all the file paths used by the app in a single
**.qsk** (QLC+ Swiss Knife) file.  Load it once at the start of a session and the
app automatically re-opens your workspace, descriptions dictionary, setlist backup
and all fixture QXF overrides — no manual file hunting.

### What is saved

| Item | Details |
|---|---|
| **Workspace** | Absolute path to the `.qxw` show file |
| **Dictionary** | Absolute path to the descriptions `.txt` file |
| **Setlist backup** | Absolute path to the all-slots setlist backup `.txt` |
| **QXF overrides** | All per-fixture fixture-definition forced assignments (from the Brightness tab) |

### How to use

**Saving a session:**

1. Load your workspace, dictionary and setlist as usual.
2. Click **📋 Session** in the top-right corner of the header.
3. Click **💾 Save Session** — on Chrome/Edge a native Save dialog appears (so you can
   choose exactly where to put the `.qsk` file); on other browsers it downloads automatically.

**Loading a session:**

1. Click **📋 Session** → **📂 Open Session…** and pick the `.qsk` file.
2. The app immediately applies everything: loads the workspace, loads the dictionary,
   re-applies all forced QXF assignments and fills the setlist backup path.
3. A status message confirms each item and flags any paths that could not be found
   (e.g. the file was moved since the last save).

**Quick file-path change:**

Open the Session modal at any time to see all remembered paths.  Each row has a
**📂 Change…** button:

- **Workspace** — clicking Change… pre-fills the path input in the header with the
  current workspace path so you can edit just the filename (e.g. `_v28.qxw` → `_v29.qxw`)
  without re-navigating to the folder.
- **Dictionary / Setlist** — opens a file picker scoped to that item type.

**Unsaved-changes warning:**

If you have loaded a session file and then changed any paths (different workspace,
different dictionary, new QXF override) without saving, closing or reloading the
browser tab shows a standard "Leave page?" confirmation so you do not accidentally
lose the updated state.

### Technical notes

- The `.qsk` file is plain JSON (pretty-printed, version-stamped) — human-readable
  and safe to add to version control alongside the show file.
- Paths are stored as absolute strings; the file can be shared across machines
  if the paths are updated accordingly.
- Loading a `.qsk` is best-effort: items whose file no longer exists at the recorded
  path are skipped and reported, not silently ignored.
- QXF overrides are keyed by normalised `manufacturer||model` strings so they survive
  QXF file renames as long as the internal fixture metadata is unchanged.

---

### Native OS file picker — paths always remembered

Browse buttons throughout the app now open the **real macOS file dialog** (via `osascript`) rather than the browser's sandboxed file input. Because the native dialog runs server-side, the full filesystem path is returned to the app and saved into the session automatically — no manual path pasting required.

- Clicking **📂 Browse…** in the header now loads the workspace in path-mode (path tracked) with the native dialog as the primary path; the hidden browser file input is retained as a fallback if the native picker is not available.
- The **📂** buttons in the Session modal (Dictionary, Setlist backup) open the native picker and write the full path directly into the editable fields.
- On non-macOS platforms (Linux, Windows) the same mechanism uses `tkinter.filedialog` if tkinter is available; otherwise the browser file input is used as a fallback.

### Session modal — editable path fields

The session modal now shows an **editable text input** for each path so the user can paste or correct a path without re-loading the file. Useful for upload-mode workspaces where the native picker is not available: the warning shows the uploaded filename and a field to paste the full path.

### Header tooltip fix

Tooltips on header buttons were appearing above the element and clipping off the top of the viewport. Added a `.tt-below` CSS modifier that renders them below the element with the arrow pointing up, and applied it to all header elements.

---

## Files changed

| File | Change |
|---|---|
| `core/session.py` | **New** — in-memory session state, dirty tracking, `to_export()`, `apply_import()` |
| `routes/session_routes.py` | **New** — `/api/session/{current,export,update-field,apply,mark-saved}`; richer `/export` with upload-mode metadata |
| `routes/native_picker_routes.py` | **New** — `/api/picker/{available,pick}`; opens macOS `osascript` / tkinter native file dialog |
| `core/brightness.py` | Added `get_forced_assignments()` and `restore_forced_assignments()` for session round-trip |
| `routes/workspace_routes.py` | Updates session state after successful path-mode workspace load |
| `routes/dictionary_routes.py` | Updates session state after successful dictionary load |
| `static/js/session.js` | **New** — session modal with editable path inputs; native picker for Browse buttons; dirty tracking; `beforeunload` guard |
| `static/js/app.js` | `nativePick()` helper; `browseWorkspace()` tries native picker first; calls `initSession()` on startup |
| `templates/index.html` | `📋 Session` button; session modal; header Browse → `browseWorkspace()`; `tt-below` on all header tooltips |
| `static/css/style.css` | Session modal styles; `.tt-below` tooltip modifier |
| `app.py` | Registered `session_bp` and `picker_bp` blueprints |
