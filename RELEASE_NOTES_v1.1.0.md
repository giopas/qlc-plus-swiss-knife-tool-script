# Release Notes — v1.1.0

**QLC+ Swiss Knife v1.1.0** is a complete GUI redesign. Every feature from v1.0.10 is preserved — this is a re-skin, not a rewrite.

---

## Highlights

### Sidebar Navigation
The flat 9-tab bar is gone. Tools are now grouped in a collapsible left sidebar by workflow stage: **Run the show** (Setlist, Triggers, Dictionary), **Build the rig** (Fixtures, Checklist, Brightness), and **Workspace tools** (ID Browser, VC Visual Editor, QXW Merger). The sidebar remembers its collapsed/expanded state.

### Start Screen
A welcoming home page with a personalised greeting, a drag-and-drop zone for `.qxw` and `.qsk` files, a recent-files list, an "About" box, and workflow cards guiding you through the typical build → prepare → export cycle.

### Design Tokens & Three Themes
All hard-coded colours are replaced with CSS custom properties. The three themes (Dark, Grey, Light) are switched via a `data-theme` attribute — faster, cleaner, and easier to extend.

### SVG Icons
Every emoji in the UI chrome has been replaced with a crisp, consistent SVG icon sprite.

### Output Footers
Every tool page has a colour-coded footer that tells you exactly what happens when you click Save/Generate:
- **Green**: writes a *new* file — your original `.qxw` is never touched.
- **Orange** (Triggers only): overwrites the loaded `.qxw` — the only tool that does.

Triggers also gains a **"Save as new file…"** button for non-destructive saves.

### Files Panel
The sidebar footer shows which files are loaded (workspace, dictionary, QXF) and the current session state — replacing the old header bar and status bar.

---

## Breaking Changes

None. All API routes, URL structure, and `.qsk` session file format are unchanged. The only visual change is the navigation model — all functionality is in the same place, just organized differently.

---

## Upgrade

Pull the latest and run as usual:

```bash
git pull
python3 app.py
```

No new dependencies.

---

## Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete list of changes.
