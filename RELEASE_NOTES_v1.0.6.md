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
