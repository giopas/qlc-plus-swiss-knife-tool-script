# QLC+ Swiss Knife — Work Plan

> Living plan for turning Swiss Knife from a set of helpers into a **deterministic, accurate show-file builder** for QLC+ 5.
> Agreed 23 Sep 2026. Baseline: `main` @ `387db18` (v1.3.1).
> Update the checkboxes and the *Status* line of each step as work lands. Anything new goes into §7 *Backlog* so nothing gets lost.

**Status (5 Oct, later — giopas: "work on points 1, 2, 3, 4, 5, 6, 7 and 9"; upstream reports dropped):**
- v2.2.1 is prepared on `feat/v2.2.1` (the 3.2 leftovers + the white-window fix, 653 tests; giopas releases). The old *parked* list becomes **five themed releases** (Phase 3.3–3.7 below), built on `feat/v2.3.0` and its successors, stacked on `feat/v2.2.1`.
- **Order (giopas, 5 Oct): v2.3.0 New-show flow · v2.4.0 Doctor + Quick Start · v2.5.0 Looks + Stage · v2.6.0 Paperwork, setlists, MIDI · v2.7.0 Localisation + community library — then packaging (v2.8.0) and the MCP server (v2.9.0).** Packaging still goes before the MCP server (one executable for Claude Desktop to point at; the update check carries later releases).
- **Out of the plan:** the audio-trigger helper (giopas is not sure it is needed) and the upstream reports to QLC+ (probably solved in future QLC+ 5 releases). The SSH-keys housekeeping item is gone (checked 5 Oct).

**Status (3 Oct, later — v2.1.0 prepared on `feat/v2.1.0`; giopas: "do 1, 2 and 5 together for the 2.1.0 release"):**
- **Show Profiles** and the command-line build (3.1, below).
- The recipe extras: saved from the History without saving the show, and replayed onto another show.
- The three small items from Phase 0:
  - the Fixtures tool keeps the tilt instead of writing 65°;
  - Quick Start tilt buttons;
  - Quick Start `_vN` file names.

Packages move to **Phase 3 → v2.2.0**. 649 tests. Docs: CHANGELOG, README, release notes, ROADMAP, wiki (new *Show Profiles*; Recipe, Quick Start, Fixture Configurator, Show in Progress, Home), Start *New in 2.1*.

**Status (3 Oct — v2.0.1 prepared on `feat/patch-sheet`):** after giopas's tests of the cue-list notes on a Quick Start show. The **setlist CueList** was hard to find (the last, folded item of *Ready-made blocks*), so it is now:
- a highlighted **▶ Setlist cue list** box at the top of VC Editor › ＋ Add & wire, saying how many CueLists the show has, with a button that names what it does (*＋ Add a CueList on this page* / *Wire “…”*);
- **▶ Use for a new setlist** in the Selection of a CueList;
- **▶ ＋ Add a setlist CueList** in the Setlist when the show has none.

A new setlist CueList is placed where it covers nothing (720 × 420, smaller if the page is full). Also fixed from the test: a song with no function was silently dropped, and new CueLists were too narrow for the *Note* column. Released together: the Patch sheet, the cue notes, the FloorShow corpus and D008 *Stop All*. VERSION 2.0.1, CHANGELOG, release notes, ROADMAP, wiki (Setlist Manager, VC Visual Editor). 637 tests.

**Status (1 Oct, evening — anonymised):** giopas asked that the public repo carry no real names: author references are now *giopas*, show / band / venue names replaced (FloorShow, BigShow, BarShow, SmallShow; corpus already neutral), the naming profile is `prefix`, LICENSE says *giopas*. Commits from here on: `giopas <giopas@users.noreply.github.com>`. Older commits still carry the real name in their author field — rewriting history is optional (instructions given, giopas decides).

**Status (1 Oct, later — v1.9.0 released by giopas; his five points before 2.7):**
- Decided with giopas:
  1. **Wiring copied fixtures into the existing show** gets its own phase, **2.7 Grow a rig → v1.10.0**, before the Pub test (now **2.8 → v2.0.0**).
  2. **README = presentation only** (what it is, how it works, the tools, screenshots, install, docs links); the history lives in the CHANGELOG. Done after the 1.9.0 release (branch `docs/readme-and-plan`).
  3. **All screenshots retaken** (16, named in menu order, `screenshots/01-start.png` … `16-show-in-progress.png`). Done (same branch).
  4. **Forum**: no post per release; the BBCode drafts are deleted from the repo. One complete post (every tool + the show-in-progress logic) is written at v2.0.0 (task in 2.8).
  5. **Installable packages with an update check** → **Phase 3 → v2.1.0**, after v2.0. Running from sources stays. *(3 Oct: moved to v2.2.0 — Show Profiles went first as v2.1.0; 4 Oct: moved to **v2.3.0** — the UI polish is v2.2.0.)*
- Also fixed on the way: the VC Editor page title still said *BETA*; the README's security details moved to DEVELOPMENT.md. 563 tests.

**Status (1 Oct — 2.6 finished, v1.9.0 ready to release):** the rest of the audit built on `feat/show-in-progress`, 562 tests, browser-checked at 1440 × 900 and 1280 × 800.
- **Screen pattern**: a **?** in every tool header opens its wiki page (`POST /api/help`, system browser, also from the desktop window); Look Builder tabs *Looks · Chasers*; Stage & Meshes tabs *Selection · Place · Add · Stage*; Porter's Back / Next / Apply in each step's footer (no second target chip); Show Paperwork exports and paper in the footer, show name / date moved there from Start; Brightness help folded; ID Browser empty state + plain sortable tables when Grid.js can't load (offline at the venue); stray closing tags from the removed Checklist / Tech Rider screens removed.
- **Start** (A1, A2): purpose sentence, *New in 1.9*, compact *Open a show*, *What do you want to do?* cards, sessions below.
- **Route strip** (`static/js/route.js`): *Adapt a show to a new venue* and *Get ready for the gig* from Start cards 2 and 4; steps ticked by the tool's change to the show or by hand; *Done, next ›*.
- **Words / navigation**: *💾 Save as new file…* for Quick Start and Fixtures (was *Generate QXW*); Quick Start **🎛 Open it as the show**; VC Editor out of Beta; use-this-when tooltips; menu fits short windows.
- Tests: `test_ui_consistency.py` + 8 (help button per tool, `/api/help` whitelist, one save verb, Porter footers, empty states, inspector tabs, routes open real tools).
- Release: VERSION 1.9.0, CHANGELOG, README, release notes, wiki (18 pages).
- Left for later (§7): Setlist in fewer columns (functions in a drawer); `/api/checklist|techrider` as thin wrappers and `core/merger.py` retired; Fixtures "open it as the show".

**Status (30 Sep, late — giopas's tests of Porter copies and Show Paperwork):** v12 port report showed copied Ceilings tiled onto the floor PARs by *pattern repeat* → copies pinned 1:1 (`plan_blocks`); a thread race in `_with_copies` (candidates + preview in parallel) could leave the copies in the target / copy twice → `_COPIES_LOCK`; step 3 target picker = drop-down with tick boxes; Show Paperwork preview draws the stage plot, sections grouped (rig / show / console & checks). JS parse test added. 555 tests.

**Status (30 Sep, night — Show Paperwork built):** one tool for the three papers, on `feat/show-in-progress`; 548 tests; browser-checked (Start chip *Tech rider* → preset, ⇧ + *Crew checklist* → one PDF with rider, checklist, stage plot). Next in 2.6: the screen pattern (inspector tabs for Look Builder / Stage & Meshes, primary action in the footer everywhere), the route strip, words; then **v1.9.0**.

**Status (30 Sep, evening — giopas's Porter test):** FloorShow_v11 ← BigShow_v41 *Ceiling* group, applied, saved v12: works; three points fixed — copies had no 3D position (QLC+ stacked them top-left: now source position scaled to the target stage, `_copy_positions`), step 3 did not show the copies in the target (now drawn green, `target_preview`), and "where is Save?" (button on the finish screen + "top right" in messages). Also: no spurious "unassigned" warning for copies, re-copy flagged. 542 tests.

**Status (30 Sep, later — Porter on the show in progress, Merger folded in):**
- giopas checked the saved file of his test against v40: identical byte for byte to a Doctor-only run here (the undone Reducer step left nothing behind).
- Built: the Porter's target is the show in progress by default (`load_target_root`, `/target/show`), **Apply to the show** (`/apply`, re-reads the show first), and the **QXW Merger folded in** (step 2 copy fixtures / groups: `copy_fixtures_into`, `_with_copies`, `check_plan`). The old Merger bugs are not carried over (shared ID map, `FixtureGroupMember`, `FixtureVal@Fixture`). Tests `tests/test_porter_show.py` (5). 541 green; browser-checked (group copy into Pub → 12 fixtures, step 1).
- Next in 2.6: Show Paperwork; the screen pattern; the route strip; then 1.9.0.

**Status (30 Sep — giopas's test of the show in progress):**
- Test on a real show (v40, 1 error / 1327 warnings): header Doctor pill → Doctor → Check → All → *Fix 1413 selected in the show* (1324 fixes, 0 errors / 5 warnings) → Rig Reducer, ceiling fixtures removed → *Apply to the show* (8 fixtures; their faders gone in the VC Editor) → History → undo the Reducer step → Save as new file. Result + one report (1443 lines, both steps' details) correct; the saved file checks 0 errors / 5 warnings.
- His ask: **a history log with a revert button on the left**. Built: *Changes* under the menu (last 5 steps, ↶ per step with a confirmation when it undoes several, click → tool, *All ›*), and **↷ Redo** (core `show.redo()`, ended by a new step or a save). Also: the Doctor checks the show as soon as it opens; footer notes shortened (they wrapped next to three buttons). 536 tests.

**Status (29 Sep, evening — 2.6: the show in progress built):**
- Branch `feat/show-in-progress` (from `main` @ `8b10b49`, after v1.8.1). `core/show.py` keeps the history (snapshot of the show before each step, serialised; 60 steps), `touch()` for in-place edits (one step per tool while it keeps editing), `adopt()` for tools that build a new tree; `workspace.load_qxw` starts a new show. `routes/show_routes.py`: status (+ Doctor counts cached per change), history, undo to any step, file, saved (report next to the file the Save dialog wrote), save. Apply routes for Doctor, Reducer, Looks, Brightness, Setlist; Triggers / VC Editor / Stage record steps as they edit (Stage merges its `<Monitor>` into the show after every op, so its edits survive other tools' steps). Front end: `static/js/show.js` — header bar, History drawer, orange dots, Save; a fetch hook refreshes the bar after any POST/PATCH and resets the other tools when the show changed; VC Editor pending drags are sent before switching tool, undo or save.
- Tests: `tests/test_show.py` (8) — each apply equals the old export byte for byte (Doctor → Looks → Reducer → Brightness), undo to any step (tables follow), save + one report + keep working, Stage edits survive a Doctor step, live edits coalesce. 535 green. Browser-checked at 1440 × 900 and 1280 × 800 (Doctor fix → header, dots; Stage edit; History; undo from History; Reducer apply → 12 fixtures; re-open asks).
- Wiki: new page *Show in Progress*; Doctor, Rig Reducer, Look Builder, Stage and Meshes, Brightness, Setlist Manager, Trigger Manager, VC Visual Editor updated.
- Next in 2.6: Porter on the show + Merger folded in; Show Paperwork; screen pattern; then 1.9.0.

**Status (29 Sep — decision: Show Paperwork):**
- giopas asked whether Show Book, Checklist and Tech Rider should be one modular report. Yes: they differ by reader, not by data. Decided to do it **with the 2.6 audit (v1.9.0)** — task *Show Book, Checklist and Tech Rider → one tool* in 2.6.

**Status (29 Sep, later still — Start and side menu by job, added to v1.8.1):**
- giopas's report on the v1.8.1 Start page: *"Build the rig"* opened only Fixtures although the group has more tools, and the Start cards 1–6 did not match the side menu. Fixed on branch `feat/start-sidebar` (stacked on `feat/stage-fixtures`), part of the v1.8.1 release: the side menu and the Start cards share the same **six numbered groups by job** — 1 New show (Quick Start, Fixtures) · 2 Adapt a show (Rig Reducer, Function Porter, QXW Merger, Brightness) · 3 Create (Look Builder, VC Visual Editor, Stage & Meshes) · 4 Run the show (Setlist, Trigger Manager, Dictionary) · 5 Check & fix (Workspace Doctor, ID Browser) · 6 Document (Show Book, Checklist, Tech Rider). Each card shows its tools as buttons; hovering a card lights up those tools in the menu; the collapsed menu shows the numbers. New purpose text; the empty recent-files box hidden. Test `test_start_cards_match_side_menu_groups` keeps both in step. 527 tests green; browser-checked. Wiki Home, Sessions-and-Files and the "sidebar →" hints updated. This is the first part of the 2.6 Start/Navigation tasks (the route cards and the show-in-progress model are still to come).

**Status (29 Sep, late night — v1.8.1 prepared: fixtures in the Stage placement):**
- giopas's feedback on the mock-up: (1) a tool that changed the show in progress gets an **orange dot** in the sidebar — useful in long sessions (added to 2.6 and to the mock-up); (2) **arrange meshes along fixtures and back** (e.g. a mesh between two fixtures) → built now as **v1.8.1** on branch `feat/stage-fixtures` (stacked on `feat/ui-audit`): `stage3d.fixtures()` with body sizes from the .qxf `<Dimensions>` (300 mm default; XPos/ZPos = left/back edge, YPos = underside, from QLC+ `updateFixturePosition`), `move_fixture()`, `arrange(move=all|meshes|fixtures)` where the non-moving items are the reference; fixtures selectable/draggable in the views, *Fixtures* list, *Move* choice, fixture editor; report lists fixture moves. 526 tests green; browser-checked (bassist centred between Wing Left / Wing Right, backs aligned; fixture drag). Commands in §8.
- Next: giopas's go on the mock-up → 2.6.

**Status (29 Sep, night — v1.8.0 released; plan for 2.6 UI audit and 2.7 Pub test):**
- **v1.8.0 released** by giopas (main `874f72a`, tag `v1.8.0`): Stage & Meshes with the placement tools.
- giopas asked for a **usability audit of the whole UI** (align the logic across screens, fix crowded screens) and a **Start screen that explains what the app is for** — before the benchmark, because the benchmark tutorial walks through the UI. Audit done on all 19 screens (screenshots, Festival_14fix loaded); findings and tasks in **Phase 2.6 UI audit → v1.9.0**. The benchmark becomes **2.7 Pub test → v2.0.0**, now with measurable pass criteria and the tool it needs (a functional *Compare* of two workspaces).
- Next: **2.6** (Start screen first, then navigation, then the shared screen pattern, screen by screen).

**Status (29 Sep, evening — Phase 2.5 done, v1.8.0 prepared):**
- v1.7.0 released by giopas (main `7d31694`, tag `v1.7.0`).
- giopas's mesh sample (`mesh test.qxw` + `Bassist.obj` + `cube.obj`, QLC+ 5.2.2) + QLC+ source (`mainview3d.cpp`, `monitorproperties.cpp`, `StageSimple.qml`) → format and placement formula recorded in the wiki page *Stage and Meshes*. His request: fix mesh positions so "on the floor" really is 0 (his bassist needed Y −755 by eye).
- **2.5 Stage and Meshes — done** on branch `feat/stage-meshes` (from `main`; commit `7053f07` + docs/release commit; wiki *Stage and Meshes* page). **v1.8.0 prepared** on the same branch. 517 tests green; tab browser-checked on Festival_14fix (plan/front views, drag, put all on the floor, add from library). **Open: confirm in QLC+ that the Simple ground floor is at 0.1 m** (read from `StageSimple.qml`: 0.2 m slab centred on 0; his eyeballed values sit 45–55 mm above it) — see §8.
- giopas's check: Simple ground floor at 0.1 m confirmed in QLC+ ("It works!"). His request: place one or several meshes with one click → `stage3d.arrange()` + *Place* card: to the stage edges / centre (group, gap to the edge), floor / ceiling (each), line up (8), space evenly between the outer two or across the stage (X/Z), nudge (buttons, arrow keys, PgUp/PgDn, Shift = fine); multi-select (Shift/⌘-click, select all/none), group drag. `tests/test_stage3d.py` 15 tests. 523 tests green; browser-checked.
- Next: **2.6 UI audit → v1.9.0**, then **2.7 Pub test → v2.0.0** (see the status above).

**Status (29 Sep, later — Phase 2.4 done, v1.7.0 prepared):**
- v1.6.0 released by giopas (main `e62a6ee`, tag `v1.6.0`); his QLC+ open-check of `Festival_looks.qxw`: folders, *Looks* page, buttons and chaser timings all as intended.
- **2.4 VC Builder — done** on branch `feat/vc-builder` (from `main`; commit `9eafddb` + docs/release commit; wiki *VC Visual Editor* page updated). **v1.7.0 prepared** on the same branch. 508 tests green; editor browser-checked on Festival_14fix (add, wire, drop a function, drag-move with snap, label panel, template save/apply, page first, setlist CueList, Delete key). Found and fixed on the way: Doctor ignored a slider's playback function. Waiting for giopas: QLC+ open-check of `tests/manual/Festival_vc_builder.qxw` (page *Built*: solo frame of 4 looks, playback slider, label, legend panel, setlist CueList), try the editor on a real show, push, merge, tag (commands in §8).
- giopas's test: `Festival_vc_builder.qxw` fine in QLC+; templates fine on a real show. His feedback "too many options, unclear" → right panel reorganised in three tabs (**✥ Selection** · **＋ Add & wire** ① new widget ② wire ③ ready-made blocks · **▤ Pages**), commit `894929b`; Stop all / Blackout buttons no longer shown as "not wired" (`af2c97d`).
- Next: **2.5 Stage and Meshes** → v1.8.0.

**Status (29 Sep, night — Phase 2.3 done, v1.6.0 prepared):**
- v1.5.0 released by giopas (main `4abaef8`, tag `v1.5.0`); his tests: Doctor D017 fix on the real show works, Rig Reducer works.
- **2.3 Look and Chaser Builder — done** on branch `feat/look-builder` (from `main`; commit `d0ab5c2` + docs/release commit; wiki *Look Builder* page). **v1.6.0 prepared** on the same branch (VERSION, CHANGELOG `[1.6.0]`, README, ROADMAP ✅, release notes + forum post). 497 tests green; tab browser-checked on Festival_14fix. Found and fixed on the way: a new VC page copied the first page's *Enable* MIDI input (`vc_ops.new_page`, `porter_vc._new_page`). Waiting for giopas: open `tests/manual/Festival_looks.qxw` in QLC+ (§6 open-check), try the tab on a real show, push, merge, tag (commands in §8).
- Next: **2.4 VC Builder** → v1.7.0.

**Status (29 Sep, evening — Phase 2.2 done, v1.5.0 prepared):**
- **2.2 Rig Reducer — done** on branch `feat/rig-reducer` (stacked on `feat/doctor-fixes`; commit `35c4dd6` + release commit; wiki `f87b867` *Rig Reducer* page). **v1.5.0 prepared** on the same branch (VERSION, CHANGELOG `[1.5.0]`, README, ROADMAP ✅, release notes + forum post). 476 tests green; both tabs browser-checked. Waiting for giopas: test on the Mac, push, merge, tag (commands in §8).
- Next: **2.3 Look and Chaser Builder** → v1.6.0. *(done — see above)*

**Status (29 Sep, later — Phase 2.1 done):**
- v1.4.1 released by giopas (main `61cdcb9`, tag `v1.4.1`).
- **2.1 Workspace Doctor fixes — done** on branch `feat/doctor-fixes` (from `main`; commits `27bc592` D017, `9c4ba6c` fix engine + CLI, `df1c0ec` Doctor tab, `72efd7c` D010/D011/D013/D014, `9a012ac` docs; wiki `e3157e3`). 469 tests green; tab browser-checked (Festival_14fix: 1 error / 855 warnings → 0 / 53 with the recommended fixes). Not released: v1.5.0 = 2.1 + 2.2 Rig Reducer.
- Next: **2.2 Rig Reducer**.

**Status (29 Sep — v1.4.1 prepared):**
- **Re-test by giopas (29 Sep, v1.4.1 branch): works.** BarShow_v14 *1. SETLIST* → SmallShow, *Source wins*: one page, layout kept; ported CueList has MIDI Next ch 20 / Previous ch 10 + Space, PANIC / BLACKOUT has ch 40; STROBE BLIND!, *Setlist Cue* and BLACKOUT lost exactly those. *Setlist Cue* keeps MIDI Stop ch 30 (BarShow's CueList has no MIDI Stop, so nothing clashed) — expected; to drop the old setlist entirely, tick it under "Remove existing items" in step 4. PANIC RESET = BarShow's scene (see backlog), works as in the source; PANIC / BLACKOUT is the one that stops everything. Idea (not planned): option "replace" — when a ported widget takes over a target widget's bindings, move *all* of that widget's bindings.
- v1.4.0 was released by giopas (main `ed80607`, tag `v1.4.0`). His real-show test (BarShow_v14 *1. SETLIST* → SmallShow, *Source wins*) found: (1) the ported CueList had no MIDI and the target kept its bindings — **bug**: `routes/porter_routes._normalize_plan` whitelisted `bindings` to keep_free/keep/drop and dropped `universe_map`, `copy_input`, `bindings_only`, so every app export used *keep unless used* (the core tests called `porter.port()` directly and never went through the route); (2) *1. SETLIST* split over two pages; (3) PANIC RESET "doesn't work" — **not a Porter bug**: in BarShow it is a *Scene* at 0 (kill auto modes), which can't pull down HTP dimmer/RGB of a running look (same as in the source show); use PANIC / BLACKOUT (Stop all) first, as in BarShow. Backlog item added.
- **Fixed on branch `fix/porter-midi-feedback`** (from `main`, worktree `.wt-fix/`): route passes all 1.5/1.6 options + API-level regression test; step 4 warns about key/MIDI clashes per policy (re-validates on change); a page ported onto a new page keeps its source layout when every unit fits. VERSION 1.4.1, CHANGELOG, README, release notes. 448 tests green; UI checked in a browser with a rebuilt SmallShow target (warning → *Source wins* → 4 bindings moved, one page).

**Status (27 Sep, night — Phase 1.4 release prepared):**
- **v1.4.0 prepared** on branch `chore/release-1.4.0` (stacked on `feat/showbook` @ `88bae82`; worktree `.wt-release/`): VERSION 1.4.0, CHANGELOG `[1.4.0] — 2026-09-27`, README *What's new in v1.4.0* + Workspace Doctor feature section, Alpha badges removed (Quick Start, Function Porter, Show Book — QXW Merger stays α, VC Visual Editor β), new screenshots 13 (Porter) + 14 (Show Book) — the README referenced them but they were missing — release notes `docs/release-notes/RELEASE_NOTES_v1.4.0.md`, forum post `docs/release-notes/FORUM_v1.4.0.bbcode`, ROADMAP. Wiki `f78d1ed`: *Workspace Doctor* page, "(Alpha)" removed. 443 tests green. **giopas:** merge, tag, GitHub Release, forum post — commands in §8. Waits for his tests of 1.5 / 1.6 / 1.3 (any fix goes on `chore/release-1.4.0` before tagging).

**Status (27 Sep, evening — Phase 1.3 done):**
- **1.3 Show Book — done** on branch `feat/showbook` (stacked on `feat/porter-midi` @ `6a5bd84`; local commit `67cbd1f` + docs; wiki `c276e17` *Show Book* page). Built in a separate git worktree (`.wt-showbook/`, git-excluded) so giopas could test 1.5/1.6 in the main folder at the same time — remove it with `git worktree remove .wt-showbook` after pushing. 443 tests green; preview browser-checked; PDF pages checked as images.
- Next: **1.4 release v1.4.0** (after giopas's tests of 1.5 / 1.6 and merges).

**Status (27 Sep, later — Phase 1.6 done):**
- **1.6 Port MIDI / input control — done** on new branch `feat/porter-midi` (stacked on `feat/quickstart-porter` @ `4a234b8`; local commits `0f5275d` engine + tests, `5df21f2` step 4 UI, + docs; wiki `ab21a18`). New `core/porter_input.py`; input patch copied, universe mapping, policy *source wins*, bindings-only copy, report section INPUT / MIDI, step 4 Key / MIDI panel (browser-checked). 420 tests green. Waiting for giopas: push both branches, try with the real BarShow → SmallShow case (§8).
- Next: **1.3 Show Book**, then 1.4 release v1.4.0.

**Status (27 Sep — Phase 1.5 done except the live QLC+ check):**
- **1.5 part 2 done** on `feat/quickstart-porter` (local commits `6b2fd33`, `f08d197`, `6106647` + docs; giopas pushes; wiki commit `0b32320`): Sequence step values remapped/translated, EFX drop targets that can't run their mode, gobo by slot number, Doctor D003 fix for Sequence steps, step 3 translation badge, step 4 translation preview, step 3 starts with Fan-in when the target has none of the source's types. 409 tests green. UI browser-checked (Quick Start hand-off → Porter steps 3/4, Festival_14fix → QuickStart_club).
- **Open:** `tools/qlc_check.py` on the translated output — must run on the Mac (the cloud container's apt QLC+ 4.12.7 reports every button dark even on the untouched `QuickStart_club.qxw`, so it can't judge). Then 1.6.

**Status (25 Sep, late — Phase 1.5 part 1):**
- **1.5 — capability translation + Quick Start hand-off done** on branch `feat/quickstart-porter` (local commits `cdf4ea6`, `f179f39`; giopas pushes). New `core/capability_map.py`; the Porter translates scene values between different fixture types and fan-in Auto-Map pairs different types by family; Quick Start has *➜ Port from an existing show* after export. Festival_14fix → QuickStart_club (all types different): Doctor 0 / 0, byte-identical. 397 tests green. **Waiting for giopas:** QLC+ check of `tests/manual/Festival_to_club_translated.qxw` + UI test of the hand-off (see §8), push.
- Still open in 1.5: in-memory target (no save first), Porter step 3 hint for translated pairs, EFX/Sequence on different types, live `qlc_check` golden. Then 1.6, then 1.3.

**Status (25 Sep):**
- **Phase 1.2 + 1.2b — done** on branch `feat/porter-vc` (local commits, stacked on `main` @ `60db1fa`; giopas pushes, commands in §8): VC porting, fan-in, Doctor gate, port report next to the output; 1.2b UX after giopas's tests (VC tree ticking, automatic dependencies, stage plans, "Port this fixture", highlight, remove target VC items, step 4 → Next / step 5 Export). Real cases Festival_14fix → QuickStart_6fix (fan-in 14 → 6) and Festival_14fix → bare Pub rig (same IDs) pass Doctor with 0 errors / 0 warnings and are byte-identical run to run; the fan-in output passes `tools/qlc_check.py` in QLC+ 5.2.2 for every ported button. 365 tests green. Waiting for giopas: try the Porter tab on the Mac, push.
- Next: **Phase 1.5 (Quick Start × Porter)**, then 1.3 (Show Book) — order changed by giopas on 25 Sep, see §8.

**Status (24 Sep, end of session):**
- **Phase 0 — done and released** as `v1.3.2` (main @ `2cc9dbc`, CI green).
- **Phase 1.0 — core done** on branch `feat/doctor`: corpus, `core/doctor` engine + CLI. Still open: `FloorShow` corpus file.
- **Phase 1.1 — done** on branch `feat/quickstart-1.1` (local commits; giopas pushes): mode-aware channels, neutral values, PANIC RESET (script, works in QLC+ 5.2.2), naming profiles, VC style cloning, Doctor gate, 3 golden rigs, live QLC+ check (`tools/qlc_check.py`). **1.1b (24 Sep, after giopas's test):** full-width page, whole-rig solo frame + one solo frame per group (groups combine), Audio React, fixture groups (editor in step 3; per-group frame with submaster, looks, effects), MASTER submaster, working RGB-matrix effects (Collection: dimmer scene + matrix), fixture `.qxf` saved next to the workspace only when QLC+ lacks it, indented XML (QLC+ 5.2.2 loader bug), corpus renamed/scrubbed (`Festival_14fix`, `Pub_6fix`). All golden rigs PASS `tools/qlc_check.py` in QLC+ 5.2.2 (and club in 4.14.5). Waiting for giopas: test on the Mac, push.

---

## 1. Goal

Build the next show file (e.g. a new venue version like Pub) **with the tool, not with an AI patching XML**:

- Reduce or adapt a rig.
- Port looks and effects.
- Generate looks and chasers.
- Lay out the Virtual Console: pages, frames, buttons, CueList and labels.
- Place fixtures and meshes in 3D.
- Validate everything before export.

The result must be:

- **Deterministic:** same input gives byte-identical output.
- **Accurate:** QLC+ opens it cleanly and it behaves on stage.
- **Useful to other QLC+ users too:** conventions are configurable, not hard-coded to one band's habits.

### Acceptance benchmark (the "Pub test")

Rebuild `Pub_6fix.qxw` starting from `Festival_14fix.qxw` using **only Swiss Knife**:

1. Reduce the rig from 14 fixtures to 6.
2. Port the looks.
3. Generate the new chasers.
4. Build the two-page VC and wire the setlist CueList.
5. Run Doctor.

The result must pass Doctor with zero errors and, compared with the hand-made `Pub_6fix.qxw`, show no functional regressions (same patch and groups, the same looks, chasers, VC pages and setlist). When this passes, the goal is met. The route, the measurable pass criteria and the tools still missing are in **Phase 2.8** (renumbered 1 Oct: 2.7 is now *Grow a rig*).

---

## 2. Engineering principles (apply to every change)

1. **Never overwrite.** Every write produces a new file: `<name>_v<N+1>.qxw` for edits, `<name>_doctor.qxw` for Doctor fixes. The original is never touched.
2. **One writer.** All QXW output goes through `core/qxw_io.write_qxw()`:
   - XML declaration and `<!DOCTYPE Workspace>` are always present.
   - `ElementTree.write()` is never used directly.
   - A round-trip test (load → write → load) must be lossless.
3. **Deterministic IDs and ordering.**
   - New IDs are allocated as `max(existing) + 1`, in a stable sorted order.
   - Generated XML has no timestamps or random values.
   - Golden-file tests compare output byte-for-byte.
4. **Doctor gates every export.** Quick Start, Porter, Rig Reducer, Look Builder and VC Builder all run Doctor before writing. Errors block the export; warnings are shown in the report.
5. **Safe-by-default show content.** Generated scenes:
   - declare **every channel of every fixture** they touch (no LTP bleed);
   - keep strobe and internal-program channels at 0 unless explicitly asked;
   - always include a PANIC RESET.
   - VC buttons and chaser steps never share a scene (latch conflict).
6. **QLC+ is the reference.** Every generator has a manual *QLC+ open-check* (§6) before release.
7. **Conventions are data, not code.** Nomenclature, palettes, VC screen size and templates live in JSON *profiles* that users can share. The two-letter prefix profile is just the first one.
8. **Tests and CI green before merge.** No feature merges without tests; CI runs on every push.

---

## 3. Decisions log

| Date | Decision |
|---|---|
| 2026-09-23 | Doctor **always saves to a new file** (never in place). The same applies to every tool that writes a QXW, including Trigger Manager. |
| 2026-09-23 | **Fixture tilt defaults for music shows** (QLC+ 3D convention: XRot 0 = beam straight down, 90 = horizontal, 180 = straight up):<br>• Truss/ceiling: 45° from vertical, aimed at the stage (front/back-light angle).<br>• Floor: 45° up toward the performers (uplight).<br>• Mid-height: horizontal, aimed at the stage.<br>Tilt direction comes from the fixture's depth position (downstage fixtures tilt upstage, upstage fixtures tilt downstage). Per-fixture override stays available. The previous straight down/up defaults lit only the floor and the ceiling. |
| 2026-09-23 | The `*-1` files (`qxw_builder-1.py`, `quick_start_routes-1.py`, `quickstart-1.js`) are **older copies** of the current files (they predate commit `a950cc8` and still use `requests`). They are to be deleted, not merged. |
| 2026-09-23 | The benchmark target is **Pub_6fix** (it supersedes v11). `FloorShow` is optional; add it when available. |
| 2026-09-23 | Doctor treats a scene as intentional FX if it **or any function containing it** is marked as FX (name or allow-list). Caption-only buttons are *info*, not errors. |
| 2026-09-23 | AI integration (MCP server) is deferred until Doctor and the builders are done. See §7. |
| 2026-09-23 | **One naming rule for every tool:** suggested/new files are `<name>_v<N+1>.qxw` (`<name>_v2.qxw` if there is no `_vN`), replacing `_GIG_READY`, `_BRIGHTNESS`, `_merged`, `_imported`, `_modified`. `next_version_path()` skips names already on disk. |
| 2026-09-23 | Tilt sign convention (from the corpus): positive XRot swings a hanging beam toward +Z ("Front"). Defaults: truss 45/315, mid 90/270, floor 135/225 (upstage half / downstage half). **Confirmed in QLC+ 5 3D view on 23 Sep (0.2): all three pairs cross toward centre stage.** |
| 2026-09-23 | Doctor severities: D001–D003 errors; D004–D009, D012, D016 warnings; D015 and I-codes info. D005 is a warning (not an error) so porting from older shows is not blocked before auto-fix exists. |
| 2026-09-23 | VC copy/move (added to v1.3.2 at giopas's request): copies get new widget IDs (`max+1`) and **drop key/MIDI bindings by default** (opt-in to keep); moves keep IDs and bindings; operations refuse duplicated widget IDs (D002). The Triggers tab is renamed **Trigger Manager**. The venv lives in `~/.venvs/swissknife` (iCloud duplicates break pywebview). |
| 2026-09-23 | **Quick Start channel model:** channel indices come from the selected **mode**; unused channels get a capability-aware **neutral** value (ShutterOpen preset or an *Open / No function / White / Off* capability, never a *Closed/Blackout* one; Pan/Tilt coarse 127, fine 0; otherwise 0). BLACKOUT additionally closes the shutter on fixtures with no dimmer channel. PANIC RESET = neutral + intensity 0, on its own Toggle button. |
| 2026-09-23 | **Two-letter prefix naming profile** taken from the legend on the Pub_6fix EFFECTS page: format `{group}{effect} · {name}`; groups A F S B R D L X (all, front four, singer pair, band pair, rear two, drums floor, logo, split/spatial); effects S D P M \* (static, dynamic, pulse, movement, special FX). Quick Start only knows "all" (A); anything the profile can't map (utility functions, per-type group scenes) gets **no prefix** rather than a wrong one. Buttons carry the prefix too (`prefix_captions`). |
| 2026-09-23 | **VC style cloning** copies geometry and fonts only (button size = most common ≥30 px tall, gap = median horizontal gap, header = smallest child Y in headed frames, page = most common top-level frame size). Colours stay semantic. |
| 2026-09-23 | Doctor D006: a value of **0** on a capability with no preset and no "active" words (strobe, program, auto, macro, sound, pulse, chase …) is safe — it is the fixture's plain operating mode (SlimPAR 56 `Mode = 0 (RGB)`). Corpus baselines unchanged. |
| 2026-09-24 | **Quick Start VC = one page.** Whole-rig LOOKS + EFFECTS share one SoloFrame (plain sub-frames pass the solo signal up in QLC+ 5): one at a time. **Each group is its own SoloFrame** (one at a time inside a group, groups combine — giopas, 24 Sep). Only PANIC / BLACKOUT and PANIC RESET are outside. Page size = style page (default 1650 × 884). Sliders carry `InvertedAppearance="false"` (QLC+ 5 default is inverted). **Audio React** = fixture's own sound-active capability (Sound/Audio/Music label, middle of range), only if present. |
| 2026-09-24 | **Fixture groups** are user-defined in step 3 (default: one per fixture name). Each group: frame with a **submaster** (group dimmer), looks (On, Red, Blue, Green, Warm), effects (Pulse, Color Fade, Chase). Group scenes declare only the group's fixtures. MASTER is a page-level submaster. RED/GREEN/BLUE Level sliders and the *Color Fixtures* button are dropped. two-letter prefix names: group letter = first letter of the group name unless mapped. |
| 2026-09-24 | **RGB-matrix buttons run a Collection** (scene opening the master dimmers + the matrix): QLC+ ignores *DimmerControl* in RGB mode (`rgbmatrix.cpp`). Only scripts that exist in QLC+ 4 and 5: One By One, Even/Odd, Gradient, Plasma, Waves, Stripes. |
| 2026-09-24 | **Generated XML is indented** like QLC+'s own (QLC+ 5.2.2 `VCSlider::loadXMLLevel` reads one token too many after an empty `<Level/>`; on a one-line file that drops every later widget). **Fixture definitions QLC+ lacks are saved next to the workspace** as `<Manufacturer>-<Model>.qxf` (QLC+'s fallback path in `Fixture::loader`), else unknown fixtures load as plain dimmers. Stock fixtures (found in the installed QLC+ library or user folder, `qlc_library.py`) get no file; if the installed definition lacks the chosen mode → warning (QLC+ prefers its own definition). |
| 2026-09-24 | Real show files in the public repo are **renamed and scrubbed** (`Festival_14fix`, `Pub_6fix`; bands/songs/venue → neutral names). Git history still contains the originals — purge only if needed (needs a force-push). |
| 2026-09-23 | **PANIC RESET is a Script**, not a scene: `stoponexit:false`, stop every generated function, start *Reset: neutral state*, `wait:100ms`, stop itself. Reasons, all reproduced in real QLC+ builds: HTP channels can't be pulled down by a scene; QLC+ 5 scripts (to spring 2026) never end on their own; QLC+ 5.2.2 drops queued script commands if the code ends before the next tick (upstream fix `ca8ffd41`). The master slider is a Level **DIMMER** at 0 (a Level slider at 255 held dimmers full; a Submaster slider made 5.2.2 drop the VC). |
| 2026-09-23 | **Behaviour is verified in real QLC+**, not only by reading XML: `tools/qlc_check.py` (web-socket API) is part of the §6 open-check. Target versions: QLC+ 5.2.2 (giopas's) and 4.14. |
| 2026-09-25 | **Porter fan-in rule:** a target fed by several sources takes, per scene, the values of the **first lit source** in its block (intensity/colour > 0, from the QXF; any channel > 0 without one), else the first declared source. Blocks come from 3D stage order (X, then depth; DMX address if positions are missing), per fixture type. Colours are never mixed. |
| 2026-09-25 | **Porter safety defaults:** unmapped source fixtures are an error unless *leave out* is ticked; functions left with no fixture are removed with their steps/buttons (reported); ported scenes declare every channel (neutral values from `channel_model`); a Quick Start PANIC RESET script in the target gets `stopfunction` for every ported function; ported Level sliders start at their low limit; Doctor blocks the export only on errors the target didn't already have. |
| 2026-09-25 | **Porter VC rules:** units = items directly on a source page (a picked page = its items); a widget stays if all its functions are ported; label/StopAll buttons stay inside kept frames; in auto mode a frame needs a working widget. New IDs `max+1` in document order; bottom-left placement with 10 px margin/gap; continuation page when full. Bindings default *keep unless already used in the target*. Source widgets are addressed by document-order keys (`w<N>`), since real files can repeat widget IDs (D002). |
| 2026-09-23 | D006 intent keywords: *strob, flash, `*`, punk, macro, program, audio, fx* (own name or any containing function). A value is neutral if it falls in a *No function / No flash / Open / Off / DMX mode* capability. StopAll/Blackout buttons are not "caption-only". |

---

## 4. Git and documentation workflow (every step)

**Branches**
- One branch per phase: `chore/phase0-cleanup`, `feat/doctor`, `feat/porter-vc`, and so on.
- Merge to `main` when CI is green.
- Tag releases `vX.Y.Z`.

**Commits** (Conventional Commits, as already used in the repo)
- Types: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`.
- Keep commits small and focused: one logical change each.
- Suggested messages are listed per step below.

**Per step, before committing**
- [ ] Tests added or updated; `python -m pytest -q` is green locally.
- [ ] `CHANGELOG.md`: entry under `## [Unreleased]` (Added / Changed / Fixed / Security).
- [ ] Docstrings for new public functions; user-facing wording checked.

**Per release**
- [ ] Bump `VERSION` in `core/workspace.py`. The single source of truth; check that it matches the CHANGELOG.
- [ ] Move `[Unreleased]` to `[X.Y.Z] — date`.
- [ ] README stays a presentation (no *What's new* sections — the CHANGELOG has them); screenshots retaken where a screen changed.
- [ ] Wiki page for each new or changed tool (usage, limits, examples).
- [ ] `git tag vX.Y.Z` and a GitHub Release, with notes copied from the CHANGELOG.
- [ ] Forum: no post per release (giopas, 1 Oct). One complete post at v2.0.0, then only for major releases; drafts are not kept in the repo.

**Push:** Cowork's sandbox cannot reach GitHub, so Cowork commits locally and giopas pushes.

---

## 5. Work programme

### Phase 0 — Clean the bench → **v1.3.2** *(½ session)*

Findings this phase fixes (repo review, 23 Sep):
- 27 stale Quick Start tests.
- `test_porter.py` imports a module that doesn't exist (`core_porter`).
- Trigger save uses `ET.write()` in place, which drops the DOCTYPE and overwrites the original.
- `VERSION` says 1.3.0 while the CHANGELOG says 1.3.1.
- No CI.
- `ROADMAP.md` is still the May tkinter plan.

| # | Task | Acceptance | Commit |
|---|---|---|---|
| 0.1 | Delete the three `*-1` duplicate files; confirm nothing imports them. | App starts; all tabs load. | `chore: remove stale duplicate Quick Start files` |
| 0.2 | Apply the tilt defaults from §3 in `_compute_orientation()`, deriving direction from depth. Update the Quick Start UI presets to match. | Unit tests per zone. Visual check in the QLC+ 5 3D view using a 4-fixture test file. | `fix(quickstart): show-lighting tilt defaults (45°)` |
| 0.3 | Create `core/qxw_io.py`:<br>• `write_qxw(root, path)`<br>• `next_version_path(path)` (`_v41` → `_v42`, otherwise `_v2`)<br>• `load_qxw(path)`<br>Refactor all write sites (workspace, merger, porter, fixture, brightness, quick start) to use it. | Round-trip test; a grep finds no other `.write(`/`tostring` output paths. | `refactor: single safe QXW writer` |
| 0.4 | Trigger Manager saves to a new versioned file via `write_qxw()`. | DOCTYPE kept; original untouched. | `fix(triggers): keep DOCTYPE, never overwrite original` |
| 0.5 | Move `test_porter.py` and `test_qxf_parser.py` into `tests/` and fix the import. Update the stale Quick Start tests to the 3-tuple return; check each failure is a stale test, not a bug. Add `pytest.ini`. | `pytest -q`: 0 failures. | `test: consolidate suites under tests/, fix stale tests` |
| 0.6 | Add `.github/workflows/tests.yml` (Python 3.11 and 3.12, pytest). | Badge in README; green run. | `ci: run tests on push and PR` |
| 0.7 | Documentation:<br>• Rewrite `ROADMAP.md` from this plan.<br>• Move the `RELEASE_NOTES_*.md` files to `docs/release-notes/`.<br>• Add these principles and the test command to `DEVELOPMENT.md`.<br>• Add `WORKPLAN.md` (this file).<br>• Decide whether `Claude outputs/` belongs in the repo (probably `.gitignore` it). | Docs reviewed. | `docs: new roadmap, work plan, dev principles` |
| 0.8 | Fix the `VERSION` mismatch and release **v1.3.2**. | Tag and GitHub Release. | `chore(release): v1.3.2` |

**Phase 0 status — ✅ done 23 Sep** (branch `chore/phase0-cleanup`, 0.1–0.8 each in its own commit; 216 tests green). Open items for giopas: ~~0.2 visual check~~ (done 23 Sep, correct); 0.6 first green CI run; 0.8 tag + GitHub Release after merge.

Found and fixed along the way (all in the CHANGELOG):
- **Merger and Porter read 0 fixtures / 0 functions from every real QLC+ file** (namespace bug; their tests used namespace-free files). Fixed in `fix(merger,porter): read namespaced QLC+ workspaces`.
- Brightness "Fetch missing QXFs" always failed (`NameError` on `_HTTP_HEADERS`).
- Trigger Manager's "Save as new file…" button actually called the in-place save.
- `app.py` hard-coded the UI version string; it now reads `VERSION`.
- The 27 stale Quick Start tests were all stale (no code bugs).

### Phase 1 — Take the three tools out of Alpha → **v1.4.0** *(2–3 sessions)*

**1.0 Test corpus and Doctor core (read-only checks).** Doctor comes first because it is the test oracle for everything else.
- [x] Create `tests/corpus/` *(done 23 Sep)*:
  - Workspaces: `Festival_14fix`, `Pub_6fix` (only `<Author>` sanitised).
  - QXFs: Eurolite LED 4C-12, Generic 7-Ch RGB PAR.
  - Also included: `expected_baseline.json`, `README.md` (baseline findings and lessons), `tests/test_corpus.py` (6 tests), and `tools/doctor_prototype.py` (throw-away reference implementation).
- [x] Add a clean Quick Start output to the corpus *(`QuickStart_6fix.qxw`, generated by `tools/make_quickstart_sample.py`; Doctor: 0 errors, 1 warning D008)*.
- [x] Add `FloorShow` when available. *(3 Oct: `FloorShow_8fix.qxw`, anonymised; baseline pinned)*
- [x] `core/doctor/` exposes `check(root, qxf_defs) → Report`. Each finding has an ID, severity, location and message. Read-only in this phase. *(Also `check_file()`, `load_qxf_defs()`; docs in `docs/doctor.md`.)*
- [x] Initial checks: the D-codes in §5 Phase 2.1 marked ★. *(Plus D009, D012, D015, D016 and info I001–I003. Corpus: Pub_6fix 0 errors / 0 warnings; Festival_14fix 1 error (D002 widget ID 0); all prototype D006 false positives gone. Counts pinned in `expected_baseline.json`.)*
- [x] Command line: `python -m core.doctor file.qxw` prints the report and exits non-zero on errors. Used by tests and CI; it's also the future hook for automation. *(`--json`, `--qxf`, `--allow-fx`, `--all`, `--min-severity`.)*
- Commit: `feat(doctor): read-only check engine + CLI`

**1.1 Quick Start**
- [x] Golden-file tests: 3 reference rigs produce byte-identical `.qxw` output. *(`QuickStart_6fix`, `QuickStart_club` (Spot 110 6-ch + SlimPAR 56), `QuickStart_multiuni` (8 × Spot 375Z + 60 × SlimPAR 56, 2 universes); `tests/test_quickstart_golden.py`.)*
- [x] Output passes Doctor with zero errors, and the QLC+ open-check (§6) passes. *(Doctor: all three golden files 0 errors / 0 warnings; export gated by Doctor. QLC+: `tools/qlc_check.py` PASS on club + multiuni in 5.2.2 and 4.14.5; manual check on the Mac, 23 Sep.)*
- [x] **Live QLC+ check** (`tools/qlc_check.py`, `docs/qlc-live-check.md`, opt-in `tests/test_qlc_live.py`): VC loaded + every button lights something + PANIC RESET after every button, on the real DMX output.
- [x] **1.1b after giopas's test (24 Sep):** full-width page; one SHOW solo frame (one button at a time); fixture groups (step 3 editor, per-group frame + submaster + looks + effects); MASTER submaster; RGB matrices lit (Collection); `.qxf` next to the `.qxw`; indented XML.
- [x] Safe defaults baked in: PANIC RESET, strobe and program channels at 0, full channel declaration. *(Plus mode-aware channel indices and capability-aware neutral values — `core/quick_start/channel_model.py`.)*
- [x] **Clone VC style from a reference QXW**: button size, gaps, header, fonts, page size (`core/quick_start/vc_style.py`). Built-in `compact` style extracted from `Pub_6fix`; *From a reference .qxw…* in step 4. *(Frame layout/page structure cloning → Phase 2.4 VC templates.)*
- [x] Nomenclature profile (JSON): `plain` and `prefix` (two-letter prefix; renamed 1 Oct) in `core/quick_start/profiles/nomenclature/`. The two-letter prefix profile:
  - First letter, fixture group: A = all, F = front four, S = singer pair, B = band pair, R = rear two, D = drums floor, L = logo, X = split/spatial.
  - Second letter, effect type: S = static, D = dynamic, P = pulse, M = movement, \* = special FX.
- Commits: `test(quickstart): golden outputs`, `feat(quickstart): clone VC style from reference`, `feat: nomenclature profiles`

**1.2 Function Porter** — ✅ *done 25 Sep, branch `feat/porter-vc`*
- [x] **VC porting**: bring each ported function's buttons and frames too, with widget ID remapping, a target page chosen by the user, and collision-free placement. *(`core/porter_vc.py`; step 2 picks frames/buttons from the source VC and seeds the port; step 4: target page or new page, binding policy.)*
- [x] Verify **fan-in** (many source fixtures to fewer targets, e.g. 14 → 6). *(Explicit `fan_in` mode + Auto-Map strategies `fan_in` (stage order) and `same_id` (reduced rig); "first lit source wins" per scene.)*
- [x] Real case: port looks from Festival_14fix into a 6-fixture rig. The result passes Doctor. *(Both QuickStart_6fix (fan-in) and the bare Pub rig (same IDs): 0 errors, 0 warnings; `tests/test_porter_fanin.py`.)*
- [x] The import report is saved next to the output file. *(`<name>_port_report.txt`.)*
- **1.2b — Porter UX after giopas's test (25 Sep)** *(branch `feat/porter-vc`)*:
  - [x] Step 2: VC list has its own ✓ All / ✗ None; ticking a page/frame ticks everything inside (dash when partly ticked). *(commit `3bdaaee`)*
  - [x] Step 2: dependencies resolve automatically while ticking; *Resolve Dependencies* button removed; **Next** resolves then moves on. *(`3bdaaee`)*
  - [x] Porter messages use the app's single status bar (a stale "No workspace is open" from ⤵ Open workspace no longer shows under the Porter). *(`3bdaaee`)*
  - [x] **Stage plans** *(done 25 Sep)*: step 1 shows a top view of where the fixtures are in the source and in the target (from the 3D monitor positions; nothing drawn if the file has none), reusing the Fixtures-tab drawing code (`static/js/fixture.js` top view, `core/fixture.py` stage/position reading). Step 3 shows the same two plans coloured by the mapping (each target a colour, its sources in the same colour, unmapped grey) so the mapping can be checked at a glance. *(Implemented: `core/fixture.py` `read_stage_dims()` / `read_positions()` / `stage_plan()` (pure, reused by `import_from_qxw`); `GET /api/porter/stage/<source|target>`; `static/js/fixture.js` `drawStageTopView()` shared by the Fixtures tab and the Porter; tests in `tests/test_porter_fanin.py::TestStagePlan`. Checked in a browser with BarShow_v14 → SmallShow_4generic_2.)*
  - [x] Step 2 **Next button hidden** when the two lists are tall (giopas's screenshot, 25 Sep): the step's content now scrolls in `.porter-panel-body`, the Back / Next bar stays at the bottom (checked at 1000×620 and 1600×1000).
  - [x] Step 3 **"Don't port this fixture"** *(done 25 Sep: "Port this fixture" checkbox per row; uses `lit_fixture_map` from `resolve_closure` — a scene declaring a fixture at 0 doesn't "use" it; checked in a browser: skipping DR + LG unticks *RS · Silhouette* and *LS · Logo Only* in step 2, re-including restores them)* per source fixture (giopas, 25 Sep): the fixture gets no target and its values are left out; functions (and VC widgets) that use *only* skipped fixtures are unticked in step 2 (visible when going back) and come back when the fixture is included again. The mapping of the other fixtures is kept when the selection changes.
  - [x] Step 3 **highlight**: hovering or clicking a mapping row rings that source fixture on the source plan and its target(s) on the target plan. *(done 25 Sep; click pins the highlight)*
  - [x] *(done 25 Sep)* Export step: say clearly that the **import report** was saved too (file name + folder of both files); if it could not be saved, say so and point to 📋 Copy Report. (giopas, 25 Sep)
  - [x] *(done 25 Sep: `porter_vc.remove_widgets()`, `GET /api/porter/target/vc`, plan `vc.remove`; report section "Removed from the target VC"; browser-checked on SmallShow — removing *Control Panel (Exclusive)*: 0 new Doctor errors, the now-unused functions show as D016 warnings)* Step 4: **remove existing target VC items** (pages, frames, buttons, sliders…) from the output — a tree of the target VC with "remove" ticks; removal happens before placement so the freed space is reused; a removed page can't be the "Place on" page. (giopas, 25 Sep)
  - [x] *(done 25 Sep, browser-checked)* Step 4 → **Next: Export**; the new `.qxw` is written only in step 5 (summary of what will be written + "💾 Export new QXW…"), so step 5 is a real step. Wording: Porter *exports* a new workspace + *port report* (no "Import & Save"). (giopas, 25 Sep)
  - [x] *(done 25 Sep)* Full documentation pass (WORKPLAN, wiki, README "Coming in v1.4.0" + Function Porter section + project structure, CHANGELOG) and push commands for giopas before starting 1.5.
  - [ ] Fan-in ordering idea (not started): use Left/Right/Front/Back words in fixture names when positions and names disagree (SmallShow case).
- Found and fixed along the way: non-deterministic function IDs (closure ordered by a set); EFX fixtures and percent-encoded script commands not recognised in real QLC+ files; values of unmapped fixtures left in scenes (dangling refs); RGB matrices pointing at a group missing in the target; ported looks surviving the target's PANIC RESET (live check).
- Commits: `feat(porter): port VC widgets with functions`, `test(porter): Festival_14fix→Pub_6fix fan-in case`

**1.3 Show Book** — ✅ *done 27 Sep, branch `feat/showbook` (`67cbd1f`)*
- [x] Test suite `tests/test_showbook.py` (24): section builders on Pub_6fix (summary 6 fixtures / 207 functions / 98 widgets on 2 pages, patch sorted, function index, chaser times), DMX decoding against the corpus QXFs (`78% (200)`, `No flash (0)`, `DMX Mode …`, Eurolite RGBW names, Spot 110 pan `268.9° (127)` with `qxf_dir`, raw when no definition), CSV zip contents (11 files, row counts, summary.txt), PDF text layer (own Flate/`Tj` extractor: patch names, `Page: 1. SETLIST`, emoji dropped, `» »` depth), deterministic zip + PDF.
- [x] **VC Layout** rebuilt from the VC XML (`_build_vc_layout(root, state)` → `{pages: [{id, type, caption, size, widgets}], widget_count}`): widgets in document order with ID (was always empty: `widget_id` vs `id`), frame path inside the page, depth, X/Y/W/H, function (or *(stop all functions)* / *(blackout)*), key/MIDI bindings with slot (`Next: key Space, Prev: key Backspace, Stop: key Esc`, `MIDI U2 ch 40`). Matches Pub_6fix: pages *1. SETLIST* / *2. EFFECTS* 1650×884, *AS · Emerald City* in `◆ SHOW — one look at a time › ◼ LOOKS` at depth 2. Preview: one table per page, frames indented; PDF: per-page sub-tables (`» ` per depth); CSV: page + frame path + geometry + bindings.
- [x] **Doctor summary** section `doctor` (in `ALL_SECTIONS`, can be unticked): counts of errors / warnings / info + every error and warning; preview, PDF, `doctor.csv`, summary.txt.
- [x] Also: shows/scripts in PDF + CSV; definitions next to the workspace and from the installed QLC+ library loaded automatically; patch model without the manufacturer prefix; PDF text cleaned (emoji dropped, `—`→`-`, `›`→`>`); title/table overlap fixed; empty sections left out of the PDF; `generate(date=…)` + fixed zip timestamps → byte-identical exports.
- Commit: `feat(showbook): VC layout by page with bindings, Doctor section, tests`
- Commit: `test(showbook): coverage for sections, decoding, exports`

**1.4 Release v1.4.0** — *prepared 27 Sep, branch `chore/release-1.4.0`; tag + release by giopas*
- [x] Remove the Alpha badges (sidebar + page titles of Quick Start, Function Porter, Show Book; README feature headings and screenshot captions; wiki titles and Home).
- [x] Wiki pages for Quick Start, Porter, Show Book (all current) and **Workspace Doctor** (new, from `docs/doctor.md`: where it runs, CLI, checks table, v1.5 auto-fixes).
- [x] VERSION `1.4.0` (`core/workspace.py`), CHANGELOG `[1.4.0] — 2026-09-27` (+ Changed: out of Alpha), README title + *What's new in v1.4.0*, ROADMAP ✅, release notes, screenshots 13/14 (taken from the app with the scrubbed corpus files).
- [x] Forum post drafted (BBCode): `docs/release-notes/FORUM_v1.4.0.bbcode`.
- [ ] giopas: merge to `main`, `git tag -a v1.4.0`, GitHub Release (body = `RELEASE_NOTES_v1.4.0.md`), forum post, wiki push.

**1.5 Quick Start × Porter — "start a new rig from an existing show"** *(requested by giopas 25 Sep; before 1.3 Show Book. **Part 1 done 25 Sep**, branch `feat/quickstart-porter`: commits `cdf4ea6` capability translation + Porter, `f179f39` Quick Start hand-off)*

Goal: build a new show for a **different rig** (other fixture types, number, arrangement, positions) and port everything that can be ported from an existing show in one flow, instead of Quick Start first and Porter second.

- [x] **Different fixture types — `core/capability_map.py`** *(done 25 Sep, `cdf4ea6`)*: `decode()` reads a fixture's values into a `LookState` (dimmer level, colour, white emitter, pan/tilt in degrees from centre, shutter open/closed/strobe + relative speed); `encode()` writes it on the target mode, every channel declared; `translate()` / `translate_text()` ("ch,val,…"); `kind()` = family *moving / colour / dimmer / unknown*. Rules (also in the module docstring):
  - level = source master dimmer (1.0 if none); colour from emitters R G B W A UV C M Y Lime Indigo, else colour wheel, else white;
  - target dimmer + RGB → dimmer = level, RGB = colour; RGB without dimmer → RGB × level; dimmer + wheel → dimmer = level × brightest component, wheel = nearest slot (`Res1` hex, else a colour word in the label; *Open*/*White* = white; ties → lowest DMX value); dimmer only → level × peak;
  - target White emitter = the source's white emitter (0 if none), RGB reduced by it;
  - pan/tilt: centre-relative degrees via QXF `PanMax`/`TiltMax` (fraction of range if either side lacks it), 16-bit when the mode has fine channels, clamped + noted; position on a fixture without pan/tilt is dropped (noted only if off-centre, > 3°);
  - shutter: open → target open value; closed → target closed value, or intensity 0 when it has none; strobe → same relative speed in the target's first strobe range (`strobe="drop"` → open, noted);
  - everything else (gobo, prism, macros, programs, speeds, zoom) → `channel_model.neutral_value`.
- [x] **Porter uses it** *(done 25 Sep, `cdf4ea6`)*: `_translators()` builds `(src, tgt) → defs` for mapped pairs whose model/mode differ and whose definitions are both known; `_remap_fixture_refs()` translates Scene values for those pairs (EFX / Sequence untouched). Validation: *info* "values translated by capability" (the "copied channel by channel" warning stays for pairs without definitions). Plan options `translate_types` (default True), `strobe` ("keep" | "drop"). Result key `translated` → report section *TRANSLATED BETWEEN FIXTURE TYPES* (pairs + notes).
- [x] **Fan-in Auto-Map across types** *(done 25 Sep, `cdf4ea6`)*: same-type pairs as before; source types with no same-type target are paired with the target types no source uses — bigger source types choose first: unused target type of the same family, else any unused one, else same family (shared), else any; then equal stage-order blocks. `auto_map(ids, strategy, qxf_paths=None)`; `POST /api/porter/auto-map` accepts `qxf_paths`.
- [x] **Golden test (Doctor part)** *(done 25 Sep, `tests/test_capability_map.py`, 24 tests)*: Festival_14fix FLOOR + CEILING → QuickStart_club (Spot 110 ×2 + SlimPAR 56 ×4, all types different): 6 ceiling spots → the 2 Spot 110, 8 floor PARs → the 4 SlimPARs; Doctor 0 errors / 0 warnings; *Dark Red* on the Spot 110 = wheel 32 (Red) + dimmer > 0; byte-identical run to run. Sample output for the QLC+ check: `tests/manual/Festival_to_club_translated.qxw`.
- [x] **Quick Start hand-off** *(first version, done 25 Sep, `f179f39`)*: after *💾 Generate QXW* saves the rig, the footer shows **➜ Port from an existing show** (`qsPortFromShow()` in `static/js/quickstart.js`): opens the Porter, loads the saved file as the target, goes to step 1; the user loads the source show and uses Auto-Map *Fan-in*. Output = the Porter's `<name>_v2.qxw` (Quick Start VC/looks + ported functions/widgets, PANIC RESET extended, Doctor gate once). *Not browser-tested in this session (the app runs on the Mac) — giopas to test.*
- [ ] `tools/qlc_check.py` PASS on the translated output (needs QLC+ — giopas's Mac; tried 27 Sep in the cloud container with `apt install qlcplus` (4.12.7 GUI build, `--offscreen`): every button reads dark even on the untouched `QuickStart_club.qxw`, so that setup can't judge — use the source build from `docs/qlc-live-check.md` for CI later).
- [ ] *(optional, only if the save-first hand-off feels clumsy in use)* Quick Start rig **in memory** as the Porter target.
- [x] **Step 3 translation badge** *(27 Sep, `f08d197`)*: under each mapping row — *↔ Different type — values translated by capability* or *⚠ Different type, definition missing — values copied channel by channel* (`_pXlateBadge()` in `static/js/porter.js`; tier2/tier3 candidates carry `translatable`; `build_fixture_candidates(ids, qxf_paths)`, route accepts `qxf_paths`).
- [x] **Step 4 translation preview** *(27 Sep, `f08d197`)*: `porter.translation_preview()` runs the translation on the closure's scene/sequence values before export → *info* "Translation source X → target Y: <note> (n×)"; *warning* for every EFX target that will be left out. Called from `validate()`.
- [x] **Step 3 default** *(27 Sep, `6106647`)*: when no source fixture has an exact-type target, the first Auto-Map uses *Fan-in by stage position* (and fan-out mode fan-in, leave-out on) instead of *every exact match* (which mapped nothing). Browser-checked: all 14 rows mapped with the ↔ badge.
- [x] **Sequence step values** *(27 Sep, `6b2fd33`)*: `Step` text `fid:ch,val,…:fid:…` remapped like scenes (fan-in "first lit", translation, every channel declared, `Values` = number of pairs); step fixtures are part of the closure. Doctor D003 no longer reads Sequence steps as function IDs (false "step → missing function").
- [x] **EFX** *(27 Sep, `6b2fd33`)*: `capability_map.efx_modes()` (position / dimmer / rgb); an EFX fixture whose target can't run its `<Mode>` (0 position, 1 dimmer, 2 RGB) is left out, noted in the report; an EFX left with no fixture is removed as before.
- [x] **Gobo** *(27 Sep, `6b2fd33`)*: gobo wheel slots (preset GoboMacro or *Open* / *Gobo N*) map by slot number; *Open* stays open; wraps on a smaller wheel (noted); dropped with a note on fixtures without a gobo wheel. Rotation channels are not wheels.
- Fixed along the way (27 Sep): false note *target cannot make colour* for a dark look on a colour-wheel fixture.

**1.6 Port MIDI / input control from the old show** *(requested by giopas 25 Sep; **done 27 Sep**, branch `feat/porter-midi`: `0f5275d`, `5df21f2`)*

Today the Porter keeps the key/MIDI bindings **on the widgets it ports** (policy *keep unless already used in the target*), but it does not bring the **input setup** they depend on, so in the new file they may point at a universe with no MIDI input (dead bindings, Doctor D012).

- [x] **Input patch** (`porter_input.apply_patch()`): for every target universe that kept bindings use — same device already there → ok; no device → copy the source universe's `<Input>` (plugin, UID, Name, line, `Profile`) and `<Feedback>` (option `vc.copy_input`, default on; creates the `<Universe>` in ID order if the target lacks it); another device → warning (bindings kept); source had none → warning. Device name = `Name`, else `UID` (5.2.1 GIT saves `UID="SINCO"` only), compared case-insensitively.
- [x] **Universe mapping** (`vc.universe_map` = {source universe ID: target universe ID}, 0-based): `remap_universes()` rewrites every `<Input Universe>` in ported widgets before the binding policy runs, so conflicts are checked on the target universe.
- [x] **Bindings on ported widgets**: `porter_vc._filter_bindings()` logs each binding (kept / dropped: *already used by the target's Button 'X'* / moved); new policy **`source_wins`** keeps the binding on the ported widget and removes it from the target widgets that had it (after placement). Summary line counts kept / dropped / moved / remapped.
- [x] **Bindings only** (`vc.bindings_only`, `porter_input.copy_bindings()`): source widgets (the step 2 selection, else all) → target widget using the ported copy of the same function, else the **only** target widget of the same type with the same caption (letters/digits, case-insensitive: `🚨 PANIC RESET` = `PANIC\nRESET`); slots kept (CueList `Next`/`Previous`/`Stop`, created if missing); same policies and universe map. Runs after "remove target items" and before the ported widgets are placed.
- [x] **Report**: section *INPUT / MIDI* — input patch lines (⚠ for other device / none / skipped), every binding not simply kept, copied bindings with where they came from. Doctor D012 clean on the result when the patch is copied (test).
- [x] **Step 4 UI**: *Key / MIDI input* panel (`GET /api/porter/inputs` → `porter_input.summary()`): per source universe with bindings — device, profile, count, target universe select (target devices shown), live status; *Copy the input patch*; *Also copy bindings onto matching existing target widgets*; policy *Source wins*. Step 5 summary line. Browser-checked (rebuilt MIDI Pub → QuickStart_6fix, universe 2 → 3).
- [x] **Tests** (`tests/test_porter_input.py`, 11): Pub_6fix + SINCO on universe 2 + PANIC RESET ← ch 40, CueList Next ← 20, Previous ← 10 (giopas's setup, rebuilt; the real `BarShow_v14.qxw` is not committed) → QuickStart_6fix (patch copied incl. profile, D012 clean; copy off → D012; universe 2 → 3); → a copy with SINCO (`UID` only) and *ALL ON* on ch 40 (keep-free names the conflict, source-wins moves it, same device = ok); → a copy with another device (warning); bindings only (PANIC RESET by caption, CueList binding reported as unmatched); deterministic.
- [x] *(done, giopas 2 Oct)* giopas: real case BarShow_v14 (*1. SETLIST*) → SmallShow with *Source wins*, and → a rig without MIDI; check in QLC+ that PANIC / Next / Previous respond on the SINCO.

*Analysis of giopas's file (25 Sep):*
- Input patch: Universe 2 (ID 1) ← MIDI device **SINCO** (`Name="SINCO" UID="528145425"`, mode *Program Change*). 3 VC bindings, all on that universe: **PANIC / BLACKOUT** ← ch 40, setlist **CueList Next** ← ch 20, **Previous** ← ch 10. Plus 42 keyboard keys.
- SmallShow (target) has the same controller on the same universe (5.2.1 GIT saves it as `UID="SINCO"`, no Name) and uses the **same channels** (40 = STROBE BLIND, 20/10/30 = CueList Next/Previous/Stop). So porting *1. SETLIST* today: with the target page kept, 3 of the source bindings are dropped as conflicts (*keep unless used*); with the target page removed in step 4, all 3 are kept and work. → 1.6 needs a third policy **"source wins"** (move the binding to the ported widget and remove it from the target widget), and the report should name each conflict (which target widget had it).
- Found a Doctor false positive (fixed 25 Sep): D012 reported "no input device patched" for inputs saved as `UID="SINCO"` without `Name` (QLC+ 5.2.1 GIT format).
- Later (Phase 2 backlog "MIDI / input mapping manager"): re-patch inputs across a whole show, MIDI-learn simulation.

### Phase 2 — Show-building toolkit (replaces manual/AI XML patching)

**2.1 Workspace Doctor: fixes → v1.5.0** — ✅ *done 29 Sep, branch `feat/doctor-fixes`*

Doctor is a UI tab plus the CLI. Every fix is opt-in per finding, and the output always goes to a new file with a fix report.

*As built (29 Sep):*
- [x] `core/doctor/fixes.py`: `fix(root, defs, keys=…, codes=…)` → `FixResult(root, before, after, actions, skipped)` on a copy; `fixable()`, `fix_hint()`, `finding_key()` (`code|location|message`), `DEFAULT_CODES` (no removals) and `REMOVING` (D004/D015/D016); `format_report()`; `fix_file()` writes `<name>_v<N+1>.qxw` (protects the source) + `<name>_v<N+1>_fix_report.txt`. **Naming:** follows the 23 Sep one-naming-rule decision (`_v<N+1>`), not the older `<name>_doctor.qxw` of §2 principle 1.
- [x] Fixes per code: table below and `docs/doctor.md` → *Fixes*. D008 and D017 use the Quick Start PANIC RESET recipe (script: `stoponexit:false`, stop every function, start the reset scene, `wait:100ms`, stop itself).
- [x] CLI: `--fix`, `--remove`, `--codes`, `--out`.
- [x] **Workspace Doctor tab** (`routes/doctor_routes.py`, `static/js/doctor.js`, sidebar → Workspace tools): check the open workspace (definitions next to it + installed QLC+ library), groups per code with tick boxes (a group tick covers all its findings, also those beyond the 150 shown), ✓ Recommended / ✓ All / ✗ None, Show info, Save dialog, fix report next to the saved file, before/after summary, 📋 Copy Report; messages in the app's status bar.
- [x] New checks: **D017** PANIC RESET is a plain scene (from giopas's BarShow → SmallShow test), D010 (info), D011 (8 px tolerance — the Festival sub-frames overflow by 4 px), D013, D014 (built as "CueList runs an empty chaser": "setlist chaser ≠ CueList chaser" is too ambiguous in real files — Festival has empty *Setlist: Band A* chasers next to the *(Auto)* ones its CueLists use).
- [x] Doctor: script `stopfunction` commands no longer count as a use (else a PANIC RESET script hides every D016).
- [ ] Not built: D002 fixture/group renumbering, D003 CueList / matrix / bound-scene repairs, D004 degenerate chasers, D012 (→ backlog MIDI manager), D013 fix (needs a timing choice → 2.3), D015 name suggestions.
- [ ] giopas: try the tab on a real show; open a fixed file in QLC+ (PANIC RESET script from D017 on BarShow / Pub).

Checks (★ = included in Phase 1.0):

| ID | Check | Auto-fix |
|---|---|---|
| D001★ | XML well-formed, DOCTYPE present, no stray closing tags | — (report) |
| D002★ | Duplicate function IDs / duplicate VC widget IDs (across pages) | Renumber |
| D003★ | Dangling references (chaser step → missing function, button → missing function, CueList → `4294967295`) | Unlink / prompt to rewire |
| D004★ | Empty scenes, orphaned functions, degenerate chasers (0–1 real steps) | Remove / merge |
| D005★ | Scene doesn't declare all channels of each fixture it touches (LTP bleed) | Complete with 0 |
| D006★ | Strobe / internal program / macro channels ≠ 0 outside intentional FX (the scene or any parent is marked FX, or it is allow-listed) | Zero out |
| D007★ | Scene shared by a VC button and a chaser step (latch conflict) | Duplicate scene for one side |
| D008★ | No PANIC RESET scene, or it isn't on a VC button | Create and place |
| D009 | Fixture references to fixtures not in the patch; DMX address overlaps | Report |
| D010 | Default VC page isn't the setlist page | Reorder pages |
| D011 | Widgets overflow the target screen profile (e.g. 1650×884) | Report / clamp |
| D012 | Input profile / MIDI input missing (saved as None); key binding duplicates | Report |
| D013 | Chaser timing anomalies (Hold 0 = infinite where not intended; mixed speed modes) | Report |
| D014 | Setlist CueList chaser ≠ the chaser attached to the CueList widget | Rewire |
| D015 | Unnamed functions (`[NNN] Scene - Unassigned` pattern) | Suggest a name from context / remove if unreferenced |
| D016 | Unreferenced functions (not used by any function or VC widget) | Report; optional bulk remove |

- Commits: `feat(doctor): auto-fix engine, always writes new file`, `feat(doctor): UI tab with per-finding fixes`

**2.2 Rig Reducer → v1.5.0** — ✅ *done 29 Sep, branch `feat/rig-reducer` (`35c4dd6`)*
- [x] Choose the fixtures to keep. Everything else is removed, with cascade *(`core/rig_reducer.reduce()`)*:
  - channel values in scenes; *(and Sequence step values; `Values` updated)*
  - EFX and RGB Matrix fixture lists; *(EFX left empty and matrices without group removed)*
  - fixture groups; *(heads removed; empty groups removed)*
  - 3D monitor items; *(`FxItem`; meshes kept)*
  - functions that become empty; *(scenes/sequences/EFX that had fixtures and have none; chasers/collections that **lost** all their steps — already-empty ones are left alone; sequences whose bound scene is removed; their steps, script commands, show items are removed via `doctor.fixes._unlink_function`)*
  - VC buttons for functions that no longer exist. *(buttons and CueLists that pointed at a removed function are removed; Level sliders lose the channels of removed fixtures and go when empty; frames stay)*
- [x] Optional re-patch of the kept fixtures (DMX addresses, renames), e.g. FLS/FRS/FLB/FRB/DR/LG. *(`{id: {name, universe, address}}`, 1-based as QLC+ shows them)*
- [x] Doctor runs automatically, and the result is saved as a new version. *(`run()`: only new findings vs the original renamed the same way; new errors block the export; `reduce_file()` / tab → `<name>_v<N+1>.qxw` + `_reduce_report.txt`)*
- [x] **Rig Reducer tab** (sidebar → Build the rig; `routes/reducer_routes.py`, `static/js/reducer.js`): fixture table with Keep / name / universe / address, ✓ Keep all / ✗ Keep none, 🔍 Preview (counts, new Doctor findings, change log), 💾 Reduce → new file… (Save dialog, report next to it). Browser-checked on Festival_14fix.
- [x] Tests `tests/test_rig_reducer.py` (7): Festival keep-the-PARs (counts, nothing new for Doctor, deterministic, input untouched, pre-empty chasers kept), synthetic cascade (EFX, matrix, sequence, bound scene, slider, CueList, buttons), re-patch + D009, `reduce_file` never overwrites, API, rename not a new finding.
- Commit: `feat: Rig Reducer with cascading clean-up`

**2.3 Look and Chaser Builder → v1.6.0** — ✅ *done 29 Sep, branch `feat/look-builder` (`d0ab5c2`)*
- [x] **Looks**: fixture group × palette. Palettes are warm, cold, scenic and custom (with RGB pickers). Every channel is declared. Names follow the nomenclature profile. *(`core/look_builder.py`; palettes in `core/looks/palettes.json`; colour written by `capability_map.encode` — RGB(W) mix / nearest wheel slot / dimmer; "All fixtures" + the workspace's fixture groups, head order row by row; plain names `Group · Colour`, two-letter prefix `AS · Amber`; duplicates get ` (2)`; level 5–100 %)*
- [x] **Chaser patterns**: all-hit; left/right alternation (halves or odd/even); chase across a group; ping-pong; build-up; random (seeded, *n* per step, never the same set twice in a row). *(`pattern_states()`; colours per step or per fixture; off = dark or a background colour/level; identical steps share one scene; steps in folder `Look Builder/Chasers/<name>`)*
- [x] Chaser options: cut vs fade (a % of the step, fade in = fade out, Common speed modes), and step time entered in ms or as BPM plus note length (1/1 … 1/16, a quarter = one beat).
- [x] Song presets are saved in a profile and reusable. *(built-in `core/looks/presets.json` — "Drive — 8 steps, 280 ms, cut" and 4 more; yours in `~/.qlc_swiss_knife/look_presets.json` / `$QSK_LOOK_PRESETS`; built-in names reserved)*
- [x] Simulated DMX preview: a per-step colour strip for each fixture. *(values decoded back with `capability_map.decode`; ▶ Play at the step time; look preview too)*
- [x] Extra: optional new VC page (solo frame of coloured toggle buttons per look group + one for chasers); an existing PANIC RESET script gets `stopfunction` for every new look/chaser; Doctor gate (new errors block); new file + `_looks_report.txt`; **Look Builder tab** + `/api/looks/*`; `tests/test_look_builder.py` (21); `tests/manual/Festival_looks.qxw`.
- [ ] Not built: D013 fix with a timing choice (the chaser timing UI could offer it) → backlog; moving-head *position* in looks (pan/tilt are centred) → 2.4/backlog.
- Commits: `feat: look builder (group × palette)`, `feat: chaser pattern builder with BPM timing`

**2.4 VC Builder → v1.7.0** (extends the existing VC Visual Editor) — ✅ *done 29 Sep, branch `feat/vc-builder` (`9eafddb`)*
- [x] Create, delete and duplicate widgets: frames, SoloFrames, buttons, sliders, labels, CueList. *(`core/vc_builder.py` `create_widget` at the first free spot of the selected frame/page (full → top-left); `delete_widgets` (pages refused → delete page); `duplicate_widgets` = copy to the same frame +20/+20 without key/MIDI; Delete key, ⌘D)*
- [x] Wire widgets to functions: a picker filtered by nomenclature, and drag a function from the list onto a button. *(`wire`: Button `<Function ID>`, CueList `<Chaser>` chasers only, Slider → Playback `<Playback><Function>id</Function>` / unwire → Submaster; function list filtered by search, type, profile group/effect letters; drop on a widget = wire, on a frame/page = new button there, ⌥ = CueList)*
- [x] Pages (top-level frames): add, rename, reorder, set the default page. *(`rename_page`, `move_page`, ★ First = index 0 — QLC+ opens on the first page, D010; `delete_page` keeps at least one)*
- [x] Layout tools: grid snap, multi-column label panels (e.g. the nomenclature legend), auto-arrange buttons by nomenclature group. *(drag-to-move with grid snap in the canvas; `label_panel` column-major, `legend_lines(profile)`; `auto_arrange`: one row per group letter in the profile's group/effect order, no prefix → last by type)*
- [x] Screen profiles (1650×884 MacBook, 1920×1080, tablet). *(+ iPad 1024×768; this page / all; optional proportional scale; count of widgets left outside)*
- [x] VC templates: save any page as a template and apply it to another workspace. *(JSON in `~/.qlc_swiss_knife/vc_templates/` / `$QSK_VC_TEMPLATES`: page XML without bindings + function names; apply = new page, functions matched by name + type, missing listed and unwired, widget IDs renumbered)*
- [x] Setlist integration: wire the setlist chaser to the CueList widget in one click; Doctor D014 checks it. *(`setlist_cuelist`: selected CueList or a new one on the page; setlist chasers listed first)*
- [x] All via `/api/vc/op` (undoable, `vc_structural_edit`) + `/api/vc/builder-info`, `/api/vc/template`; `static/js/vc_builder.js`; `tests/test_vc_builder.py` (10); `tests/manual/Festival_vc_builder.qxw`.
- [ ] Not built: resize by dragging handles; widget types beyond the six (knob, XY pad, speed dial, clock…); templates with key/MIDI bindings.
- Commits: `feat(vc): create/delete/wire widgets`, `feat(vc): pages, grid snap, screen profiles`, `feat(vc): page templates`

**2.5 Stage and Meshes → v1.8.0** — ✅ *done 29 Sep, branch `feat/stage-meshes` (`7053f07`)*
- [x] Work out how QLC+ 5 stores meshes: add an OBJ in QLC+, save, and diff the files. Record the findings in the wiki. *(`<Monitor>`: `Grid` (m/ft), `StageItem` 0–3, `MeshItem ID XPos YPos ZPos` always, `XRot..` only ≠ 0, `XScale..` only ≠ 1, `Name`, `Hidden`, `Res` absolute / QLC+ mesh dir (`generic/cube.obj`) / workspace-relative. Placement: model origin at (XPos/1000 − W/2 + extX/2, YPos/1000 + extY/2, ZPos/1000 − D/2 + extZ/2), unscaled extents, then S then R = Rx·Ry·Rz. Floor top: Simple ground 0.1 m (slab centred on 0), box/rock/theatre 0. Z towards the audience. Wiki *Stage and Meshes*.)*
- [x] Import OBJ meshes (band members, risers, truss) with position, rotation and scale. Build a small reusable mesh library. *(`core/stage3d.py`: OBJ bounds from every vertex (cached, sampled > 20 k); placement shown as centre X/Z + bottom above the floor; `on_floor` exact after rotation/scale; `move_to`; rotate/scale keeping spot and height; add (centre, on the floor), duplicate, remove, relink; stage type/size keeping meshes; library = folders of .obj in `~/.qlc_swiss_knife/mesh_dirs.json` (default `~/Documents/QLC+/Meshes`); built-in cube bounds. Tab *Stage & Meshes* with plan/front SVG views, drag with 10 mm snap, undo/discard, save → new file + `_stage_report.txt`. `tests/test_stage3d.py` (9).)*
- [~] Unified 3D placement for fixtures and meshes, reusing the tilt logic from §3. *(Fixtures shown in both views for reference; editing fixture positions/tilt there → backlog — they're placed by the Fixture Configurator / Quick Start.)*
- Commit: `feat: stage meshes in 3D monitor`

**2.6 UI audit → v1.9.0** (asked by giopas, 29 Sep)

*Audit of the 19 screens (v1.8.0, Festival_14fix loaded).* What works: every tool has the same header, the same footer (one primary action on the right, an "original untouched" note), the metrics strip and the Open/Reload buttons. What doesn't:

| # | Finding | Where |
|---|---|---|
| A1 | **The Start screen undersells the app.** "What is QLC+ Swiss Knife?" still says *build setlists, manage triggers, configure fixtures, browse IDs*; the six cards are the v1.3 tools. Nothing mentions Doctor, Rig Reducer, Look Builder, VC Builder, Stage & Meshes, or the main idea — *build and adapt shows with the tool, safely, into new files*. An empty full-width bar and the show-name / date / path fields sit between the drop zone and the explanation. | Start |
| A2 | **Three ways to open a file** (header *Open…*, Start drop zone + *Open Workspace* + path field, *Files* panel) and Sessions in the middle of the Start screen. | Start, header, sidebar |
| A3 | **Sidebar groups don't match jobs**: *Quick Start* is a group of one; *Build the rig* has 8 items mixing rig tools, paperwork (Checklist, Tech Rider) and Brightness; *Workspace tools* mixes the Porter, Show Book, Doctor, ID Browser and Merger. | Sidebar |
| A4 | **Overlapping tools** with no hint which to use: Quick Start vs Fixtures (both build a rig from fixtures); Function Porter vs QXW Merger (α); Checklist / Tech Rider vs Show Book. | Sidebar, Start |
| A5 | **Four interaction models** for similar work: numbered steps (Quick Start, Porter), a right panel with tabs (VC Editor), stacked cards (Look Builder, Stage & Meshes), multi-column desks (Setlist, Triggers). Crowded right columns in Look Builder and Stage & Meshes (VC Editor was fixed with tabs in 1.7). | Looks, Stage, Setlist |
| A6 | **The primary action moves**: footer (most), toolbar (Doctor *Check*, Show Book *Export PDF*), middle of the page (Merger *Copy*, Porter *Next*). | Doctor, Show Book, Merger, Porter |
| A7 | **Different words for the same thing**: *Generate QXW*, *Save new version*, *Save → new file…*, *Build → new file…*, *Fix selected → new file…*, *Apply & Save QXW…*; "workspace / show / QXW / file"; some tools write next to the file, others open a Save dialog. | all writers |
| A8 | **Empty states** are inconsistent: some explain the next step ("Open a workspace and press 🔍 Check"), others are blank (ID Browser before a tab is clicked, Merger panes). | ID Browser, Merger |
| A9 | **Maturity badges** out of date: VC Editor still *Beta* after the 1.7 builder; Merger *Alpha* next to a Porter that does more. | Sidebar |
| A10 | **Long inline help** in some screens (Brightness paragraph) vs a wiki link elsewhere; no consistent "?" to the wiki page. | Brightness, all |

*Decision (giopas, 29 Sep): one **show in progress** for every tool.* Moving a show to a new venue takes many adjustments across tools, back and forth; today each tool writes its own new file and the next tool starts from the open (old) workspace — so you save, re-open, and lose the thread. Instead:
- **The show in progress** — opening a `.qxw` makes a working copy in memory; *every* tool reads it and its primary action becomes **"Apply to the show"** (no file written). The header shows it all the time: its name, the file it came from, *N changes, not saved*, the Doctor status (errors / warnings, click → Doctor), ↶ Undo, **History**, **💾 Save as new file…**.
- **History** — each apply is a step (tool, summary, Doctor after it); click a step to reopen that tool; *undo this step* / go back to any step; save a **checkpoint** file at any step; the saved file gets one report with every step. Sidebar items that changed the show get an **orange dot** (with the count on hover) — giopas, 29 Sep: useful in long sessions; the dot goes when the steps are undone or the show is saved.
- **Routes** — the Start screen's jobs (e.g. *Adapt a show*: Reducer → Doctor → Groups → Looks → VC → Stage → Setlist → final check) show as a strip of steps above the tool; any step, any order; done steps ticked.
- **Two-file tools** — the Function Porter (with the QXW Merger folded in, giopas 29 Sep) takes the *other* show as its source and the show in progress as its target; Compare compares the show in progress with another file.
- **What changes in the code**: a `core/session_show.py` holding the working root + step snapshots (the VC Editor and Stage & Meshes already keep a working copy with undo — generalise that); each tool's "export" route gains an `apply` variant returning the new root to the session instead of bytes; tools that read `workspace._state` read the show in progress; writers that save next to the file (Trigger Manager, Setlist, Dictionary) apply too; one save route (Save dialog, `<name>_v<N+1>.qxw` + `_report.txt`). Existing "→ new file" buttons stay available as *Export a copy* during the transition.
- **Mock-up** (Start by job · a tool inside the show in progress with the route strip and the inspector tabs · History and Save): design canvas *Swiss Knife 1.9 mock-up* (Claude artifact, 29 Sep) — to be agreed with giopas before building.

*Tasks* (each one: commit, wiki, CHANGELOG; browser-check at 1440 × 900 and 1280 × 800):
- [x] **Show in progress** (above): session model + history + header bar + Apply in every tool + one Save; tests that every tool's apply equals its old export byte for byte. *Done 29 Sep on `feat/show-in-progress` — Doctor, Reducer, Looks, Brightness, Setlist, VC Editor, Triggers, Stage; then (30 Sep) the Function Porter with the Merger fold-in; (1 Oct) the route strip (`route.js`) and Quick Start *Open it as the show*; still to do: Compare (2.8), Fixtures "open the result as the show".*
- [x] **Merger into the Porter** *(done 30 Sep, with the Porter on the show in progress — copy fixtures (free-address check) and groups in step 2, Apply to the show; Merger tab removed, core/routes kept for now)*: the Porter's step 2 gains *fixtures* and *groups* (what the Merger copies) next to functions and VC widgets; the QXW Merger tab goes (wiki page redirects to the Porter).
- [x] **Show Book, Checklist and Tech Rider → one tool, *Show Paperwork*** *(done 30 Sep: presets rider / crew checklist / operator / custom, combine with ⇧; venue rule enforced server-side; stage plot page via `pdf.blueprint_stream`; old routes kept as they were — not yet thin wrappers; paper sizes added the same evening: A4 / A3 / US Letter, landscape or portrait)* (giopas, 29 Sep: "not quite the same? merge into one, modular report" — decided: together with the audit, v1.9.0). The three overlap (Checklist ≈ the Show Book *patch* section; Rider = a grouped count of the same fixtures); what differs is the **reader**. `core/showbook.generate(sections)` is already section-based → add sections `rider` (types/counts/modes by make and model, universes, power if known), `stage_plan` (the Checklist blueprint), `patch` gains a tick-box column and 3D positions, `checklist_txt` output. **Presets by reader**, each editable: *Tech rider (venue)* · *Crew checklist (load-in)* · *Operator show book* · *Custom*; several presets in one PDF (e.g. rider + checklist for a festival advance). **Rule, not a tick box:** the *Tech rider* preset never includes function names, MIDI/key maps, VC or the Doctor summary — it leaves your hands. Exports unchanged: PDF, CSV, TXT (and the blueprint PDF). Menu **6 · Document** becomes one entry; the old routes `checklist` / `techrider` open *Show Paperwork* with their preset, so habits, wiki links and `/api/checklist/*`, `/api/techrider/*` keep working (kept as thin wrappers, tests unchanged). Wiki: *Show Book*, *Setup Checklist*, *Tech Rider* → one page *Show Paperwork* with the old pages as short redirects. Tests: each preset's section list; the rider preset contains no function/VC/MIDI data; old endpoints still answer.
- [x] **Start screen** (A1, A2) *(done 1 Oct: purpose, New in 1.9, compact open box, job cards, sessions below; show name/date moved to Show Paperwork)*: one sentence of purpose (*"Build, adapt, check and document QLC+ 5 shows — every change goes to a new file, your original is never touched"*); **"What do you want to do?"** cards by job, each opening the right tool and saying what it produces: *Start a new show* (Quick Start) · *Adapt a show to a new venue* (Rig Reducer → Function Porter → Look Builder → VC Editor → Stage & Meshes → Doctor — the Pub workflow) · *Get ready for the gig* (Setlist, Trigger Manager, Show Book) · *Check and fix a show* (Doctor); the open-file zone at the top, sessions below as "recent"; show name/date moved to where they're used (Show Book, Tech Rider); a short "what's new in this version" line.
- [x] **Navigation** (A3, A4, A9) *(done: six groups in 1.8.1; 1 Oct: use-this-when tooltips, VC Editor out of Beta, Merger folded into the Porter, menu fits short windows)* — *first part done in v1.8.1: menu and Start cards share six numbered groups (New show · Adapt a show · Create · Run the show · Check & fix · Document); Brightness sits in Adapt a show, the Doctor and ID Browser in Check & fix, the paperwork in Document* — sidebar grouped by job — *Start* · *New show*: Quick Start, Fixtures · *Adapt a show*: Rig Reducer, Function Porter, QXW Merger · *Create*: Look Builder, VC Editor, Stage & Meshes · *Run the show*: Setlist, Trigger Manager, Dictionary · *Check & document*: Doctor, Show Book, Checklist, Tech Rider, ID Browser · *Adjust*: Brightness. One-line "use this when…" in each tooltip for the overlapping pairs; badges reviewed (VC Editor out of Beta; Merger: keep α or fold into the Porter — decide with giopas).
- [x] **One screen pattern** (A5, A6, A8, A10) *(done 1 Oct: ? wiki link on every tool, Look Builder and Stage tabs, Porter and Show Paperwork actions in the footer, empty states, Brightness help folded; Setlist fewer columns → §7)*: header (what it does + *?* link to its wiki page) · work area · an *inspector* on the right with **tabs when it has more than three sections** (as in the VC Editor) · footer with the single primary action and what it writes. Apply to Look Builder (tabs *Looks · Chasers · Build*), Stage & Meshes (*Selection · Place · Add · Stage*), Setlist (fewer columns: slot list + songs, functions in a drawer), Doctor / Show Book / Merger / Porter (primary action to the footer). Empty states always say the next step.
- [x] **Words** (A7) *(done 1 Oct: Save as new file… everywhere, Apply to the show for tools on the show)*: one verb for writers — **"💾 Save as new file…"** (Save dialog, `<name>_v<N+1>.qxw` suggested) and the same footer note everywhere; a glossary line in the wiki (*workspace = the .qxw show file*).
- [x] **Usability check** with giopas *(his tests 29–30 Sep on real shows; UI tests extended 1 Oct)* on a real show after each screen, and a UI consistency test (`tests/test_ui_consistency.py`: one primary per footer — exists; add: every screen has a wiki link, the same save verb, an empty-state text).
- Commits: `feat(ui): start screen by job`, `feat(ui): sidebar by job`, `refactor(ui): shared tool layout …` (one per screen), `docs: ui audit`.

**2.7 Grow a rig — wire new fixtures into the show → v1.10.0** *(asked by giopas, 1 Oct)*

*Status (1 Oct, late) — tested by giopas, **v1.10.0 prepared**:* his run (FloorShow v11 ← BigShow v41, 8 functions + the *Ceiling* group; in step 3 he tried *None*, then set Ceiling 1 → CL: Ceiling Left): Ceiling 1 added to the 150 own scenes and the 12 ported ones; Ceilings 2–6 only in the 12 ported; level and colour match the template in all 150 (checked by decoding); Doctor 0 errors / 220 warnings (as before); matrices reported. Added after his test: the report and step 4 name the copies left dark. VERSION 1.10.0, CHANGELOG, README, release notes.

*Status (1 Oct, night) — built for the Porter, waiting for giopas's test:*
- Decisions (giopas, 1 Oct): default *plays like* = the nearest fixture **at the same level, same side** (ceiling spots follow *CL: Ceiling Left / Right*); **matrices stay on their groups** (reported, not changed); wiring **in the Function Porter only** — the Rig Editor (rename + add fixtures + group editor) is not built now; the fixture group editor moves back to 2.8 (Pub test step 3).
- Built: `core/rig_grow.py`, plan key `wire`, `/api/porter/wire/options`, step 3 card *The copies in the show's own looks*, step 4 + report lines, 10 tests. On giopas's real files (FloorShow v11 ← BigShow v41 *Ceiling* group): Ceiling 1–3 → CL Left, 4–6 → CL Right, each added to 150 scenes; the 5 matrices on *Floor_All* reported; Doctor 0 errors (220 warnings, as before).
- Next: giopas tests in the app and in QLC+ (press a few looks: the spots light in the same colour as the ceiling PARs), then release v1.10.0.

*The problem.* Copying fixtures into a show (e.g. the 6 ceiling spots of BigShow into FloorShow, Porter step 2) gives them only the **ported** functions. The show's own scenes, chasers, RGB matrices, EFX and buttons don't know them: press *Red Pulse* and the ceilings stay dark. Today nothing says so. giopas: "ensure I can wire them on existing scenes / matrices… if not, it is well explained (or add new scenes / buttons?)".

*How the show uses a fixture* (what wiring must touch):
- **Scenes** hold per-fixture channel values; everything else plays scenes (chasers, sequences, collections, cue lists, shows, buttons).
- **Fixture groups** feed RGB matrices and the VC's group-based widgets.
- **EFX** list their fixtures.
- **Scripts** may set channels directly.
- **VC sliders** in *Channels* mode list channels.
- The **PANIC RESET** scene must cover every fixture.

*The feature — "Wire into the show"*: one panel, used from the Porter after copying fixtures and from the Rig Editor after adding them.
1. **Plays like** — for each new fixture (or all at once), pick a **template**:
   - an existing fixture (e.g. Ceiling 1 plays like *FL: Drums*);
   - "like this fixture group, by position" (the new heads take the group's heads in stage order, wrapping);
   - or *nothing* (it stays dark outside its own functions).
   - Proposed default: the nearest existing fixture of the most similar type on the stage plan.
   - Every **scene** that sets the template gets the new fixture's values, **translated by capability** when the types differ (`capability_map`: RGB ↔ colour wheel, dimmer, strobe, pan/tilt; every channel declared, neutral values for the rest). Chasers, collections, cue lists and shows then play the new fixture with no change.
   - Option: limit it to scenes in some folders, or used by some VC frames.
2. **Groups → matrices** — add the new fixtures to chosen **existing fixture groups**, with their place in the group's grid (append a row, fill gaps, or by stage position — previewed). RGB matrices and group widgets then include them. Warn when a matrix's group changes shape (the pattern will look different), and offer *a new group + a copy of the matrix* instead.
3. **EFX** — add the new fixture to the EFX that use its template (same direction / offset); optional.
4. **PANIC RESET and blackout** — the new fixtures are added to the PANIC RESET scene (Doctor D005 / D017 already check it).
5. **Or new looks and buttons** — *Build looks for the new fixtures* hands them (as a group) to the Look Builder: palette looks, chasers, a VC page of buttons. Use it when the show's existing looks should stay as they are.
6. **What is not wired, said plainly** — on screen and in the report: scenes that don't use the template (the fixture stays dark there, by design), scripts with channel commands, *Channels* sliders, EFX not chosen, matrices whose group was not extended. Each line says what to do (e.g. "add it to group *Floor* to make *Rainbow* include it").

*Where*:
- **Function Porter**: in step 3, copied rows get a *Plays like* choice next to *✚ its copy*; step 4 shows the wiring summary; Apply does port + wiring as one step.
- **Rig Reducer → Rig Editor** (menu 2 · Adapt a show): keep / remove (as today), re-patch, **add fixtures** (a `.qxf`, the QLC+ library, or another show), **Plays like**, and a **fixture group editor** (create, rename, add / remove heads, grid order). The group editor also closes the Pub test's step-3 gap. The Reducer's report and tests stay.
- `core/rig_grow.py`: `wire(root, new_ids, plan) → (root, report)`; pure, deterministic, Doctor-checked like the other tools.

*Tasks*:
- [x] Design check with giopas on his case (FloorShow + BigShow ceilings): which defaults he expects for *plays like* and for the groups. *(1 Oct, decisions above)*
- [x] `core/rig_grow.py` — scenes and sequence steps by template (with translation), EFX, PANIC RESET (a scene like the others), the "not wired" list (matrices stay on their groups — decided). Tests on the corpus (Pub_6fix + Festival ceilings): every scene with the template gets the new fixture and nothing else changes; colour and level kept through the translation; the Doctor finds no new errors; idempotent; only the show's own functions.
- [x] Porter step 3/4: *Plays like* + summary; Apply = one History step.
- [ ] ~~Rig Editor: rename + add fixtures + group editor + wiring panel.~~ Not now (giopas, 1 Oct: wiring in the Porter only); the group editor goes to 2.8.
- [x] Wiki: *Function Porter* — *The copies in the show's own looks*, with the how-to "Add ceiling lights to a floor show".
- [x] Corpus: a sanitised `FloorShow` (wanted since Phase 1) — giopas's real case. *(3 Oct)*
- [x] Release **v1.10.0** — prepared 1 Oct (giopas tags and pushes).

**2.8 Pub test (benchmark) → v2.0.0**

*Status (2 Oct) — the two missing tools built, first measured run:*
- Decisions (giopas, 2 Oct): the **group editor lives in Stage & Meshes** (tab *Groups*); the **recipe / CLI replay moves after v2.0** (§7, with Show Profiles).
- Built: **fixture groups** (`core/fixture_groups.py`, Stage & Meshes › Groups) and **Compare** (`core/compare.py`, menu 5, `/api/compare/run`). 586 tests.
- First run through the API (Festival_14fix → Rig Reducer keeping the 6 pub PARs renamed DR/FLB/FRB/LG/FRS/FLS → Doctor default fixes (429) → the 4 pub groups) then **Compare with Pub_6fix**: fixtures and patch **6/6 the same**; groups: the pub's 5 all present and equal (5 festival-only groups left, e.g. *Floor*, *Side_Wings* — delete or keep); scenes: the hand-made pub changed the two singer PARs (FRS/FLS) in most looks and renamed / replaced many functions — that is the Look Builder / VC part of the route, still to do by hand with the tools.
- Next: giopas runs the whole route in the app, timed, with Compare at the end; what gets in the way is fixed; then the tutorial, README / screenshots, the forum post, **v2.0.0**.

*Status (2 Oct, evening) — giopas's timed run in the app:*
- **12 minutes** for the whole route (Compare not counted) → the time criterion passes (< 30 min).
- Steps in his show report: Rig Reducer (6 kept, 6 re-patched) → Doctor (429 fixes) → Stage groups (4 edits) → Look Builder (6 looks, 1 chaser, 7 buttons on a page *Looks*) → VC Editor (4 edits) → stage edits → setlist into the CueList. **Doctor at the end: 0 errors**, 52 warnings.
- In the saved file: patch 6/6 as the pub; the pub groups are there; the CueList *Setlist: Band A* on *1. SETLIST* plays exactly the pub's 34 songs; pages *1. SETLIST*, *2. EFFECTS*, *Band C*, *Looks*.
- Left as it was (his choice, not a tool problem): page *Band C* and its cue list not deleted; a group typed *Front Band:* (with the colon); the pub's *All 6* group not made (not in the steps given).
- What got in the way — fixed the same evening:
  - **Compare did not pair the setlist** (*Setlist: Band A* vs *Pub Setlist*, two cue lists in his show) → cue lists are now paired by caption, then by their songs (most in common, at least half), then the only one left on each side. His file now shows *Setlist: 1 same*.
  - **Compare noise**: the festival's unused functions (*[1000] Collection - Unassigned* …) filled "only here" → functions nothing plays (Doctor D016) are listed per section as *unused* and **not counted**; a look that is a Scene in one show and a Collection in the other is now paired (*a Scene here, a Collection in the other*).
  - **The show report said nothing for in-place steps** (groups, VC Editor, stage, setlist, triggers) → each such step now lists what it changed: fixtures, moved on the stage, groups, functions, VC pages and widgets — added / removed / renamed / changed (`core/show_diff.py`, snapshot against the next step).
  - **Group names**: spaces, quotes and a trailing `:` `;` `,` `.` are trimmed.
  - 593 tests.
- Compare after the fixes (his file vs Pub_6fix): fixtures 6 same; groups 8 same + the festival's own; setlist 1 same; looks mostly *different* by design — the hand-made pub changed the two singer PARs (FRS/FLS) in most looks and is built from different functions (*AC:*, *PUB:*, *CP:* looks). Matching those is not the goal of a 12-minute route; the criterion becomes "patch, groups, setlist and a working Looks / Effects page", with the look differences listed in the report.
- **QLC+ open-check** (giopas, 2 Oct): all good, except *Song 12* all black. Cause: in the festival show *Song 12* is a chaser with **no steps** (already dark there, cue 12 of *Band C*); the route carried it as it was. The Doctor only said "degenerate chaser (0 steps)" among 52 warnings → new check **D018 — setlist song that lights nothing** (on the CueList, with the cue number); not auto-fixed. In the pub show Song 12 plays *All Apologies Murk*.
- **Tutorial written (2 Oct)** — wiki *Tutorial — from a big-venue show to a pub show in 30 minutes*, made by running the guided route in the app (Playwright) on Festival_14fix with 9 screenshots (`screenshots/tutorial/`; raw links on `main`, live after the v2.0 merge). Doing it found and fixed: the route had no *Groups* step (added, 9 steps); the Groups list hid new groups below a short scroll (taller, new group highlighted); the Rig Reducer called renames "re-patched"; the Setlist didn't show a dark song (orange dot + warning); the report didn't say a page moved. 597 tests.
- **v2.0.0 prepared (2 Oct; with the recipe 2.9 folded in, giopas)**: VERSION 2.0.0, CHANGELOG [2.0.0], release notes, ROADMAP; the README opens with a **GIF of the route** (`screenshots/route.gif`, 12 frames, 1 MB, made from the same Playwright run as the tutorial screenshots, which were retaken with the v2.0.0 badge) and gains *Start* and *Compare* screenshots; the **forum post** drafted as a project document (`claude/FORUM_POST_v2.0.0.md`, BBCode). giopas merges, tags, publishes the GitHub Release and posts.

*The test* (§1): rebuild the real pub show from the real festival show **using only Swiss Knife**, and prove the result is as good as the hand-made one. Corpus: `Festival_14fix.qxw` (source: 6 ceiling Eurolite LED 4C-12 spots + 8 Generic 7-ch PARs, 286 functions, 13 groups, 4 VC pages: MASTER SHOW + 3 band setlist pages, 11 meshes) → reference `Pub_6fix.qxw` (6 PARs — the festival's PARs 6, 7, 8, 9, 11, 12 renamed **DR, FLB, FRB, LG, FRS, FLS** — 207 functions, 10 groups incl. *Singer Pair*, *Band Pair*, *Front Band*, *Logo*, 2 pages: **1. SETLIST** with the CueList wired to the setlist chaser, **2. EFFECTS** with 6 frames).

*The route* (each step a Swiss Knife tool, each output a new file checked by the Doctor):
1. **Rig Reducer** — keep the 6 PARs, remove the ceiling spots and 2 PARs with cascade, rename to DR/FLB/FRB/LG/FRS/FLS, re-patch.
2. **Workspace Doctor** — fix what the festival show carries (duplicate widget IDs, incomplete scenes, degenerate setlist chasers, PANIC RESET).
3. **Fixture groups** for the pub (*Singer Pair*, *Band Pair*, *Front Band*, *Logo*) — **gap: no tool creates fixture groups yet** → a fixture group editor (task below).
4. **Look Builder** — the pub looks and chasers per group (palette + patterns, two-letter prefix names).
5. **Function Porter** — only if looks must come from another show (the festival's own looks survive step 1 for the kept PARs).
6. **VC Editor** — page *1. SETLIST* first with the setlist CueList (one click), page *2. EFFECTS* from a template / the Look Builder page, label legend.
7. **Stage & Meshes** — pub stage size, band meshes on the floor, lined up.
8. **Setlist** — songs → slots → the setlist chaser.
9. **Doctor** — final check.

*Pass criteria* (to be measured, not eyeballed):
- [x] Doctor on the result: **0 errors**, and no warning the reference doesn't have. *(0 errors, 52 warnings — mostly the festival's unused functions, which the Doctor can remove)*
- [x] **Compare with `Pub_6fix.qxw`** *(2 Oct: patch, groups, setlist the same; looks differ by design)* — needs a new tool: **Compare** (`core/compare.py`, from the backlog "functional workspace diff"): fixtures and patch identical; groups present with the same heads; every reference look reproduced (per fixture: same colour/intensity after decoding, ± a tolerance), chasers by steps and timing, VC pages / frames / buttons by function, setlist CueList wired; a report of what's missing, extra or different.
- [x] **QLC+ open-check** (§6) and a live run of the setlist, PANIC RESET and a few looks. *(giopas, 2 Oct: all good; Song 12 dark → D018)*
- [x] **Time**: under 30 minutes for someone who knows the show. *(12 min, giopas, 2 Oct)*
- [ ] ~~**Repeatable**: every step's options recorded in a *recipe* (JSON) that the command line replays to a byte-identical file~~ — moved after v2.0 (giopas, 2 Oct): first item of §7 with the *Show Profile / CLI pipeline*.

*Tasks*:
- [x] `core/compare.py` + **Compare** tab (two workspaces, functional diff, report). *(2 Oct)*
- [x] Fixture group editor (step 3 gap; moved back from 2.7) — Stage & Meshes › Groups. *(2 Oct)*
- [x] Run the route on the corpus, fix what gets in the way (each fix: test + commit). *(2 Oct: giopas, 12 min; Compare setlist pairing, unused functions, show-report detail for in-place steps, group-name trim.)*
- [x] Tutorial on the wiki: *"From a big-venue show to a pub show in 30 minutes"*, with screenshots or a GIF. *(2 Oct, 9 screenshots)*
- [x] README and screenshots: retake the screens that changed since 1.9; a short GIF of the route for the top of the README. *(2 Oct: route GIF, tutorial screenshots, Start + Compare added)*
- [x] **The forum post** (giopas, 1 Oct — the last one was in March, with a short follow-up in August): one complete presentation for the QLC+ forum, in BBCode:
  - what Swiss Knife is, and the change of logic (*the show in progress*: open once, every tool, History, one save, the original never touched);
  - every tool by job (1–6), one or two lines each, and the guided routes;
  - the Pub test as the worked example (festival → pub in under 30 minutes);
  - safety (local only, never overwrites), how to install, links (wiki, releases, issues).
  Drafted as a project document, not in the repo; giopas posts it. *(2 Oct: `claude/FORUM_POST_v2.0.0.md`)*
- [x] Release **v2.0.0** (GitHub Release with the notes; the forum post above). *Prepared 2 Oct; giopas tags and publishes.*

---

**2.9 The recipe — every change recorded, replayed to the same file** *(first after v2.0, giopas 2 Oct; built 2 Oct while giopas was away; **released with v2.0.0** — giopas: one big release)*

*Goal*: the Pub test's last criterion, *repeatable*: what was done to a show can be replayed by the command line to a **byte-identical** `.qxw`.

*Decisions taken (unattended, to confirm)*:
- **Record the calls, not the options.** Every tool already changes the show through one API call per action (Apply, a stage op, a VC op, a setlist step…). An `after_request` hook appends each successful POST / PATCH / DELETE under `/api/` to the recipe, except reads, previews, exports, desktop dialogs, sessions and the save (`recipe.SKIP`). Undo and redo are calls too, so the replay goes through the same history. No tool had to change; a new tool is recorded automatically.
- **Where it lives**: `<name>.recipe.json` next to the saved file and its report (only when the save knows the folder: the native dialog or `/api/show/save`; a plain browser download gives no folder).
- **Inputs**: any absolute file path a call names is listed with its SHA-256; at replay a missing one is looked up by name next to the recipe or in `--inputs`. The source show is checked by SHA-256 (a warning if it differs). *The recipe holds the full paths of the files used* — worth knowing before sharing one.
- **Version**: the recipe records the Swiss Knife version; replaying with another version warns that the result may differ.
- **Version number**: giopas chose (2 Oct) **one release, v2.0.0**, with the Pub test and the recipe; Phase 3 packages stay **v2.1.0**.

*Status (2 Oct)*: built and tested. `core/recipe.py` (record, write, `replay`, CLI `python -m core.recipe replay|show`), hook in `app.py`, `show.reset` / `show.mark_saved` start and write it, the save message names it. The tutorial run (19 calls: Reducer, Doctor, 5 group ops, Looks, 5 VC ops, setlist load / match / details / apply, Doctor) **replays to the identical file in 1.9 s**; tests `tests/test_recipe.py` (7): Pub route with undo, Porter with another show as input, files moved to another folder, missing input named, skip list, live edits with VC and stage undo, CLI. 604 tests. Docs: wiki *Recipe*, CHANGELOG, README.

*Next for the recipe*: ~~Show Profiles on top~~, ~~a recipe from the History screen~~, ~~replay onto another show~~ — all done in 3.1 (v2.1.0).

**3.1 Show Profiles — the changes of a show, done again on another show → v2.1.0** *(giopas, 3 Oct: "do 1, 2 and 5 together for the 2.1.0 release" — Show Profiles + CLI build, the recipe extras, the small Phase 0 items)*

*Goal*: what was done to one show can be done again on **another** show (tonight's venue, next month's rig, a friend's show), in the app or from the command line, deterministically, and saying what could not be done.

*Decisions taken (giopas away, to confirm)*:
- **A profile is the recipe made portable, not a new description language.** The tools already change the show through one call per action; a profile is those calls with every ID replaced by **what it is**. No new schema per tool; a new tool works as soon as its ID fields are declared in `retarget.RULES`.
- **Meaning, recorded before each call.** A `before_request` hook notes, while the show is as the call sees it, what each ID is (`core/retarget.symbolize`, under 1 ms on Festival). Things created by earlier calls exist by then, so they are named too. A recipe from 2.0.x has no meanings: it is first replayed on its own show (command line only — it replaces the open show).
- **How a thing is found on the other show**:
  - functions by type + name (+ the *n*-th of equal names);
  - fixtures by name, else **by address** (written in the result: a different rig with the same patch works, and you see the pairing);
  - groups and meshes by name;
  - VC widgets by their place (page › frame › caption), else by type + caption if only one;
  - triggers by their widget;
  - Doctor fixes as *the same kinds* (codes) on the other show.
- **Never guess silently.** A call naming something the show doesn't have is **left out** with the reason. Lists are not trimmed (a Rig Reducer *keep* list missing one fixture would remove it). A failing call is noted and the rest goes on. An undo after a left-out step is flagged.
- **Files become parameters**; the VC templates a profile uses go inside it; no paths of the computer that made it.
- **In the app**, applying a profile makes each step a History step (undo works) and adds those calls to the show's own recipe. In `~/.qlc_swiss_knife/profiles/`.
- **Version**: this is **v2.1.0**; packages become **v2.2.0**.

*Status (3 Oct)*: built. `core/retarget.py`, `core/profile.py`, `core/recipe.py` (`symbolize`, `run_calls`, `replay_onto`, `add_symbols`, `describe`, CLI `--onto`), `routes/profile_routes.py`, History › *↻ Do it again* (`static/js/show.js`). The Pub-test calls replayed onto Festival give the identical file; onto FloorShow they apply with 6 fixtures paired by address and 161 Doctor fixes of the same kinds. Tests `tests/test_profile.py` (10). Browser-checked: profile saved on Festival, applied to FloorShow from the History.

*Not done / next*:
- channel numbers inside a fixture (pan/tilt maps in the Porter) are not translated between fixture types;
- a profile can't yet *start* a show from nothing (it applies to an open show: Quick Start first);
- parameters other than files are hand-written (`"@param:name"` in a step, `--param name=value`);
- an editor for a profile's steps (drop one, reorder).

**3.2 UI polish — after an outside review → v2.2.0** *(giopas, 4 Oct: "make it 2.2.0 and push the packages to 2.3.0")* *(giopas, 4 Oct: Copilot's PDF review and Gemini's CSS brief; "tell me what you think, create a mockup and implement what makes sense")*

*Assessment* — Copilot scored the UX 7.8/10: strong on structure and workflow, weak on visual hierarchy and polish ("an excellent technical tool, not yet a professional product"). Most of its points are fair. Gemini's brief is a CSS recipe, partly right and partly wrong for this tool. Each point:

| Suggestion | Verdict | Done |
|---|---|---|
| Copilot 1, 7 — a primary action zone; "what happens if I press Apply?" | **Yes.** The footer pattern already existed, but it only said *Changes the show in progress*. | An **"Apply will …"** line next to the button (Reducer, Doctor, Looks, Brightness, Setlist). The Reducer previews as you tick. |
| Copilot 2 — a context ribbon instead of bare numbers | **Yes.** The labels were hidden below 1560 px, so most screens showed *14 · 286 · 113* with no words. | Labelled cards; the Doctor card is red, amber or green. |
| Copilot 3 — History always visible | **Already there** (the *Changes* list under the menu), but easy to miss. | Renamed **History**, made a card, ✓ on saved steps. Not a permanent right pane: the tools need the width. |
| Copilot 4 — guided routes first-class | **Yes.** | Route cards first on Start, with their steps, plus *Do it again with a profile*. No invented time estimates: only the Pub test's measured 12 minutes. |
| Copilot 5 — Porter: one thing at a time | **Partly.** The steps exist; step 3 shows both stages and the mapping at once. | Labels on plates, quieter grid. **Not done:** folding the stage maps in step 3 — next. |
| Copilot 6, Gemini 3 — tables | **Yes**, but with **less padding** than Gemini's 10 × 12 px: Trigger Manager has 200 rows. | Zebra, hover, quiet ID, bold name, UI font for names. |
| Copilot 8 — stronger group titles in the side menu | **Yes.** | Done. |
| Copilot 9, Gemini 1 — tokens: type scale, 8 px spacing, softer panels, semantic colours | **Yes, as tokens.** Not a rewrite of 300 font sizes at once: the dense tools (VC Editor, Stage) would break. | `--sp-*`, `--fs-*`, `--success/--warning/--error`, `--shadow-1`, in all three themes. Hard-coded yellows, greens and reds replaced. |
| Copilot 10 — ⌘K command palette | **Yes** — cheap and liked by power users. | Done, with profiles and routes in it. |
| Gemini 1 — a strict dark palette | **No.** The app has dark, grey and light themes, and people use light in daylight venues. | Tokens per theme instead. |
| Gemini 2 — Start cards with the icon on the left and clamped text | **Partly.** Clamping would hide what each job is for. | Cards tightened; routes moved above them. |
| Gemini 4 — stage grid at 0.1 opacity, label backgrounds | **Yes** for the 2D top views. | Grid at 0.45 (0.1 hides the cells you aim at); labels on plates. |
| Gemini 5 — desaturated, rounded VC buttons; frames as soft boxes | **No.** The VC Editor must look like QLC+ will: the colours and square buttons are what you are designing. | — |
| Copilot "Qt-native widgets" | **Not applicable**: Swiss Knife is a web UI (Flask + pywebview). | — |

*Status (4 Oct)*: built on `feat/ui-polish`. Mockup `mockups/mockup_C_ui_polish.html` (Start, Rig Reducer, palette). Browser-checked at 1440 × 900 in the dark and light themes. 650 tests; `test_ui_polish_v22` checks the routes-first Start, the outcome slots, the palette and the tokens.

*Added to 2.2.0 (giopas, 4 Oct)*: **references in the cue notes of older shows**.
- On opening a show, the app fills every setlist cue that has no note, as one undoable History step. Notes already there are never touched.
- `core/workspace.cue_notes_missing / fill_cue_notes`; `/api/setlist/notes`; Setlist › *↪ Add references to the cue notes*.
- How the original is found:
  - the copy marker;
  - an old-style *(Setlist)* name;
  - else the unique same-content function a button plays;
  - else the function itself.
- 652 tests.

*Done in v2.2.1 (5 Oct)*: the Porter step 3 with the stage maps folded (mapping first); the Porter footers in the same "Apply will" form (the Look Builder already had it); the odd font sizes (8–10.5, 11.5, 12.5, 13.5 px) onto the scale, with tokens `--fs-micro` 10 · `--fs-small` 11 · `--fs-ui` 12 · `--fs-body` 13 · `--fs-lead` 14 · `--fs-section` 15 · `--fs-title` 20. Left as they are on purpose: the on-canvas sizes of the VC Editor widgets, the fixture chips and the stage-plot SVG; inline `font-size` in a few JS-built tables (about 70, mostly 10–12 px).

### Phase 3.3–3.7 — Finishing the toolkit → **v2.3.0 … v2.7.0** *(giopas, 5 Oct; each release is tested by giopas on real shows before the next)*

**3.3 New-show flow → v2.3.0** ✅ *(5 Oct, 665 tests; giopas tests on real shows)*
- [x] **Fixtures "open it as the show"**: after 💾 Save as new file…, a button *🎛 Open it as the show* (as Quick Start has), the result becomes the show in progress.
- [x] **Guided route *New show***: Quick Start or Fixtures → Look Builder → VC Editor → Stage & Meshes → Show Paperwork → Doctor, a third route card on Start and in the ⌘K palette.
- [x] **A profile that starts a show from nothing**: the Quick Start rig and options saved inside the profile; `python -m core.profile build --new` builds the rig, then applies the steps; in the app *Start a show from a profile*.
- [x] **Profile step editor**: open a profile, drop a step, reorder steps, rename it; the left-out reasons stay visible.
- [x] **Setlist in fewer columns**: slot list + songs, the QLC+ functions in a drawer.
- [x] **Thin wrappers**: `/api/checklist/*` and `/api/techrider/*` over `showbook`; retire `core/merger.py` and `/api/merger/*` (tests moved to the Porter).
- [x] **Housekeeping**: (already gone from the folder) `Old and tests/` archived as a zip outside the repo folder and removed from the working folder (the folder is git-ignored; nothing is lost from history).

**3.4 Doctor and Quick Start → v2.4.0** ✅ *(5 Oct, 675 tests; giopas tests on real shows)*
- [x] **Looks for fixtures without a dimmer** (found by giopas testing v2.3.0 with an Abstract VR8 scanner: every look was the same neutral state): use the colour-wheel slots for Warm / Cold and the shutter/gobo-closed slot for BLACKOUT where the fixture has one; say in Quick Start step 5 and in the report which fixtures can't do a look.
- [x] **Say where a profile is saved**: path + *Open folder* in the Quick Start message and in the History profile box (`~/.qlc_swiss_knife/profiles/`).
- [x] **PANIC RESET as a plain Scene**: the Porter offers to convert it to the script form when porting (as D017 does in the Doctor).
- [x] **D013 fix** with the timing choice (ms or BPM, as in the Look Builder).
- [x] **D002 renumbering** (duplicate function / widget IDs), **D003 repairs** (dangling CueList / button / chaser step: unlink or rewire), **D004** (degenerate chasers: remove or merge), **D015** (name suggestions from context). Each opt-in per finding, always into a new file, with the report.
- [x] **Quick Start options saved in the session** (rig, groups, naming profile, tilt, VC style).
- [x] **Whole-rig Chase / Stripes buttons**: cause found: a chaser that starts on a dark step; the check now watches one whole cycle (`Workspace.cycle_ms`).
- [x] **`tools/qlc_check.py` in CI** *(Dockerfile + workflow written, not yet run on GitHub: advisory until the first green run)*: a cached Docker image with a QLC+ 5.2.2 source build; the live check runs on the golden rigs on every push.

**3.5 Looks and Stage → v2.5.0**
- [x] **Look Builder** *(done 5 Oct, `feat/v2.5.0`)*: chasers in QLC+ *beats* tempo (BPM sync); looks with a moving-head **position** (pan/tilt presets); **own palettes** saved in the profile; **RGB-matrix patterns** for pixel bars.
- [x] **Stage & Meshes** *(done 5 Oct, `feat/v2.5.0`; aiming = tilt only, thumbnails = SVG dot drawings from the OBJ)*: fixture **tilt aiming** at a point or a mesh (`qxw_builder.default_x_rot`); **mesh thumbnails** in the library; **hide / show** meshes (`Hidden`); **copy meshes between shows** (in the Porter).

**3.6 Paperwork, setlists, MIDI → v2.6.0**
- [x] **MIDI / input mapping manager** *(done 6 Oct, `feat/v2.6.0`: Trigger Manager › Inputs & MIDI; patch editor, remembered controllers, move / swap, simulator)*: re-patch inputs across a show, MIDI-learn simulation; covers the recurring "MIDI input saved as None".
- [x] **Setlist import** *(done 6 Oct)* from txt / csv / clipboard; **tablet setlist**: a plain HTML page of the setlist for a tablet on stage.
- [x] **Tech rider** with the patch, tilt and meshes *(done 6 Oct; in the rider table + PDF — the blueprint page itself is unchanged)*.

**3.7 Localisation and community library → v2.7.0** ✅ *(6 Oct, `feat/v2.7.0`, 761 tests; giopas tests on real shows)*
- [x] **Interface in EN / IT / FR**: `static/js/i18n.js` translates by the English text itself (exact dictionary + `{n}` patterns, DOM observer for what the tools draw, tooltips / placeholders / dialogs); `static/i18n/it.json` and `fr.json` (~2,800 strings each, written with parallel AI agents from a glossary and checked by placeholder / count tests and screenshots, not by a native reviewer); language box under *Files* + ⌘K actions; remembered in the browser; English default; show data, reports, PDFs and the wiki stay as they are. `tools/i18n_extract.py` lists the app's strings and what a language lacks. Wiki *Language*. Known gaps: show data (function / fixture names) is intentionally English; some sentences built from fragments with tags read oddly; colour names mixed.
- [x] **Community library** (`core/library.py`, `routes/library_routes.py`, `static/js/library.js`, menu 3 · Create): share VC templates, palettes, look presets, naming profiles, VC styles and Show Profiles as one `*.qsklib.json`; preview before install, per-item skip / replace / keep both, built-ins reserved, validation (no DOCTYPE / entities, placeholder whitelist, profile steps limited to recordable calls, path warning, size caps); never shares controllers, sessions, meshes. Local files only. Wiki *Community Library*.
- [ ] giopas: try the language switch on a real show (IT and FR on every screen you use; tell me the strings that read badly), and share / install a library file between two machines.

*Out of the plan (giopas, 5 Oct):* the audio-trigger helper (he is not sure it is needed) and the upstream bug reports to QLC+ (probably solved in future QLC+ 5 releases).

### Phase 3 — Install like an app → **v2.8.0** *(asked by giopas, 1 Oct; after v2.0; was v2.1.0 until 3 Oct, v2.2.0 until 4 Oct)*

*Goal*: download, double-click, run — on macOS, Windows and Linux — and be told when a new version is out. As simple as StemDeck (github.com/stemdeckapp/stemdeck: a Tauri shell + bundled Python, a DMG per Mac architecture, a Windows ZIP with a self-contained `.exe`, a first-run note for unsigned apps; StemDeck itself has no auto-update). **Running from sources stays** exactly as today.

*Plan*:
- **Build**: PyInstaller (one-folder) around `app.py` with Flask, pywebview and the static files. Per-OS bundles are built by **GitHub Actions on each tag** (macOS arm64 + x86_64, Windows x64, Linux x64) and attached to the GitHub Release with a `SHA256SUMS` file. Alternative to weigh: Briefcase. Tauri would mean a Rust shell around the Python server — more moving parts for no gain here.
- **Formats**: macOS `.app` in a `.dmg` (arm64 and Intel); Windows `.zip` with `QLC Swiss Knife.exe` (an installer later if wanted); Linux `.AppImage` (+ `.tar.gz`).
- **Update check**:
  - At start (opt-out in the settings), the app asks the GitHub Releases API for the latest tag. This is the only network call besides the optional fixture-library fetch.
  - If there is a newer version: a header badge *v2.x available*, with the release notes and **Download** (opens the right asset).
  - Then **Update and restart** for the packaged app: download the asset for this OS, verify the SHA-256, swap the app folder / `.app` / AppImage on exit via a small helper, restart.
  - Run from sources: the badge says `git pull` and links the release.
- **Signing**: the first releases are unsigned, with first-run instructions (macOS: right-click → Open, or `xattr -dr com.apple.quarantine`; Windows SmartScreen: *More info → Run anyway*). Apple Developer ID / notarisation and a Windows certificate later, if giopas wants them (they cost money).
- **User data** stays in `~/.qlc_swiss_knife/` (settings, presets, recent files, sessions), untouched by updates.

*Tasks*:
- [ ] PyInstaller spec + a local build on the Mac (size, start time, native window, QLC+ library path detection, file dialogs).
- [ ] GitHub Actions release workflow (matrix build, smoke test: start, `GET /`, quit; upload the assets + `SHA256SUMS`).
- [ ] Update check (`/api/update/check`, setting, header badge) and *Update and restart* per OS; tests with a fake release feed.
- [ ] README *Install*: download first, sources second; wiki *Installing and updating*.
- [ ] Release **v2.8.0**.

### Phase 4 — The MCP server → **v2.9.0** *(after the packages; was "Backlog: MCP server / AI layer")*

*Goal*: Claude Desktop / Cowork can drive the deterministic tools on the user's existing subscription. **The AI proposes, the tools write, the Doctor validates** — the same rule as everywhere else: nothing is written without a new file, nothing is exported with new errors.

*Plan* (to confirm with giopas before building):
- **Where it lives**: `python -m core.mcp_server` (stdio), and `QLC Swiss Knife --mcp` in the packaged app — the same code, no second install. A Claude Desktop config snippet in the wiki and in the app's settings (*Connect to Claude*).
- **Built on what exists**: the tools already change the show through one call per action (the recipe / Show Profile mechanism: `core/recipe.py`, `core/retarget.py`). The MCP tools are thin wrappers over those calls, so a session driven by an AI also produces a recipe and a History with the same undo.
- **Tools (first cut)**: `open_show`, `doctor_check`, `doctor_fix`, `reduce_rig`, `port_functions`, `build_looks`, `build_chaser`, `edit_vc` (create / wire / pages), `setlist_apply`, `compare`, `show_history`, `save_show` (always a new `_v<N+1>` file + report). Read-only helpers first: `list_fixtures`, `list_functions`, `describe_show`.
- **Safety**: one show in progress per server; a write tool returns the Doctor's new findings and the History step, never raw XML; `save_show` is the only way to write a file and never overwrites; paths limited to folders the user lists in the settings.
- **Tests**: a fake MCP client runs the Pub-test route through the tools and must give the identical file as the recipe replay.

*Tasks*:
- [ ] Decide the tool list and the folder permissions with giopas.
- [ ] `core/mcp_server.py` (stdio) + `--mcp` entry in the package.
- [ ] Route test through a fake client = the recipe's byte-identical file.
- [ ] Wiki *Connect Claude to Swiss Knife*; README line; the settings snippet.
- [ ] Release **v2.9.0**.

---

## 6. QLC+ open-check (manual, before each release)

1. Open the output in QLC+ 5. No warnings in the log; all functions are listed; the VC renders on the expected default page.
2. Fixture Manager: addresses match and there are no overlaps.
3. 3D monitor: fixtures and meshes are positioned and tilted as expected.
4. Run PANIC RESET, a scene, a chaser and the CueList with DMX output enabled. *Automated for PANIC RESET + VC loading: `python3 tools/qlc_check.py file.qxw` (see `docs/qlc-live-check.md`).*
5. Save from QLC+, then run Doctor on the saved file. It must still be clean, which confirms QLC+ didn't have to "repair" anything.

---

## 7. Next steps

**Scheduled (giopas, 5 Oct), in this order:** 3.3 New-show flow (v2.3.0) → 3.4 Doctor and Quick Start (v2.4.0) → 3.5 Looks and Stage (v2.5.0) → 3.6 Paperwork, setlists, MIDI (v2.6.0) → 3.7 Localisation and community library (v2.7.0) → **Phase 3 packages (v2.8.0)** → **Phase 4 MCP server (v2.9.0)**. All in §5.

**Dropped:** the audio-trigger helper; the upstream bug reports to QLC+ (see §5, 3.3–3.7).

---

## 8. Next session checklist

**giopas, before the next session (on the Mac):**
1. ✅ *Done 23 Sep — tilt correct.* Open `tests/manual/tilt_check.qxw` in QLC+ 5 → 3D view. Every beam should cross toward the middle of the stage (none straight down/up). If a direction is mirrored, note which zone — the fix is one sign in `_ZONE_XROT`.
2. `git push -u origin chore/phase0-cleanup` and check the Actions run is green.
3. Merge to `main`, then `git tag -a v1.3.2 -m "v1.3.2" && git push --tags`; create the GitHub Release from the CHANGELOG; forum post optional (patch release).
4. `git push -u origin feat/doctor` (it is stacked on Phase 0; rebase onto `main` after the merge if needed).

**giopas, before the next session (Phase 1.1):**
1. ✅ *Done 23 Sep* — QLC+ open-check on the club / multiuni files (PANIC RESET works in 5.2.2).
2. Test 1.1b in the app: step 3 groups editor, step 4 preview, export (the `.qxf` files appear next to the `.qxw`), then in QLC+: one button at a time, matrix effects light up, MASTER and group sliders dim.
3. `git push -u origin feat/quickstart-1.1`; CI green; merge into `main` (it contains `feat/doctor`). Push the wiki.
3. Optional: `pip install websocket-client`, then `python3 tools/qlc_check.py tests/corpus/QuickStart_club.qxw` with QLC+ closed — should print `RESULT: PASS`.

**giopas, before the next session (Phase 1.2 + 1.2b) — push and merge:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
source ~/.venvs/swissknife/bin/activate && python -m pytest -q      # expect all green
git push -u origin feat/porter-vc                                    # CI runs on the branch
git checkout main && git pull --ff-only
git merge --no-ff feat/porter-vc -m "Merge feat/porter-vc: Function Porter 1.2/1.2b"
python -m pytest -q && git push origin main
cd wiki && git push origin master && cd ..                           # wiki: Function Porter page
git checkout -b feat/quickstart-porter                               # branch for Phase 1.5
```

**giopas, before the next session (Phase 1.5 part 1):**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
source ~/.venvs/swissknife/bin/activate && python -m pytest -q      # expect 397 passed
python3 tools/qlc_check.py tests/manual/Festival_to_club_translated.qxw   # QLC+ closed; expect RESULT: PASS
git push -u origin feat/quickstart-porter
```
Then in the app: Quick Start with a rig of *different* types (e.g. 2 × Intimidator Spot 110 + 4 × SlimPAR 56) → 💾 Generate QXW → **➜ Port from an existing show** → load Festival_14fix (or BarShow) as source → step 2 tick FLOOR/CEILING → step 3 Auto-Map *Fan-in* → export. Open the result in QLC+: colours on the spots come from the wheel, PARs keep their colours, PANIC RESET stops everything. Note anything that looks wrong (colour choice, dimmer levels) — the rules are in WORKPLAN 1.5.

**giopas, before the next session (Phase 1.5 part 2):** same as above (pytest now 409 passed), plus `cd wiki && git push origin master && cd ..` for the wiki pages (Function Porter: different fixture types; Quick Start: port from an existing show). If the QLC+ check or the app test is fine, merge `feat/quickstart-porter` into `main` like the Porter branch.

**giopas, before the next session (Phase 1.6):**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/porter-midi
source ~/.venvs/swissknife/bin/activate && python -m pytest -q      # expect 420 passed
git push -u origin feat/quickstart-porter feat/porter-midi
cd wiki && git push origin master && cd ..
```
Try in the app: Porter, source BarShow_v14, target SmallShow, step 2 tick *1. SETLIST*, step 4 open *Key / MIDI input* (SINCO, universe 2 → *same device already patched*), policy *Source wins* → export; the report's INPUT / MIDI section lists the 3 bindings moved from STROBE BLIND / the CueList. Then merge `feat/porter-midi` into `main` (it contains `feat/quickstart-porter`).

**giopas, before the next session (Phase 1.3):**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git -C .wt-showbook log --oneline -2                 # feat/showbook
git push -u origin feat/showbook
cd wiki && git push origin master && cd ..
git worktree remove .wt-showbook                      # the branch stays
```
Try: open a show → Show Book → Generate Preview → VC Layout (pages, indented frames, Key / MIDI column) and Doctor summary → Export PDF. Merge order into `main`: `feat/quickstart-porter` → `feat/porter-midi` → `feat/showbook` (each contains the previous; merging `feat/showbook` alone brings all three).

**giopas — v1.4.1 (Porter MIDI fixes):**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git worktree remove .wt-fix                           # branch fix/porter-midi-feedback stays
git checkout fix/porter-midi-feedback
source ~/.venvs/swissknife/bin/activate && python -m pytest -q   # expect 448 passed
# restart the app (python3 app.py) — a running app keeps the old code
```
Re-test: BarShow_v14 → SmallShow, tick *1. SETLIST*; step 4 now shows the "will be DROPPED" warning; choose *Source wins* (the warning becomes info) → export → the ported CueList has MIDI Next ch 20 / Previous ch 10 (QLC+ shows them as 21 / 11), STROBE BLIND! and *Setlist Cue* lost them; everything on one page. Then:
```bash
git push -u origin fix/porter-midi-feedback
git checkout main && git merge --no-ff fix/porter-midi-feedback -m "Release v1.4.1"
python -m pytest -q && git push origin main
git tag -a v1.4.1 -m "v1.4.1" && git push origin v1.4.1
```
GitHub Release body: `docs/release-notes/RELEASE_NOTES_v1.4.1.md`.

**giopas — release v1.4.0 (done 28 Sep):**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git worktree remove .wt-release                       # branch chore/release-1.4.0 stays
source ~/.venvs/swissknife/bin/activate
git checkout chore/release-1.4.0 && python -m pytest -q          # expect 443 passed
git push -u origin chore/release-1.4.0                # CI runs
git checkout main && git pull --ff-only
git merge --no-ff chore/release-1.4.0 -m "Release v1.4.0"   # brings 1.5, 1.6, 1.3 and the release commit
python -m pytest -q && git push origin main
git tag -a v1.4.0 -m "v1.4.0" && git push origin v1.4.0
cd wiki && git push origin master && cd ..
```
Then on GitHub: *Releases → Draft a new release → tag v1.4.0*, title "v1.4.0 — build the next show with the tool", body = `docs/release-notes/RELEASE_NOTES_v1.4.0.md`. Forum: paste `docs/release-notes/FORUM_v1.4.0.bbcode`. Old branches can be deleted after the merge (`feat/quickstart-porter`, `feat/porter-midi`, `feat/showbook`).

**giopas — release v2.0.0 (the Pub test + the recipe), branch `feat/recipe`** (it contains `feat/pub-test`):
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/recipe
source ~/.venvs/swissknife/bin/activate
python -m pytest -q
git push -u origin feat/recipe
git checkout main
git pull --ff-only
git merge --no-ff feat/recipe -m "Release v2.0.0"
python -m pytest -q
git push origin main
git tag -a v2.0.0 -m "v2.0.0"
git push origin v2.0.0
cd wiki
git push origin master
cd ..
```
(expect 604 passed.) GitHub Release: tag v2.0.0, title "v2.0.0 — the Pub test, and repeatable shows", body `docs/release-notes/RELEASE_NOTES_v2.0.0.md`. Then the forum post (`claude/FORUM_POST_v2.0.0.md` in the project). `feat/pub-test` and `feat/recipe` can be deleted after the merge.

**giopas — release v1.10.0 (Grow a rig), branch `feat/grow-rig`:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/grow-rig
source ~/.venvs/swissknife/bin/activate
python -m pytest -q
git push -u origin feat/grow-rig
git checkout main
git pull --ff-only
git merge --no-ff feat/grow-rig -m "Release v1.10.0"
python -m pytest -q
git push origin main
git tag -a v1.10.0 -m "v1.10.0"
git push origin v1.10.0
cd wiki
git push origin master
cd ..
```
(expect 573 passed.) GitHub Release: tag v1.10.0, title "v1.10.0 — new fixtures join the show", body `docs/release-notes/RELEASE_NOTES_v1.10.0.md`.

**giopas — release v1.9.0 (the show in progress, UI audit 2.6), branch `feat/show-in-progress`:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/show-in-progress
source ~/.venvs/swissknife/bin/activate
python -m pytest -q
git push -u origin feat/show-in-progress
git checkout main
git pull --ff-only
git merge --no-ff feat/show-in-progress -m "Release v1.9.0"
python -m pytest -q
git push origin main
git tag -a v1.9.0 -m "v1.9.0"
git push origin v1.9.0
cd wiki
git push origin master
cd ..
```
(expect 563 passed.) GitHub Release: tag v1.9.0, title "v1.9.0 — one show, every tool", body `docs/release-notes/RELEASE_NOTES_v1.9.0.md` (no forum post: one complete post at v2.0). Try first: Start → *▶ Guided route: adapt a show to a new venue* on a real show, a "?" on any tool, Look Builder / Stage tabs, Porter footer, Show Paperwork export from the footer.

**giopas — release v1.8.1 (fixtures in the Stage placement + Start and menu by job), branch `feat/start-sidebar`:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/start-sidebar
source ~/.venvs/swissknife/bin/activate
python -m pytest -q
git push -u origin feat/ui-audit feat/stage-fixtures feat/start-sidebar
git checkout main
git pull --ff-only
git merge --no-ff feat/start-sidebar -m "Release v1.8.1"
python -m pytest -q
git push origin main
git tag -a v1.8.1 -m "v1.8.1"
git push origin v1.8.1
cd wiki
git push origin master
cd ..
```
(expect 527 passed; the branch also carries `feat/stage-fixtures` and the WORKPLAN commits of `feat/ui-audit`.) GitHub Release body: `docs/release-notes/RELEASE_NOTES_v1.8.1.md`.

**giopas — release v1.8.0 (done 29 Sep), branch `feat/stage-meshes`:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/stage-meshes
source ~/.venvs/swissknife/bin/activate && python -m pytest -q
python3 app.py
```
(expect 523 passed.) Check first: open `~/Downloads/mesh test.qxw` → Stage & Meshes → the bassist says "floats 45 mm", the cube "floats 55 mm" → ⤓ Put all on the floor → 💾 Save → open the new file in QLC+: both must stand exactly on the Simple ground (bassist Y −800, cube Y 100). Then a show on a Simple box / Rock stage (floor at 0), e.g. the Festival show meshes → put all on the floor → QLC+. Then:
```bash
git push -u origin feat/stage-meshes
git checkout main && git pull --ff-only
git merge --no-ff feat/stage-meshes -m "Release v1.8.0"
python -m pytest -q && git push origin main
git tag -a v1.8.0 -m "v1.8.0" && git push origin v1.8.0
cd wiki && git push origin master && cd ..
```
GitHub Release body: `docs/release-notes/RELEASE_NOTES_v1.8.0.md`; forum: `docs/release-notes/FORUM_v1.8.0.bbcode`.

**giopas — release v1.7.0 (done 29 Sep), branch `feat/vc-builder`:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/vc-builder
source ~/.venvs/swissknife/bin/activate && python -m pytest -q      # expect 508 passed
python3 app.py                                                        # restart the app → VC Visual Editor
git push -u origin feat/vc-builder
git checkout main && git pull --ff-only
git merge --no-ff feat/vc-builder -m "Release v1.7.0"
python -m pytest -q && git push origin main
git tag -a v1.7.0 -m "v1.7.0" && git push origin v1.7.0
cd wiki && git push origin master && cd ..
```
GitHub Release body: `docs/release-notes/RELEASE_NOTES_v1.7.0.md`; forum: `docs/release-notes/FORUM_v1.7.0.bbcode`.
Try first: open `tests/manual/Festival_vc_builder.qxw` in QLC+ → page 2 *Built*: the 4 look buttons (solo frame), the *Chaser fader* slider runs the setlist chaser, the label, the *Legend* frame, the CueList plays the setlist chaser. Then in Swiss Knife on a real show: drag a function onto a page, build a page, save it as a template, add it to another show, Apply & Save, open in QLC+.

**giopas — release v1.6.0 (done 29 Sep), branch `feat/look-builder`:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/look-builder
source ~/.venvs/swissknife/bin/activate && python -m pytest -q      # expect 497 passed
python3 app.py                                                        # restart the app → Look Builder
git push -u origin feat/look-builder
git checkout main && git pull --ff-only
git merge --no-ff feat/look-builder -m "Release v1.6.0"
python -m pytest -q && git push origin main
git tag -a v1.6.0 -m "v1.6.0" && git push origin v1.6.0
cd wiki && git push origin master && cd ..
```
GitHub Release body: `docs/release-notes/RELEASE_NOTES_v1.6.0.md`; forum: `docs/release-notes/FORUM_v1.6.0.bbcode`.
Try first: open `tests/manual/Festival_looks.qxw` in QLC+ (functions in the *Look Builder* folder, page *Looks*, the chasers run at 280 ms / 250 ms …); then on a real show: looks for a group, a chaser from the *Drive* preset, 💾 Build, open in QLC+.

**giopas — release v1.5.0 (done 29 Sep), branch `feat/rig-reducer`:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/rig-reducer
source ~/.venvs/swissknife/bin/activate && python -m pytest -q      # expect 476 passed
python3 app.py                                                        # restart the app, try both tabs
git push -u origin feat/doctor-fixes feat/rig-reducer
git checkout main && git pull --ff-only
git merge --no-ff feat/rig-reducer -m "Release v1.5.0"                # contains feat/doctor-fixes
python -m pytest -q && git push origin main
git tag -a v1.5.0 -m "v1.5.0" && git push origin v1.5.0
cd wiki && git push origin master && cd ..
```
GitHub Release body: `docs/release-notes/RELEASE_NOTES_v1.5.0.md`; forum: `docs/release-notes/FORUM_v1.5.0.bbcode`.
Try first: Workspace Doctor on BarShow_v14 (D017 → open the fixed file in QLC+: PANIC RESET stops a running look); Rig Reducer on BarShow_v14 → keep the 4 PARs of SmallShow's layout, re-patch, open in QLC+.

**giopas — Phase 2.1 (Doctor fixes) — superseded by the v1.5.0 steps above:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/doctor-fixes
source ~/.venvs/swissknife/bin/activate && python -m pytest -q     # expect 469 passed
python3 app.py                                                       # restart the app
git push -u origin feat/doctor-fixes
cd wiki && git push origin master && cd ..
```
Try: open BarShow_v14 → Workspace Doctor → 🔍 Check → D017 is ticked → 💾 Fix → open the new file in QLC+: PANIC RESET now stops a running look. Merge into `main` after the test (v1.5.0 is released with 2.2).

**giopas — release v2.2.1 (the UI polish finished + the white-window fix), branch `feat/v2.2.1`:**
```bash
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script
git checkout feat/v2.2.1
source ~/.venvs/swissknife/bin/activate
python -m pytest -q
git push -u origin feat/v2.2.1
git checkout main
git pull --ff-only
git merge --no-ff feat/v2.2.1 -m "Release v2.2.1"
python -m pytest -q
git push origin main
git tag -a v2.2.1 -m "v2.2.1"
git push origin v2.2.1
cd wiki
git push origin master
cd ..
```
(expect 653 passed.) GitHub Release: tag v2.2.1, title "v2.2.1 — the UI polish, finished", body `docs/release-notes/RELEASE_NOTES_v2.2.1.md`. The v2.2.0 GitHub Release (tag already pushed) is created the same way from `RELEASE_NOTES_v2.2.0.md`.

**Next Cowork session:**
1. Release v2.7.0 (giopas), then **Phase 3 packages → v2.8.0** (PyInstaller, GitHub Actions per-OS builds, update check).
2. Then the MCP server (v2.9.0).
