# QLC+ Swiss Knife — Work Plan

> Living plan for turning Swiss Knife from a set of helpers into a **deterministic, accurate show-file builder** for QLC+ 5.
> Agreed 23 Sep 2026. Baseline: `main` @ `387db18` (v1.3.1).
> Update the checkboxes and the *Status* line of each step as work lands. Anything new goes into §7 *Backlog* so nothing gets lost.

**Status (25 Sep):**
- **Phase 1.2 — done** on branch `feat/porter-vc` (local commits, stacked on `main` @ `60db1fa`; Giovanni pushes): VC porting, fan-in, Doctor gate, import report next to the output. Real cases Festival_14fix → QuickStart_6fix (fan-in 14 → 6) and Festival_14fix → bare Pub rig (same IDs) pass Doctor with 0 errors / 0 warnings and are byte-identical run to run; the fan-in output passes `tools/qlc_check.py` in QLC+ 5.2.2 for every ported button. 365 tests green. Waiting for Giovanni: try the Porter tab on the Mac, push.
- Next: Phase 1.3 (Show Book), see §8.

**Status (24 Sep, end of session):**
- **Phase 0 — done and released** as `v1.3.2` (main @ `2cc9dbc`, CI green).
- **Phase 1.0 — core done** on branch `feat/doctor`: corpus, `core/doctor` engine + CLI. Still open: `20Minutes_FLOOR` corpus file.
- **Phase 1.1 — done** on branch `feat/quickstart-1.1` (local commits; Giovanni pushes): mode-aware channels, neutral values, PANIC RESET (script, works in QLC+ 5.2.2), naming profiles, VC style cloning, Doctor gate, 3 golden rigs, live QLC+ check (`tools/qlc_check.py`). **1.1b (24 Sep, after Giovanni's test):** full-width page, whole-rig solo frame + one solo frame per group (groups combine), Audio React, fixture groups (editor in step 3; per-group frame with submaster, looks, effects), MASTER submaster, working RGB-matrix effects (Collection: dimmer scene + matrix), fixture `.qxf` saved next to the workspace only when QLC+ lacks it, indented XML (QLC+ 5.2.2 loader bug), corpus renamed/scrubbed (`Festival_14fix`, `Pub_6fix`). All golden rigs PASS `tools/qlc_check.py` in QLC+ 5.2.2 (and club in 4.14.5). Waiting for Giovanni: test on the Mac, push.

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
- **Useful to other QLC+ users too:** conventions are configurable, not hard-coded to 20Minutes.

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
7. **Conventions are data, not code.** Nomenclature, palettes, VC screen size and templates live in JSON *profiles* that users can share. The 20Minutes profile is just the first one.
8. **Tests and CI green before merge.** No feature merges without tests; CI runs on every push.

---

## 3. Decisions log

| Date | Decision |
|---|---|
| 2026-09-23 | Doctor **always saves to a new file** (never in place). The same applies to every tool that writes a QXW, including Trigger Manager. |
| 2026-09-23 | **Fixture tilt defaults for music shows** (QLC+ 3D convention: XRot 0 = beam straight down, 90 = horizontal, 180 = straight up):<br>• Truss/ceiling: 45° from vertical, aimed at the stage (front/back-light angle).<br>• Floor: 45° up toward the performers (uplight).<br>• Mid-height: horizontal, aimed at the stage.<br>Tilt direction comes from the fixture's depth position (downstage fixtures tilt upstage, upstage fixtures tilt downstage). Per-fixture override stays available. The previous straight down/up defaults lit only the floor and the ceiling. |
| 2026-09-23 | The `*-1` files (`qxw_builder-1.py`, `quick_start_routes-1.py`, `quickstart-1.js`) are **older copies** of the current files (they predate commit `a950cc8` and still use `requests`). They are to be deleted, not merged. |
| 2026-09-23 | The benchmark target is **Pub_6fix** (it supersedes v11). `20Minutes_FLOOR` is optional; add it when available. |
| 2026-09-23 | Doctor treats a scene as intentional FX if it **or any function containing it** is marked as FX (name or allow-list). Caption-only buttons are *info*, not errors. |
| 2026-09-23 | AI integration (MCP server) is deferred until Doctor and the builders are done. See §7. |
| 2026-09-23 | **One naming rule for every tool:** suggested/new files are `<name>_v<N+1>.qxw` (`<name>_v2.qxw` if there is no `_vN`), replacing `_GIG_READY`, `_BRIGHTNESS`, `_merged`, `_imported`, `_modified`. `next_version_path()` skips names already on disk. |
| 2026-09-23 | Tilt sign convention (from the corpus): positive XRot swings a hanging beam toward +Z ("Front"). Defaults: truss 45/315, mid 90/270, floor 135/225 (upstage half / downstage half). **Confirmed in QLC+ 5 3D view on 23 Sep (0.2): all three pairs cross toward centre stage.** |
| 2026-09-23 | Doctor severities: D001–D003 errors; D004–D009, D012, D016 warnings; D015 and I-codes info. D005 is a warning (not an error) so porting from older shows is not blocked before auto-fix exists. |
| 2026-09-23 | VC copy/move (added to v1.3.2 at Giovanni's request): copies get new widget IDs (`max+1`) and **drop key/MIDI bindings by default** (opt-in to keep); moves keep IDs and bindings; operations refuse duplicated widget IDs (D002). The Triggers tab is renamed **Trigger Manager**. The venv lives in `~/.venvs/swissknife` (iCloud duplicates break pywebview). |
| 2026-09-23 | **Quick Start channel model:** channel indices come from the selected **mode**; unused channels get a capability-aware **neutral** value (ShutterOpen preset or an *Open / No function / White / Off* capability, never a *Closed/Blackout* one; Pan/Tilt coarse 127, fine 0; otherwise 0). BLACKOUT additionally closes the shutter on fixtures with no dimmer channel. PANIC RESET = neutral + intensity 0, on its own Toggle button. |
| 2026-09-23 | **20Minutes naming profile** taken from the legend on the Pub_6fix EFFECTS page: format `{group}{effect} · {name}`; groups A F S B R D L X (all, front four, singer pair, band pair, rear two, drums floor, logo, split/spatial); effects S D P M \* (static, dynamic, pulse, movement, special FX). Quick Start only knows "all" (A); anything the profile can't map (utility functions, per-type group scenes) gets **no prefix** rather than a wrong one. Buttons carry the prefix too (`prefix_captions`). |
| 2026-09-23 | **VC style cloning** copies geometry and fonts only (button size = most common ≥30 px tall, gap = median horizontal gap, header = smallest child Y in headed frames, page = most common top-level frame size). Colours stay semantic. |
| 2026-09-23 | Doctor D006: a value of **0** on a capability with no preset and no "active" words (strobe, program, auto, macro, sound, pulse, chase …) is safe — it is the fixture's plain operating mode (SlimPAR 56 `Mode = 0 (RGB)`). Corpus baselines unchanged. |
| 2026-09-24 | **Quick Start VC = one page.** Whole-rig LOOKS + EFFECTS share one SoloFrame (plain sub-frames pass the solo signal up in QLC+ 5): one at a time. **Each group is its own SoloFrame** (one at a time inside a group, groups combine — Giovanni, 24 Sep). Only PANIC / BLACKOUT and PANIC RESET are outside. Page size = style page (default 1650 × 884). Sliders carry `InvertedAppearance="false"` (QLC+ 5 default is inverted). **Audio React** = fixture's own sound-active capability (Sound/Audio/Music label, middle of range), only if present. |
| 2026-09-24 | **Fixture groups** are user-defined in step 3 (default: one per fixture name). Each group: frame with a **submaster** (group dimmer), looks (On, Red, Blue, Green, Warm), effects (Pulse, Color Fade, Chase). Group scenes declare only the group's fixtures. MASTER is a page-level submaster. RED/GREEN/BLUE Level sliders and the *Color Fixtures* button are dropped. 20Minutes names: group letter = first letter of the group name unless mapped. |
| 2026-09-24 | **RGB-matrix buttons run a Collection** (scene opening the master dimmers + the matrix): QLC+ ignores *DimmerControl* in RGB mode (`rgbmatrix.cpp`). Only scripts that exist in QLC+ 4 and 5: One By One, Even/Odd, Gradient, Plasma, Waves, Stripes. |
| 2026-09-24 | **Generated XML is indented** like QLC+'s own (QLC+ 5.2.2 `VCSlider::loadXMLLevel` reads one token too many after an empty `<Level/>`; on a one-line file that drops every later widget). **Fixture definitions QLC+ lacks are saved next to the workspace** as `<Manufacturer>-<Model>.qxf` (QLC+'s fallback path in `Fixture::loader`), else unknown fixtures load as plain dimmers. Stock fixtures (found in the installed QLC+ library or user folder, `qlc_library.py`) get no file; if the installed definition lacks the chosen mode → warning (QLC+ prefers its own definition). |
| 2026-09-24 | Real show files in the public repo are **renamed and scrubbed** (`Festival_14fix`, `Pub_6fix`; bands/songs/venue → neutral names). Git history still contains the originals — purge only if needed (needs a force-push). |
| 2026-09-23 | **PANIC RESET is a Script**, not a scene: `stoponexit:false`, stop every generated function, start *Reset: neutral state*, `wait:100ms`, stop itself. Reasons, all reproduced in real QLC+ builds: HTP channels can't be pulled down by a scene; QLC+ 5 scripts (to spring 2026) never end on their own; QLC+ 5.2.2 drops queued script commands if the code ends before the next tick (upstream fix `ca8ffd41`). The master slider is a Level **DIMMER** at 0 (a Level slider at 255 held dimmers full; a Submaster slider made 5.2.2 drop the VC). |
| 2026-09-23 | **Behaviour is verified in real QLC+**, not only by reading XML: `tools/qlc_check.py` (web-socket API) is part of the §6 open-check. Target versions: QLC+ 5.2.2 (Giovanni's) and 4.14. |
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

**Push:** Cowork's sandbox cannot reach GitHub, so Cowork commits locally and Giovanni pushes.

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

**Phase 0 status — ✅ done 23 Sep** (branch `chore/phase0-cleanup`, 0.1–0.8 each in its own commit; 216 tests green). Open items for Giovanni: ~~0.2 visual check~~ (done 23 Sep, correct); 0.6 first green CI run; 0.8 tag + GitHub Release after merge.

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
- [ ] Add `20Minutes_FLOOR` when available.
- [x] `core/doctor/` exposes `check(root, qxf_defs) → Report`. Each finding has an ID, severity, location and message. Read-only in this phase. *(Also `check_file()`, `load_qxf_defs()`; docs in `docs/doctor.md`.)*
- [x] Initial checks: the D-codes in §5 Phase 2.1 marked ★. *(Plus D009, D012, D015, D016 and info I001–I003. Corpus: Pub_6fix 0 errors / 0 warnings; Festival_14fix 1 error (D002 widget ID 0); all prototype D006 false positives gone. Counts pinned in `expected_baseline.json`.)*
- [x] Command line: `python -m core.doctor file.qxw` prints the report and exits non-zero on errors. Used by tests and CI; it's also the future hook for automation. *(`--json`, `--qxf`, `--allow-fx`, `--all`, `--min-severity`.)*
- Commit: `feat(doctor): read-only check engine + CLI`

**1.1 Quick Start**
- [x] Golden-file tests: 3 reference rigs produce byte-identical `.qxw` output. *(`QuickStart_6fix`, `QuickStart_club` (Spot 110 6-ch + SlimPAR 56), `QuickStart_multiuni` (8 × Spot 375Z + 60 × SlimPAR 56, 2 universes); `tests/test_quickstart_golden.py`.)*
- [x] Output passes Doctor with zero errors, and the QLC+ open-check (§6) passes. *(Doctor: all three golden files 0 errors / 0 warnings; export gated by Doctor. QLC+: `tools/qlc_check.py` PASS on club + multiuni in 5.2.2 and 4.14.5; manual check on the Mac, 23 Sep.)*
- [x] **Live QLC+ check** (`tools/qlc_check.py`, `docs/qlc-live-check.md`, opt-in `tests/test_qlc_live.py`): VC loaded + every button lights something + PANIC RESET after every button, on the real DMX output.
- [x] **1.1b after Giovanni's test (24 Sep):** full-width page; one SHOW solo frame (one button at a time); fixture groups (step 3 editor, per-group frame + submaster + looks + effects); MASTER submaster; RGB matrices lit (Collection); `.qxf` next to the `.qxw`; indented XML.
- [x] Safe defaults baked in: PANIC RESET, strobe and program channels at 0, full channel declaration. *(Plus mode-aware channel indices and capability-aware neutral values — `core/quick_start/channel_model.py`.)*
- [x] **Clone VC style from a reference QXW**: button size, gaps, header, fonts, page size (`core/quick_start/vc_style.py`). Built-in `compact` style extracted from `Pub_6fix`; *From a reference .qxw…* in step 4. *(Frame layout/page structure cloning → Phase 2.4 VC templates.)*
- [x] Nomenclature profile (JSON): `plain` and `20minutes` in `core/quick_start/profiles/nomenclature/`. The 20Minutes profile:
  - First letter, fixture group: A = all, F = front four, S = singer pair, B = band pair, R = rear two, D = drums floor, L = logo, X = split/spatial.
  - Second letter, effect type: S = static, D = dynamic, P = pulse, M = movement, \* = special FX.
- Commits: `test(quickstart): golden outputs`, `feat(quickstart): clone VC style from reference`, `feat: nomenclature profiles`

**1.2 Function Porter** — ✅ *done 25 Sep, branch `feat/porter-vc`*
- [x] **VC porting**: bring each ported function's buttons and frames too, with widget ID remapping, a target page chosen by the user, and collision-free placement. *(`core/porter_vc.py`; step 2 picks frames/buttons from the source VC and seeds the port; step 4: target page or new page, binding policy.)*
- [x] Verify **fan-in** (many source fixtures to fewer targets, e.g. 14 → 6). *(Explicit `fan_in` mode + Auto-Map strategies `fan_in` (stage order) and `same_id` (reduced rig); "first lit source wins" per scene.)*
- [x] Real case: port looks from Festival_14fix into a 6-fixture rig. The result passes Doctor. *(Both QuickStart_6fix (fan-in) and the bare Pub rig (same IDs): 0 errors, 0 warnings; `tests/test_porter_fanin.py`.)*
- [x] The import report is saved next to the output file. *(`<name>_port_report.txt`.)*
- **1.2b — Porter UX after Giovanni's test (25 Sep)** *(branch `feat/porter-vc`)*:
  - [x] Step 2: VC list has its own ✓ All / ✗ None; ticking a page/frame ticks everything inside (dash when partly ticked). *(commit `3bdaaee`)*
  - [x] Step 2: dependencies resolve automatically while ticking; *Resolve Dependencies* button removed; **Next** resolves then moves on. *(`3bdaaee`)*
  - [x] Porter messages use the app's single status bar (a stale "No workspace is open" from ⤵ Open workspace no longer shows under the Porter). *(`3bdaaee`)*
  - [x] **Stage plans** *(done 25 Sep)*: step 1 shows a top view of where the fixtures are in the source and in the target (from the 3D monitor positions; nothing drawn if the file has none), reusing the Fixtures-tab drawing code (`static/js/fixture.js` top view, `core/fixture.py` stage/position reading). Step 3 shows the same two plans coloured by the mapping (each target a colour, its sources in the same colour, unmapped grey) so the mapping can be checked at a glance. *(Implemented: `core/fixture.py` `read_stage_dims()` / `read_positions()` / `stage_plan()` (pure, reused by `import_from_qxw`); `GET /api/porter/stage/<source|target>`; `static/js/fixture.js` `drawStageTopView()` shared by the Fixtures tab and the Porter; tests in `tests/test_porter_fanin.py::TestStagePlan`. Checked in a browser with LiquidBar_v14 → MiniRockShow_4generic_2.)*
  - [x] Step 2 **Next button hidden** when the two lists are tall (Giovanni's screenshot, 25 Sep): the step's content now scrolls in `.porter-panel-body`, the Back / Next bar stays at the bottom (checked at 1000×620 and 1600×1000).
  - [x] Step 3 **"Don't port this fixture"** *(done 25 Sep: "Port this fixture" checkbox per row; uses `lit_fixture_map` from `resolve_closure` — a scene declaring a fixture at 0 doesn't "use" it; checked in a browser: skipping DR + LG unticks *RS · Silhouette* and *LS · Logo Only* in step 2, re-including restores them)* per source fixture (Giovanni, 25 Sep): the fixture gets no target and its values are left out; functions (and VC widgets) that use *only* skipped fixtures are unticked in step 2 (visible when going back) and come back when the fixture is included again. The mapping of the other fixtures is kept when the selection changes.
  - [x] Step 3 **highlight**: hovering or clicking a mapping row rings that source fixture on the source plan and its target(s) on the target plan. *(done 25 Sep; click pins the highlight)*
  - [ ] Fan-in ordering idea (not started): use Left/Right/Front/Back words in fixture names when positions and names disagree (MiniRockShow case).
- Found and fixed along the way: non-deterministic function IDs (closure ordered by a set); EFX fixtures and percent-encoded script commands not recognised in real QLC+ files; values of unmapped fixtures left in scenes (dangling refs); RGB matrices pointing at a group missing in the target; ported looks surviving the target's PANIC RESET (live check).
- Commits: `feat(porter): port VC widgets with functions`, `test(porter): Festival_14fix→Pub_6fix fan-in case`

**1.3 Show Book**
- [ ] Test suite: section builders, DMX decoding against the corpus QXFs, CSV zip contents, and the PDF text layer.
- [ ] The VC Layout section matches the Pub_6fix pages and frames.
- [ ] Add an optional Doctor summary section.
- Commit: `test(showbook): coverage for sections, decoding, exports`

**1.4 Release v1.4.0**
- [ ] Remove the Alpha badges.
- [ ] Wiki pages for Quick Start, Porter, Show Book and Doctor (read-only).
- [ ] Forum post.

### Phase 2 — Show-building toolkit (replaces manual/AI XML patching)

**2.1 Workspace Doctor: fixes → v1.5.0**

Doctor is a UI tab plus the CLI. Every fix is opt-in per finding, and the output always goes to a new file with a fix report.

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

**2.2 Rig Reducer → v1.5.0**
- [ ] Choose the fixtures to keep. Everything else is removed, with cascade:
  - channel values in scenes;
  - EFX and RGB Matrix fixture lists;
  - fixture groups;
  - 3D monitor items;
  - functions that become empty;
  - VC buttons for functions that no longer exist.
- [ ] Optional re-patch of the kept fixtures (DMX addresses, renames), e.g. FLS/FRS/FLB/FRB/DR/LG.
- [ ] Doctor runs automatically, and the result is saved as a new version.
- Commit: `feat: Rig Reducer with cascading clean-up`

**2.3 Look and Chaser Builder → v1.6.0**
- [ ] **Looks**: fixture group × palette. Palettes are warm, cold, scenic and custom (with RGB pickers). Every channel is declared. Names follow the nomenclature profile.
- [ ] **Chaser patterns**:
  - all-hit;
  - left/right alternation;
  - chase across a group;
  - ping-pong;
  - build-up;
  - random (seeded, so it stays deterministic).
- [ ] Chaser options: cut vs fade, and step time entered in ms or as BPM plus note length.
- [ ] Song presets (e.g. "Take Me Out Drive": 8 steps, 280 ms, hard cut) are saved in a profile and reusable.
- [ ] Simulated DMX preview: a per-step colour strip for each fixture.
- Commits: `feat: look builder (group × palette)`, `feat: chaser pattern builder with BPM timing`

**2.4 VC Builder → v1.7.0** (extends the existing VC Visual Editor)
- [ ] Create, delete and duplicate widgets: frames, SoloFrames, buttons, sliders, labels, CueList. *(Copy/move of widgets and frames between pages shipped early in v1.3.2 — `core/vc_ops.py`.)*
- [ ] Wire widgets to functions: a picker filtered by nomenclature, and drag a function from the list onto a button.
- [ ] Pages (top-level frames): add, rename, reorder, set the default page. *(Add and duplicate shipped in v1.3.2.)*
- [ ] Layout tools: grid snap, multi-column label panels (e.g. the nomenclature legend), auto-arrange buttons by nomenclature group.
- [ ] Screen profiles (1650×884 MacBook, 1920×1080, tablet).
- [ ] VC templates: save any page as a template and apply it to another workspace.
- [ ] Setlist integration: wire the setlist chaser to the CueList widget in one click; Doctor D014 checks it.
- Commits: `feat(vc): create/delete/wire widgets`, `feat(vc): pages, grid snap, screen profiles`, `feat(vc): page templates`

**2.5 Stage and Meshes → v1.8.0**
- [ ] Work out how QLC+ 5 stores meshes: add an OBJ in QLC+, save, and diff the files. Record the findings in the wiki.
- [ ] Import OBJ meshes (band members, risers, truss) with position, rotation and scale. Build a small reusable mesh library.
- [ ] Unified 3D placement for fixtures and meshes, reusing the tilt logic from §3.
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

**Giovanni, before the next session (on the Mac):**
1. ✅ *Done 23 Sep — tilt correct.* Open `tests/manual/tilt_check.qxw` in QLC+ 5 → 3D view. Every beam should cross toward the middle of the stage (none straight down/up). If a direction is mirrored, note which zone — the fix is one sign in `_ZONE_XROT`.
2. `git push -u origin chore/phase0-cleanup` and check the Actions run is green.
3. Merge to `main`, then `git tag -a v1.3.2 -m "v1.3.2" && git push --tags`; create the GitHub Release from the CHANGELOG; forum post optional (patch release).
4. `git push -u origin feat/doctor` (it is stacked on Phase 0; rebase onto `main` after the merge if needed).

**Giovanni, before the next session (Phase 1.1):**
1. ✅ *Done 23 Sep* — QLC+ open-check on the club / multiuni files (PANIC RESET works in 5.2.2).
2. Test 1.1b in the app: step 3 groups editor, step 4 preview, export (the `.qxf` files appear next to the `.qxw`), then in QLC+: one button at a time, matrix effects light up, MASTER and group sliders dim.
3. `git push -u origin feat/quickstart-1.1`; CI green; merge into `main` (it contains `feat/doctor`). Push the wiki.
3. Optional: `pip install websocket-client`, then `python3 tools/qlc_check.py tests/corpus/QuickStart_club.qxw` with QLC+ closed — should print `RESULT: PASS`.

**Giovanni, before the next session (Phase 1.2):**
1. Try the Porter tab: source *Festival_14fix*, target a 6-fixture rig; step 2 tick *COMBINED FX* → *Select their functions*; step 3 Auto-Map *Fan-in by stage position* (or *Same fixture ID* for a reduced copy); step 4 new page; export → `<name>_v2.qxw` + `<name>_v2_port_report.txt`. Open in QLC+ 5.2.2: ported page renders, buttons light, PANIC RESET clears them.
2. `git push -u origin feat/porter-vc`; CI green; merge into `main`. Push the wiki (new page *Function Porter*).

**Next Cowork session:**
1. Phase 1.3 Show Book (test suite, VC Layout section vs Pub_6fix, Doctor summary section).
2. Add `20Minutes_FLOOR` to the corpus when available.
3. Look into `QuickStart_6fix`'s whole-rig *Chase* / *Stripes* buttons: in the live check (QLC+ 5.2.2 headless) one of them is intermittently dark (a different one per run) — timing of the Collection (dimmer scene + matrix) start, or the check's 1 s settle?
4. Porter backlog: channel translation between different fixture types (by capability, e.g. PAR → spot); Sequence step values; Show timelines; optional "compact frames" after pruning.
5. Backlog candidates: `_vN` file name for the Quick Start download; save Quick Start options in the session; run `tools/qlc_check.py` in CI (build QLC+ 5.2.2 in a cached Docker image).
6. Upstream reports (QLC+ forum/GitHub): `VCSlider::loadXMLLevel` token over-read after an empty `<Level/>` on unindented XML; RGB-mode matrices ignoring *DimmerControl*; 5.2.2 script-command race (if not covered by `ca8ffd41`). Doctor: add a check for fixtures whose definition won't be found next to the workspace.
