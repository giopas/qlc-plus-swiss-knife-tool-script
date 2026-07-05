# Release v1.0.10

## Brightness tab: baseline dimmer indicator

When you reopen a workspace that was previously scaled with the Brightness tool, all sliders reset to 100% — giving no indication that the scene values in the file are already dimmed relative to another group. This release adds a **baseline indicator** that reads the actual dimmer channel values stored in the scenes and shows the current peak per fixture group directly in the Brightness tab header.

### What it looks like

Each fixture group header now shows a small coloured pill next to the QXF badge:

| Colour | Meaning |
|---|---|
| 🟢 Green — **⟂ 100%** | Group is at full power in the loaded file |
| 🔵 Teal — **⟂ 80%** | Slightly dimmed |
| 🟡 Yellow — **⟂ 50% −30%** | Moderately dimmed; −30% means 30 pp below the brightest group |
| 🔴 Red — **⟂ 20%** | Heavily dimmed |

The **−X%** relative offset only appears when at least two groups have scene data, so at a glance you can see which groups were already scaled down and by how much compared to the brightest group in the file.

### Technical notes

- New function `get_fixture_baseline_stats()` in `core/brightness.py` scans all `<Function Type="Scene">` elements, reads the dimmer channel offset per fixture (same logic used by the apply/preview path), and returns `{peak, mean, scene_count}` per fixture.
- New endpoint `GET /api/brightness/baseline` returns the stats as JSON.
- Stats are fetched in parallel with fixtures on tab load (`Promise.all`) — zero extra round-trip latency.
- A group with no scene dimmer data (e.g. fixture whose QXF was not found) shows no badge at all.

---

## VC Visual Editor promoted to its own tab

The **🎨 VC Visual Editor** is now a top-level tab in the main navigation bar, positioned between QXW Merger and Brightness. It was previously a sub-tab inside ID Browser.

- Renamed from *VC Editor* → **VC Visual Editor** with a **β** (beta) badge.
- Removing it from the ID Browser sub-tab bar gives it a full-height canvas area and makes it discoverable without first navigating into ID Browser.
- No functionality changes — all canvas rendering, selection, alignment, distribute, grid arrange, sort, snap and export behaviour is identical.

---

### Files changed

| File | Change |
|---|---|
| `core/brightness.py` | Add `get_fixture_baseline_stats()` |
| `core/workspace.py` | Bump `VERSION` → `1.0.10` |
| `routes/brightness_routes.py` | Add `GET /api/brightness/baseline` |
| `static/js/brightness.js` | Fetch baseline on load; add `_brtBaselineBadge()` and `_brtGroupPeakPct()` helpers; render indicator in group header |
| `static/css/style.css` | Add `.brt-baseline`, `.brt-bl-*` and `.brt-baseline-diff` styles |
| `templates/index.html` | Add `tab-vc-visual-editor` top-level tab + section; remove `subtab-vc-editor` from ID Browser; rename to VC Visual Editor with β badge |
