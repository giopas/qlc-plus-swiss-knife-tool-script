# QLC+ Swiss Knife v2.2.0 — UI polish: see what Apply will do

![Rig Reducer: what Apply will do, next to the button](https://raw.githubusercontent.com/giopas/qlc-plus-swiss-knife-tool-script/main/screenshots/04-rig-reducer.png)

Swiss Knife was organised around jobs; now the screens show it. After an outside review of the whole interface, each tool says what Apply will do before you press it, the guided routes come first, and you can go anywhere with the keyboard. No new library: CSS and a little JavaScript.

### New
- **Cue notes for older shows.**
  - Open a show made before 2.0.1, or by hand: every setlist cue without a note gets its reference — the original function and the button that plays it, as new cue lists have since 2.0.1.
  - Your own notes are kept.
  - It is a step of the History: undo it, or keep it with 💾 Save as new file….
- **"Apply will …" next to the button** — in the Rig Reducer, Workspace Doctor, Look Builder, Brightness and Setlist:
  - *−6 fixtures · −3 groups · −11 functions · ✓ no new Doctor errors*;
  - *D005 × 801 · D017 × 1*;
  - *12 cues · 1 song without a function — left out*.
- **Rig Reducer without a Preview click**: what Apply will do updates as you tick. It is grouped — fixtures, renamed / re-patched, groups, functions, VC widgets, the Doctor on the result — and each group folds.
- **Guided routes first on Start**:
  - *Adapt a show to a new venue* — 9 steps; the Pub test took 12 minutes;
  - *Get ready for the gig* — 4 steps;
  - *Do it again with a profile* — your saved profiles.

  Each card lists its steps. The six job cards follow.
- **⌘K / Ctrl+K — Go to…**: type a few letters to open a tool, or to undo, save, start a route, apply a profile, check with the Doctor, change the theme, or open the help.

### Changed
- **Header**: fixtures, functions, VC widgets, unsaved changes and the Doctor are labelled cards at every window width. The Doctor card is red, amber or green.
- **Side menu**: clearer group titles. The last steps are an always-visible **History** card, with ↶ on each.
- **Tables**: shaded rows, a row highlight, a quiet ID column, bold names.
- **Stage top views** (Fixtures, Function Porter): a lighter grid, and fixture labels on small plates.
- **One set of colours, spacing and text sizes** in the dark, grey and light themes; thin scrollbars.

Installable packages, planned as 2.2, are now **2.3**.

Your original files are never changed.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Home](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki) · [Show in Progress](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-in-Progress) · [Rig Reducer](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Rig-Reducer).
