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

**Version 3.0.2, 8 October 2026.** Every phase of the plan is built and released. Swiss Knife opens a QLC+ 5 workspace once, lets any tool change it as the show in progress, checks it with the Workspace Doctor and saves it as a new file with a report and a recipe.

| Area | State |
|---|---|
| Tools | Quick Start, Fixtures, Rig Reducer, Function Porter, Brightness, Look Builder, VC Visual Editor, Stage and Meshes, Library, Setlist, Trigger Manager, Dictionary, Workspace Doctor, Compare, ID Browser, Show Paperwork. |
| Reuse | The recipe replays a session to the same file. Show Profiles apply the same changes to another show. |
| Install | Packages for macOS (Apple silicon and Intel), Windows (installer and zip) and Linux. An update check with *Update and restart*, tested on macOS several times. |
| Language | English, Italian, French, German, Spanish, Portuguese, Japanese and Chinese. |
| Claude | Swiss Knife is an MCP server with 24 tools, among them `guide`, which explains the others. It also offers four ready requests (MCP prompts) and the guide as resources. Claude Desktop connects with one file (`.mcpb`), Claude Code with one command. Claude gets only the folders you list and Swiss Knife itself, and it writes only new files. The *Connect to Claude* card and the menu item show whether the connection exists. |
| Tests | 849 automated tests pass. A live check against a real QLC+ 5.2.2 runs in CI (advisory). |
| Documentation | README, wiki (31 pages, *Claude's tools* written from the code), CHANGELOG, one set of release notes per version. |

Release 3.0.0 was the milestone: installing, updating, three languages and the Claude connection all in place, with the documentation rewritten to match. Release 3.0.1 follows a test on a real show with Claude: the Dictionary drafts descriptions itself and can hand the job to Claude, cue notes name the button, and Claude's tools are documented where Claude reads them. Release 3.0.2 adds German, Spanish, Portuguese, Japanese and Chinese.

## 2. What is left

Nothing in the programme is open. What remains is testing on real systems and a few decisions.

### Tests only giopas can do

| Item | Why it is open |
|---|---|
| Claude Desktop with the Windows console program (`QLC Swiss Knife MCP.exe`) and the Windows launcher | The build smoke-tests it on a Windows runner, but nobody has used it from Claude Desktop on Windows. |
| Claude Desktop with the packaged macOS app | So far Claude has been connected to Swiss Knife run from the sources. |
| A live check against QLC+ 5.3.0 | The Docker image has 5.2.2. Opening the output in a real QLC+ 5.3.0 is still to do. |
| Wording in the seven translations | Written with an AI assistant and checked against the screens, not by native reviewers. German, Spanish, Portuguese, Japanese and Chinese are new in 3.0.2. |
| A library file moved between two machines | Built and tested, never tried between two computers. |
| The SINCO MIDI patch and a real controller | The Inputs and MIDI tools are verified on show files and by tests, not with a controller connected. |
| The v2.4.0 live check on the Mac | Doctor fixes with a choice, opened in real QLC+. |

### Decisions taken

| Decision | Date |
|---|---|
| No code signing or notarisation of the apps. Users keep seeing the unsigned-app warning, which the README and wiki explain. | 8 Oct |
| No Linux AppImage unless someone asks. The `.tar.gz` stays. | 8 Oct |
| The update on macOS is tested and works (several runs). | 8 Oct |
| Forum: no post per release. A post for 2.0 and one for 3.0. | 1 Oct, 8 Oct |

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
| Behaviour | Verified in real QLC+, not only by reading XML (`tools/qlc_check.py`). Targets are QLC+ 5.2.2 and 5.3.0. |
| README | A presentation only. The history lives in the CHANGELOG. |
| Forum | One complete post at 2.0, one at 3.0. No post per release. Drafts stay out of the repository. |
| Claude | Full tool set, writes only to new files, only the folders giopas lists, nothing else on the computer. Connection by one `.mcpb` file for Claude Desktop. |
| Signing | The apps are not signed or notarised. No AppImage unless someone asks. |

## 7. How we work

### Branches and commits

One branch per release, named `feat/vX.Y.Z` (or `fix/...` for a small change). Commits follow Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`), small and focused. The sandbox Claude works in cannot reach GitHub, so Claude commits locally and giopas pushes.

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
- Move `[Unreleased]` to `[X.Y.Z] date`.
- README stays a presentation; retake screenshots where a screen changed.
- A wiki page for each new or changed tool. When a Claude tool changed, run `python tools/make_claude_tools_wiki.py` (the tests fail until the page matches).
- Release notes in `docs/release-notes/RELEASE_NOTES_vX.Y.Z.md`.

### Merge and release, always this way

Do not push the feature branch, because that starts a third run of the tests for the same commit. Merge locally, tag, push `main` and the tag together, then the wiki:

```
cd ~/Documents/QLC+/qlc-plus-swiss-knife-tool-script && git status --short
git checkout main && git merge --ff-only feat/vX.Y.Z && git tag vX.Y.Z && git push origin main vX.Y.Z && (cd wiki && git push origin master)
```

`git status --short` must print nothing first. For a change that is not a release, leave out the `git tag` part.

Pushing runs `tests` once on `main` (version tags and documentation-only changes are ignored), `qlc-live-check` once (advisory) and `release` once on the tag (tests, build, installer test on macOS twice, Windows and Linux). When `release` finishes there is a draft release. Edit it: title `QLC+ Swiss Knife vX.Y.Z`, notes from the release-notes file, mark it *Latest*, keep only the `…-X.Y.Z-…` files plus `SHA256SUMS`, then publish. Then try *Update and restart* from the previous version.

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
| Dropped | The audio-trigger helper, and the upstream bug reports to QLC+. |
