# Implementation Guide — QLC+ Swiss Knife v1.1.0 GUI Redesign

**Audience:** an AI coding agent (Claude Opus) implementing this in the real codebase.
**Reference mockup:** `mockups/mockup_B_sidebar.html` — open it in a browser; it is clickable and contains all 10 screens, the 3 themes, and the collapsible sidebar. Copy its visual language exactly (tokens, spacing, components). `DESIGN_v1.1.0.md` explains the rationale.

---

## 0. Ground rules

- **Stack stays as-is:** Flask + vanilla JS + one HTML template + Grid.js. No frameworks, no build step, no new dependencies.
- **Zero functional regressions.** This is a re-skin and re-organisation. Every button, filter, modal and API call that exists in v1.0.10 must still exist and call the same route. Do not touch files in `routes/` or `core/` except where explicitly noted.
- **Work on a branch** (`redesign-1.1.0`). Migrate one tool at a time; the app must stay runnable after every step.
- **The mockup is the source of truth for visuals.** When in doubt about a color, spacing or layout, read the mockup's CSS.

## 1. Architecture of the change

| Piece | Today | v1.1.0 |
|---|---|---|
| Navigation | Flat 9-tab bar | Collapsible left sidebar, 3 groups + Start |
| Entry point | Empty tab + header path input | Start screen (greeting, open zone, about, workflow, footer) |
| File state | Header input + session modal + per-tab inputs | Files panel pinned at sidebar bottom (session, workspace, dictionary, QXF) |
| Themes | Dark/Grey/Light via JS class swap | Same 3 themes via `data-theme` attribute + token overrides |
| Icons | Emoji | Inline SVG sprite (Lucide-style, stroke 1.75–2) |
| Save semantics | Tooltips | Color-coded "output footer" on every tool page |

Keep the SPA model: one `index.html`, `<section>` per screen, JS `showTab()` → rename to `go()`.

## 2. Step-by-step plan

### Step 1 — `static/css/tokens.css` (new file)
Copy the three `[data-theme]` token blocks from the mockup `<style>` (dark, grey, light) plus the shared tokens (`--radius`, fonts). Load it **before** `style.css`. Then, in `style.css`, progressively replace hard-coded colors with tokens. Keep old variable names working during migration by aliasing them to the new tokens if needed.

Theme switching: set `data-theme="dark|grey|light"` on `<html>`; cycle order dark → grey → light; persist in `localStorage('sk-theme')` and restore on boot. Replace the current theme JS in `app.js` with this mechanism.

### Step 2 — SVG icon sprite
Create `static/icons.svg` as a symbol sprite containing every icon used in the mockup (bolt logo, list/setlist, midi-pad, book, grid, check-square, sun, search, palette-nodes, merge-columns, home, save, folder, clock, shield, alert-triangle, github, bug, globe, chevrons-left, arrow-right, check, plus-circle, upload, eye, moon). Use with `<svg class="ic"><use href="/static/icons.svg#name"/></svg>`. Remove all emoji from UI chrome (emoji may stay inside user data rendering).

### Step 3 — Shell: sidebar + files panel
Rewrite the skeleton of `templates/index.html`:

```
<body>
  <aside>            ← logo, grouped nav, files panel, collapse button
  <main>
    <section id="scr-start">…
    <section id="scr-setlist">…   (one per tool, existing tab content moves inside)
  </main>
```

Sidebar spec (copy from mockup):
- Groups: **Start** · **Run the show** (Setlist, Triggers, Dictionary) · **Build the rig** (Fixtures, Checklist, Brightness) · **Workspace tools** (ID Browser, VC Visual Editor β, QXW Merger α).
- Maturity badges are pill spans (`.b.alpha`, `.b.beta`), not `<sup>`. **Brightness carries NO alpha badge in v1.1.0** (neither in the sidebar nor its page header); only VC Visual Editor (β) and QXW Merger (α) keep badges.
- **Nav tooltips:** every sidebar item has `data-tip` (tool name) and `data-desc` (a few-word explanation of what the tab does). On hover a floating tooltip appears to the right of the item — JS-positioned with `getBoundingClientRect` into a single fixed-position `#nav-tip` div (CSS `::after` would be clipped by the sidebar's overflow). Expanded sidebar → show the description only; collapsed sidebar → show "**Name** — description". Hide on mouseleave and on click. Descriptions (copy verbatim): Start "Open files & overview" · Setlist "Songs → functions cuelist" · Triggers "Key & MIDI bindings" · Dictionary "Function descriptions" · Fixtures "Stage plot & DMX patch" · Checklist "Printable patch list" · Brightness "Scale dimmers per group" · ID Browser "Function & widget tables" · VC Visual Editor "Layout the Virtual Console" · QXW Merger "Copy between workspaces".
- **Collapse:** a bottom button toggles `body.nav-min`; collapsed width 58px, icons only, group separators as hairlines. Persist collapsed state in `localStorage('sk-nav-min')`.
- **Files panel** (bottom of sidebar, above collapse): shows session name + dirty dot + Save link, then one row per loaded file (workspace, dictionary, QXF overrides) with a green check or grey plus icon, and Open…/Manage buttons. "Manage" opens the existing session modal (keep the modal, restyle with tokens). All existing session.js logic is reused — this panel is a new *renderer* of the same state. In collapsed mode the panel shows nothing but the session dot.
- Keep drag-and-drop-anywhere for `.qxw` and add `.qsk`.

Delete the old `<header>` and `<nav id="tab-bar">`. The header's path input moves to the Start screen "Advanced: paste a file path…" row (a small expandable input + Load button, same `loadFromPath()`); Reload moves next to the workspace row in the files panel (icon button).

### Step 4 — Start screen (new `static/js/start.js`)
Layout per mockup, top to bottom:
1. **Greeting** — `Good morning/afternoon/evening, <name> 👋` ONLY if a name is available; otherwise plain `Welcome 👋`. Name source: optional `user_name` in a small `settings.json` next to the app (expose via a tiny `/api/settings` GET; also try `getpass.getuser()` only if it's not generic like `root`/`user`/`admin` — otherwise null). Never guess.
2. **Open zone** — drop hint + `Open Session (.qsk)` (primary) + `Open Workspace (.qxw)` (secondary), using the existing native-picker routes; "Advanced: paste a file path…" row underneath.
3. **Recents** — right column; store last 5 opened `.qsk`/`.qxw` paths in `localStorage('sk-recents')` (path, type, timestamp); clicking re-opens via the existing path-load routes; show relative time.
4. **About box** — "What is QLC+ Swiss Knife?" — copy the text verbatim from the mockup, including the independent-project notice and the "never overwritten" promise.
5. **Workflow strip** — 3 numbered steps ("Build the rig" / "Prepare the show" / "Polish & export"), each linking to its tools via `go()`. Copy link lists from mockup.
6. **Footer** — links: GitHub repo (`https://github.com/giopas/qlc-plus-swiss-knife-tool-script`), Report a bug (`…/issues/new/choose`), QLC+ website (`https://www.qlcplus.org/`), right-aligned `v{{ version }} · MIT License`. All `target="_blank"`.

On boot show Start unless a session auto-restores, in which case still show Start (with files panel populated) — don't jump to a tool.

### Step 5 — Tool page template
Wrap every existing tab in the uniform template:

- **`.page-h`**: 38px icon tile + `<h2>` + one-line description + right-aligned page-level actions + the theme button. Page descriptions: copy from mockup.
- **`.out-footer`** (only for tools that write files): left side a color-coded note, right side exports + the primary Generate/Save button.
  - Green "Writes a **new .qxw** — original untouched": Setlist, Fixtures, Brightness, VC Editor, Merger (Export), Checklist ("Exports TXT or blueprint PDF"), Dictionary ("Saves to your dictionary .txt").
  - **Orange** "Save **overwrites the loaded .qxw** — the only tool that does": Triggers. Also add a "Save as new file…" ghost button next to it (new small route reusing the existing writer with a Save dialog — the only backend addition, ~20 lines in `triggers_routes.py`).
- **Empty states**: one shared `.empty-state` component — icon, one sentence, and a CTA button that jumps to Start ("Open a workspace to begin").

### Step 6 — Migrate tools one by one (order: smallest first)
For each: move markup inside its `<section>`, replace toolbar with `.page-h` + optional `.toolbar` row, keep every control, swap emoji→sprite icons, replace inline styles with token classes.

1. **Checklist** — filter in toolbar; TXT + paper-size + Blueprint PDF into out-footer.
2. **ID Browser** — sub-tabs become two `.mini-btn` toggles ("Functions (n)" / "VC Widgets (n)") in the toolbar; CSV export in page header.
3. **Dictionary** — filters in toolbar; Load/Export/Save txt in page header; keep bottom inline-edit row; out-footer note about the .txt.
4. **Triggers** — filter + "Assigned only" in toolbar; Duplicates/Matrix/MIDI Shift in page header; edit panel unchanged; orange out-footer (see Step 5).
5. **Brightness** — Scan/Upload/Fetch in page header; replace the long help banner with the one-line page description + preview bar (mockup); group cards per mockup incl. baseline pills and QXF status lines; Reset All + Generate in out-footer.
6. **Merger** — source/dest load bar under page header (mockup `.mg-load`); category toggles + search in toolbar; Copy → in middle column; Export in out-footer.
7. **VC Visual Editor** — delete its scoped `<style>` block, restyle with tokens; page selector in header; mode/zoom in toolbar; right panel sections per mockup; Apply & Save in out-footer.
8. **Fixtures** — two toolbars collapse to page header (Import/Load QXF/Add) + one toolbar (views, snap, Auto-DMX, stage dims, grid); table + canvas split kept; paper + Blueprint PDF + Generate in out-footer. Keep the Add Fixture modal, restyled.
9. **Setlist** — 4-pane layout kept, but the "Actions" column dissolves per mockup: Assign stays as double-click + an Assign button in the functions pane header; Clear/Purge/Delete-clones become the songs-pane footer row; Load/Save slot file + Re-Match + Save songs go to the page header; timing panel and function pool (with its 3 filters) in the right pane; target-chaser select + PDF/XML/Generate in the out-footer.

### Step 7 — Cleanup & release
- Remove dead CSS (old tab bar, old header, old theme classes, tooltip-below machinery where replaced) and audit for stray emoji.
- Update `app.py` version string to `1.1.0-dev`, README screenshots, CHANGELOG entry.
- Update the session `.qsk` handling only if field names changed (they shouldn't).

## 3. Behaviours checklist (must all pass)

- [ ] Sidebar collapses/expands, state persists across reloads.
- [ ] Every sidebar item shows its short description tooltip on hover in BOTH states (expanded: description; collapsed: name — description), never clipped by the sidebar.
- [ ] Brightness has no alpha/beta badge anywhere; VC Editor (β) and Merger (α) keep theirs.
- [ ] Theme cycles dark→grey→light from any page, persists, and all three themes have readable contrast everywhere (check tables, pills, canvas placeholders).
- [ ] Start greeting is generic when no name is configured; personalised only when available.
- [ ] Start footer links open GitHub, issue tracker, qlcplus.org in new tabs.
- [ ] Drag-and-drop of `.qxw` and `.qsk` works from any screen.
- [ ] Every v1.0.10 feature reachable: setlist slots/songs/timing/re-match/purge/delete-clones/slot files/target chaser/PDF/XML/generate; dictionary filters incl. VC-name + frame; checklist TXT + blueprint PDF with paper sizes; triggers edit/duplicates/matrix/MIDI-shift/save (+ new "save as new"); fixtures add/remove/move/auto-DMX/import/QXF/views/snap/stage-dims/blueprint/generate; ID browser both tables + CSV; VC editor select/props/align/distribute/same-size/fit-text/grid-arrange/sort/snap/mask/zoom/apply-save; merger src+dst load/categories/filter/select-all/copy/export; brightness scan/upload/fetch-GitHub/link-group/baseline-pills/preview/reset/generate; session save/open/dirty-indicator/change-paths; reload-from-disk; status counts (move into files panel or page headers — do not lose them).
- [ ] Triggers is the ONLY place that can overwrite a loaded file, and its footer says so in orange.
- [ ] No emoji in UI chrome; no `<sup>` α/β; no leftover `#tab-bar` CSS.
- [ ] App runs with `./run.sh`, no new pip/npm dependencies, single-page load < previous total asset size.

## 4. Nice-to-have (only if everything above is done)

- Keyboard shortcuts: `Ctrl/Cmd+O` open workspace, `Ctrl/Cmd+Shift+O` open session, `[` toggle sidebar, `1–9` jump to tools.
- `prefers-color-scheme` as the default theme before the user first picks one.
- Reduced-motion respect for the sidebar transition.
