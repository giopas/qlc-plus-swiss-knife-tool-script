# Release v1.0.9

## 🎨 New: VC Layout Editor

A new **🎨 VC Editor** sub-tab inside the ID Browser gives you a visual, canvas-based editor for every widget in your Virtual Console — buttons, sliders, frames and solo frames — letting you clean up positioning, colours and fonts and export a corrected workspace without ever touching the QLC+ XML by hand.

---

### What it does

#### Visual canvas

- Your entire VC layout is rendered as a scaled canvas, with every frame, button and slider drawn at its correct position, size and background colour read directly from the `.qxw` file.
- Use the **mouse wheel** to zoom in and out; click **fit** to auto-scale the page to the available area.
- A **Page** dropdown lets you switch between top-level VC pages (e.g. *MASTER SHOW*, *20Minutes*, *Smoky Seattle*…).
- Frames are outlined rectangles (dashed for SoloFrames); buttons and sliders are filled with their actual `<Appearance>` background colour.

#### Selection

| Gesture | Result |
|---|---|
| Click | Select single widget |
| Shift+click | Add/remove from selection |
| Click on empty area | Deselect all |
| Click-drag on empty area | Rubber-band select all widgets fully inside the rectangle |

#### Properties panel

The right panel (toggle with **⚙ Panel**) shows, for the current selection:

- **X / Y / W / H** — editable pixel inputs; changes to multiple selected widgets are applied to all of them.
- **Font size** — click a size chip (7–14 px); Bold toggle.
- **Button background** — colour swatches; click to apply to all selected.
- **Font colour** — colour swatches; click to apply to all selected.

#### Quick actions

| Action | Effect |
|---|---|
| **← left / — H ctr / → right** | Align all selected left edges / horizontal centres / right edges |
| **↑ top / \| V ctr / ↓ bottom** | Align top edges / vertical centres / bottom edges |
| **↔ distr H / ↕ distr V** | Distribute with equal gaps horizontally / vertically (needs 3+) |
| **= W / = H** | Equalise width or height to that of the first selected widget |
| **fit text** | Shrink each widget to fit its caption at the current font size |

#### Grid arrange

Select a set of buttons (or sliders), then:

1. Set **Cols**, **Gap X**, **Gap Y** and an **Order by** criterion.
2. Click **▦ Arrange** — the selection is laid out in a tidy grid starting from the top-left of the bounding box. The reference cell size is taken from the first selected widget.

Order-by options: *Position* (original reading order), *A–Z*, *Natural #* (handles `AD · 1` before `AD · 10`), *Colour hue*, *Widget ID*.

#### Sort in place

Select siblings (widgets in the same parent frame), choose a sort criterion and click **↕ Sort**. The widgets swap positions to match the sorted order, keeping the original grid positions intact — useful for re-alphabetising a button bank without changing the layout geometry.

#### Snap to grid

Select any widgets and click **⊞ Snap** to round every X, Y, W, H to the nearest multiple of the configured grid size.

#### Alignment mask mode

Toggle **Mask** in the toolbar to switch to a diagnostic colour overlay:

- Every button is colour-coded by how far its position deviates from its siblings in the same row or column:
  - 🟢 **Green** — within ±0 px (perfect)
  - 🟡 **Yellow** — minor offset (configurable, default ±2 px)
  - 🟠 **Orange** — moderate offset (default ±5 px)
  - 🔴 **Red** — large offset (above major threshold)
- The two thresholds are configurable inline in the toolbar.
- The properties panel shows the legend and the quality level of the selected widget.

#### Apply & Save QXW

When you are happy with the edits, click **💾 Apply & Save QXW…**:

1. All pending changes are pushed to the in-memory XML representation via `POST /api/vc/patch`.
2. A native OS Save dialog opens (same mechanism as the rest of the app) — choose a new filename.
3. The modified workspace is written to the new file. **The original `.qxw` is never touched.**

---

### Technical notes

- X, Y, W, H are now correctly read from the `<WindowState>` child element of each VC widget (they were always empty before this release because the parser was reading from the wrong attribute).
- Background and foreground colours are decoded from Qt's 32-bit ARGB integer format to CSS `#rrggbb` strings.
- Font strings (`Roboto,9,-1,5,700,...`) are parsed to extract family, size and bold; changes are round-tripped back to the Qt format on export.
- The namespace `xmlns="http://www.qlcplus.org/Workspace"` is preserved on export (registered as the default namespace with `ET.register_namespace`), so QLC+ can read the output file without any issues.

---

### Files changed

| File | Change |
|---|---|
| `core/workspace.py` | Fix `_parse_vc_node` (WindowState + Appearance); add `get_vc_tree()`, `patch_vc_widgets()`, `export_qxw()` and colour/font helpers; add `vc_nodes_by_id` to state; bump `VERSION` → `1.0.9` |
| `routes/id_browser_routes.py` | Add `GET /api/vc/tree`, `POST /api/vc/patch`, `POST /api/vc/export-qxw`; update docstring; remove X/Y/W/H from PDF export columns |
| `static/js/vc_editor.js` | **New** — full canvas VC editor (selection, properties, alignment, distribution, grid arrange, sort, snap, mask mode, export) |
| `templates/index.html` | Add **🎨 VC Editor** sub-tab with canvas + right panel (properties + actions); inline scoped CSS; include `vc_editor.js` |
| `static/js/app.js` | Remove X/Y/W/H columns from VC Widgets table (now in the editor) |
