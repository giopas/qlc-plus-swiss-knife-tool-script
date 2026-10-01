# QLC+ Swiss Knife v2.0.0 — the Pub test

![The guided route: from a festival show to a pub show](https://raw.githubusercontent.com/giopas/qlc-plus-swiss-knife-tool-script/main/screenshots/route.gif)

**The goal set at the start of the project is met.** A real festival show (14 fixtures, one setlist page per band) was rebuilt as the show for a small pub (6 PARs, tonight's 34 songs) **with Swiss Knife only**, through the guided route *Adapt a show to a new venue*:

- **12 minutes** in the app;
- the Workspace Doctor at the end: **0 errors**;
- opened and played in QLC+: setlist, PANIC RESET, looks;
- compared with the show made by hand: same patch, groups and setlist.

### New
- **Fixture groups** — Stage & Meshes, tab **Groups**: make a group from the fixtures you select (left → right as seen from the audience), rename it, change its fixtures, delete it. The Look Builder uses the new groups at once.
- **Compare** (5 · Check & fix): the show in progress next to another show — the hand-made version, or the file you opened — **by what they do**, not by their IDs. Patch, groups, looks (decoded to level and colour), chasers, collections, EFX, matrices, VC pages, setlist cue lists. Functions nothing plays are listed apart. Copy or save the report.
- **Workspace Doctor D018**: a setlist song that lights nothing (an empty scene, a chaser with no steps) — the stage would go dark on that song. The **Setlist** shows those songs with an orange dot and a warning.
- **The show report** now says what every step changed, including the tools that edit the show in place (fixture groups, stage, VC Editor, setlist, triggers): fixtures, groups, functions, pages and widgets added, removed, renamed or changed.
- **Tutorial** on the wiki: *From a big-venue show to a pub show in 30 minutes* — the route step by step, with screenshots.

### Changed
- The guided route *Adapt a show to a new venue* has a **Groups** step before *Looks* (nine steps).
- The Rig Reducer counts *renamed* and *re-patched* fixtures apart.
- Group names are trimmed of stray spaces, quotes and a trailing `:`.

Your original files are never changed.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Tutorial](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Tutorial-Big-Venue-to-Pub) · [Compare](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Compare) · [Stage & Meshes](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Stage-and-Meshes).
