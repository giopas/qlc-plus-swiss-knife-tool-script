# QLC+ Swiss Knife — Work Plan

> Living plan for turning Swiss Knife from a set of helpers into a **deterministic, accurate show-file builder** for QLC+ 5.
> Agreed 23 Sep 2026. Baseline: `main` @ `387db18` (v1.3.1).
> Update the checkboxes and the *Status* line of each step as work lands. Anything new goes into §7 *Backlog* so nothing gets lost.

**Status (29 Sep, evening — Phase 2.5 done, v1.8.0 prepared):**
- v1.7.0 released by giopas (main `7d31694`, tag `v1.7.0`).
- giopas's mesh sample (`mesh test.qxw` + `Bassist.obj` + `cube.obj`, QLC+ 5.2.2) + QLC+ source (`mainview3d.cpp`, `monitorproperties.cpp`, `StageSimple.qml`) → format and placement formula recorded in the wiki page *Stage and Meshes*. His request: fix mesh positions so "on the floor" really is 0 (his bassist needed Y −755 by eye).
- **2.5 Stage and Meshes — done** on branch `feat/stage-meshes` (from `main`; commit `7053f07` + docs/release commit; wiki *Stage and Meshes* page). **v1.8.0 prepared** on the same branch. 517 tests green; tab browser-checked on Festival_14fix (plan/front views, drag, put all on the floor, add from library). **Open: confirm in QLC+ that the Simple ground floor is at 0.1 m** (read from `StageSimple.qml`: 0.2 m slab centred on 0; his eyeballed values sit 45–55 mm above it) — see §8.
- giopas's check: Simple ground floor at 0.1 m confirmed in QLC+ ("It works!"). His request: place one or several meshes with one click → `stage3d.arrange()` + *Place* card: to the stage edges / centre (group, gap to the edge), floor / ceiling (each), line up (8), space evenly between the outer two or across the stage (X/Z), nudge (buttons, arrow keys, PgUp/PgDn, Shift = fine); multi-select (Shift/⌘-click, select all/none), group drag. `tests/test_stage3d.py` 15 tests. 523 tests green; browser-checked.
- Next: **2.6 Benchmark** → v2.0.0.

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
- **Useful to other QLC+ users too:** conventions are configurable, not hard-coded to TheBand.

### Acceptance benchmark (the "Pub test")

Rebuild `Pub_6fix.qxw` starting from `Festival_14fix.qxw` using **only Swiss Knife**:

1. Reduce the rig from 14 fixtures to 6.
2. Port the looks.
3. Generate the new chasers.
4. Build the two-page VC and wire the setlist CueList.
5. Run Doctor.

The result must pass Doctor with zero errors, and a Doctor diff against v14 must show no functional regressions. When this passes, the goal is met.

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
7. **Conventions are data, not code.** Nomenclature, palettes, VC screen size and templates live in JSON *profiles* that users can share. The TheBand profile is just the first one.
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
| 2026-09-23 | **TheBand naming profile** taken from the legend on the Pub_6fix EFFECTS page: format `{group}{effect} · {name}`; groups A F S B R D L X (all, front four, singer pair, band pair, rear two, drums floor, logo, split/spatial); effects S D P M \* (static, dynamic, pulse, movement, special FX). Quick Start only knows "all" (A); anything the profile can't map (utility functions, per-type group scenes) gets **no prefix** rather than a wrong one. Buttons carry the prefix too (`prefix_captions`). |
| 2026-09-23 | **VC style cloning** copies geometry and fonts only (button size = most common ≥30 px tall, gap = median horizontal gap, header = smallest child Y in headed frames, page = most common top-level frame size). Colours stay semantic. |
| 2026-09-23 | Doctor D006: a value of **0** on a capability with no preset and no "active" words (strobe, program, auto, macro, sound, pulse, chase …) is safe — it is the fixture's plain operating mode (SlimPAR 56 `Mode = 0 (RGB)`). Corpus baselines unchanged. |
| 2026-09-24 | **Quick Start VC = one page.** Whole-rig LOOKS + EFFECTS share one SoloFrame (plain sub-frames pass the solo signal up in QLC+ 5): one at a time. **Each group is its own SoloFrame** (one at a time inside a group, groups combine — giopas, 24 Sep). Only PANIC / BLACKOUT and PANIC RESET are outside. Page size = style page (default 1650 × 884). Sliders carry `InvertedAppearance="false"` (QLC+ 5 default is inverted). **Audio React** = fixture's own sound-active capability (Sound/Audio/Music label, middle of range), only if present. |
| 2026-09-24 | **Fixture groups** are user-defined in step 3 (default: one per fixture name). Each group: frame with a **submaster** (group dimmer), looks (On, Red, Blue, Green, Warm), effects (Pulse, Color Fade, Chase). Group scenes declare only the group's fixtures. MASTER is a page-level submaster. RED/GREEN/BLUE Level sliders and the *Color Fixtures* button are dropped. TheBand names: group letter = first letter of the group name unless mapped. |
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
- [ ] README *What's new* updated; screenshots refreshed if the UI changed.
- [ ] Wiki page for each new or changed tool (usage, limits, examples).
- [ ] `git tag vX.Y.Z` and a GitHub Release, with notes copied from the CHANGELOG.
- [ ] Forum post (BBCode) on the QLC+ forum for minor and major releases.

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
- [ ] Add `FloorShow` when available.
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
- [x] Nomenclature profile (JSON): `plain` and `prefix` in `core/quick_start/profiles/nomenclature/`. The TheBand profile:
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
- [ ] giopas: real case BarShow_v14 (*1. SETLIST*) → SmallShow with *Source wins*, and → a rig without MIDI; check in QLC+ that PANIC / Next / Previous respond on the SINCO.

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
- [x] **Looks**: fixture group × palette. Palettes are warm, cold, scenic and custom (with RGB pickers). Every channel is declared. Names follow the nomenclature profile. *(`core/look_builder.py`; palettes in `core/looks/palettes.json`; colour written by `capability_map.encode` — RGB(W) mix / nearest wheel slot / dimmer; "All fixtures" + the workspace's fixture groups, head order row by row; plain names `Group · Colour`, TheBand `AS · Amber`; duplicates get ` (2)`; level 5–100 %)*
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

**2.6 Benchmark → v2.0.0**
- [ ] Run the Pub test (§1) end-to-end.
- [ ] Document it as a tutorial ("From a big-venue show to a pub show in 30 minutes").
- [ ] Release **v2.0.0**, with a forum post and a video or GIF.

---

## 6. QLC+ open-check (manual, before each release)

1. Open the output in QLC+ 5. No warnings in the log; all functions are listed; the VC renders on the expected default page.
2. Fixture Manager: addresses match and there are no overlaps.
3. 3D monitor: fixtures and meshes are positioned and tilted as expected.
4. Run PANIC RESET, a scene, a chaser and the CueList with DMX output enabled. *Automated for PANIC RESET + VC loading: `python3 tools/qlc_check.py file.qxw` (see `docs/qlc-live-check.md`).*
5. Save from QLC+, then run Doctor on the saved file. It must still be clean, which confirms QLC+ didn't have to "repair" anything.

---

## 7. Backlog / next steps (after v2.0)

**Found during Phase 0 (small, do when touching the area):**
- `core/fixture.py` (Fixture Configurator QXW generation) still hard-codes `XRot="65"` for every fixture; align it with `qxw_builder.default_x_rot()`.
- Quick Start canvas: `qsSetOrientation()` exists but no UI button calls it; wire the Down/Horizontal/Up/Auto presets (now zone rules) into the Quick Start placement panel.
- Quick Start download file name still carries a timestamp (`<project>_YYYYMMDD_HHMM.qxw`); switch to the `_vN` rule when Quick Start gets profiles.
- Housekeeping: the repo folder holds SSH private keys (`ssh_github_key`, `github-giopas-ssh-hey.txt`) — git-ignored, but better moved to `~/.ssh`. `Old and tests/` is ignored and can be archived.


- **Show Profile**: one JSON describing rig, conventions, palettes, VC screen and templates, so a new show starts from the profile. This is the base for sharing with other users.
- **Command-line pipeline**: `swissknife build profile.json → show.qxw`, fully scripted and reproducible.
- **MCP server / AI layer**: expose the deterministic tools (reduce, port, build looks, build VC, doctor) to Claude Desktop/Cowork on the existing subscription. The AI proposes; the tools write; Doctor validates. The API-key route is optional and later.
- **PANIC RESET as a Scene** (seen on BarShow → SmallShow, 29 Sep): a scene at 0 cannot darken HTP channels of a running look. Doctor could flag a PANIC RESET that is a plain Scene and suggest the Quick Start script form (stop functions + neutral scene); the Porter could offer to convert it when porting.
- **Look Builder follow-ups** (from 2.3): Doctor D013 fix using the chaser timing choice (ms / BPM); chasers in QLC+ *beats* tempo (tap/BPM sync) instead of fixed ms; looks with a moving-head position (pan/tilt presets instead of centre); save your own palettes; RGB-matrix patterns for pixel bars.
- **Stage follow-ups** (from 2.5): edit fixture positions and tilt in the same plan/front views (reuse `qxw_builder.default_x_rot`); mesh thumbnails in the library; hide/show meshes (`Hidden`); copy meshes between shows (Porter); rotated footprints in the plan view (now the axis-aligned box).
- **MIDI / input mapping manager**: re-patch inputs; MIDI learn simulation. This covers the recurring "MIDI input saved as None" issue.
- **Audio triggers** helper (DMX-mode pitfalls documented).
- Setlist: import setlists from txt/csv/clipboard; an HTML setlist for a tablet on stage.
- Tech Rider: pull the patch, tilt and meshes into the rider and the blueprint PDF.
- Workspace diff: compare two versions functionally (fixtures, functions, VC), not as text.
- Packaging: PyInstaller builds for macOS and Windows; community template and profile library.
- Localisation (EN / IT / FR).
- Upstream: report QLC+ 5 bugs found along the way (RGBMatrix orientation, Audio Triggers DMX mode, shared-scene latch) to the QLC+ project.

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

**giopas — release v1.8.0 (2.5 Stage & Meshes), branch `feat/stage-meshes`:**
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

**Next Cowork session:**
1. Results of giopas's v1.8.0 check (Simple ground floor at 0.1 m — if QLC+ shows the models slightly in the air or sunk, adjust `stage3d.FLOOR_M`); then Phase 2.6 Benchmark → v2.0.0.
1e. (done) v1.7.0 released; Phase 2.5 Stage and Meshes.
1d. (done) v1.6.0 tests; Phase 2.4 VC Builder.
1c. (done) v1.5.0 tests; Phase 2.3 Look and Chaser Builder.
2. (done) Phase 2.1 Workspace Doctor fixes.
1a. Then Phase 1.6 Port MIDI / input control (needs giopas's show with MIDI controls in the corpus).
1b. Then Phase 1.3 Show Book (test suite, VC Layout section vs Pub_6fix, Doctor summary section).
2. Add `FloorShow` to the corpus when available.
3. Look into `QuickStart_6fix`'s whole-rig *Chase* / *Stripes* buttons: in the live check (QLC+ 5.2.2 headless) one of them is intermittently dark (a different one per run) — timing of the Collection (dimmer scene + matrix) start, or the check's 1 s settle?
4. Porter backlog: channel translation between different fixture types (by capability, e.g. PAR → spot); Sequence step values; Show timelines; optional "compact frames" after pruning.
5. Backlog candidates: `_vN` file name for the Quick Start download; save Quick Start options in the session; run `tools/qlc_check.py` in CI (build QLC+ 5.2.2 in a cached Docker image).
6. Upstream reports (QLC+ forum/GitHub): `VCSlider::loadXMLLevel` token over-read after an empty `<Level/>` on unindented XML; RGB-mode matrices ignoring *DimmerControl*; 5.2.2 script-command race (if not covered by `ca8ffd41`). Doctor: add a check for fixtures whose definition won't be found next to the workspace.
