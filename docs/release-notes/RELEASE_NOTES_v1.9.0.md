# QLC+ Swiss Knife v1.9.0 — one show, every tool

A usability release: open a show once, use every tool on it in any order, and find every screen laid out the same way.

### New
- **The show in progress**: opening a `.qxw` makes one working copy that every tool changes. Each tool's main button is **✓ Apply to the show**.
  - The header counts the changes, shows the Doctor on the show as it is now, and has **↶ Undo**, **🕘 History** and **💾 Save as new file…**.
  - **History** (and *Changes* on the left) goes back to any step, with **↷ Redo**; orange dots in the menu mark the tools that changed the show.
  - One save writes `<name>_v<N+1>.qxw` and one report with every step. The file you opened is never written.
- **Function Porter on the show in progress, with the QXW Merger folded in**: copy fixtures and fixture groups from another show (free addresses checked, 3D positions carried over), then port looks, chasers and their buttons onto them. Copies always play their own looks. Step 3 has a tick-box picker for the targets.
- **Show Paperwork** replaces the Show Book, Setup Checklist and Tech Rider, with **presets by reader**:
  - 🎟 *Tech rider* for the venue. By rule it never carries function names, key/MIDI maps, the Virtual Console or the Doctor.
  - ✅ *Crew checklist* for load-in, 📖 *Show book* for you, ⚙ *Custom*.
  - ⇧-click combines presets in one PDF, with a **stage plot** page. Paper: A4, A3 or US Letter, landscape or portrait.
- **Guided routes**: *Adapt a show to a new venue* and *Get ready for the gig* put a strip of steps above the tools. You can do any step, in any order, and each one is ticked as you go.
- **A "?" on every tool** opens its wiki page.
- **Quick Start → Open it as the show**: the new show goes straight into the show in progress.

### Changed
- **Every screen follows the same pattern**: what the tool does at the top, and its main action bottom right.
  - Tabs in the Look Builder (*Looks · Chasers*) and in Stage & Meshes (*Selection · Place · Add · Stage*).
  - Function Porter: Back / Next / Apply sit in the footer.
  - Show Paperwork: the exports are in the footer, and the show name and date moved here.
- **Start screen**: says what the app is for and what is new in this version. The job cards 1–6 now come first; sessions are below them.
- One wording for new files: **💾 Save as new file…**. The VC Visual Editor is out of Beta.
- The ID Browser works offline (plain tables when the table library can't load).

Your original files are never changed.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Show in Progress](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-in-Progress) · [Function Porter](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Function-Porter) · [Show Paperwork](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Paperwork).
