# QLC+ Swiss Knife: work plan

This is the living plan for Swiss Knife: where the project stands, what comes next, how releases are made and which decisions stay in force. Finished work is not repeated here. The history is kept in two archives:

- [docs/WORKPLAN_ARCHIVE.md](docs/WORKPLAN_ARCHIVE.md): the working log from 23 September to 8 October 2026 (1.3 to 3.0). Code comments that mention "WORKPLAN 3.6" or similar point to its numbered sections.
- [docs/WORKPLAN_ARCHIVE_2.md](docs/WORKPLAN_ARCHIVE_2.md): the plan as it stood at 3.6.0 on 20 October 2026, with the full design of every release from 3.0.1 to 3.6.0 (Stage Monitor protocol, Cabling, the QLC+ 5.3 alignment).

**Contents**

1. Where we are
2. Next releases
3. Wishlist and dropped ideas
4. Release history
5. Goal and the Pub test
6. Principles
7. Standing decisions
8. How we work (git, documentation, releases)
9. QLC+ open-check before a release

---

## 1. Where we are

**Version 3.6.1, 20 October 2026.** Swiss Knife opens a QLC+ 5 workspace once, lets any tool change it as the show in progress, checks it with the Workspace Doctor and saves it as a new file with a report and a recipe.

| Area | State |
|---|---|
| Tools | Quick Start, Fixtures, Rig Reducer, Function Porter, Brightness, Look Builder, VC Visual Editor, Stage and Meshes, Library, Setlist, Trigger Manager, Dictionary, Stage Monitor, Cabling, Workspace Doctor, Wizard Repair, Upgrade to QLC+ 5.3, Compare, ID Browser, Show Paperwork. |
| Reuse | The recipe replays a session to the same file. Show Profiles apply the same changes to another show. |
| Install | Packages for macOS (Apple silicon and Intel), Windows (installer and zip) and Linux, with an update check and *Update and restart*. |
| Language | English, Italian, French, German, Spanish, Portuguese, Japanese and Chinese. |
| Claude | An MCP server with 28 tools (among them `guide`), seven ready requests, the guide as resources. Claude Desktop connects with one `.mcpb` file, Claude Code with one command. Claude gets only the folders you list and writes only new files (the Stage Monitor's own page and settings are the exception). |
| Tests | 1102 automated tests pass (1 skipped without the `websocket` module). A live check against QLC+ 5.2.2 runs in CI (advisory). |
| Documentation | README, wiki (35 pages), CHANGELOG, release notes per version. |

**Order agreed on 20 October** (giopas): 3.6.1 gig-ready pass, 3.7.0 another computer and another screen, 3.8.0 stage layouts and per-song tempo, 3.9.0 Stage Monitor song cards, 3.10.0 teleprompter, 3.11.0 colour themes and porting by eye.

## 2. Next releases

### 3.6.1 · Ready for the gig (released 20 October, branch `fix/v3.6.1`)

No new screens. Fix what a real gig would show, and do the checks on the Mac that 3.0.1 to 3.6.0 left open.

**Fixed so far**

- Brightness looked for fixture definitions in its own list of folders, which missed the macOS user folder `~/Library/Application Support/QLC+/Fixtures`. A definition made in QLC+'s Fixture Editor on the Mac was therefore not found by Brightness. It now uses the shared lookup (`core/quick_start/qlc_library.library_dirs()`) first, like the Porter, the Doctor, Quick Start, Show Paperwork and Cabling. Test: `tests/test_brightness_dirs.py`.
- Show Paperwork's cabling section read the rig with only the show folder's definitions, while the Cabling screen uses `_defs()` (show folder, then the QLC+ library). A stock fixture's connector was unknown on paper (3-pin guessed, C101), so the printed plan could differ from the screen. It now uses `_defs()` too.
- Input profiles: the lookup also covers the Windows user folder `%USERPROFILE%\QLC+\InputProfiles`, `~/Applications/QLC+.app`, `C:\qlcplus\InputProfiles`, and spells the macOS user folder `InputProfiles` as QLC+ does (matters on a case-sensitive disk). Tests for both: `tests/test_lookup_dirs_361.py`.

**Automated checks done (20 October)**: the full test suite (1102 passed after the fixes above), `tools/ground_truth.py` clean apart from two stale `maintenance.lock` files (removed), the Doctor on the nine test shows (only the known D002 in the raw `Festival_14fix.qxw`, which the tests expect).

**Checks on the Mac** (giopas). A1 to A6 passed on 20 October; A7 is done right after the push (*Update and restart* from 3.6.0). The B and C checks stay open and move with the next releases; anything that fails becomes a fix.

A. Before the next gig (the show path)

| # | Check | From |
|---|---|---|
| A1 | ✓ Open the gig show in Swiss Knife, Doctor at 0 errors, save, open in the QLC+ used on stage (5.2.2 or 5.3.0); PANIC RESET, a scene, a chaser, the setlist CueList with DMX on | 3.x |
| A2 | ✓ Stage Monitor with QLC+ and the MIDI pedal: `tools/stage_probe.html` first, then the exported page; current and next cue follow every press | 3.5.0 |
| A3 | ✓ Stage Monitor on the real tablet (10-inch Android and/or iPad, portrait), via *Start Stage Monitor* on the installed app; tablet Wi-Fi off and on; QLC+ quit and restarted | 3.5.0, 3.5.3 |
| A4 | ✓ Stage Monitor: a two-hour soak; the two black colours under stage light; control mode *Previous*, *Next*, *Stop* with the chosen *Safety hold* | 3.5.0, 3.5.5 |
| A5 | ✓ Stage Monitor: a CueList on a hidden page of a multipage frame still reports | 3.5.0 |
| A6 | ✓ Cabling with the real cable bag (lengths, counts, any mic cables): a plan for the next venue, plot and labels printed, pick list used to pack | 3.6.0 |
| A7 | *Update and restart* from 3.6.0 to 3.6.1 | release |

B. Before the next release (the tools)

| # | Check | From |
|---|---|---|
| B1 | Cabling screen, four steps, dark and light; Library round trip of the kit; *Ask Claude…* with a photo of a fixture's back; the `cabling` tool and both ready requests in Claude Desktop | 3.6.0 |
| B2 | The five guided routes start to end; Quick Start *Save and go on*; *Skip*; leaving and coming back to a route; a narrow window | 3.4.0 |
| B3 | Look Builder on a show with moving heads: *Start from Concert*, *Add to the show*, then in QLC+ 5.3.0 the Looks page (one page per group, gobo and strobe looks, circle aimed at a musician, fly out and in); the same show in QLC+ 5.2.2 | 3.3.0 |
| B4 | An upgraded Festival or Pub show in QLC+ 5.3.0 (folders, palettes, Groups page, frame page selector) and in 5.2.2; floor XY pads and Position3D palettes on moving heads | 3.2.0 |
| B5 | Claude Desktop with the packaged macOS app (so far only from the sources) | 3.0 |
| B6 | Dictionary *Ask Claude…*, a dictionary written by Claude, cue notes seen in QLC+ | 3.0.1 |
| B7 | Doctor fixes with a choice, output opened in QLC+ | 2.4.0 |
| B8 | Fit a console to the real tablet and to a Pi touchscreen: *Fit*, *Check* with its list of small buttons, the result in QLC+'s web page (port 9999) on the device; the iPad sizes against what Safari reports | 3.7.0 |
| B9 | *Take the show elsewhere (.zip)*: unzip on a computer without your user definitions, open the show in QLC+ and see the fixtures as moving heads, not dimmers | 3.7.0 |

C. For other users (when there is a chance)

| # | Check | From |
|---|---|---|
| C1 | Claude Desktop on Windows with `QLC Swiss Knife MCP.exe` and the launcher | 2.9 |
| C2 | Each language on the Mac; native readers for the seven translations | 3.0.2, 3.4.1 |
| C3 | A Library file moved between two computers | 2.7.0 |
| C4 | The SINCO MIDI patch with a real controller | 2.6.0 |

### 3.7.0 · Another computer, another screen

For moving a show to another machine (a stage laptop, a Raspberry Pi) or another screen (a tablet, a small touchscreen). giopas plays from his MacBook Pro, so this is mainly for other users, and for the day the show moves.

**Status (20 October, branch `feat/v3.7.0`, not released).** Both parts are built and committed locally; the wiki (separate repository) has its commit too. 1145 tests pass (1 skipped without the `websocket` module). Left for the release: the pictures with `python3 tools/shots.py all`, release notes, the version bump and the merge as in section 8.

- Part 1 is `core/definitions.py` (where each definition was found; the zip), `core/quick_start/qlc_library.py` (`stock_dirs()`, `user_dirs()`, `in_stock()`), Doctor D021 to D023 and I009 in `core/doctor/checks.py`, `/api/show/definitions` and `/api/show/travel`, the button in the Doctor and Show Paperwork, and `save_show` with `with_definitions`. Severities, confirmed from QLC+'s `Fixture::loadXML`: D021 to D023 are warnings (a missing mode becomes a generic dimmer sized by the file's channel count). The *chosen folder* source is in `source_of()` but no screen offers a chosen folder yet.
- Part 2 is `core/vc_screens.py` (the sizes; your own in `~/.qlc_swiss_knife/vc_screens/`; Library kind `vc_screen`), `apply_screen()` and `preview_screen()` in `core/vc_builder.py`, `/api/vc/screen-preview`, the panel in `static/js/vc_builder.js`, the outline in `static/js/vc_editor.js`, and `edit_vc` `screen` with `preview` for Claude. A call with no `mode` behaves as before 3.7.0 (text unchanged), so recorded sessions replay to the same file.
- Pixel values: the 7-inch touchscreens (800 × 480, 1024 × 600) and the Pi Touch Display 2 (720 × 1280 native, 1280 × 720 turned to landscape) were checked against shop and maker pages. The iPad sizes (CSS points, landscape) come from memory and are to be checked on the device (B8).
- Tap size: 44 px on the short side (Apple asks for 44 pt, Material for 48 dp), `vc_screens.TAP_MIN`.

**1. Fixture definitions that travel**

A `.qxw` names each fixture's manufacturer, model, mode and channel count but does not carry the definition. QLC+ finds it in its stock library, in the user folder, or next to the workspace as `<Manufacturer>-<Model>.qxf` (`Fixture::loader`). On another computer a custom definition is missing, and channels, sliders and addresses go wrong without a clear message.

- One lookup for every tool: the stock and user folders of the system (`qlc_library.library_dirs()`), the show's folder, and the folder the user chose for decoding. Each definition remembers where it was found: *QLC+ library*, *user folder*, *show folder* or *chosen folder*.
- New Doctor checks (severities confirmed against QLC+'s `Fixture::loadXML` on 20 October: warnings):
  - D021: the fixture's mode is not in its definition.
  - D022: the channel count in the show differs from the mode's channels in the definition.
  - D023: a scene sets a channel beyond the fixture's channel count.
  - I009: the definition is not in QLC+'s stock library (user folder or show folder only), so it has to travel with the show.
  - I003 stays as it is (no definition found).
- *Take the show elsewhere (.zip)*, in the Doctor and in Show Paperwork: the show, every definition that is not in the stock library, saved next to the show under the name QLC+ looks for (so it loads with no copying), the side files (`<show>.stage.json`, `<show>.cabling.json`), and a short text on where definitions go on macOS, Linux, Windows and a Pi if you prefer to install them. A new file every time; fixed timestamps in the zip, as in Show Paperwork's CSV export, so the same show gives the same zip.
- Claude: an option on an existing tool (the tool count stays 28).

**2. Fit the Virtual Console to a screen**

QLC+ places Virtual Console widgets at fixed pixel positions, so a console made on a laptop overflows a small touchscreen and is tiny on a big one. QLC+'s web page (port 9999) draws the desktop layout and scales it down. The VC Visual Editor already has *Screen size* with four sizes and *scale the widgets too*, which scales width and height separately (square buttons get stretched) and leaves the fonts unchanged.

- Screen sizes as data (principle 7), shareable through the Library: the four of today plus a 7-inch 800 × 480 and 1024 × 600 touchscreen (Raspberry Pi and similar), current iPad and Android tablet sizes, Full HD and larger monitors. Pixel values checked before release. Your own width and height. Portrait or landscape.
- Three ways to apply: *Fit* (one factor for width and height, so shapes keep their proportions; the default), *Stretch* (today's behaviour), *Page size only*.
- Fonts scale with the widgets, within limits so text stays readable.
- On a touch screen size, a warning for buttons and sliders that end up too small to tap, with their names.
- The device's outline drawn over the page in the editor before applying.
- The result is saved as usual, as a new `_vN`. It is recorded in the recipe, so a Show Profile can fit another show to the same screen.
- Claude: `edit_vc`'s screen operation takes the size, the orientation and the way to apply.

### 3.8.0 · Stage layouts and per-song tempo

Decided 18 October, from the wiki of mjcmatrix's fork of QLC+ (https://github.com/mjcmatrix/qlcplus/wiki, by Matt C). Ideas only, no code; Swiss Knife writes only what upstream QLC+ 5.2.2 to 5.3.x reads. Both features credit mjcmatrix by name, with a link, in the CHANGELOG, the release notes and their wiki pages.

**1. Stage layouts.** A saved layout of the stage and the band, used as the base of a new show, the way My kit is the base of tonight's kit in Cabling.

- It holds the stage size and type, drum riser, backline, members by role (vocals, guitar, bass, drums, keys) and where they stand, wedges, curtain or backdrop, the band floor and walkways.
- Kept in the user's settings, shared through the Library; several layouts (full band, acoustic, festival). *Save as layout* takes one from the current show's meshes.
- Quick Start and Stage & Meshes start a new show from it; Cabling takes its band floor, so it is defined once; the Look Builder's *places on the stage* aim at its members.
- Written in the show: the meshes and their positions, as Stage & Meshes writes them today. Colours and the curtain only if upstream QLC+ 5 stores them; otherwise they stay in the layout.

**2. Per-song tempo in the setlist** (the fork's *Show Tempo Sections*).

- A setlist line takes an optional tempo: `Song name | 128BPM` (spaces, case and the `BPM` word optional). Lines without it work as today; *Save setlist…* writes it back.
- A *BPM* column on the Setlist screen, and a check that flags a matched chaser whose step timing does not fit the tempo.
- *Apply tempo* recomputes hold and fade of each step from the BPM and the beats per step (Swiss Knife's chasers run on time; no BPM speed dial). Beats per step: what the Look Builder recorded, else 1, changeable per song.
- A chaser used by two songs at different tempos is copied per song (`<name> · 128 BPM`) and each song's CueList step points to its copy.
- Every change goes through the show in progress, the History and the Doctor. Claude's `setlist` tool reads and writes the tempo.

### 3.9.0 · Stage Monitor song cards

The cheap part of the teleprompter idea: what each player needs to know about the next song, on the stage tablet, from data Swiss Knife already has.

- A card per song: tuning, tempo (from 3.8.0), who starts and how (count-in, drums 4 bars), pedal or FX settings per player, a free note. Edited on the Stage Monitor screen, kept in `<show>.stage.json` (shared by every version of the show), with the Dictionary's descriptions offered as a start.
- *Next song* alert: when the setlist reaches a new song, a large banner shows its card for a few seconds or until the next step; a change of tuning from the previous song is shown in its own colour.
- Views by role in the address: `?role=commander` (cues and card side by side, for the player with the pedal), `?role=vocals`, `?role=band`. Same page, same export, no setup on the tablet.
- From the 3.5.0 phase 3: chosen VC buttons (PANIC RESET) as big tiles in control mode, the Setlist screen's order, a QR code for the address if a small pure-Python encoder fits.
- The page stays offline (nothing from the internet) and read-only by default.

### 3.10.0 · Teleprompter (later stage)

Chords and lyrics from giopas's `song_writer` app (the "song-notation-tool" of the 20 October brief), following the setlist on the stage tablet. To be designed when song cards have been used at a gig.

- The notation files are taken from a folder and put inside the exported page, so it still needs no internet. Songs are matched to the setlist with the setlist's own name matching.
- A CueList step named like a section (`03 - Chorus`) brings that section of the sheet (`[Chorus]`) to the middle of the screen and highlights it; manual scrolling stays possible.
- Text size A− / A+, chords and lyrics, lyrics only.
- Depends on `song_writer` writing section headers Swiss Knife can match; that is the first thing to check.

### 3.11.0 · Colour themes and porting by eye

**1. Colour themes.** Push a whole show, or part of it, towards a colour: more green for a Saint Patrick's night, more blue, more red, or a song re-themed to suit a venue's backdrop.

- *Shift towards* a colour by an amount, *swap* one colour for another within a tolerance, or *rotate* every hue.
- Brightness stays as it is: dimmers, strobe, timings and every non-colour channel are untouched; whites and near-whites stay white.
- Scope: the whole show, one song's chaser and its scenes, or a fixture group. Colour-mixing fixtures get new values; colour-wheel fixtures get the nearest slot (`core/capability_map.py`); QLC+ 5.3 colour palettes are changed with them.
- Before and after swatches for each scene before applying. Recorded in the recipe, so a theme (*Saint Patrick's*) can be saved as a Show Profile and applied to another show.

**2. Porting by eye.** The Function Porter already translates between fixture types by capability (`core/capability_map.py`). What is missing is seeing it: a table per fixture pair (source channel, what it does, target channel) shown before porting, and the choices kept as a Library item for the next port between the same two models.

## 3. Wishlist and dropped ideas

**Wishlist** (no date)

| Item | Note |
|---|---|
| DAW markers to a song chaser | The band has song sessions with markers but uses no DAW at gigs. REAPER marker CSV only: each marker becomes a step, with infinite hold (pedal) or its duration (backing track). Fits after 3.8.0's tempo. |
| Compare, more detail | Widget position and size, key and MIDI bindings, timings in seconds, a Markdown export. Compare stays read-only. |
| Power planning | Circuits and powerCON chains from `PowerConsumption`, on the Cabling kit model. |
| Cabling extras | A network switch or Wi-Fi between computer and node, cables in QLC+'s 3D view, trusses in 3D, links to shops. |
| VC Editor | Resizing by dragging handles; knob, XY pad, speed dial and clock widgets; templates with key or MIDI bindings. |
| Porter | Replace all of a widget's bindings when a ported widget takes over; fan-in ordering by Left, Right, Front and Back in names. |
| Doctor | Renumbering of fixtures and groups (D002), more CueList, matrix and bound-scene repairs; D012 belongs to a future MIDI manager. |
| Moving heads | Positions beyond what the Look Builder sets (pan and tilt are centred unless set). |
| Quick Start | Its rig in memory as the Porter's target (only if the save-first hand-off feels clumsy); write `5.2.2` instead of `4.13.1` as the QLC+ version (QLC+ never reads it; it changes the golden files). |
| Rig Editor | Rename, add and wiring in one place. |
| MIDI learn simulation | Tell what a message would trigger. |
| Folder names | In the user's language or naming profile (the upgrade writes English, like the Show Wizard). |
| Separate `build_chaser` and `describe_show` Claude tools | Covered by `build_looks` and `show_summary`. |

**Dropped**

| Idea | Why |
|---|---|
| A new cross-mapping engine for the Porter (20 Oct brief) | `core/capability_map.py` already does it, deterministically, and keeps the white emitter that the brief's blend would lose. |
| Revert or copy single changes from Compare (20 Oct brief) | Copying between files with different IDs is the Porter's job; a second way would duplicate it with the most risk of breaking a show. |
| `.mid` marker files and automatic look choice by an AI (20 Oct brief) | Swiss Knife never calls an AI itself; marker names can be matched by rules, and Claude works through the MCP tools. |
| The audio-trigger helper; upstream bug reports to QLC+ | Dropped earlier. |

## 4. Release history

Details of each release are in [CHANGELOG.md](CHANGELOG.md), `docs/release-notes/` and the two archives.

| Versions | Dates | What they did |
|---|---|---|
| 1.3.2 to 1.10.0 | 23 Sep to 1 Oct | The foundation: one safe writer, the Workspace Doctor and its fixes, Quick Start, Function Porter, Rig Reducer, looks and chasers, VC Visual Editor, meshes, the show in progress, Show Paperwork, guided routes. |
| 2.0.0 to 2.2.1 | 1 to 5 Oct | The Pub test passed; fixture groups, Compare, the recipe, Show Profiles, UI polish. |
| 2.3.0 to 2.7.0 | 5 to 6 Oct | Themed releases: new-show flow, Doctor and Quick Start, looks and stage, paperwork and setlists and MIDI, languages and the Library. |
| 2.8.0 to 2.8.6 | 6 to 7 Oct | Packages for three systems, the update check, the logo, Windows installer. |
| 2.9.0 to 3.0.3 | 8 to 9 Oct | Swiss Knife as an MCP server for Claude; the 3.0.0 milestone; eight languages. |
| 3.1.0 | 14 Oct | QLC+ 5.3 Show Wizard shows: palettes read everywhere, Doctor D019 and D020, Wizard Repair. |
| 3.2.0 | 15 Oct | Upgrade to QLC+ 5.3 for older shows; Doctor I008. |
| 3.3.0 | 15 Oct | The Look & Chaser Builder in the wizard's families: gobo, strobe and level looks, places, movement effects, a page per group. |
| 3.4.0, 3.4.1 | 16 Oct | One way forward in the guided routes; the languages checked screen by screen; `tools/shots.py` and `tools/release_notes.py`. |
| 3.5.0 to 3.5.5 | 17 Oct | Stage Monitor: the current cue live on a tablet on stage, black colours, preview in the browser, Start Stage Monitor, asking before replacing a page, Stop and *Safety hold* in control mode. |
| 3.6.0 | 20 Oct | Cabling: a DMX cabling planner with the kit you own, 24 checks, plot, pick list, labels and load-in order; Claude's `cabling` tool. |
| 3.6.1 | 20 Oct | Ready for the gig: the show path checked on stage (A1 to A6); fixture definitions and input profiles found in every folder QLC+ uses. |

## 5. Goal and the Pub test

The goal is to build the next show file with the tool, and not by asking an AI to patch XML. The tool must reduce or adapt a rig, port looks and effects, generate looks and chasers, lay out the Virtual Console, place fixtures and meshes in 3D and validate everything before export. The result has to be deterministic (the same input gives a byte-identical output), accurate (QLC+ opens it cleanly and it behaves on stage) and useful to other QLC+ users (conventions are configurable and nothing is hard-coded to one band's habits).

The acceptance benchmark was the **Pub test**: rebuild the 6-fixture pub show from the 14-fixture festival show using only Swiss Knife. It passed in 2.0.0 in 12 minutes, with the Doctor at 0 errors, the show played in QLC+, the same patch, groups, looks, chasers, pages and setlist as the hand-made show, and a byte-identical replay from the recipe.

## 6. Principles

These apply to every change.

1. **Never overwrite.** Every write produces a new file: `<name>_v<N+1>.qxw`. The original is never touched. The one exception is the Stage Monitor: a page from an earlier Stage Monitor export is replaced, and only after a yes (see *The one exception* in section 7).
2. **One writer.** All `.qxw` output goes through `core/qxw_io.write_qxw()`, which keeps the XML declaration and the `<!DOCTYPE Workspace>`. A load, write, load round trip must lose nothing.
3. **Deterministic IDs and ordering.** New IDs are `max(existing) + 1` in a stable order. Generated XML has no timestamps or random values. Golden-file tests compare output byte for byte.
4. **The Doctor gates every export.** Quick Start, Porter, Rig Reducer, Look Builder and VC Builder run it before writing. Errors block the export and warnings go into the report.
5. **Safe show content by default.** Generated scenes declare every channel of every fixture they touch, keep strobe and internal-program channels at 0 unless asked, and always include a PANIC RESET. A VC button and a chaser step never share a scene.
6. **QLC+ is the reference.** Every generator has a manual open-check (section 9) before release.
7. **Conventions are data.** Naming, palettes, VC screen sizes and templates live in JSON profiles that users can share.
8. **Tests and CI are green before a merge.** Nothing merges without tests.

## 7. Standing decisions

The reasons and dates are in the archives.

| Topic | Decision |
|---|---|
| Saving | Every tool that writes a `.qxw` saves a new `_v<N+1>` file. |
| The one exception | A page from an earlier Stage Monitor export (`index.html`, `serve_stage.py`, Start Stage Monitor; they carry a mark) is replaced only after a yes, in the app and for Claude (`replace=true`). Files the Stage Monitor did not write are refused. |
| Side files | Settings that belong to a show but not to QLC+ live next to it without `_vN`: `<show>.stage.json`, `<show>.cabling.json`. Personal kit and stage layouts live in the user's settings and travel through the Library. |
| No AI or internet from Swiss Knife | Swiss Knife never calls the internet or an AI itself. Claude works through the MCP tools or an *Ask Claude…* window; what Claude proposes is saved only after the user confirms, each value with its source. |
| Claude | The only AI connected (others cannot start a local program; putting Swiss Knife online is not planned). Full tool set, new files only (plus the Stage Monitor exception), only the folders giopas lists. Connection by one `.mcpb` for Claude Desktop. |
| Supported QLC+ | 5.2.2 to 5.3.x. QLC+ 4 is not a target. Behaviour verified in real QLC+ (`tools/qlc_check.py`), not only by reading XML. |
| Fixture tilt | QLC+ 3D convention: 0 straight down, 90 horizontal, 180 straight up. Truss fixtures 45° toward the stage, floor fixtures 45° up toward the performers. |
| Doctor severities | D001 to D003 errors; D004 to D009, D012, D016 and D021 to D023 warnings; D015 and the I-codes information. |
| PANIC RESET | A script: stop every generated function, start a neutral-state scene, wait 100 ms, stop itself. |
| Quick Start VC | One page; looks and effects in one solo frame; each fixture group in its own solo frame with a submaster; RGB matrices through a collection that opens the master dimmers. |
| Generated XML | Indented like QLC+'s own files. Definitions QLC+ lacks are saved next to the workspace as `.qxf`. |
| Porter | Fan-in takes the first lit source of a block. Unmapped source fixtures are an error unless *leave out* is ticked. Functions left with no fixture are removed and reported. VC copies drop key and MIDI bindings unless you opt in. |
| Layer scenes | Swiss Knife's generators declare every channel; layer and palette scenes from others are accepted (I004) and never filled in. |
| Chasers and tempo | Swiss Knife's chasers run on time; no BPM speed dial. Positions are palettes and XY pads, not position-only scenes. |
| Test data | Real shows are renamed and scrubbed. The public repository carries no real names. Commits use the author *giopas*. |
| Ideas from others | Credited by name and link in the CHANGELOG, release notes and wiki. Ideas only, no code. |
| README | A presentation only. History lives in the CHANGELOG. |
| Forum | One complete post at 2.0, one at 3.0. No post per release. Drafts stay out of the repository. |
| Signing | Apps are not signed or notarised; the README and wiki explain the warning. No Linux AppImage unless someone asks. |

## 8. How we work

### Branches and commits

One branch per release, named `feat/vX.Y.Z` (or `fix/...` for a small change). Commits follow Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`), small and focused. The sandbox Claude works in cannot reach GitHub, so Claude commits locally and giopas pushes.

### At the start of a session

Run `python3 tools/ground_truth.py` before trusting this file or any note. It says what git and GitHub show: anything not pushed, a branch only on this disk, the tag and the release for `VERSION`, the last CI run and stale lock files. Exit code 0 means nothing to act on, 1 means drift, 2 means a check could not run. Run it again after a release.

### Before every commit

- Tests added or updated, and `python -m pytest -q` green.
- Every new or changed interface string has its entry in each file of `static/i18n/` (`it`, `fr`, `de`, `es`, `pt`, `ja`, `zh`). `python tools/i18n_extract.py --missing <code>` lists what a language lacks. Placeholders such as `{0}` stay.
- No version-specific text on the Start page.
- Nothing confidential or working-material is committed: no scratch folders (`_tmp_sync/`), archives, assistant folders (`.claude/`), notes, forum drafts, real show files or real names, keys, logs or personal paths. Run `git status` and `git diff --cached --stat` and read them.
- CHANGELOG entry under `## [Unreleased]`.
- Docstrings on new public functions, and user-facing wording checked.
- Documentation prose is written plainly: no dashes as connectors, no staged contrasts, no marketing tone.
- Every step of the work is written into this file as it happens, so work can continue safely after an interruption.

### Before a release

- Run the two `--missing` commands once more.
- Bump `VERSION` in `core/workspace.py` (it must match the CHANGELOG), the installer version, the README title and the spec comment.
- Move `[Unreleased]` to `[X.Y.Z] — date — Short title`: two to four words that say what the release is for. The GitHub release is called `vX.Y.Z · Short title` and its text is that CHANGELOG section; `python3 tools/release_notes.py vX.Y.Z` shows both before the push.
- Retake the pictures with `python3 tools/shots.py all` (quit Swiss Knife first; it needs port 5731). It retakes the README screenshots, the route GIF and the tutorial pictures, says which changed and writes `contact.png`. `--dry` leaves the repo alone, `--only 07` keeps one picture, `python3 tools/shots.py state <name> "<js>" … --lang it` takes any other screen.
- A wiki page for each new or changed tool. When a Claude tool changed, run `python tools/make_claude_tools_wiki.py` (the tests fail until the page matches).
- Release notes in `docs/release-notes/RELEASE_NOTES_vX.Y.Z.md`.

### Merge and release, always this way

Do not push the feature branch (that starts a third test run for the same commit). Merge locally, tag, push `main` and the tag together, then the wiki:

```
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script && git status --short
git checkout main && git merge --ff-only feat/vX.Y.Z && git tag vX.Y.Z && git push origin main vX.Y.Z && (cd wiki && git push origin master)
```

`git status --short` must print nothing first. For a change that is not a release, leave out the `git tag` part. If a change is risky, push `main` first, wait for `tests` to pass, then push the tag.

Pushing runs `tests` once on `main`, `qlc-live-check` once (advisory) and `release` once on the tag (tests, build, installer test on macOS twice, Windows and Linux). Check that the release is marked *Latest* and keeps only the `…-X.Y.Z-…` files plus `SHA256SUMS`: macOS arm64 and Intel (`.tar.gz` and `.dmg`), Windows (`-setup.exe` and `.zip`), Linux (`.tar.gz`) and the Claude Desktop file (`-claude.mcpb`). Then try *Update and restart* from the previous version.

### Keeping this file in step

This file lives in the repository and in the Claude project (`claude/WORKPLAN.md`). After a change, copy the repository file to the project.

## 9. QLC+ open-check before a release

1. Open the output in QLC+ 5. The log shows no warnings, every function is listed and the VC shows the expected page.
2. In the Fixture Manager the addresses match and nothing overlaps.
3. In the 3D monitor, fixtures and meshes sit where you expect and are tilted as expected.
4. Run PANIC RESET, a scene, a chaser and the CueList with DMX output on. PANIC RESET and VC loading are automated: `python3 tools/qlc_check.py file.qxw` (see `docs/qlc-live-check.md`).
5. Save from QLC+ and run the Doctor on the saved file. It must still be clean, which shows QLC+ did not have to repair anything.
