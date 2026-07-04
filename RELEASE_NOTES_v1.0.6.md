# Release v1.0.6

## 💡 New: Brightness tab (Alpha)

Adds a new **Brightness** tab for programmatic per-fixture dimmer scaling across an entire show file — the feature you need when you arrive at a venue and realise one fixture type is far more powerful than the rest, with no time to rebuild scenes.

**How it works:**

1. Load any `.qxw` workspace.
2. Open the Brightness tab. Every fixture in the workspace is listed, grouped by manufacturer/model/mode.
3. Each group has a scale slider (0–200%). Drag it to set brightness relative to the current values. 100% = no change; 50% = half as bright; 200% = double (clamped to 255).
4. A live preview counter updates as you drag: `N fixtures, N scenes, N values will change`.
5. Click **Generate QXW** to download a new workspace file with all Master Dimmer channel values adjusted. Your original file is never touched.

**Fixture definition detection:**

The dimmer channel is identified by parsing QXF fixture-definition files. The app searches standard QLC+ installation paths automatically (macOS app bundle, Linux system install, user fixture directories, and the folder containing the loaded workspace). If a QXF is not found, a ⚠ badge appears and you can either:
- Type the 0-indexed dimmer channel offset manually in the fixture row, or
- Upload the QXF via the **Load QXF** button — it is saved alongside the workspace and used immediately.

**Controls:**
- **Link group** checkbox — when checked (default), all fixtures of the same model move together with a single group slider. Uncheck to adjust each fixture instance independently.
- **↺ Reset All** — returns every fixture to 100%.
- **Generate QXW** — uses the native OS Save dialog (Chrome/Edge) or a fallback download; output filename is auto-incremented (e.g. `ShowFile_v28.qxw` → `ShowFile_v29.qxw`).

---

## 🐛 Bug fixes

### Setlist — Generate QXW now saves all cuelists in one click

Previously, clicking "Generate QXW" in the Setlist tab only regenerated the **currently-selected** cuelist slot. All other slots were unchanged, meaning a multi-cuelist show required switching to each slot and clicking Generate individually.

The button now processes **every slot that has at least one song with a function assignment** in a single pass and outputs one combined QXW file. Slots that have songs but no assignments yet are silently skipped so their existing chaser content is preserved.

### Setlist — Clone names no longer show `(Setlist)` in QLC+

Generated clone functions used to have `(Setlist)` appended to their name (e.g. `20M - Stay (Setlist)`). QLC+'s Show Manager displayed this suffix on every step, which was noisy and confusing.

Clones are now marked using a custom XML attribute `SwissKnifeClone="<base_id>"` instead of a name suffix. The clone is named exactly like the original function. QLC+ ignores unknown XML attributes, so this has zero effect on playback or Show Manager display.

Backward compatibility: files generated with the old `(Setlist)` suffix are still fully recognised — the app detects both the attribute and the legacy suffix at load time.

### Setlist — Regression fix: cuelists not yet assigned are no longer wiped

When the "generate all slots" feature was first introduced, a regression caused any cuelist slot that had songs loaded but **no function assignments** to have its chaser steps cleared during generation. This silently destroyed existing chaser content for those slots.

Two-part fix:
1. `generate_slot_qxw_content` now raises a `ValueError` immediately if no song in the slot has a function assignment, preventing the chaser from ever being cleared.
2. `generate_all_slots_qxw_content` filters to only the slots that have at least one assigned song before iterating, so unassigned slots are never passed to the generator.

---

## 🔒 Security

- QXF file uploads now pass through `werkzeug.utils.secure_filename` before the path is constructed, preventing path-traversal attacks via crafted filenames.
- Malformed `FixtureVal` XML content in a workspace (non-integer channel/value pairs) is now caught and skipped gracefully in both the preview and apply paths, instead of raising an unhandled `ValueError`.

---

## 🏷 UI

- The **QXW Merger** and **Brightness** tab buttons now display an **α** (Alpha) superscript badge in the tab bar, clearly marking them as features still maturing.

---

## Files changed

| File | Change |
|---|---|
| `core/brightness.py` | **New** — QXF parsing, fixture channel detection, `preview_scales`, `apply_brightness_scales` |
| `routes/brightness_routes.py` | **New** — `/api/brightness/{fixtures,preview,apply,upload-qxf}` |
| `static/js/brightness.js` | **New** — Brightness tab UI, slider sync, preview, generate/download |
| `static/css/style.css` | Added `.tab-alpha` badge style + full Brightness tab CSS |
| `templates/index.html` | Added Brightness tab panel + tab button with α badge; α badge on QXW Merger |
| `static/js/app.js` | `showTab('brightness')` → `ensureBrightnessLoaded()`; `invalidateBrightness()` on workspace reload |
| `app.py` | Registered `brightness_bp` blueprint |
| `core/workspace.py` | Generate-all skips unassigned slots; guard in per-slot generator; `SwissKnifeClone` attribute for clone identification; `clone_ids` / `clone_base_map` state tracking |
| `routes/setlist_routes.py` | `/api/setlist/generate-all-qxw` endpoint |
| `README.md` | Updated to v1.0.6; new Brightness feature docs; updated project structure and security sections |

---

## 💡 Brightness tab — QXF Detection & Fixture Lookup (follow-up patch)

### Root cause: QXF files were not detected even after upload

The initial implementation matched QXF files by normalising filenames (collapsing spaces, hyphens, and other punctuation into a single separator). This works when the QXF filename mirrors the internal `<Model>` declaration exactly, but fails when the two diverge — for example when the filename omits a word present in the model name, or when a token like `7Ch` in the filename is written `7-Ch` inside the file.

### Fix: two-phase QXF search

**Phase 1** — fast filename normalisation (unchanged): normalise manufacturer+model and the filename stem identically, compare. Zero overhead for correct files.

**Phase 2** — content-based fallback: when Phase 1 finds nothing, read the first 3 KB of each QXF file (just enough to find `<Manufacturer>` and `<Model>` tags), build a per-directory index, and match by exact or normalised internal declaration. The index is cached per session and invalidated when QXF files are uploaded or new workspaces are loaded.

### New: Scan Local button

`📁 Scan Local` — scans all standard QLC+ installation directories for the current OS (macOS app bundle, Linux system install, Windows Program Files, user fixture directories, workspace directory) and reports:
- How many QXF files were found and in which directories
- How many workspace fixtures are now matched vs. still unmatched

The scan result reloads the fixture list immediately.

### New: multi-file QXF upload

The `📂 Upload QXF` button now accepts multiple files at once (HTML `multiple` attribute). All files are uploaded in a single request and saved next to the workspace.

### New: Fetch from GitHub (internet)

`🌐 Fetch from GitHub` — for fixtures that still have no QXF after local scanning, downloads definitions from `github.com/mcallegari/qlcplus/resources/fixtures`. A confirmation dialog always appears before any connection is made, listing:
- Exactly which external hostnames will be contacted (`api.github.com`, `raw.githubusercontent.com`)
- Which fixture types will be looked up
- Where the downloaded files will be saved

The button is disabled when all fixtures are already matched. Status messages clearly prefix internet-sourced activity with 🌐 and local activity with 📁. The backend route also stamps `source_type: "internet"` in its JSON response.

### Security

- QXF content index reads only the first 3 KB of each file — no full parse during indexing.
- `urllib.request` with a 12 s API timeout and 20 s download timeout; GitHub API rate-limit errors surface as user-visible error messages.
- `secure_filename` applied to all uploaded filenames; multi-file upload validates each file individually.

### New: per-group QXF override and always-editable dimmer channel

When auto-detection is uncertain or wrong, users can now take full manual control at the fixture-group level:

- **📂 Assign QXF** button in each group header — opens a file picker scoped to that specific fixture group. The selected QXF is uploaded and immediately forced as the definition for that manufacturer/model combination, bypassing all name-matching logic. This is the escape hatch for any fixture whose filename and internal model declaration diverge.
- **Dimmer ch** field is now always visible for every fixture row, regardless of whether a QXF was found. When a QXF is detected the field is pre-filled with the auto-detected offset and shown in a muted style; it can still be edited to override. When no QXF is found it is shown highlighted, prompting manual entry. The value in the field is always what gets used during generation.

### Files changed (this patch)

| File | Change |
|---|---|
| `core/brightness.py` | Two-phase `_find_qxf`; `_read_qxf_identity`; `_build_content_index`; `scan_local_fixtures`; `fetch_fixtures_from_github`; `force_qxf_for_fixture`; `_forced_qxf` map; Windows fixture paths |
| `routes/brightness_routes.py` | Multi-file `upload_qxf`; new `scan_local`; new `fetch_github`; new `assign_qxf` endpoints |
| `static/js/brightness.js` | `brtScanLocal`; `brtFetchGithub` with internet warning; `brtAssignQxf`; `_brtMissingFixtures`; `_brtUpdateFetchBtn`; always-visible channel override; ✓/⚠ QXF badges; multi-file upload |
| `templates/index.html` | `📁 Scan Local`; `🌐 Fetch from GitHub`; `multiple` on QXF input; updated help text |
| `static/css/style.css` | `.brt-badge-ok`; `.brt-gh-btn`; `.brt-internet-label`; `.brt-ch-override`; `.brt-assign-qxf-btn` |
