# QLC+ Swiss Knife: work plan

This is the living plan for Swiss Knife. It says where the project stands, what is left, how releases are made and which decisions stay in force. The full working log from 23 September to 8 October 2026 (every phase, task, test count and live-test note) is kept in [docs/WORKPLAN_ARCHIVE.md](docs/WORKPLAN_ARCHIVE.md). Code comments that mention "WORKPLAN 3.6" or similar point to the numbered sections of that archive.

**Contents**

1. Where we are
2. What is left
3. Release history
4. Goal and the Pub test
5. Principles
6. Standing decisions
7. How we work (git, documentation, releases)
8. QLC+ open-check before a release
9. Not built, and ideas

---

## 1. Where we are

**Version 3.5.0, 17 October 2026.** 3.1.0 added support for shows made by the QLC+ 5.3 Show Wizard, 3.2.0 gives older QLC+ 5 shows what QLC+ 5.3 offers, 3.3.0 rebuilds the Look & Chaser Builder in the wizard's terms, 3.4.0 gives the guided routes one way forward, 3.4.1 checks the seven languages screen by screen, and 3.5.0 adds the Stage Monitor, a page for a tablet on stage that follows QLC+ live. Swiss Knife opens a QLC+ 5 workspace once, lets any tool change it as the show in progress, checks it with the Workspace Doctor and saves it as a new file with a report and a recipe.

| Area | State |
|---|---|
| Tools | Quick Start, Fixtures, Rig Reducer, Function Porter, Brightness, Look Builder, VC Visual Editor, Stage and Meshes, Library, Setlist, Trigger Manager, Dictionary, Stage Monitor, Workspace Doctor, Wizard Repair, Upgrade to QLC+ 5.3, Compare, ID Browser, Show Paperwork. |
| Reuse | The recipe replays a session to the same file. Show Profiles apply the same changes to another show. |
| Install | Packages for macOS (Apple silicon and Intel), Windows (installer and zip) and Linux. An update check with *Update and restart*, tested on macOS several times. |
| Language | English, Italian, French, German, Spanish, Portuguese, Japanese and Chinese. |
| Claude | Swiss Knife is an MCP server with 27 tools, among them `guide`, which explains the others. It also offers five ready requests (MCP prompts) and the guide as resources. Claude Desktop connects with one file (`.mcpb`), Claude Code with one command. Claude gets only the folders you list and Swiss Knife itself, and it writes only new files (the Stage Monitor's own page and settings are replaced). The *Connect to Claude* card and the menu item show whether the connection exists. |
| Tests | 1009 automated tests pass (in the sandbox; 3 skipped there). A live check against a real QLC+ 5.2.2 runs in CI (advisory). |
| Documentation | README, wiki (32 pages, *Claude's tools* written from the code), CHANGELOG, one set of release notes per version. |

Release 3.0.0 was the milestone: installing, updating, three languages and the Claude connection all in place, with the documentation rewritten to match. Release 3.0.1 follows a test on a real show with Claude: the Dictionary drafts descriptions itself and can hand the job to Claude, cue notes name the button, and Claude's tools are documented where Claude reads them. Release 3.0.2 adds German, Spanish, Portuguese, Japanese and Chinese, and 3.0.3 translates the tool names and fills the gaps found on the first look.

## 2. What is left

Nothing in the programme is open. What remains is testing on real systems and a few decisions.

### Released in 3.5.0 (17 October): Stage Monitor

Added after a gig. The spec is the Claude doc *Swiss Knife — Stage Monitor tab (spec)*; this section is the plan as it was built.

**The use case.** The setlist changed during the show. The person stepping through the setlist CueList with a MIDI pedalboard also plays an instrument, cannot leave the spot and cannot see the laptop, so they lost track of which cue was live. They need the current cue and the next one, with song names, readable from 1 to 1.5 m under stage light, on a tablet at their feet or on a mic stand. The page only shows by default; the pedal stays the controller. On a dark stage the tablet itself must give off as little light as possible.

**What already exists** (checked 17 October in the forum and in the QLC+ 5.2.2 and 5.3.0 source):

| Existing | What it is | Why it does not cover the case |
|---|---|---|
| QLC+'s own web page (`qlcplus -w`, port 9999) | The whole Virtual Console in a browser, live, with the CueList as a table (fade, hold, note columns) and Play, Stop, Previous, Next buttons | It draws the console at its desktop layout and scales it down on tablets (0.65 to 0.75). The cue name is small, every widget reacts to a tap, and there is no current and next view. |
| QLC+ 5 for Android (beta, autumn 2026) | The full QLC+ on a tablet, paid, network plugins only; it can run as a client of the QLC+ on the laptop | It is a second operator console. The developer says the interface does not fit small screens yet, and reconnecting is still unstable in the beta. |
| OSC or MIDI tablet apps | Remote controls | They send commands and show nothing of what QLC+ plays. |
| Swiss Knife's *📱 Tablet page* in the Setlist (2.6.0) | One offline HTML file with the setlists in big type; songs are ticked by hand | It has no link to QLC+, so it cannot follow a pedal. It stays for shows with no network, and the two wiki pages point to each other. |

**What Phase 0 found** (the QLC+ 5.2.2 and 5.3.0 source, then QLC+ 5.3.0 built from its tag and run headless with `-w` in the sandbox; details in `docs/STAGE_MONITOR_PROTOCOL.md`). The web socket is `ws://<host>:9999/qlcplusWS`. `QLC+API|getWidgetStatus|<id>` answers `…|<id>|PLAY|<n>` or `…|<id>|STOP`, and an empty reply for an ID the show does not have. Every client gets `<id>|CUE|<n>` when the cue list moves, whoever moved it, and `<id>|CUE_STATE|<status>|<n>|<next>|…` when it starts, stops or pauses. Steps count from 0, and −1 means none. QLC+ does not check the Origin header, so a page from port 8080 can connect. Two findings changed the design:

- QLC+ 5 sends those pushes only after a web client has asked for `/vc.json`, which its own web page does. Without that request a pedal press sends no `CUE` message at all. The stage page asks for it on every connection and every minute (QLC+ sends no CORS header, so the page cannot read the answer, but the request is enough) and also asks every list's status every 2 seconds.
- `<id>|STEP|<n>` moves the selection but not what plays while the list runs: step 5 was shown while step 2 kept playing. Control mode therefore has *Previous* and *Next* and no jump to a step.

Measured in the sandbox: a `NEXT` reaches the page in 35 to 50 ms. When QLC+ quits the page shows it at once, and it is back 5 ms after QLC+ is, with pushes. A frozen QLC+ (socket open, no answers) shows as not connected after 7.6 s.

**As built**

- A screen *Stage Monitor* in group 4, *Run the show*. Swiss Knife is a web app now, so the spec's Tkinter tab became a screen. It reads the show in progress and never changes it, so it adds nothing to the History.
- The screen lists every CueList with its frame path, page, chaser, steps and bindings. You tick the lists, give labels and an order, hide or rename steps, and choose the text size, the colours, the next cue, the time, step numbers and the mode (read-only by default, or control).
- Colours: dark, high contrast, *Black, white song* and *Black, grey song*. In the two black ones the screen is black and only the current song is lit.
- *Export* writes a `stage_monitor/` folder, next to the show by default: `index.html`, one page with the cue names inside and nothing from the internet, and `serve_stage.py`, a standard-library server for the folder. An export replaces only files the Stage Monitor wrote (they carry a mark), so another `index.html` in that folder is refused.
- At run time the tablet talks to QLC+ directly and Swiss Knife does not relay. Swiss Knife can serve the folder (*Serve*, *Stop*), or `python3 serve_stage.py` does it without Swiss Knife. The screen shows the computer's addresses and the full address for the tablet.
- The settings are kept in `<show>.stage.json` next to the show, without the `_vN` suffix, so every version of the show shares them. Lists are matched by widget ID, and the screen names a list that disappeared and a new one not set up yet.
- If the status answers stop, the dot turns red and the current song greys out, then the page reconnects after 1 s, 2 s and every 5 s.
- Control mode: *Previous* and *Next* at the bottom act after a 600 ms press. With several lists the page has tabs and follows the list that just moved.
- The preview in Swiss Knife gets its own Content-Security-Policy, which lets it reach QLC+ on this computer and nothing else.
- Claude: a `stage_monitor` tool (list, settings, export) and a ready request, *A tablet page for the stage*. Claude may replace the Stage Monitor's own page and settings; everything else it writes is still a new file.
- Pictures: `tools/make_stage_shots.py`, run by `python3 tools/shots.py stage` and by `all`, takes `19-stage-monitor.png`, `20-stage-page.png`, `21-stage-page-black.png` and `stage-monitor.gif`. A stand-in answers the page's web socket, so no QLC+ is needed. The contact sheet keeps a portrait picture upright.

| Phase | What | State |
|---|---|---|
| 0 | Protocol from the QLC+ source and a live QLC+ 5.3.0; `docs/STAGE_MONITOR_PROTOCOL.md`; a probe page (`tools/stage_probe.html`) for the Mac | Done in the sandbox; the probe with the pedal on the Mac is still to do |
| 1 | Read-only page: list, configure, export, serve, reconnect, debug overlay (triple tap on the title), black colours, seven languages, wiki page *Stage Monitor* with Linux and Windows, Claude tool, pictures | Released in 3.5.0 |
| 2 | Control mode: *Previous* and *Next* with a 600 ms press; no jump (see above) | Released in 3.5.0, off by default |
| 3 (optional) | Chosen VC buttons (PANIC RESET) as big tiles; the Setlist screen's order; a QR code for the address if a small pure-Python encoder fits | Not started |

Left as it is: the binding names on the cards (*next*, *previous*) are in English.

**Checks only giopas can do**: the probe and the page against QLC+ 5.3.0 on the Mac with the MIDI pedal, the Mac's own Wi-Fi (Internet Sharing), a 10-inch Android tablet and an iPad in portrait, tablet Wi-Fi off and on, QLC+ quit and restarted, a two-hour soak, the two black colours under stage light. A cue list on a hidden page of a multipage frame should still report, because `/vc.json` covers every page; to confirm live.

### Tests only giopas can do

| Item | Why it is open |
|---|---|
| Claude Desktop with the Windows console program (`QLC Swiss Knife MCP.exe`) and the Windows launcher | The build smoke-tests it on a Windows runner, but nobody has used it from Claude Desktop on Windows. |
| Claude Desktop with the packaged macOS app | So far Claude has been connected to Swiss Knife run from the sources. |
| A live check against QLC+ 5.3.0 | The Docker image has 5.2.2. On 17 October `tests/test_qlc_live.py` passed in the sandbox against QLC+ 5.3.0 built from its tag and run headless (the Quick Start club and multi-universe shows). Opening the output in the Mac's QLC+ 5.3.0 is still to do. |
| Wording in the seven translations | Written with an AI assistant and checked against the screens, not by native reviewers. German, Spanish, Portuguese, Japanese and Chinese are new in 3.0.2. |
| A library file moved between two machines | Built and tested, never tried between two computers. |
| The SINCO MIDI patch and a real controller | The Inputs and MIDI tools are verified on show files and by tests, not with a controller connected. |
| The v2.4.0 live check on the Mac | Doctor fixes with a choice, opened in real QLC+. |

### QLC+ 5.3 alignment: plan items and releases

The alignment plan (`claude/STAGE_WIZARD_ALIGNMENT.md`) numbered its items 3.1 to 3.4 before any of them was released. Items 3.1 and 3.2 were built together and shipped as one release, 3.1.0, so from there the release numbers run one behind the plan:

| Plan item | What | Release |
|---|---|---|
| 3.1 | QLC+ 5.3 shows are safe in Swiss Knife (palettes read everywhere, layer scenes, Doctor D019 and D020) | 3.1.0, 14 October |
| 3.2 | Finish a QLC+ wizard show (Wizard Repair) | 3.1.0, 14 October |
| 3.3 | Upgrade a v5 show to QLC+ 5.3 | 3.2.0, 15 October |
| 3.4 | Align Swiss Knife's own generators with the wizard: the Look Builder | 3.3.0, 15 October |
| 3.4 | … and Quick Start (roles, capabilities from the definition, placement by role, the wizard's order) | next |

### Released in 3.4.1 (16 October)

Right after 3.4.0: the translations checked by running the app in every language, the pictures retaken, and two tools so that the next releases cost less.

| Change | Where |
|---|---|
| Translations reviewed by running the app in each language (every tool, the routes, Apply in Look Builder, Upgrade, Wizard Repair, Doctor): about 120 strings added per language, terms made consistent, one-word patterns no longer half-translate sentences, text rebuilt on a language change, the escape helper fixed for quotes | `static/i18n/*.json`, `static/js/i18n.js`, `static/js/show.js`, `static/js/doctor.js`, `tests/test_i18n_quality.py` |
| The route steps stay on one line in a narrow window and slide to the current one | `static/js/route.js`, `static/css/style.css` |
| README screenshots, route GIF and tutorial pictures retaken; the GIF script follows the 3.4.0 route | `screenshots/`, `tools/make_route_gif.py` |
| `tools/shots.py`: every picture in one command, what changed, a contact sheet; any screen in any language | `tools/shots.py` |
| `tools/release_notes.py`: the GitHub release is called `vX.Y.Z · Short title` and its text is the CHANGELOG section; the release workflow uses it | `tools/release_notes.py`, `.github/workflows/release.yml` |
| Tests | `tests/test_i18n_quality.py`, `tests/test_release_tools.py` |

### Released in 3.4.0 (16 October)

Not in the alignment plan: from the UX review of 15 October (`claude/UX_REVIEW_STEPS.md`, the Claude design canvas *Steps and routes UX review*). Inside a guided route there were two ways forward (*Done, next ›* at the top, the tool's *Next* at the bottom) and two step counters with the same look. giopas chose option C: the top shows where you are, the footer moves you on.

| Change | Where |
|---|---|
| The route strip shows progress only (step N of M, done, current, skipped), *Skip this step* and ✕; the current step opens into a second row with the tool's steps or the panel you are in; one shared stepper | `static/js/route.js`, `static/css/style.css`, `templates/index.html` |
| The footer's route button: *Go on: <step> ›* once the step is done, *<verb> and go on* at a tool's last step, *Finish the route*; the tool's own main button turns secondary next to it | `static/js/route.js` |
| Quick Start: steps reported to the route, *Save and go on* saves, opens the show and ticks the step; its own stepper outside a route | `static/js/quickstart.js` |
| Function Porter: steps reported to the route, its own stepper outside a route; *Bring functions* is an optional step | `static/js/porter.js` |
| Look Builder effect panel: *Cancel* and *Keep these settings* in the footer, the panel shown in the second row | `static/js/looks.js` |
| A step whose tool comes twice in the route is ticked where you are; the status line is cleared when the screen changes | `static/js/route.js`, `static/js/app.js` |
| Seven translations; tests that keep the pieces in place | `static/i18n/*.json`, `tests/test_route_steps.py` |
| Wiki: *Show in Progress* (guided routes), *Quick Start*, *Function Porter*, *Look Builder* | wiki |
| Check on the Mac: each of the five routes from start to end, Quick Start's *Save and go on*, Skip, leaving and coming back to a route, the narrow window | To do (giopas) |

### Released in 3.3.0 (15 October)

The Look Builder part of item 3.4 of the alignment plan. Mockup first (the Claude design canvas *Look Builder redesign*, plan in `claude/LOOK_BUILDER_PLAN.md`), then built.

| Change | Where |
|---|---|
| What a group can do (colour mixing, wheel, gobo, strobe, moves, dimmer, grid), the wizard's nine roles and a suggestion, static gobos, places on the stage, EFX in the wizard's form (5.2.2-safe) | `core/look_families.py` |
| New plan kinds: levels, strobes, gobos (gobo × colour), blinder, place on looks and chasers, efx, matrices on a group (Dimmer mode without colour mixing), folders per group, QLC+ palettes, buttons on a page per group. A 3.2.0 plan builds byte for byte as before | `core/look_builder.py` |
| The page-per-group console shared with Upgrade to QLC+ 5.3 (its output unchanged); the XY pad gets its own column | `core/vc_group_pages.py`, `core/upgrade53.py` |
| The screen: groups, families, Start from, will add (live check), effect panel with More, in seven languages | `static/js/looks.js`, `static/css/style.css`, `static/i18n/*.json` |
| Claude: `build_looks` and `looks_options` | `core/mcp_server.py`, `core/mcp_guide.py`, `routes/looks_routes.py` |
| 17 tests on the wizard's concert show and the Quick Start club show | `tests/test_look_families.py` |
| Fixed on the way: the options route stripped the namespace of the show in progress (the VC editor lost its pages); the fly out read the fixture rotation from the wrong place | Done |
| Check on the Mac: on a show with moving heads, Start from Concert, Add to the show, then in QLC+ 5.3.0 the Looks page (one page per group, gobo looks, strobe looks on a Sharpy or JDC1, circle on a look aimed at a musician, fly out and in); the same show in QLC+ 5.2.2 | To do (giopas) |

Decisions taken with it (15 October, giopas): the tool keeps its name; buttons on a page per group by default; gobo looks are one per gobo and colour; movement effects in 3.3.0. Roles are suggested and steer *Start from*, but are not stored in the show profile yet.

### Released in 3.2.0 (15 October)

Item 3.3 of the alignment plan, *Upgrade a v5 show to 5.3*. The source of QLC+ 5.2.2 and 5.3.0 (tags `QLC+_5.2.2` and `QLC+_5.3.0`) was compared first: an older show loads in 5.3 as it is (5.2.2 already runs the `Engine.*` script form), so the upgrade only adds. The XML keys new in 5.3 are `Locked`, the XY pad's `FloorControl`, `Group` and `FloorPosition`, `ControlBPM`, `Position3D` palettes and EFX `DimmerControl`.

| Change | Where |
|---|---|
| Upgrade to QLC+ 5.3: folders, palettes (the wizard's names and values, only those that work on the rig, colours the looks use), All Fixtures group, grids from the stage (off by default), Position3D palettes from the stage and musician models (5.3), a page per group with intensity slider, looks, effects, PANIC RESET and floor XY pads, hide, lock (5.3); target 5.3 or 5.2.2; a wizard show goes to Wizard Repair | `core/upgrade53.py` |
| Screen, route, guided route *Upgrade a show to QLC+ 5.3*, `upgrade_show` Claude tool and guide workflow | `routes/upgrade_routes.py`, `static/js/upgrade.js`, `core/mcp_server.py`, `core/mcp_guide.py` |
| Doctor I008: what QLC+ 5.2.2 ignores in a 5.3 show | `core/doctor/checks.py` |
| Translations in the seven languages | `static/i18n/*.json` |
| 21 tests on Festival, Pub and Quick Start shows (one with moving heads sharing a group with PARs) and on the wizard video show without its folders and frame (moving heads) | `tests/test_upgrade53.py` |
| Wiki: new page *Upgrade Older Shows*; I008 on *Workspace Doctor*; *Claude's tools* regenerated; the route on *Home* and *Show in Progress* | wiki, commit `7433d54` |
| Check of the branch (15 October): 915 tests pass on the Mac. On all nine shows in the test data, for both targets, the upgrade gives the same file twice, a second run adds nothing, no widgets overlap and the Doctor reports no new warning or error. Fixed on the way: a group page that mixes moving heads with other lights got no XY pad | Done |
| Check on the Mac: open an upgraded Festival or Pub show in QLC+ 5.3.0 (function tree folders, palettes in the palette panel, the Groups page, the frame's page selector) and in QLC+ 5.2.2; on a show with moving heads, the floor XY pads and the Position3D palettes | To do (giopas) |

Decisions taken with it (14 October): no position-only or colour-only scenes are generated (principle 5 stays; positions are palettes and XY pads). No BPM speed dial (it only drives functions set to follow the beat, and Swiss Knife's chasers run on time). The XY pads list fixtures, not groups, so they work in 5.2.2. Folder names are English, like the wizard's. Next: aligning Quick Start and the Look Builder with the wizard (roles, capabilities from the definition, grids from the stage, placement by role), item 3.4 of the alignment plan, to be released as 3.3.0.

### Released in 3.1.0 (14 October)

Started from the QLC+ 5.3.0 highlights video and two wizard shows giopas made on the Mac. The analysis is in the Claude project (`claude/STAGE_WIZARD_ALIGNMENT.md`). Items 3.1 and 3.2 of that plan were built together and released as one version, 3.1.0.

| Change | Where |
|---|---|
| Palettes read and resolved the way QLC+ does it (Dimmer, Color, Shutter, Pan/Tilt, Position3D, fanning); layer scenes; page-switch fixtures | `core/palettes.py` |
| Doctor: palette scenes not empty (D004, D018), layer scenes not D005 (I004), wizard functions not D016 (I005), built-in generic dimmer needs no .qxf, *default* capabilities safe for D006, new D019 (fixed by default), D020, I006, I007 | `core/doctor/` |
| Rig Reducer: group scenes, XY pads, grids closed up, the wizard page of a gone group, page dimmers always kept | `core/rig_reducer.py` |
| Porter: group scenes bring their group and palettes; XY pad groups mapped | `core/porter.py`, `core/porter_vc.py` |
| Compare, Dictionary drafts, Brightness, paperwork, Fixtures import | `core/compare.py`, `core/dictionary_draft.py`, `core/brightness.py`, `core/showbook.py`, `core/fixture.py` |
| Wizard Repair: lost chasers, palettes that do nothing, PANIC RESET per page, buttons, grids, hide, lock, captions; screen, route, `wizard_repair` Claude tool | `core/wizard_repair.py`, `routes/wizard_routes.py`, `static/js/wizard.js` |
| Translations of the new strings in the seven languages | `static/i18n/*.json` |
| Two scrubbed wizard shows and their definitions; 22 tests | `tests/corpus/Wizard530_*.qxw`, `tests/fixtures/wizard530/`, `tests/test_wizard530.py` |
| Wiki: new page *Wizard Repair*; *Workspace Doctor* codes; *Claude's tools* regenerated; the wizard route on *Home* and *Show in Progress* | wiki, commit `3159647` |
| Second check of the branch (14 October): 894 tests pass. On both shows the repair gives the same file twice, a second run changes nothing, no widgets overlap on any page, the Doctor finds no errors. Left on purpose: D020 on fixtures with no dimmer or shutter channel (nothing to fill), and D007 where the wizard's gobo cycle uses the gobo buttons' scenes (the Doctor's D007 fix handles it) | Done |
| Check on the Mac: open both repaired shows in QLC+ 5.3.0 (buttons, chasers, PANIC RESET, matrices on the new grids, the strobe buttons on the Sharpys); open a wizard show in QLC+ 5.2.2 | Done: working, giopas, 15 October |

Decisions taken with it (14 October): Swiss Knife's own output keeps declaring every channel (principle 5); the Doctor accepts layer scenes made by others. Supported range: QLC+ 5.2.2 to 5.3.x; QLC+ 4 is not a target. Next: *Upgrade a v5 show to 5.3* (released as 3.2.0) and aligning Quick Start with the wizard (to be released as 3.3.0) (roles, capabilities from the definition, grids from the stage, placement by role).

Open question for giopas: report the `makeChaserFromScenes` bug upstream (one missing line in `stagewizard_functions.cpp`), although upstream reports were dropped.

### Decisions taken

| Decision | Date |
|---|---|
| No code signing or notarisation of the apps. Users keep seeing the unsigned-app warning, which the README and wiki explain. | 8 Oct |
| No Linux AppImage unless someone asks. The `.tar.gz` stays. | 8 Oct |
| The update on macOS is tested and works (several runs). | 8 Oct |
| Forum: no post per release. A post for 2.0 and one for 3.0. | 1 Oct, 8 Oct |
| Only Claude is connected. The Gemini app, Gems and other assistants that run on their makers' servers cannot start a local program, and putting Swiss Knife online is not planned. Gemini CLI may work with `--mcp` but is untested and unsupported. The wiki page *Connect Claude to Swiss Knife* explains why (wiki only, no release). | 10 Oct |
| Claude may replace one kind of file: the Stage Monitor's own page and server (they carry a mark) and its settings file `<show>.stage.json`. Every other file it writes is new. | 17 Oct |

### Released in 3.0.3

Found on 9 October by giopas on the Mac, in Japanese: English left in the menu and on the Start page.

| Change | Where |
|---|---|
| Tool names translated in all seven languages, also inside sentences; wiki links keep the English page name | `static/i18n/*.json` |
| A numbered label uses its exact translation before any pattern (fixes *ファンクション Porter* and *3. Bring funzioni*) | `static/js/i18n.js` |
| Textarea placeholders translated; the language box tooltip follows the language | `static/js/i18n.js` |
| Palette colours translated through `data-i18n-ctx="colour"`; group names in the Look Builder never translated | `static/js/looks.js`, `static/js/i18n.js` |
| About 90 strings that were English everywhere (Console, Doctor titles, D012, patterns, presets, positions, CueList actions, type filters) | `static/i18n/*.json` |
| A crawl of every screen with a show open, in English, Japanese, Italian and Chinese, left only show data, brand and file names in English | Done |
| Check on the Mac in each language | To do (giopas) |

### Released in 3.0.2

Written on 8 October while giopas was away from the laptop; the local folder is aligned when it is back.

| Change | Where |
|---|---|
| German, Spanish, Portuguese (European spelling), Japanese and Simplified Chinese, about 2,970 strings each | `static/i18n/de.json`, `es.json`, `pt.json`, `ja.json`, `zh.json` |
| The language box, ⌘K entries and the i18n tests know the eight languages | `templates/index.html`, `static/js/i18n.js`, `static/js/palette.js`, `tests/test_i18n.py` |
| Five strings that had no translation anywhere (*Connect to Claude* in the menu, *Auto-Map*, *Patch…*, *Stop*, *Strobe / flash*) | all seven language files |
| A real venue name removed from the `guide` example and from this plan | `core/mcp_guide.py`, wiki *Claude's tools* |
| Wiki *Language* and *Home* list the eight languages | wiki |
| Screens checked in German and Japanese at 1440 × 900 | Done |
| Check on the Mac in each new language | To do (giopas) |

### Released in 3.0.1

Found on 8 October while Claude described a real show (the show stays out of the repository).

| Change | Where |
|---|---|
| Cue notes name the button that plays the same look, or what the cue plays; Swiss Knife's own notes are refreshed on open and before saving | `core/workspace.py`, `routes/show_routes.py` |
| Setlist: *Load setlist…* and *Save setlist…*; the function list button is filled; an edge tab and wider columns while the list is closed | Setlist screen, IT and FR strings |
| Dictionary: *Draft descriptions*, *Save as new file*, *Load dictionary…*, and *Ask Claude…*, a window with the request for Claude Desktop | `core/dictionary_draft.py`, `core/scene_words.py`, `static/js/dictionary.js` |
| Claude: `guide` tool, guide resources, four ready requests, `draft_missing`, `list_shows` paging, `edit_vc` arguments in its schema | `core/mcp_guide.py`, `core/mcp_server.py`, `core/mcpb.py` |
| Wiki page *Claude's tools* written from `core/mcp_guide.py` by `tools/make_claude_tools_wiki.py`; a test fails when they differ | `wiki/Claude-Tools.md` |
| Tooltips drawn in a layer that fits the window | `static/js/tooltip.js` |
| Doctor: D016 counts the original of a setlist copy as used; D012 names the widgets | `core/doctor/checks.py` |
| Claude test on the real show: a *3. SONGS* page with 15 song buttons built through `edit_vc`, saved as v18 | Done |
| Check on the Mac: the Ask Claude window, a dictionary written by Claude, the cue notes in QLC+ | To do (giopas) |

## 3. Release history

Dates are the CHANGELOG dates. Details of each release are in [CHANGELOG.md](CHANGELOG.md) and `docs/release-notes/`.

### Foundation (1.x)

| Version | Date | What it did |
|---|---|---|
| 1.3.2 | 23 Sep | Cleaned the bench: one safe QXW writer, Trigger Manager never overwrites, tilt defaults, tests consolidated, CI. |
| 1.4.0 | 27 Sep | Quick Start, Function Porter and Show Book out of Alpha; the Workspace Doctor; tests on real show files. |
| 1.4.1 | 29 Sep | Fixes from the first real-show test of the Porter. |
| 1.5.0 | 29 Sep | The Doctor fixes what it finds; the Rig Reducer. |
| 1.6.0 | 29 Sep | Looks and chasers built from a palette and a pattern. |
| 1.7.0 | 29 Sep | The VC Visual Editor builds the Virtual Console. |
| 1.8.0 | 29 Sep | Meshes on the 3D stage. |
| 1.9.0 | 1 Oct | The show in progress for every tool, Show Paperwork, guided routes, one screen pattern. |
| 1.10.0 | 1 Oct | Grow a rig: copied fixtures join the show's own looks. |

### The Pub test and after (2.0 to 2.2)

| Version | Date | What it did |
|---|---|---|
| 2.0.0 | 1 Oct | The Pub test passed in 12 minutes with the Doctor at 0 errors; fixture groups; Compare; the recipe. |
| 2.0.1 | 3 Oct | Patch sheet with DIP switches, cue notes in the setlist, the setlist CueList in one click. |
| 2.1.0 | 3 Oct | Show Profiles: do it again on another show. |
| 2.2.0 | 4 Oct | UI polish after an outside review. |
| 2.2.1 | 5 Oct | The rest of the polish, and the white-window fix. |

### Themed releases (2.3 to 2.7)

| Version | Date | Theme |
|---|---|---|
| 2.3.0 | 5 Oct | The new-show flow. |
| 2.4.0 | 5 Oct | Doctor and Quick Start. |
| 2.5.0 | 5 Oct | Looks and Stage. |
| 2.6.0 | 6 Oct | Paperwork, setlists, MIDI. |
| 2.7.0 | 6 Oct | Language and sharing (three languages, the Library). |

### Packages (2.8)

| Version | Date | What it did |
|---|---|---|
| 2.8.0 | 6 Oct | Packages for three systems, the update check, *Update and restart*. |
| 2.8.1 | 6 Oct | A logo. |
| 2.8.2 | 6 Oct | The update check fixed after the first live try. |
| 2.8.3 | 6 Oct | QLC+ 5.3.0 compatibility (script commands). |
| 2.8.4 | 6 Oct | *Update and restart* works on macOS (`.tar.gz`). |
| 2.8.5 | 7 Oct | All screenshots retaken, sidebar fix, GitHub Actions updated. |
| 2.8.6 | 7 Oct | Windows: the app starts, and there is an installer. |

### Claude (2.9) and the milestone

| Version | Date | What it did |
|---|---|---|
| 2.9.0 | 8 Oct | Swiss Knife as an MCP server; one-click connection for Claude Desktop; Dictionary descriptions by Claude. |
| 2.9.1 | 8 Oct | The *Connect to Claude* card shows whether Claude is connected. |
| 2.9.2 | 8 Oct | The menu item reads *MCP connected to Claude* when it is. |
| 3.0.0 | 8 Oct | Milestone release. Documentation rewritten, work plan reorganised. |
| 3.0.1 | 8 Oct | Dictionary drafts and *Ask Claude…*; cue notes name the button; Claude's `guide`, ready requests and the *Claude's tools* wiki page; tooltips that fit the window; D016 and D012 fixes. |
| 3.0.2 | 8 Oct | German, Spanish, Portuguese, Japanese and Chinese. |
| 3.0.3 | 9 Oct | Tool names translated; the gaps of the new languages filled. |
| 3.1.0 | 14 Oct | QLC+ 5.3 Show Wizard shows: palettes read everywhere, Doctor D019 and D020, Wizard Repair. |
| 3.2.0 | 15 Oct | Upgrade to QLC+ 5.3 for older shows; Doctor I008. |
| 3.3.0 | 15 Oct | The Look & Chaser Builder in the wizard's families: gobo, strobe and level looks, places, movement effects, a page per group. |
| 3.4.0 | 16 Oct | One way forward in the guided routes: the top shows where you are, the footer moves you on. |
| 3.4.1 | 16 Oct | The seven languages checked screen by screen; `tools/shots.py` and `tools/release_notes.py`. |
| 3.5.0 | 17 Oct | Stage Monitor: the current cue live on a tablet on stage, black colours for a dark stage, a Claude tool, its pictures in `shots.py`. |

## 4. Goal and the Pub test

The goal is to build the next show file with the tool, and not by asking an AI to patch XML. The tool must reduce or adapt a rig, port looks and effects, generate looks and chasers, lay out the Virtual Console, place fixtures and meshes in 3D and validate everything before export. The result has to be deterministic (the same input gives a byte-identical output), accurate (QLC+ opens it cleanly and it behaves on stage) and useful to other QLC+ users (conventions are configurable and nothing is hard-coded to one band's habits).

The acceptance benchmark was the **Pub test**: rebuild the 6-fixture pub show from the 14-fixture festival show using only Swiss Knife. It passed in 2.0.0. The run took 12 minutes, the Doctor reported 0 errors, the show was opened and played in QLC+, a comparison with the hand-made show found the same patch, groups, looks, chasers, pages and setlist, and a replay from the recipe gave the same file byte for byte.

## 5. Principles

These apply to every change.

1. **Never overwrite.** Every write produces a new file: `<name>_v<N+1>.qxw`. The original is never touched.
2. **One writer.** All `.qxw` output goes through `core/qxw_io.write_qxw()`, which keeps the XML declaration and the `<!DOCTYPE Workspace>`. A load, write, load round trip must lose nothing.
3. **Deterministic IDs and ordering.** New IDs are `max(existing) + 1` in a stable order. Generated XML has no timestamps or random values. Golden-file tests compare output byte for byte.
4. **The Doctor gates every export.** Quick Start, Porter, Rig Reducer, Look Builder and VC Builder run it before writing. Errors block the export and warnings go into the report.
5. **Safe show content by default.** Generated scenes declare every channel of every fixture they touch, keep strobe and internal-program channels at 0 unless asked, and always include a PANIC RESET. A VC button and a chaser step never share a scene.
6. **QLC+ is the reference.** Every generator has a manual open-check (section 8) before release.
7. **Conventions are data.** Naming, palettes, VC screen size and templates live in JSON profiles that users can share.
8. **Tests and CI are green before a merge.** Nothing merges without tests.

## 6. Standing decisions

The complete decision log, with the reasons, is in section 3 of the archive. These are the ones that still shape the code.

| Topic | Decision |
|---|---|
| Saving | Every tool that writes a `.qxw` saves a new `_v<N+1>` file. Fixed names such as `_GIG_READY` or `_merged` are gone. |
| Fixture tilt | QLC+ 3D convention: 0 is straight down, 90 horizontal, 180 straight up. Truss fixtures 45 degrees toward the stage, floor fixtures 45 degrees up toward the performers, mid-height horizontal. Confirmed in the QLC+ 5 3D view. |
| Doctor severities | D001 to D003 are errors. D004 to D009, D012 and D016 are warnings. D015 and the I-codes are information. |
| PANIC RESET | A script, not a scene. It stops every generated function, starts a neutral-state scene, waits 100 ms and stops itself. A scene cannot pull down HTP channels, and QLC+ 5.2.2 drops queued script commands if the script ends first. |
| Quick Start VC | One page. Looks and effects share one solo frame, and each fixture group has its own solo frame and a submaster. RGB matrices run through a collection that opens the master dimmers. |
| Generated XML | Indented like QLC+'s own files, because QLC+ 5.2.2 misreads a one-line file after an empty `<Level/>`. Fixture definitions QLC+ lacks are saved next to the workspace as `.qxf`. |
| Porter | Fan-in takes, per scene, the values of the first lit source of a block. Unmapped source fixtures are an error unless you tick *leave out*. Functions left with no fixture are removed and reported. VC copies drop key and MIDI bindings unless you opt in. |
| Test data | Real shows in the repository are renamed and scrubbed. The public repository carries no real names. Commits since 1 October use the author *giopas*. |
| Behaviour | Verified in real QLC+, not only by reading XML (`tools/qlc_check.py`). Targets are QLC+ 5.2.2 to 5.3.x; QLC+ 4 is not a target. |
| Layer scenes | Swiss Knife's generators declare every channel (principle 5). Scenes from others that set one family of channels on purpose, or palette scenes, are accepted (I004) and never filled in. |
| README | A presentation only. The history lives in the CHANGELOG. |
| Forum | One complete post at 2.0, one at 3.0. No post per release. Drafts stay out of the repository. |
| Claude | Full tool set, writes only to new files (except the Stage Monitor's own page and settings), only the folders giopas lists, nothing else on the computer. Connection by one `.mcpb` file for Claude Desktop. |
| Signing | The apps are not signed or notarised. No AppImage unless someone asks. |

## 7. How we work

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

### Before a release

- Run the two `--missing` commands once more.
- Bump `VERSION` in `core/workspace.py` (it must match the CHANGELOG), the installer version, the README title and the spec comment.
- Move `[Unreleased]` to `[X.Y.Z] — date — Short title`: two to four words that say what the release is for (*One way forward*, *Upgrade to QLC+ 5.3*). The GitHub release is called `vX.Y.Z · Short title` and its text is that section of the CHANGELOG; `python3 tools/release_notes.py vX.Y.Z` shows both before the push.
- README stays a presentation. Retake the pictures with `python3 tools/shots.py all`: it starts the app, retakes the README screenshots, the route GIF and the tutorial pictures, says which ones changed and writes `contact.png`, every picture small, to look at in one go. `--dry` leaves the repo alone, `--only 07` keeps one picture, and `python3 tools/shots.py state <name> "<js>" … --lang it` takes any other screen. Quit Swiss Knife first (the tool needs its port, 5731).
- A wiki page for each new or changed tool. When a Claude tool changed, run `python tools/make_claude_tools_wiki.py` (the tests fail until the page matches).
- Release notes in `docs/release-notes/RELEASE_NOTES_vX.Y.Z.md`.

### Merge and release, always this way

Do not push the feature branch, because that starts a third run of the tests for the same commit. Merge locally, tag, push `main` and the tag together, then the wiki:

```
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script && git status --short
git checkout main && git merge --ff-only feat/vX.Y.Z && git tag vX.Y.Z && git push origin main vX.Y.Z && (cd wiki && git push origin master)
```

`git status --short` must print nothing first. For a change that is not a release, leave out the `git tag` part.

Pushing runs `tests` once on `main` (version tags and documentation-only changes are ignored), `qlc-live-check` once (advisory) and `release` once on the tag (tests, build, installer test on macOS twice, Windows and Linux). When `release` finishes the release is there with its title (`vX.Y.Z · Short title`) and text (the CHANGELOG section), both from `tools/release_notes.py`, and the files attached. Check it is marked *Latest* and keeps only the `…-X.Y.Z-…` files plus `SHA256SUMS`. Then try *Update and restart* from the previous version.

The assets are: macOS arm64 and Intel (`.tar.gz` for the updater and `.dmg` for a first install), Windows (`-setup.exe` and `.zip`), Linux (`.tar.gz`) and the Claude Desktop connection file (`-claude.mcpb`).

If a change is risky, push `main` first, wait for `tests` to pass, then push the tag.

### Keeping this file in step

This file lives in the repository and in the Claude project (`claude/WORKPLAN.md`). After a change, copy the repository file to the project.

## 8. QLC+ open-check before a release

1. Open the output in QLC+ 5. The log shows no warnings, every function is listed and the VC shows the expected page.
2. In the Fixture Manager the addresses match and nothing overlaps.
3. In the 3D monitor, fixtures and meshes sit where you expect and are tilted as expected.
4. Run PANIC RESET, a scene, a chaser and the CueList with DMX output on. PANIC RESET and VC loading are automated: `python3 tools/qlc_check.py file.qxw` (see `docs/qlc-live-check.md`).
5. Save from QLC+ and run the Doctor on the saved file. It must still be clean, which shows QLC+ did not have to repair anything.

## 9. Not built, and ideas

These were left out on purpose or have no date.

| Item | Note |
|---|---|
| Separate `build_chaser` and `describe_show` tools for Claude | Chasers are part of `build_looks` and the summary is `show_summary`. |
| Doctor: renumbering of fixtures and groups (D002), CueList, matrix and bound-scene repairs beyond what exists, D012 | D012 belongs to a future MIDI manager. |
| Moving-head position beyond what Look Builder sets | Pan and tilt are centred in looks unless you set a position. |
| VC Editor: resizing by dragging handles, widget types beyond the six (knob, XY pad, speed dial, clock), templates with key or MIDI bindings | |
| Porter: an option to replace all of a widget's bindings when a ported widget takes over | |
| Fan-in ordering by Left, Right, Front and Back words in fixture names | |
| Quick Start rig in memory as the Porter target | Only if the save-first hand-off feels clumsy. |
| Rig Editor with rename, add and wiring | Wiring lives in the Porter. |
| MIDI learn simulation | The simulator tells you what a message would trigger. |
| Quick Start writes `4.13.1` as the QLC+ version in a new show | QLC+ never reads it (checked in the 5.3.0 source), so it does no harm, but *5.2.2* would be truthful. Changing it changes the golden files. |
| Folder names in the user's language or naming profile | The upgrade writes English names, like the Show Wizard. |
| Dropped | The audio-trigger helper, and the upstream bug reports to QLC+. |
