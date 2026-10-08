# Changelog

All notable changes to QLC+ Swiss Knife are documented here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) conventions.

---

## [Unreleased]


## [3.0.3] — 2026-10-09

The gaps found on the first look at 3.0.2 in Japanese, filled in every language.

### Changed
- The tool names are translated in all seven languages, Italian and French included: in the menu, on the screens and in the sentences that mention them (*クイックスタート*, *Riduttore di rig*, *Look-Baukasten*, *Documentation de la show*…). Links to a wiki page keep its English name, because the wiki is in English.
- The Look Builder shows the palette colours in your language. A colour word is looked up under its own context (`colour|Red`), so a function called *Red* elsewhere keeps its name. The fixture group names in the Look Builder are no longer translated (a group called *Floor* showed as *Boden* in German).

### Fixed
- The menu read *ファンクション Porter*: a loose pattern (`Function {0}`) translated half of *Function Porter*. Every tool name now has its own entry, and a numbered label such as *3. Bring functions* uses its exact translation before any pattern.
- Strings that stayed English in every language now have a translation: *Console* in the guided routes, the Doctor titles D004, D006, D015 and D016, the D012 message added in 3.0.1, *Apply will fix*, the Look Builder patterns, positions and chaser presets, *New group*, *floats … mm*, the CueList actions (Next, Previous, Stop), the function type filters, *My Show*, the MIDI message types and a few update messages.
- Placeholders of text boxes (the setlist paste box, the description box, the label panel) were never translated. They are now.
- The language box's own tooltip follows the language.


## [3.0.2] — 2026-10-08

Five more languages for the interface.

### Added
- The interface speaks German, Spanish, Portuguese, Japanese and Chinese, next to English, Italian and French. Pick the language at the bottom of the left menu or with ⌘K / Ctrl+K and *Language*. Each file in `static/i18n/` holds about 2,970 lines, the same strings as Italian and French. Portuguese follows the European spelling and Chinese is Simplified.
- Strings that had no translation in any language now have one: the *🔌 Connect to Claude* menu item, *🔄 Auto-Map* in the Function Porter, *Patch…* in Inputs & MIDI, *■ Stop* in the Look Builder preview and *Strobe / flash* in Quick Start.

### Changed
- The example in Claude's `guide` for `list_shows` searches for "Festival" instead of the name of a real venue. The wiki page *Claude's tools* follows.


## [3.0.1] — 2026-10-08

Found while describing a real show with Claude: the Dictionary gets a draft of its own and a way to ask Claude, the cue notes name the button, and Claude's tools are documented where Claude can read them.

### Added
- Dictionary: **✨ Draft descriptions** gives every function without a description a first one drawn from the show. A scene says which colours it shows and where, a chaser says how it changes (through which colours, moving across the fixtures, or only brighter and dimmer), a collection or script says what it starts, and a helper scene says which step of what it is. Colours come from the fixture definitions. Your own descriptions are kept.
- Dictionary: **💾 Save as new file** writes `<show>_dictionary.txt` next to the show, or `_v2`, `_v3` when the name is taken. *Save dictionary* with no dictionary loaded does the same.
- Dictionary: **🤖 Ask Claude…** appears when Claude is connected. It opens a window like *Connect to Claude* with a ready request for Claude Desktop: you choose what Claude writes (its own words for the functions with a button and a draft for the rest, only the empty ones, or everything) and whether it shows you the lines before saving, then copy it. Swiss Knife cannot start Claude itself, because the connection runs from Claude Desktop to Swiss Knife.
- Claude's `guide` tool explains any other tool: arguments, answer, an example, and the usual sequences of tools for a job. The same text is offered as MCP resources (`swissknife://guide`) and is the wiki page *Claude's tools*, written from the code by `tools/make_claude_tools_wiki.py`; a test keeps the two equal.
- Ready requests (MCP prompts) for Claude Desktop: write the Dictionary, check and fix a show, adapt a show to fewer fixtures, add buttons for looks that have none. The Claude Desktop file lists them too.
- `dictionary_set` takes `draft_missing`, so Claude writes the lines that matter and lets the app's draft cover the rest. `list_shows` takes `query`, `limit` and `offset`.

### Changed
- A setlist cue note names the button that plays the same look, for example `↪ [5225] button: XM · TMO Drive`, or says what the cue plays when no button does: `↪ [5220] no button · plays SONG: 1979 Haze Drift`. The cue list already shows the cue's name, so the note no longer repeats it.
- Swiss Knife's own cue notes (they start with ↪) are rewritten when they no longer match the show, for instance after the functions were renumbered. This happens when a show opens, and before *Save as new file…* when the show changed, so a button added in the meantime is named. Notes typed in QLC+ are never touched.
- Setlist: *Load Slot File* and *Save Slot File* are now **Load setlist…** and **Save setlist…**. The function list button is filled and reads *Show QLC+ functions ▸* or *Hide QLC+ functions ◂*; while the list is closed, a tab on the right edge opens it and the song list takes the free room.
- Dictionary: *Browse TXT* is now **Load dictionary…**.
- Tooltips are drawn above everything and placed inside the window, so they are no longer cut off at the top of the window or by narrow columns.
- The facts Claude reads for the Dictionary include the colours of each scene and chaser, every step a helper fills, and what a setlist cue runs, so Claude no longer writes "unclear" for unnamed scenes.
- `edit_vc` lists every operation and the arguments of `create` in its description and schema.
- Doctor D012 names the widgets bound to the unpatched universe and says the warning is fine when the controller is only plugged in at the venue.

### Fixed
- Doctor D016 reported the originals of setlist copies as unused (34 warnings on a rebuilt setlist). Deleting them would have broken the cue notes; they now count as used.
- `dictionary_context` pages stop before a reply would be cut, so Claude always gets whole pages.
- `list_shows` no longer comes back cut off when the shared folders hold many shows.
- The test of the Claude Desktop launcher failed on a computer where Swiss Knife is installed in Applications, because the launcher found the app there. That last check is now skipped on such a computer.


## [3.0.0] — 2026-10-08

**Swiss Knife 3.0: install it like an app, use it in three languages, and let Claude help.**

The version number marks that the plan is complete, and the documentation was rewritten to match. One small fix came with it.

### Fixed
- Claude's `list_shows` said "no shows" when a shared folder could not be read, for example when macOS denies a program access to the Documents folder. It now names the folders it could not read or that do not exist, and says where to allow access on a Mac.

### Changed
- README and wiki say that Swiss Knife is tested with QLC+ 5.x (5.2.2 and 5.3.0).
- After *Update and restart*, quit and reopen Claude Desktop so it starts the new Swiss Knife (the wiki says so in *Connect Claude to Swiss Knife* and *Troubleshooting*).
- README rewritten: a short section on Claude (what Claude can reach: only the folders you list and Swiss Knife itself), the Claude Desktop file in the install table, and every tool described up to date.
- Wiki: every page reworded in plain language, with the features of 2.0.1 to 2.9 added where they were missing (Porter meshes and script commands, setlist import and tablet page, Doctor fixes with a choice, Look Builder beats and pixel bars, Stage aiming, Claude sections, new Troubleshooting rows). Home rebuilt around "Start here".
- WORKPLAN reorganised into a short current plan with a release history. The full log of 23 September to 8 October moved to `docs/WORKPLAN_ARCHIVE.md`.
- ROADMAP brought up to date.


## [2.9.2] — 2026-10-08

**The menu says when Claude is connected.**

### Changed
- The menu item reads *🔌 MCP connected to Claude* (in the accent colour) when Claude Desktop already has Swiss Knife, and *🔌 Connect to Claude* otherwise. It checks once when the app starts, and again when you open the card.


## [2.9.1] — 2026-10-08

**The Connect to Claude card shows whether Claude is already connected.**

### Added
- *Connect to Claude* now says whether Claude Desktop already has Swiss Knife. It looks for the extension, the settings entry and the launcher log, and shows when Claude last started Swiss Knife. A *Check again* button reads it anew, and the setup button becomes *Reinstall the connection* once connected.


## [2.9.0] — 2026-10-08

**Claude can use Swiss Knife's tools.**

### Added
- An MCP server (`QLC Swiss Knife --mcp`, or `python -m core.mcp_server`) with 23 tools over stdio: open a show, summary, Doctor check and fix, rig fixtures and reduce (with a preview), porter source and port, looks options and build, VC pages and edit, setlist, compare, history, undo, redo and `save_show`. It adds no dependency.
- Limited access. Through this connection Claude gets the folders you list and the Swiss Knife tools, and nothing else on your computer. It cannot browse the disk, run commands, open other programs or use the network. A path outside the listed folders is refused, including `../` and links that lead out.
- Writing creates new files only: the show (`_v2`, `_v3` and so on), its report, its recipe and a dictionary `.txt`. An existing file is never overwritten or deleted. Every change is a History step, so it can be undone, and the Doctor refuses a result with new errors. Claude receives names, counts and findings, never the raw XML.
- One-click connection for Claude Desktop. *🔌 Connect to Claude › ⬇ Connect Claude Desktop*, or the `QLC-Swiss-Knife-<version>-claude.mcpb` file attached to each release, opens Claude Desktop's install window, which asks which folders to share. The file holds a small launcher and no Swiss Knife code. Swiss Knife writes `~/.qlc_swiss_knife/mcp-launch.json` at every start, so the launcher finds it after a move or an update. The launcher logs to `~/.qlc_swiss_knife/mcp-launcher.log`. Checked with the official `mcpb validate`, and installed in Claude Desktop on macOS.
- Dictionary descriptions by Claude. `dictionary_context` gives each function's type, VC button, users and contents (chaser steps, what a script starts and stops, matrix patterns, scene levels). `dictionary_set` stores the descriptions, `dictionary_load` and `dictionary_save` read and write the Dictionary `.txt` as a new file. `skip_steps` leaves out helper steps and `auto_steps` names them ("Step 3 of Color Fade"). The dictionary is not part of the show.
- Tool annotations tell Claude Desktop which tools only read and which change the show, so you can allow the reading group once and keep approving the two that write to disk.
- The server answers Claude's first message at once and loads the rest on the first tool call.
- *🔌 Connect to Claude* in the menu: add or remove the shared folders, copy the snippet for Claude Desktop's settings file or the one-line command for Claude Code.
- Windows: a console program, `QLC Swiss Knife MCP.exe`, next to the app, because Claude needs stdin and stdout and the window app has neither. The release build runs the MCP self-test and a ping on every platform.
- Wiki: *Connect Claude to Swiss Knife*, with setup steps, example requests, what Claude can and cannot reach, and troubleshooting.

### Changed
- CI: a version tag no longer starts the `tests` workflow a second time, because the release workflow runs the tests itself. Release in one push: merge locally, tag, `git push origin main vX.Y.Z`.


## [2.8.6] — 2026-10-07

**Windows: the app starts, and there is an installer.**

### Fixed
- **The first Windows package did not start**: `UnicodeEncodeError: 'charmap' codec can't encode character '\u26a1'` — the start message (⚡, ⚠) could not be printed on a Windows console in cp1252 (or without a console at all). The console streams are now UTF-8 and never raise (`core/console.py`).

### Added
- **A real Windows installer** (`QLC-Swiss-Knife-<version>-windows-x64-setup.exe`, Inno Setup): per-user (no administrator), Start menu entry, optional desktop shortcut, uninstaller in *Apps & features*. It installs into your user programs folder so *Update and restart* keeps working; the update keeps the uninstaller. The `.zip` stays for those who prefer to unzip. The build tests the installer silently (install, start, uninstall) before it is published.


## [2.8.5] — 2026-10-07

**Pictures retaken, a sidebar fix, and the build actions brought up to date.**

### Fixed
- The bottom of the sidebar: *Check for updates*, *Check now* and its message overlapped, and the language picker was cut off. They now stack and fit.

### Changed
- **All screenshots and the route GIF retaken** with v2.8.5 (the README's 18 pictures — *Library* is new — and the 9 pictures of the wiki tutorial). Two small scripts now make them: `tools/make_screenshots.py` and `tools/make_route_gif.py`, on the scrubbed corpus shows.
- Faster CI: a newer push cancels the older test / live-check run on the same branch, a 10-minute limit on the tests, and documentation-only changes (markdown, screenshots, docs, wiki) no longer start the tests; the live check (advisory) starts only when code, the corpus or its Docker image changed.
- GitHub Actions moved to the Node 24 versions (`checkout` v7, `setup-python` v7, `upload-artifact` v7, `download-artifact` v8, `setup-buildx-action` v4, `build-push-action` v7) before Node 20 is retired.


## [2.8.4] — 2026-10-06

**Update and restart works on macOS.**

### Fixed
- **The macOS update left an app that would not open** (first live try, v2.8.2 → v2.8.3: the Dock icon jumped, then nothing). The update archive was a `.zip`, and the unpacking turned the app's internal symbolic links into plain text files. The macOS update is now a `.tar.gz`, which keeps them (the `.dmg` for a first install is unchanged), and the zip unpacking also restores symbolic links. Windows and Linux were not affected.
- Updating from v2.8.3 or earlier on macOS uses the new `.tar.gz`, so it works with the updater you already have.


## [2.8.3] — 2026-10-06

**QLC+ 5.3.0 compatibility.**

### Fixed
- **Script commands saved by QLC+ 5.3.0 are understood.** QLC+ 5.3.0 rewrites `stopfunction:6` as `Engine.stopFunction(6);` (and `startfunction`, `stoponexit`, `wait`) when it saves a workspace. The Doctor reported a false *unreferenced function* (D016) for the PANIC RESET scene of such a file; the Function Porter, Look Builder, Doctor fixes and Rig Reducer now read both forms for dependencies, ID renumbering and removal of dead references. A script that is edited (PANIC RESET gets the stops of newly ported or built functions) is edited in its own style; new scripts are still written in the old form, which QLC+ 5.2 and 5.3 both open.
- Rig Grow's warning about scripts that set channels of a followed fixture also recognises the `Engine.setFixture(...)` form.

### Changed
- The live-check tool finds the macOS binary of QLC+ 5.3 (`qlcplus5`).
- Test and live-check workflows run on Ubuntu 24.04 (the `ubuntu-latest` alias moves on 19 October).

### Added
- `core/script_cmds.py` — one place for reading, building and renumbering Script commands; `tests/corpus/QuickStart_club_qlc530.qxw`, the QuickStart_club file saved by QLC+ 5.3.0, and tests on it.


## [2.8.2] — 2026-10-06

**Update check, fixed after the first live try.**

### Added
- **Check now** under the menu (next to *Check for updates*): asks GitHub again, ignoring the answer remembered from the last 12 hours, and says *You have the latest version* or opens the card. (First live try of v2.8.0 → v2.8.1: the app had been started before v2.8.1 existed and kept saying *latest = 2.8.0*.)

### Fixed
- **The update check could not reach GitHub from the packaged app** (the bundled Python has no list of trusted certificates): it now uses certifi's list or the system's, and when a check fails the reason is shown under the menu. *First live try on the Mac: v2.8.0 never offered v2.8.1.*
- The update arrow in the top bar showed even when there was no update (the button style overrode `hidden`); now it appears only when a newer version is out.
- The tooltips of the top-bar buttons opened upwards, outside the window, and could not be read; they now open below (the right-hand ones leftwards).


## [2.8.1] — 2026-10-06

**A logo.** The app has its own icon now, and it is the first update to try *Update and restart* on.

### Added
- **Logo**: a Q whose tail is a folding knife, red Swiss cross inside, on a dark tile (`static/logo/`). Used as the app icon (macOS `.icns` and Windows `.ico` in `packaging/icons/`, so the Dock, the Finder, the taskbar and the `.dmg` show it), the browser tab icon, the header mark, and at the top of the README and the wiki.

### Changed
- The page title and the README title no longer start with ⚡.

## [2.8.0] — 2026-10-06

**Install like an app.** Download, unzip, double-click — and be told when a newer version is out.

### Added
- **Packages for macOS (Apple silicon and Intel), Windows and Linux**, built by GitHub Actions on every `v*` tag (`.github/workflows/release.yml`): PyInstaller one-folder (`packaging/swissknife.spec`), tests and a **smoke test of the bundle** (`--smoke`: the page, its scripts, the translations and the data files answer) before anything is published, then the files and a `SHA256SUMS` are attached to the GitHub Release. Names: `QLC-Swiss-Knife-<version>-<os>-<arch>.zip` / `.tar.gz` / `.dmg` (macOS `.dmg` for the first install). Not signed: first-run steps in the README and the wiki. *Untested live on macOS and Windows (built and checked on Linux only).*
- **Update check** (`core/update.py`): once at start, one request to the GitHub Releases API (the app's only network call on its own; switch off with *Check for updates* under the menu; cached 12 hours; nothing about you or your shows is sent). A header badge *vX.Y.Z available* opens a card with the release notes.
- **Update and restart** (packaged app): downloads the file for this computer, checks it against the release's `SHA256SUMS`, refuses paths that leave the folder, unpacks it, and a small script swaps the folder (or the `.app`) after Swiss Knife quits and starts the new version; the old one is kept as `….old` until the new one has started. Your shows and `~/.qlc_swiss_knife/` are never touched. From the sources the card says `git pull`.
- `python app.py --smoke` (used by the release build).

## [2.7.0] — 2026-10-06

**Language and sharing.** The interface in English, Italian and French, and a library to share what you built as one plain file.

### Added
- **Interface in English, Italian and French**: a language menu at the bottom of the left menu (remembered in the browser; English by default). Text, tooltips, placeholders and dialogs are translated as the page is drawn — numbers and names inside a sentence stay in place ("12 functions" → "12 funzioni" / "12 fonctions"). Strings live in `static/i18n/<lang>.json` (about 2,800 each, English text → translation, `{0}` for a changing part), so another language is one more file. Show data (function, fixture and group names), reports, PDFs and the wiki are not translated. The ⌘K / Ctrl+K palette has *Language: English / Italiano / Français*. `tools/i18n_extract.py` lists the strings of the app and what a language still lacks.
- **📚 Library** (menu 3 · Create): share your VC templates, colour palettes, look presets, naming profiles, VC styles and Show Profiles as one `*.qsklib.json` file, and install what others shared. Nothing is installed before you have seen every item with its status (new / same / differs / name taken) and chosen *skip*, *replace* or *keep both*; built-in names are reserved; a file is refused when it holds an XML entity or DOCTYPE, an unknown format placeholder, a Show Profile step that is not a recordable call, or is bigger than 8 MB / 500 items; a Show Profile that names a folder of your computer is flagged. Never shared: controllers, sessions, mesh folders, shows. Local files only — no server, no network.
- Naming profiles and VC styles can now be your own: `~/.qlc_swiss_knife/nomenclature` and `vc_style` (`QSK_NOMENCLATURE`, `QSK_VC_STYLES`) next to the built-in ones.

## [2.6.0] — 2026-10-06

**Paperwork, setlists, MIDI.** The controller side of a show, setlists that come in from anywhere and go out to a tablet, and a tech rider that says where things hang.

### Added
- **Trigger Manager › 🎚 Inputs & MIDI** *(untested live with a controller)*: every universe with its input device, profile, feedback and the number of bindings; **patch** a device (plugin, name, line, profile) or clear it; a universe with bindings but no device is flagged — the *"MIDI input saved as None"* case. **★ Remember a controller** (`~/.qlc_swiss_knife/controllers.json`, `QSK_CONTROLLERS`) and patch it into any show in one click. **Re-patch** the bindings: move a universe's buttons to another universe (shifting channels if needed; refused when it would clash) or swap two universes. A **MIDI simulator** (a MIDI-learn without the controller): pick universe, message type, number and MIDI channel, and see what would fire, with near misses on other MIDI channels (OMNI) and the reason when nothing does. Channels are decoded (*Note 60 (C4)*, *Control change 7*). Each edit is one step of the History. **📂 Learn my controllers from another show…** reads the controllers patched in a show that works (QLC+ wrote their real UID and line mode there) and remembers them; patching writes that UID and the line mode (`<PluginParameters mode>`), and keeps them when the same device is patched again — QLC+ 5.2.2 saves a numeric UID that cannot be invented (found in giopas's shows: `Name="SINCO" UID="528145425"`; QLC+ 5.2.1 saved `UID="SINCO"`; a lost input is `Name="None" UID="None"`).
- **Setlist › 📋 Import / paste…**: from the clipboard, a .txt or a .csv / .tsv. Numbering is dropped (*1.*, *2)*, *03 -*), `--- Set 2 ---` / *Encore* split the sets (a song called *Set Fire to the Rain* stays a song), CSV columns *Song, Set, Fade in, Hold, Fade out* are understood (seconds or m:ss), and you see the list before anything changes.
- **Setlist › 📱 Tablet page…**: one self-contained HTML file with every setlist in big type — tap a song to tick it off, set tabs, A− / A+, light / dark, optional QLC+ function names; no app, no network.
- **Tech rider with the rig's details** (Show Paperwork › Tech rider; each opt-out): the **patch** of every fixture (universe, address, channels), **where it hangs and its tilt** (position of the centre, height of the underside, tilt in words — *45° to the front*), and the **set pieces** (visible 3D meshes) with their place and size. Still nothing about functions or the Virtual Console.

## [2.5.0] — 2026-10-05

**Looks and Stage.** The Look Builder learns beats, positions, own palettes and pixel bars; the stage learns to aim, hide and copy.

### Added
- **Look Builder: chasers in QLC+ beats tempo** — with *BPM* timing a *Beats* box writes the chaser's tempo as beats (`TempoType Beats`, 1/8-beat steps), so it follows QLC+'s tempo / tap instead of fixed milliseconds.
- **Look Builder: moving-head positions** — looks and chasers take a **position** (Centre, Left, Right, Back, Front, or your own pan/tilt in %); the scene is named `<colour> @ <position>`.
- **Look Builder: your own palettes** — *★ Save palette* keeps the colours you picked in `~/.qlc_swiss_knife/look_palettes.json` (`QSK_LOOK_PALETTES`); they sit next to Warm / Cold / Scenic and can be deleted.
- **Look Builder: RGB-matrix patterns for pixel bars** (Chase, Even-Odd, Gradient, Plasma, Waves, Stripes) — one row per bar, one column per pixel head (read from the .qxf modes); a bar with a master dimmer gets a Collection (dimmer-opening scene + matrix), and a *Matrices* row on the VC.
- **Stage & Meshes: aim fixtures** — tilt (XRot) toward a mesh (its centre, top or the floor under it) or a point (z, height); pan and roll stay, Undo brings the old tilt back.
- **Stage & Meshes: 🙈 hide / 👁 show meshes** (QLC+'s `Hidden`) — hidden ones stay in the show and are drawn dashed in the views.
- **Stage & Meshes: thumbnails** of the models in the library.
- **Function Porter: copy meshes between shows** — a *Meshes* column in step 2; each copy gets a new ID, a full path to its model file, and the same visible place and floor height (scaled when the stages differ); listed in the port report.

## [2.4.0] — 2026-10-05

**Doctor and Quick Start.** Found testing 2.3.0, plus the Doctor fixes that were left.

### Added
- **Quick Start: looks for fixtures without a dimmer.** A fixture with no dimmer and no RGB uses its colour-wheel slots (named White / Red / Amber / Light Blue… ) for ALL ON, Warm White and Cold White, and its closed shutter for BLACKOUT. Step 5 now **says which fixtures cannot make a look** (found by giopas with an Abstract VR8 scanner, whose channels are mirror pan/tilt, colour and gobo macros: every look was the same).
- **Profiles say where they are kept**: the path in the Quick Start message and the History box, with **📂 Open folder** (`~/.qlc_swiss_knife/profiles/`).
- **Function Porter: *Make PANIC RESET a script*** (on by default): a target whose PANIC RESET is a plain scene (it cannot darken running looks) gets the script form, as Doctor D017 does, so the ported functions are stopped too.
- **Doctor fixes with a choice** (each opt-in, new file, in the report; the *how* is chosen above the findings): **D013** give 0 ms chaser steps a duration in ms or a tempo in BPM; **D004** a chaser with one step is merged into its scene (or removed), an empty one removed; **D003** broken buttons / CueLists are rewired to the function (chaser) with the same name, else unlinked; **D015** unnamed functions named from the button that starts them or their parent chaser. Command line: `--timing 500ms|120bpm`, `--d004`, `--d003`, `--d015`.
- **Sessions keep the Quick Start setup**: rig, fixture files, groups, naming and style options, stage and project name come back when a `.qsk` is opened.
- **Live check in CI**: `docker/qlc-check/Dockerfile` (QLC+ 5.2.2 built headless) and `.github/workflows/qlc-live-check.yml` run `tools/qlc_check.py` on the golden workspaces (advisory until its first green run).

### Fixed
- **The live check reported Chase / Stripes buttons "dark" at random**: a chaser that starts on a dark step is dark for part of its cycle. The check now watches one whole cycle of the look before it calls a button dark.

## [2.3.0] — 2026-10-05

**The new-show flow.** Starting a show from nothing is now one path, and a profile can start it.

### Added
- **Fixtures → 🎛 Open it as the show**: after *Save as new file…* the saved file becomes the show in progress (as in Quick Start).
- **Guided route *New show***: The rig → Groups → Looks → VC Editor → Stage → Setlist → Show Book → Doctor; a third route card on Start and in the ⌘K palette.
- **Profiles that start a show from nothing**: Quick Start's *Save the rig as a profile* (rig, fixture files, options, stage) and, on Start, *Start a show from a profile*. `python -m core.profile rig` / `build` without `--show` do the same on the command line.
- **Profile step editor** (History › Do it again › ✎ Edit steps): drop a step, reorder, rename; the left-out reasons stay visible.
- **Setlist in fewer columns**: the QLC+ function list is a drawer (docked on wide windows, an overlay on narrow ones; remembered).

### Changed
- `/api/checklist/*` and `/api/techrider/*` are thin wrappers over the Show Book.

### Removed
- `core/merger.py` and `/api/merger/*` (the Function Porter has done their work since 1.9).


## [2.2.1] — 2026-10-05

**Finishing the UI polish.** The three items left over from 2.2.0, plus the white-window fix.

### Changed
- **Function Porter — "Apply will …" in the footer of steps 2–5**, like the other tools: step 2 *port N functions · M VC widgets · copy K fixtures*, step 3 *X of Y fixtures mapped* (amber when some have no target), step 4 the plan's errors / warnings (red when blocked), step 5 *one History step* or *write a new file*. It follows every tick, mapping and copy choice.
- **Function Porter step 3 — mapping first.** The two stage maps are folded under *🗺 Stage maps* (closed by default; hover or click a mapping row to ring its fixtures once opened).
- **One type scale in the stylesheet.** Seven odd sizes (8–10.5, 11.5, 12.5, 13.5 px) are now the nearest step, and every size on the scale is a token: `--fs-micro` 10 · `--fs-small` 11 · `--fs-ui` 12 · `--fs-body` 13 · `--fs-lead` 14 · `--fs-section` 15 · `--fs-title` 20. The dense on-canvas parts (VC Editor widgets, fixture chips, the stage-plot SVG) keep their small sizes on purpose. Look Builder already had its footer line since 2.2.0.

### Fixed
- **Native window opened white** (giopas, 4 Oct): the window could load the page before the server was listening, and WKWebView does not retry. `python3 app.py` now waits until the server answers (up to 15 s) before opening the window, and says so plainly if port 5731 is taken (e.g. by another Swiss Knife still running). `QSK_DEBUG=1 python3 app.py` enables *Inspect Element* in the window.


## [2.2.0] — 2026-10-04

**UI polish — after an outside review (Copilot, Gemini; 4 Oct).** What each tool will do is visible before you press Apply, the guided routes come first, the header labels its numbers, and ⌘K / Ctrl+K goes anywhere. Pure CSS and a little JavaScript; no new library. Mockup: `mockups/mockup_C_ui_polish.html`.

### Added
- **References in the cue notes of older shows** (giopas, 4 Oct: adding a song to an older show).
  - **When a show opens**, every setlist cue (a step of a chaser played by a CueList) that has **no note** gets the reference that 2.0.1 writes for new cue lists: `↪ [ID] original function — button on Page`.
  - It is one step of the History (↶ undoes it), so you see it and decide whether to keep it with 💾 Save as new file….
  - A note already there — yours from QLC+, or Swiss Knife's — is never touched.
  - Also by hand: Setlist › *↪ Add references to the cue notes*.
  - The original is found:
    - through Swiss Knife's copy marker;
    - from the name of an old-style copy (*Song (Setlist)*);
    - or, for a copy whose marker QLC+ dropped, as the one function with the same content that a button plays.

    Otherwise the note names the function the cue plays.
  - `workspace.cue_notes_missing / fill_cue_notes`, `GET|POST /api/setlist/notes`. Tests in `tests/test_setlist_notes.py` (10).
- **⌘K / Ctrl+K — Go to…** (also a button in the header). Type a few letters to open any tool, or to run an action:
  - Undo, Redo, History, Save as new file…;
  - save the recipe or a profile; apply a saved profile;
  - start a guided route;
  - check with the Doctor, open, reload, change the theme, help for this tool.

  `static/js/palette.js`.
- **"Apply will …" in the footer** of the Rig Reducer, Workspace Doctor, Look Builder, Brightness and Setlist, next to the button. For example:
  - *−6 fixtures · −3 groups · −11 functions · ✓ no new Doctor errors*;
  - *D005 × 801 · D017 × 1*;
  - *+2 looks*;
  - *12 cues · 1 song without a function — left out*.
- **Start: guided routes first.**
  - Three cards: *Adapt a show to a new venue* (9 steps — the Pub test took 12 minutes), *Get ready for the gig* (4 steps), and *Do it again with a profile* (your saved profiles).
  - Each card lists its steps.
  - The six job cards follow, under *Or pick a tool by job*; card 6 gains *Patch sheet*.

### Changed
- **Rig Reducer: no Preview click.** *What Apply will do* updates as you tick. It is grouped (fixtures, renamed / re-patched, fixture groups, functions, VC widgets, Doctor on the result), each group folding, instead of one log.
- **Header**: fixtures, functions, VC widgets, unsaved changes and the Doctor are small labelled cards, with the labels shown at every window width (they were hidden below 1560 px). The Doctor card is red, amber or green.
- **Side menu**:
  - the group titles read as titles, with a rule under each;
  - *Changes* is now **History**: a card that is always there, ✓ for saved steps, ↶ on each.
- **Tables** (Trigger Manager, Dictionary, ID Browser, Rig Reducer, Show Paperwork, Porter): zebra rows, a row highlight, quieter separators and headers, a quiet ID column and bold names. Names in the UI font; IDs, keys and MIDI stay monospace.
- **Stage top views** (Fixtures, Function Porter): a lighter grid, and each fixture label on a small plate so it reads over the grid and the other dots.
- **Design tokens** (`tokens.css`), for the dark, grey and light themes:
  - semantic colours (`--success`, `--warning`, `--error` and their soft backgrounds) in place of a dozen hard-coded yellows, greens and reds;
  - one spacing scale (`--sp-1…6`), the text levels (`--fs-title / section / body / small`), one elevation (`--shadow-1`) on cards;
  - thin scrollbars.
- Screenshots 01 (Start), 04 (Rig Reducer) and 13 (Workspace Doctor) retaken.
- **Installable packages** move to v2.3.0.

## [2.1.0] — 2026-10-03

**Show Profiles: do it again, on another show.** The changes you made to a show — reduce the rig, fix, groups, looks, VC pages, setlist… — kept as a profile and applied to any other show, in the app or from the command line. Each step finds what it changes **by meaning** (name, type, place), not by the IDs of the show it was made on, and says what it left out.

### Added — Show Profiles
- **The recipe knows what its IDs are.** Before each recorded call, Swiss Knife notes what every ID in it *is*: the Scene "Song 22", the fixture "Drums" at 1.8, the group "Band Pair", the CueList "Setlist" on the page "1. SETLIST", the mesh "Drum riser". `core/retarget.py` (`index`, `symbolize`, `bind`; which field of which call holds which kind of ID is one table, `RULES`).
- **Replay a recipe on another show**: `python -m core.recipe replay <recipe> --onto Other.qxw [--out …]`.
  - Every ID is found again on the other show:
    - by name and type;
    - a fixture not found by name is found **by address** (said so);
    - a VC widget not found at its place is found **elsewhere on the console**, if there is only one.
  - Workspace Doctor fixes become *the same kinds of fixes* on the other show.
  - A call that names something the show doesn't have is **left out**, with the reason. A call that fails is noted and the rest goes on.
  - Recipes from 2.0.x are first replayed on their own show to learn what their IDs are.
- **Show Profiles** (`core/profile.py`): a recipe made portable.
  - Its steps are by meaning.
  - The files it uses (a setlist `.txt`, another show for the Porter, a mesh) become **parameters**: give them, or put them next to the profile.
  - The VC page templates it uses travel inside it.
  - It holds no paths of the computer it was made on.
  - Saved in `~/.qlc_swiss_knife/profiles/`.
- **In the app — History › ↻ Do it again**:
  - **📋 Save the recipe…** keeps the recipe so far, without saving the show.
  - **★ Save as a profile…** keeps the show's changes as a profile, with a name and a description.
  - **▶ Apply** runs a saved profile (or *From a file…*, a profile or a recipe) on the open show. Every step becomes a step of the History (undo works), and the result lists what was left out or matched by place.
  - If the profile uses files, it asks for them.
- **The command-line pipeline**: `python -m core.profile build <profile> --show Venue.qxw [--out …] [--param Setlist.txt=…]` opens the show, applies the profile and saves `<show>_v<n+1>.qxw` with its report and recipe. The source show is never changed, and the Doctor's verdict is printed. Also `show`, `list` and `make` (a profile from a recipe file).
- Routes `/api/profile/recipe|list|save|apply|delete` (not recorded themselves; the calls a profile makes are). Tests `tests/test_profile.py` (10): same show → same file byte for byte, another show by meaning, what's left out, 2.0 recipes, profile from the app applied to FloorShow, files as parameters, CLI build, templates inside the profile, recipe without saving.

### Changed
- **Quick Start › Placement: tilt buttons.** *Beam (tilt)*: ↓ Down, ↔ Across, ↑ Up, or Auto (from the height, the default) for the selected fixtures or all. The function was there, without buttons.
- **Quick Start file name follows the `_vN` rule**: `<project>_v1.qxw`, then `_v2`… after each save, instead of a timestamp.
- **Fixtures (the configurator) keeps the tilt.** It wrote `XRot = 65` for every fixture. Now it keeps a tilt set in the show, and a new or default one follows the fixture's height and depth like Quick Start (truss down, floor up, toward the stage centre).
- **Start**: *New in 2.1*.


## [2.0.1] — 2026-10-03

**After the pub test: paperwork for the crew, notes in the cue list.** A patch sheet with DIP switches (and a thermal-printer ticket), each setlist cue saying which function and button it stands for, a setlist CueList in one click for a show that has none, a third real show in the test corpus — and the fixes from giopas's first test of all this.

### Changed
- **The setlist CueList is easy to find.** It was the last, folded item of *Ready-made blocks* in the VC Editor. Now:
  - **VC Editor › ＋ Add & wire** opens with a highlighted box **▶ Setlist cue list**. It says how many CueLists the show has ("This show has no CueList yet"). Its button names what it will do: *＋ Add a CueList on this page*, or *Wire “…”* when a CueList is selected.
  - **✥ Selection** of a CueList has **▶ Use for a new setlist**.
  - **Setlist**: a show with no CueList says so and offers **▶ ＋ Add a setlist CueList** (first VC page, new empty chaser *Setlist*); the slot appears at once.
  - A new setlist CueList no longer covers other widgets. It goes where it fits at 720 × 420, smaller if the page is full (Quick Start page: under the groups, 720 × 340).
  - `/api/vc/builder-info` lists `cuelists`; `setlist_cuelist` takes `__new__` with a selected CueList too. Tests `tests/test_setlist_notes.py` (8).

### Fixed
- **Setlist: a song with no function was dropped from the cue list without a word** (giopas's test, 3 Oct). Applying now says which songs were left out, and the show report lists them under the Setlist step.
- **VC Editor: a new CueList is 720 × 420** (was 400 × 500), wide enough to show every column in QLC+, the *Note* included.

### Added
- **VC Editor › Setlist CueList: *＋ a new, empty setlist chaser*.** A show without a cue list (e.g. fresh from Quick Start) gets one in a click — a CueList on the page, wired to a new empty chaser *Setlist*; the Setlist tool then shows its slot and fills it. Before, the CueList had to be wired to an existing chaser, which the Setlist would then overwrite.
- **Test corpus: `FloorShow_8fix.qxw`**, the third real show (8 PARs, 246 functions, the ceiling PARs brought in with the Function Porter), anonymised like the others. Its Doctor baseline is pinned; it found a real slip — the static look *Soft Yellow* leaves the PARs' strobe channel at 30.
- **Workspace Doctor D008**: a VC button with the action *Stop All* (or *Blackout*) counts as a panic button — no more "no PANIC RESET function" on shows that use one.
- **Patch sheet** (Show Paperwork, new *🔌 Patch sheet — for the crew at the rig*): every fixture by universe and address — address range, channels, name, fixture, mode — with an **ID** column and a **DIP-switch diagram** per fixture drawn like the real part — blue body, white levers, ON = lever up (switch *n* = 2^(n−1); 9 or 10 switches; checked against OH Show's sheet on the same show) and the switches to turn ON. An **event / venue** line and a **logo** (PNG or JPEG, remembered in this browser) at the top. Venue-safe: it never carries the show's internals.
  - **Thermal printer ticket**: one long PDF page 58 or 80 mm wide (DIP outlines with black levers), or plain text with 32 / 48 characters a line for printer apps.
  - **CSV**: `patch_sheet.csv` in the ZIP, with the columns proposed in QLC+ issue #2086 first (universe, address, manufacturer, model, mode, name), then channels, last address, DIP switches ON.
  - Inspired by OH Show's QLC+ patch tools (apps.fewday.go.yn.fr/QLC). `core/patch_sheet.py`; `/api/showbook/export/receipt`; logos read by `core/pdf_image.py` (standard library only: JPEG, PNG grey / RGB / palette / alpha, 1–16 bit); `core/pdf.assemble_pdf` takes images and per-page sizes. Tests `tests/test_patch_sheet.py` (18).
- **Setlist: each cue's note says what it plays.** When the Setlist builds the cue list, every step gets a note with the **original** function — not the copy the cue runs — and the button that plays it, e.g. `↪ [2328] Song 22 — buttons: CS · Soft Yellow, FD · Candle Loop`. QLC+ saves step notes in the show and the QLC+ 5 cue list shows them, so they survive a relaunch. A note you typed in QLC+ is kept (only notes starting with `↪` are Swiss Knife's). When QLC+ re-saves a show it drops Swiss Knife's copy marker; the Setlist now reads the reference back from the note. Tests `tests/test_setlist_notes.py` (3).


## [2.0.0] — 2026-10-01

**The Pub test passed.** A real festival show rebuilt as the pub show with Swiss Knife only, in 12 minutes, Doctor 0 errors, played in QLC+ (WORKPLAN 2.8). The two tools it needed, what the run showed, a tutorial — and the recipe, so a show can be replayed to the same file (WORKPLAN 2.9).

### Added — the recipe (repeatable shows)
- **The recipe**: *💾 Save as new file…* also writes `<name>.recipe.json` next to the file and its report — every change made to the show since you opened it, as the calls the tools made (undo and redo included), the source file and the other files used (another show for the Porter, a setlist `.txt`) with their SHA-256, and the SHA-256 of the saved `.qxw`.
- **Replay from the command line**: `python -m core.recipe replay <name>.recipe.json` opens the source in a fresh app, replays every call and says whether the result is **byte-identical** (`--out` keeps it, `--source` / `--inputs` when the files moved; `show` lists the steps). The Pub-test run replays to the same file. `core/recipe.py`; tests `tests/test_recipe.py` (7).

### Added
- **Fixture groups** in Stage & Meshes, new tab **Groups**.
  - **Make** a group from the fixtures you select in the views (click / Shift-click, *⬚ From the selection*) or by ticking them; heads go in one row, left → right as seen from the audience, or as listed.
  - **Change** an existing group: rename it or set its fixtures. It keeps its ID, so matrices and VC widgets that use it keep working.
  - **Delete** a group; refused while an RGB matrix runs on it (the matrices are named).
  - Each group shows its fixtures and how many matrices use it; *Show* selects its fixtures in the views.
  - Every change goes into the show in progress (History: *Stage & Meshes — fixture groups*; ↶ Undo works); the stage report lists added / changed / removed groups.
  - The Look Builder offers new groups at once. `core/fixture_groups.py`; stage ops `group_new`, `group_update`, `group_delete`. Tests `tests/test_fixture_groups.py` (8).
- **Compare** (menu 5 · Check & fix): the show in progress next to another `.qxw` — e.g. the hand-made version, or the file you opened (*⤵ Opened file*: what changed) — **by what they do, not by IDs**:
  - fixtures by patch (then name);
  - groups by name and heads;
  - scenes per fixture, decoded to level and colour (±6 %) when the definitions are found, else channel by channel;
  - chasers and sequences step by step, collections, EFX, RGB matrices;
  - VC pages by their buttons and what they run;
  - setlist cue lists by their songs.
  - Per section: same / different (≠) / only here (+) / only in the other (−). *Copy report*, *Save report…*. `core/compare.py`, `/api/compare/run`. Tests `tests/test_compare.py` (5).
- **The show report says what each in-place step changed** (Stage groups, stage edits, VC Editor, Setlist, Trigger Manager): fixtures, moved on the stage, groups, functions, VC pages and widgets — added / removed / renamed / changed. `core/show_diff.py`. Tests `tests/test_show_diff.py`.

### Changed — after the first timed Pub-test run (12 minutes)
- **Compare** pairs setlist cue lists by caption, then **by their songs**, then the only one left on each side (*Setlist: Band A* ↔ *Pub Setlist*).
- **Compare** lists functions **nothing plays** (no button, not in another function — the Doctor's D016) as *unused* per section, and does not count them in the result.
- **Compare** pairs a look that is a Scene in one show and a Collection in the other.
- **Fixture groups**: names are trimmed of spaces, quotes and a trailing `:` `;` `,` `.`.

### Changed — while writing the tutorial
- **Guided route *Adapt a show to a new venue*** has a **Groups** step (Stage & Meshes › Groups) before *Looks* — the Look Builder makes looks per group. Nine steps.
- **Stage & Meshes › Groups**: the list is taller, and a group you create or save is highlighted and scrolled into view (new groups went to the bottom of a short list, out of sight).
- **Rig Reducer** says *renamed* and *re-patched* apart (renaming 6 fixtures read "6 re-patched"), on screen and in the History.
- **Show report**: a VC Editor step also says when the page order changed.

### Added — tutorial
- Wiki **Tutorial — from a big-venue show to a pub show in 30 minutes**: the guided route step by step on the festival show, with screenshots (`screenshots/tutorial/`).

### Added — Workspace Doctor
- **D018 — setlist song that lights nothing** (warning, on the CueList): a cue whose function is an empty scene, or a chaser / collection with no steps (or only such steps) — the stage goes dark on that song. Found in the Pub-test QLC+ check: the festival show's *Song 12* is a chaser with no steps (cue 31 of the pub setlist, cue 12 of *Band C*). Not fixed automatically: only you know what the song should look like.
- **Setlist**: a song that lights nothing gets an orange dot and a warning in the song list (`/api/functions` → `dark`).


## [1.10.0] — 2026-10-01

Phase 2.7 — **Grow a rig**: fixtures copied into a show join the show's own looks.

### Added
- **Function Porter — the copies in the show's own looks** (giopas, 1 Oct: copied ceiling spots stayed dark in the show's existing looks). Step 3 has a new card. For each fixture copied in step 2 you choose which existing fixture it **plays like**; *— stays dark —* is also a choice.
  - Every scene and sequence step of the show that sets that fixture then sets the copy too, translated by capability when the types differ (dimmer, RGB/W, colour wheel, strobe), with every channel declared. EFX that use it get the copy as well.
  - Chasers, collections, cue lists, shows and buttons play those scenes, so they follow with no change. The functions ported in the same step are left as they are.
  - **Suggested choice**: the nearest existing fixture at the same level (hanging above 1.5 m, or on the floor), on the same side of the stage, so ceiling lights follow ceiling lights. Each choice shows how many looks it joins. *Suggested* / *None* buttons.
  - **Not wired, said plainly**, in step 4 and in the report:
    - RGB matrices stay on their fixture group, because their pattern would change.
    - Scripts that set channels directly.
    - *Channels* sliders.
    - A missing `.qxf` (then the values can't be translated, and the card says where to put the file).
  - `core/rig_grow.py` (`suggest`, `usage`, `wire`, `not_wired`); plan key `wire`; `POST /api/porter/wire/options`; report section *WIRED INTO THE SHOW'S OWN LOOKS*. Tests `tests/test_rig_grow.py` (10).
  - The report (and step 4) also names the copies left dark, which then play only the ported functions.

### Changed
- The Quick Start / Look Builder naming profile *two-letter prefix* has the id `prefix` (file `prefix.json`); pick it again in an older session. Project texts no longer name people, bands or venues.
- **README** is now a presentation of the project only (what it is, how it works, the tools, screenshots, install, links); the version history stays here. All **screenshots retaken** (16, in menu order). The forum drafts (`docs/release-notes/FORUM_*.bbcode`) are removed. Security details moved to DEVELOPMENT.md; ROADMAP updated (1.10 Grow a rig, 2.1 packages).

### Fixed
- VC Visual Editor: the page title still said *BETA*.

## [1.9.0] — 2026-10-01

Phase 2.6 — UI audit: **the show in progress** for every tool, the Merger in the Function Porter, **Show Paperwork**, guided routes, and one screen pattern.

### Added
- **Guided routes** (2.6, the "route strip"): *▶ Guided route* on the Start cards *Adapt a show* (Rig Reducer → Doctor → Function Porter → Look Builder → VC Editor → Stage → Setlist → final check) and *Run the show* (Setlist → Trigger Manager → Doctor → Show Paperwork) puts a strip of numbered steps above the tools: click a step to open its tool, a step is ticked when its tool changes the show (or by hand), *Done, next ›*, ✕ closes it. Any step, any order; it only guides. `static/js/route.js`.
- **A "?" on every tool** (next to the theme button) opens the tool's wiki page in the system browser, also from the desktop window (`POST /api/help`, wiki page names only).
- **Quick Start → 🎛 Open it as the show**: after saving, the new show becomes the show in progress (asks first if the open one has unsaved changes).
- **ID Browser works offline**: without the table library (no internet at the venue) it shows plain sortable tables; before a show is open it says what to do.
- **The show in progress** (giopas: "we have to allow the possibility to jump from one tab to the other"): opening a `.qxw` makes one working copy that **every tool changes**, in any order, back and forth — no more save and re-open between tools. `core/show.py`, `routes/show_routes.py` (`/api/show/status|history|undo|file|saved|save|report`), `static/js/show.js`.
  - **Header**: *N changes, not saved*, the **Doctor** on the show as it is now (click → Doctor), **↶ Undo**, **🕘 History**, **💾 Save as new file…**.
  - **History**: every step (tool, what it did, Doctor after it, time); *Open tool*; *↶ Undo from here* (back to before any step). In-place edits of one tool are one step until another tool acts. Keeps the last 60 steps.
  - **Orange dots** in the side menu on the tools that changed the show since it was opened / saved (giopas's idea).
  - **One save**: `<name>_v<N+1>.qxw` + one `<name>_v<N+1>_report.txt` with every step and each tool's report; keep working after saving. The opened file is never written (refused).
  - Asks before *Open…*, *Reload* or *Quit* drop unsaved changes.
- **✓ Apply to the show** in Workspace Doctor (*Fix selected in the show*), Rig Reducer, Look Builder (*Add to the show*), Brightness, Setlist, VC Editor; `POST /api/doctor|reducer|looks/apply`, `/api/brightness/apply-show`, `/api/setlist/apply-all`, `/api/setlist/<slot>/apply`. Tested: applying gives exactly the file the old export gave (byte for byte).
- **Function Porter on the show in progress**: with a show open, the target is *🎛 The show in progress* (chosen for you; *📂 Another file…* still ports into a file); step 5 **✓ Apply to the show** adds the port as one step (the target is re-read from the show first, so changes made meanwhile are kept); *Export a copy…* as before. `POST /api/porter/target/show`, `POST /api/porter/apply`; tested equal byte for byte to the export.
- **The QXW Merger is part of the Function Porter** (giopas, 29 Sep): step 2 *Fixtures and groups to copy into the target* — copied fixtures get the next free ID, keep their address when free or move to the first free block (reported), names made unique; groups rebuilt on the copied or mapped fixtures (an identical one is reused); works with or without functions; ported functions play on the copies. `porter.copy_fixtures_into()`, plan keys `copy_fixtures` / `copy_groups`, `GET /api/porter/source/groups`. The Merger tab is gone (menu, Start card); an old session's Merger source opens as the Porter's source; `core/merger.py` and `/api/merger/*` stay for now.
- giopas's tests, 30 Sep (evening):
  - **Porter — copied fixtures now always play on their copy.** With a fan-out mode like *pattern repeat* the copies were tiled onto other targets (report: "Ceiling 1 → FL: Drums"). Copies are pinned 1:1 (`porter.plan_blocks`); the other sources share out the remaining targets. Step 3 shows copied rows as *✚ its copy*, offers the copies as targets for the other sources, and candidates / auto-map know the copies.
  - **Porter — a race could copy the fixtures twice.** Step 3 asks the server for candidates and the preview plan at the same time; the temporary "target with copies" could overlap and stay (copies drawn twice, *Ceiling 1 (2)*). Now serialised with a lock; test with 4 threads.
  - **Porter step 3 — target picker**: the multi-select list is replaced by a drop-down with a tick box per target fixture (grouped by match), *All exact matches* / *None*, chips for the chosen ones.
  - **Show Paperwork — the stage plot is drawn in the preview** (from above and from the audience, like the PDF page), and the **sections are grouped**: *The rig* · *The show* · *Console & checks*, with the DMX-decoding folder moved to an options line.
  - A UI test now checks that every JavaScript file parses (a name clash had silently broken the Porter page during this work).
- Show Paperwork **paper sizes** (giopas, 30 Sep): A4, A3, US Letter, landscape or portrait (`showbook.PAPERS`, `paper` in the export body; saved in the session, an old session's Checklist / Tech Rider paper carries over); the page header keeps the title clear of the date on portrait pages.
- **Show Paperwork** (giopas, 29 Sep: "merge into one, modular report"): the Show Book, Setup Checklist and Tech Rider are one tool with **presets by reader** — 🎟 Tech rider (venue), ✅ Crew checklist (load-in), 📖 Show book (operator), ⚙ Custom; ⇧-click combines them in one PDF. New sections *rider* (types with channels per fixture, totals), *checklist* (tick boxes, 3D position) and *stage_plot* (the blueprint as a page of its own). **Rule, not a tick box:** with only rider / checklist presets the paper never carries function names, key/MIDI, the VC or the Doctor (locked in the UI, enforced in `showbook.resolve_sections`). Show name and date now come from the Start screen (the book used to ignore them). File names `<show>_TechRider.pdf`, `_CrewChecklist`, `_ShowBook`. `GET /api/showbook/presets`; `presets`, `show_name`, `date` in the export bodies; `pdf.blueprint_stream()`. The Checklist and Tech Rider screens are gone (menu, Start chips now open the presets); `/api/checklist/*` and `/api/techrider/*` stay for now. Tests `tests/test_show_paperwork.py`.
- Porter copies (giopas's test, 30 Sep): copied fixtures get their **3D position** from the source (scaled to the target stage) — they were all stacked top-left in QLC+; step 3 draws them **green** on both plans (*+* in the target, preview via `GET /api/porter/stage/target?copy_fixtures=…`); no more "target fixture(s) left unassigned" warning for copies; copying the same fixtures again is flagged; the finish screen has **💾 Save as new file…** and says it is also top right; messages say "(top right)".
- **Changes on the left** (giopas's test, 30 Sep: "a history log and a revert button on the left side"): under the menu, the last steps of the show, each with **↶** to undo it (asks first when it undoes several), click a line to open its tool, *All ›* for the full History.
- **↷ Redo** after an undo (side list and History), until the show changes again; `POST /api/show/redo`.
- The Workspace Doctor checks the show in progress as soon as you open it.
- Trigger Manager, VC Editor (pages, widgets, wiring) and **Stage & Meshes** edits go straight into the show; Stage & Meshes keeps its own undo and keeps its edits when another tool changes the show.

### Changed
- Each tool's old "→ new file" button is now the secondary **Export a copy…** (the tool's result as a separate file with its report; the show in progress is left as it is). Trigger Manager's *Save new version* is gone (the header save replaces it).
- Header fits 1280 px: the counts lose their labels (tooltips instead) and the Doctor pill shortens below 1560 px.
- Footer notes shortened to "Changes the show in progress" (the rest in the tooltip) — they wrapped over three lines next to three buttons.
- Page texts, menu tooltips and the Start screen describe the show in progress instead of "into a new file".
- **One screen pattern** (2.6 audit A5–A10): every tool has its purpose line and **?** at the top and its main action bottom right.
  - **Look Builder**: *🎨 Looks · 🔁 Chasers* tabs on the left, *To build* always visible on the right.
  - **Stage & Meshes**: the crowded right column is four tabs — *Selection* (meshes, fixtures, the selected item) · *Place* · *Add* · *Stage*.
  - **Function Porter**: Back / Next / Apply sit in the footer of each step, with the note on what it changes; the chosen target says *✓ The show in progress* (no second chip); step 4 → *Next: Apply*.
  - **Show Paperwork**: *Export PDF…*, *Export CSV…* and the paper size in the footer; *🔍 Preview* and expand / collapse on one line with the **show name and date** (moved here from the Start screen — they only feed the paperwork and the session); messages in the app's status line.
  - **Brightness**: the long help is a one-line *How it works* you can open.
- **Start screen** (A1, A2): one sentence on what the app is for, *New in 1.9*, a smaller *Open a show* box, *What do you want to do?* with the six job cards, sessions below; the "?" opens the wiki.
- **Words** (A7): writers of a new file say **💾 Save as new file…** (Quick Start, Fixtures — was *Generate QXW*); tool messages point to *✓ Apply to the show* and the header save.
- **Side menu**: tooltips say when to use Quick Start vs Fixtures; the VC Visual Editor is out of Beta; in short windows the menu tightens so all six groups stay in view.

### Fixed
- Show Paperwork: stray closing tags left from the removed Checklist / Tech Rider screens (their status line showed as bare text under the preview).
- Test `test_read_obj_and_resolve` failed on a computer with QLC+ installed (it found the real `generic/cube.obj` — whose size matches the built-in one); the test now covers both cases. App unchanged.

## [1.8.1] — 2026-09-29

### Added
- **Stage & Meshes — fixtures in the placement** (giopas's request): fixtures are drawn with their real body size (from the `.qxf` dimensions; 300 mm when unknown), can be selected (in the views or the new *Fixtures* list) and dragged, and take part in every placement tool. With meshes **and** fixtures selected, *Move: only the meshes / only the fixtures / everything* keeps the others where they are as the **reference**: e.g. a mesh + two fixtures, *only the meshes*, **centres ↔** → the mesh stands exactly between the fixtures; *space evenly* puts it at equal gaps; a fixture + the drummer, *only the fixtures*, centres ↔ and ↕ → the fixture right above the drummer. A single fixture can be moved by its centre and height (its tilt and pan stay). The report lists moved fixtures. (`stage3d.fixtures()`, `move_fixture()`, `arrange(move=…)`)

### Changed
- **Start screen and side menu use the same 1–6 groups** (giopas's report: "Build the rig" on the Start page opened only Fixtures, and the 1–6 cards didn't match the menu). The tools are now grouped by job, with the same numbers and names in both places: **1 New show** (Quick Start, Fixtures) · **2 Adapt a show** (Rig Reducer, Function Porter, QXW Merger, Brightness) · **3 Create** (Look Builder, VC Visual Editor, Stage & Meshes) · **4 Run the show** (Setlist, Trigger Manager, Dictionary) · **5 Check & fix** (Workspace Doctor, ID Browser) · **6 Document** (Show Book, Checklist, Tech Rider). Each Start card lists all of its tools as buttons instead of opening one tool; hovering a card lights up the same tools in the menu; the collapsed menu shows the group numbers. The "What is QLC+ Swiss Knife?" text now says what the app is for and that every change goes to a new file. The empty recent-files box is hidden until there are recent files.

## [1.8.0] — 2026-09-29

Phase 2.5: the meshes on the 3D stage, placed by what you see.

### Added
- **Stage & Meshes** (Phase 2.5, `core/stage3d.py`, tab under *Build the rig*):
  - **Plan** and **front** views of the 3D stage with the fixtures and the meshes (band members, risers, truss …); drag a mesh to move it (10 mm steps).
  - Meshes are placed by **what you see** — centre X from the left edge, centre Z from the back edge, **bottom above the floor** — and written back as QLC+'s `XPos/YPos/ZPos` (which depend on how the model was drawn: a 1.8 m character with its feet at 0 needs `YPos −900` to stand on the floor). The list flags meshes that **float** or **sink**; **⤓ On the floor** / **⤓ Put all on the floor** fixes them exactly (from the model's vertices, after rotation and scale).
  - Rotation and scale that keep the model on its spot and on the floor; name; relink the model file; duplicate; remove.
  - **Place one or several meshes** (Shift/⌘-click to select several; *Select all* / *None*): **to the stage edges** — left, right, back, front, centre (the selection moves as a group, keeping its spacing; optional gap to the edge); **on the floor** / **to the ceiling** (each mesh); **line up** left / centre / right edges, backs / centres / fronts, bottoms / tops; **space evenly** between the outer two (left–right, back–front) or **across the whole stage** width / depth; **nudge** by a step with buttons or the **arrow keys** (PgUp/PgDn for height, Shift = fine). Dragging one of several selected meshes moves them all. (`stage3d.arrange()`)
  - **Add a mesh** from your folders of `.obj` models (remembered in `~/.qlc_swiss_knife/mesh_dirs.json`), or by path — centre of the stage, on the floor.
  - **Stage** type and size, meshes kept in place.
  - Undo, discard, and 💾 Save → new file `<name>_v<N+1>.qxw` + `<name>_v<N+1>_stage_report.txt`. API `/api/stage/*` (`op: arrange` for the placement tools).
- Wiki page *Stage and Meshes*: how QLC+ 5 stores and places meshes (`MeshItem`, `Res` paths, the placement formula, the floor height of each stage type).

## [1.7.0] — 2026-09-29

Phase 2.4: the VC Visual Editor now **builds** the Virtual Console, not only tidies it.

### Added
- **VC Builder** (Phase 2.4, `core/vc_builder.py`, in the VC Visual Editor). The right panel now has three tabs — **✥ Selection** (what you clicked: function, edit, position & size, look, copy/move; line up / size / grid / snap for several), **＋ Add & wire** (① new widget, ② wire to a function, ③ ready-made blocks) and **▤ Pages** (this page, new page, screen size, templates); with nothing selected it lists the shortcuts:
  - **Create** buttons, frames, solo frames, sliders, labels and CueLists in the selected frame (or the page) at the first free spot; **delete** (Delete key) and **duplicate** (⌘D, next to the originals, key/MIDI not copied).
  - **Stop all / Blackout** buttons are shown as such (they need no function).
  - **Wire** a button, a CueList (chasers only) or a slider (playback) to a function: from the selection panel, by double-clicking a function in the **function list** (search, type, and the naming profile's **group / effect letters**), or by **dragging a function onto the canvas** — onto a widget wires it, onto a frame or the page adds a button there (⌥ Alt: a CueList for a chaser).
  - **Drag to move**: drag a selected widget; positions snap to the grid (*while dragging*, on by default).
  - **Pages**: rename, move left / right, **★ First** (the page QLC+ opens on), delete.
  - **Label panel**: a frame of labels in columns — the naming profile's legend or your own lines.
  - **Arrange by name group**: a frame's buttons in one row per nomenclature group (the name prefix, e.g. `AS ·`), in the profile's order; without a profile, by function type.
  - **Screen profiles**: MacBook 1650 × 884, Full HD 1920 × 1080, tablet 1280 × 800, iPad 1024 × 768 — this page or all; optionally **scale** every widget in proportion.
  - **Page templates**: save a page (layout, colours, function *names*; no key/MIDI) and add it to another show as a new page — functions matched by name and type, the ones not found listed and left unwired (`~/.qlc_swiss_knife/vc_templates/`, or `$QSK_VC_TEMPLATES`).
  - **Setlist CueList**: wire a setlist chaser to the selected CueList, or add a new CueList for it on the page (Doctor D014 checks the chaser has steps).
  - Every change is undoable (↶ Undo) and saved with *💾 Apply & Save QXW…* as a new file. API: `/api/vc/op` (new operations), `/api/vc/builder-info`, `/api/vc/template`.
- `tests/manual/Festival_vc_builder.qxw` — a page built with the VC Builder, for the QLC+ open-check.

### Fixed
- Workspace Doctor didn't see the function of a slider in *playback* mode (`<Playback><Function>id</Function>`), so it could report that function as unused (D016) or miss a broken reference; removing a function (Doctor fixes, Rig Reducer) now also unlinks such sliders.

## [1.6.0] — 2026-09-29

Phase 2.3: build **looks** and **chasers** straight into a show — by palette and pattern, with BPM timing and a preview — into a new file.

### Added
- **Look & Chaser Builder** (Phase 2.3, `core/look_builder.py`, tab *Look Builder* under *Build the rig*):
  - **Looks** — fixture group × palette colour, one scene each. Palettes *warm*, *cold*, *scenic* (`core/looks/palettes.json`) and your own colours (colour picker). The colour is written by capability (`capability_map.encode`): RGB(W) mixing, the nearest colour-wheel slot, or dimmer only, so one "Amber" works on PARs and moving heads. **Every channel is declared** (shutter open, pan/tilt centred, the rest neutral). Level 5–100 %.
  - **Chasers** — patterns *all-hit*, *left/right* (halves or odd/even), *chase*, *ping-pong*, *build-up*, *random* (seeded: same seed, same chaser; *n* fixtures per step); colours per step or per fixture; off fixtures dark or a background colour; step time in **ms** or **BPM + note length** (1/1 … 1/16); **cut** or **fade** (a % of the step). Identical steps share one scene; step scenes live in the chaser's function folder.
  - **Song presets** — a chaser recipe saved by name: five built-in (`core/looks/presets.json`, e.g. *Drive — 8 steps, 280 ms, cut*) and your own (`~/.qlc_swiss_knife/look_presets.json`, or `$QSK_LOOK_PRESETS`).
  - **Simulated DMX preview** — the values written for each fixture decoded back into the colour they make: one strip per fixture, one cell per step, **▶ Play** at the step time.
  - Names follow the naming profile (*plain* → `Ceiling · Amber`; *two-letter prefix* → `AS · Amber`, `CD · Drive`); functions go into the folder *Look Builder/Looks* and *Look Builder/Chasers/…*; optional **new VC page** with a solo frame of coloured toggle buttons per group and one for the chasers; an existing **PANIC RESET script** also stops the new functions. 🔍 Check shows the changes and the new Doctor findings; new Doctor errors block the export; new file `<name>_v<N+1>.qxw` + `<name>_v<N+1>_looks_report.txt`. API `/api/looks/*`.
- `tests/manual/Festival_looks.qxw` — 6 looks and 5 chasers on the festival corpus show, for the QLC+ open-check.

### Fixed
- A new VC page (VC Visual Editor *New page*, Function Porter *new page*) copied the key/MIDI bindings of the first page (e.g. its *Enable* input) — the copy now keeps only the page's look.

## [1.5.0] — 2026-09-29

Phase 2 starts: the Workspace Doctor **fixes** what it finds, and the **Rig Reducer** turns a big show into one for a smaller rig — both always into a new file.

### Added
- **Rig Reducer** (Phase 2.2, `core/rig_reducer.py`, tab under *Build the rig*): keep some fixtures, remove the others with cascade — scene / sequence values, EFX entries, group heads (empty groups removed), 3D monitor items, functions left without fixtures or that lost all their steps (with the steps, script commands, show items, buttons, CueLists and sequences that used them), Level slider channels. Optional **re-patch** of the kept fixtures (name, universe, address — 1-based as in QLC+). **🔍 Preview** lists every change and only the *new* Doctor findings (renames don't count); the export is blocked on new Doctor errors; new file `<name>_v<N+1>.qxw` + `<name>_v<N+1>_reduce_report.txt`. API `/api/reducer/fixtures`, `/preview`, `/reduce`, `/save-report`. Festival_14fix → its 8 PARs: 6 fixtures, 3 groups, 11 functions, 6 VC widgets, 672 value sets removed, nothing new for the Doctor.
- **Workspace Doctor fixes** (Phase 2.1, `core/doctor/fixes.py`): opt-in fixes for D002, D003, D004, D005, D006, D007, D008, D010, D011, D015, D016 and D017, always written to a **new file** `<name>_v<N+1>.qxw` with `<name>_v<N+1>_fix_report.txt` next to it (changes, not fixed, still open); the original is never changed. Recommended fixes are the default; fixes that delete functions (D004, D015, D016) must be asked for. Deterministic. CLI: `python -m core.doctor show.qxw --fix [--remove] [--codes …] [--out …]`.
- **Workspace Doctor tab** (sidebar → Workspace tools): check the open workspace, findings grouped by code with the fix each one gets, tick boxes per finding and per group (✓ Recommended / ✓ All / ✗ None, *Show info*), **💾 Fix selected → new file…** with a Save dialog, the fix report saved next to it, before/after counts. API `/api/doctor/check`, `/fix`, `/save-report`, `/last-result`.
- **New checks**: **D017** PANIC RESET is a plain scene (it can't darken looks that are still running — seen when porting a real show; the fix wraps it in a script that stops everything first); **D010** the setlist page is not page 1 (info); **D011** widget outside its page or frame (> 8 px); **D013** chaser steps that last 0 ms; **D014** CueList runs a chaser with no steps.

### Changed
- Doctor: a script that only *stops* a function (e.g. a PANIC RESET) no longer counts as using it — unused functions are still reported (D016) and FX detection isn't affected. Corpus baselines: Festival_14fix and Pub_6fix now have one D017 each.

## [1.4.1] — 2026-09-29

Fixes from giopas's first real-show test of v1.4.0 (a real show's *1. SETLIST* page ported into a smaller rig).

### Fixed
- **Function Porter: "Source wins", the universe mapping, "Copy the input patch" and "Also copy bindings onto matching target widgets" had no effect from the app** — the server dropped these options on the way in (`_normalize_plan`), so every export used *keep unless already used*: the ported CueList lost its MIDI Next/Previous (and the Space key) and the target kept them. They now reach the Porter; a test drives the same Flask routes the UI uses (`tests/test_porter_input.py::TestThroughTheApi`). The 1.5 options `translate_types`, `strobe` and `qxf_paths` are passed through too.

### Changed
- **Porter step 4 warns about key/MIDI clashes before export**: "N key/MIDI binding(s) of the ported widgets are already used in the target and will be DROPPED: MIDI U2 ch 40 on '🚨 PANIC RESET' (target: 'STROBE BLIND!') … Choose 'Source wins' to move them" (info with *Source wins*, warning with *Keep all*); the check re-runs when you change the policy or the universe map.
- **A page ported onto a new page keeps its layout**: when everything comes from one source page and every unit fits where it was, the widgets keep their source positions — *1. SETLIST* no longer splits over two pages (*Ported from … (2)*). Otherwise first-fit placement as before.

## [1.4.0] — 2026-09-27

Phase 1 of the work plan: Quick Start, Function Porter and Show Book leave Alpha — deterministic output, Workspace Doctor on every export, tests on real show files.

### Added

- **Show Book — tests and accuracy pass** (Phase 1.3, `tests/test_showbook.py`, 24 tests on the corpus): section builders, DMX decoding with the corpus QXFs (dimmer %, capability labels, pan/tilt in degrees), CSV zip contents, PDF text layer. **VC Layout** is now built from the Virtual Console itself, page by page: every frame and widget in order with its ID (was empty), frame path and depth, position and size, function (or *(stop all functions)*), and **key / MIDI bindings** including CueList *Next / Prev / Stop* — it matches Pub_6fix's two pages and nested frames. New optional **Doctor summary** section (errors, warnings, info counts and every error/warning). Shows and Scripts now appear in the PDF and CSV too (`shows.csv`, `scripts.csv`, `doctor.csv`). Fixture definitions next to the workspace and in the installed QLC+ library are used automatically for decoding. The patch list shows the model without the manufacturer repeated.
- Show Book PDF: emoji are dropped instead of printed as `?` (typographic dashes, arrows and quotes mapped to plain ones); scene/chaser/collection titles no longer overlap the table above; empty EFX/scene/chaser/collection sections are left out. CSV zip and PDF are byte-identical run to run (fixed zip timestamps; `generate(date=…)`).
- **Porter step 4 — Key / MIDI input** panel: lists the source universes that VC bindings use (device, input profile, number of bindings), a target universe for each (with what the target has there), a live status (*same device already patched* / *will be patched* / *target has another device* / *won't respond*), *Copy the input patch* and *Also copy bindings onto matching existing target widgets*; binding policy *Source wins* added. Step 5 summarises the choices. API `GET /api/porter/inputs`. Browser-checked with the rebuilt MIDI Pub file → QuickStart_6fix.
- **Function Porter — MIDI / input control** (Phase 1.6, `core/porter_input.py`): ported key/MIDI bindings now bring the **input patch** they depend on — when the target universe has no input device, the source's `<Input>` (plugin, device, line, input profile) and `<Feedback>` are copied to it; the same device already there is fine; another device there is a warning (bindings kept, they will listen to that device). **Universe mapping** (`vc.universe_map`, e.g. source universe 2 → target universe 3) rewrites every ported `<Input Universe>` and patches the new universe. New binding policy **source wins** (`bindings="source_wins"`): a binding the target already uses moves to the ported widget and is removed from the target widget. **Bindings only** (`vc.bindings_only`): copy the key/MIDI bindings of source widgets onto matching target widgets (the ported copy of the same function, else the only widget of the same type with the same caption, letters/digits only — `🚨 PANIC RESET` ↔ `PANIC\nRESET`), creating CueList slots such as *Next* when missing. Option `vc.copy_input` (default on). The port report gains an **INPUT / MIDI** section: input patch copied / already there / other device, and every binding dropped, moved or copied with the widget that had it. Test case: Pub_6fix with a MIDI controller rebuilt (PANIC RESET ← ch 40, CueList Next ← 20, Previous ← 10) into QuickStart_6fix (no input → patch copied, Doctor D012 clean) and into a copy with the same controller already on ch 40 (keep-free names the conflict; source-wins moves it).
- **Capability translation between fixture types** (Phase 1.5, `core/capability_map.py`): scene values are decoded into an abstract look (dimmer level, colour, pan/tilt in degrees from centre, shutter open/closed/strobe) and written on a **different** fixture type's channels: RGB(W/A/UV…) mixing ↔ colour wheel (nearest slot by `Res1` colour or colour word), level on the dimmer or baked into RGB when the target has no dimmer, pan/tilt via the QXF `PanMax`/`TiltMax` (16-bit when the mode has fine channels, clamped), strobe mapped to the same relative speed (or dropped with `strobe="drop"`), everything else at the target's neutral value. Every target channel is declared; deterministic.
- **Porter — Sequences, EFX and gobos across fixture types** (Phase 1.5 part 2): Sequence **step values** (`fid:ch,val,…:fid:…`) are now remapped to the target fixtures like scenes (fan-in, translation by capability, every channel declared, `Values` count updated) — before, they kept the source fixture IDs. **EFX** drop the targets that can't run their mode (a *Position* EFX on a PAR; *Dimmer* / *RGB* EFX need an intensity / RGB fixture), noted in the report; an EFX left with no fixture is removed as before. **Gobo** wheels translate by slot number (*Open* stays open; wraps on a smaller wheel; dropped with a note on fixtures without one).
- **Porter step 3 — translation badge**: each mapping row says how values reach the chosen target: *↔ Different type — values translated by capability* (both fixture definitions known) or *⚠ Different type, definition missing — values copied channel by channel*. Candidates carry `translatable`; `POST /api/porter/fixture-candidates` accepts `qxf_paths`. **Step 4 Validate** previews the translation before export (`translation_preview()`): notes per source → target pair with counts (e.g. *strobe dropped (2×)*, *target has no pan; position dropped*) and a warning for every EFX target that will be left out.
- Porter step 3: when the target has **none** of the source's fixture types (e.g. a new Quick Start rig), the first Auto-Map uses *Fan-in by stage position* instead of *Every exact match* (which mapped nothing). Browser-checked with the Quick Start hand-off: Festival_14fix → QuickStart_club, all 14 rows show the translation badge, step 4 lists the translation.
- Capability translation: no false *target cannot make colour* note for a dark look on a colour-wheel fixture.
- Doctor D003 no longer reads Sequence step values as function references.
- **Quick Start → "➜ Port from an existing show"** (Phase 1.5, first version): after *Generate QXW* saves the new rig, a button in the Quick Start footer opens the Function Porter with that workspace already loaded as the **target**; pick the existing show as the source and port looks, effects and their VC buttons into the new rig (Auto-Map *Fan-in* pairs different fixture types; values are translated by capability; the target's PANIC RESET is extended; Doctor gates the export). The result is a new `<name>_v2.qxw` next to the Quick Start file.
- **Function Porter uses it for different fixture types**: when a source and a target fixture differ (model or mode) and both definitions are known, scene values are translated by capability instead of copied channel by channel (validation says so as *info*; the old warning stays for pairs without definitions; plan option `translate_types`, default on). The port report gains a *TRANSLATED BETWEEN FIXTURE TYPES* section with notes (e.g. position dropped on a PAR). **Fan-in Auto-Map across types**: source types with no same-type target are paired with unused target types, same family first (moving head / colour / dimmer, `capability_map.kind`), bigger source types first — e.g. Festival_14fix → QuickStart_club: 6 ceiling spots → 2 Intimidator Spot 110, 8 floor PARs → 4 SlimPAR 56; Doctor 0 errors / 0 warnings, byte-identical run to run. `auto_map()` and `POST /api/porter/auto-map` take optional `qxf_paths`. Sample output for the QLC+ check: `tests/manual/Festival_to_club_translated.qxw`.
- **Function Porter — Virtual Console porting**: the buttons, sliders, CueLists and frames of ported functions come along (`core/porter_vc.py`). Step 2 lists the source VC (pages, frames, buttons): tick a frame and *Select their functions* seeds the port with every function it uses. Step 4 chooses the target page (default: a new *Ported from …* page), the page name and the key/MIDI binding policy (*keep unless already used in the target* by default). Widgets get new IDs (`max + 1`, document order), keep their size and inner layout and are placed at the first free spot without overlapping; a continuation page is added when the page is full. Widgets whose function isn't ported are left out (reported); Level sliders keep only channels of ported fixtures and start at 0.
- **Function Porter — fan-in** (many source fixtures → fewer targets, e.g. 14 → 6): fan-out mode *Fan-in* and Auto-Map *Fan-in by stage position* (per fixture type, sources and targets in 3D stage order, split into equal neighbouring blocks). For every scene a target takes the values of the first source in its block that is lit, so chases still light something on every step and colours are never mixed. Auto-Map *Same fixture ID* for rigs reduced from the source (the Pub case). *Leave out source fixtures with no target* (e.g. ceiling spots when porting into a floor rig); scenes, RGB matrices and EFX left with no fixture are removed with every step and button that used them.
- **Function Porter — Doctor gate and report**: the export runs Doctor on the result and blocks it if the port adds errors the target didn't have; the import report (fixture blocks, ported and removed functions, VC placement, Doctor) is saved next to the new workspace as `<name>_port_report.txt`. APIs: `GET /api/porter/source/vc`, `GET /api/porter/target/pages`, `POST /api/porter/vc/seeds`, `POST /api/porter/save-report`, `GET /api/porter/last-result`; `auto-map` takes a `strategy`.
- **Function Porter — clean scenes**: ported scenes declare every channel of each target fixture (missing channels at the fixture's neutral value, as in Quick Start), so ported looks don't inherit LTP bleed (Festival_14fix → 0 Doctor warnings). RGB matrices get a matching fixture group in the target (an existing identical group is reused). A Quick Start **PANIC RESET** in the target is extended to stop the ported functions too (found by the live QLC+ check: ported looks survived the reset).
- Porter step 2 (after giopas's test): ticking a VC page/frame ticks everything inside (partly ticked frames show a dash); the VC list has its own ✓ All / ✗ None; dependencies resolve automatically as you tick (no *Resolve Dependencies* button — **Next** always works when something is ticked); Porter messages use the app's single status bar, so a stale "No workspace is open" from another action no longer sits under the Porter.
- **Function Porter — stage plans**: step 1 shows a top view of the source and target rigs (from the 3D monitor positions, drawn with the Fixtures tab's code; a note instead when a file has no positions). Step 3 shows the same plans coloured by the mapping — each target a colour, its source fixtures in the same colour, grey = no target. API `GET /api/porter/stage/<source|target>`; `core/fixture.stage_plan()`.
- Porter step 2: the Back / Next bar stays visible; the lists scroll above it (Next was pushed off-screen on smaller windows).
- **Porter step 3 — "Port this fixture"**: untick a source fixture you don't need; it gets no target, its values are left out, and functions/widgets that only light skipped fixtures are unticked in step 2 (you see it when going back; ticking the fixture again restores them). Other fixtures keep their mapping when the selection changes. `resolve_closure` returns `lit_fixture_map` (fixtures a function lights, > 0).
- **Porter step 3 — highlight**: hovering a mapping row rings that source fixture on the source plan and its target(s) on the target plan; clicking pins it.
- **Porter step 4 — remove existing target VC items**: tick pages, frames or widgets of the target's Virtual Console to leave them out of the new file (the target file is not changed); their space is reused for the ported widgets and a removed page can't be the "Place on" page. Listed in the report.
- Porter export: the finish screen and status bar say where the workspace **and the import report** were saved (or that the report couldn't be saved, with Copy Report).
- **Porter steps 4 and 5**: step 4 ends with **Next: Export** (no more "Import & Save"); step 5 shows what will be written and has the **💾 Export new QXW…** button, then the result (workspace, port report, Doctor). "Import report" is now called **port report** everywhere.
- `tools/qlc_check.py` waits for a look's fade-out after PANIC RESET before comparing (ported Festival looks fade out over 2–3 s).
- Tests: `tests/test_porter_fanin.py` — Festival_14fix → QuickStart_6fix fan-in and Festival_14fix → bare Pub rig (same IDs), both Doctor-clean and byte-identical run to run; VC pruning, bindings and placement; HTTP flow.

- **Quick Start — fixture groups** (step 3): name groups and tick their fixtures (default: one group per fixture name). Each group gets its own VC frame with a group dimmer (submaster), looks (On, Red, Blue, Green, Warm) and effects (Pulse, Color Fade, Chase), and a QLC+ fixture group (*QS · name*) ordered left → right for matrix effects. API `GET/POST /api/quickstart/groups`.
- **Quick Start — one button at a time**: whole-rig looks and effects sit in one solo frame, so pressing a button switches the previous one off (looks and effects no longer mix); each group has its own solo frame, so groups combine (Front Red + Floor Blue).
- **Quick Start — Audio React**: for fixtures with a sound-active / music mode (capability named Sound, Audio or Music), a whole-rig and per-group button that switches it on (named *Audio …* so Doctor treats it as intentional FX). The page fills the VC style's page width (1650 × 884 by default); the preview in step 4 fits the window and shows the button colours.
- **Quick Start — missing fixture definitions saved next to the workspace** (`<Manufacturer>-<Model>.qxf`, the name QLC+ looks for), **only for fixtures the installed QLC+ doesn't have** (its stock library + user folder are checked, `core/quick_start/qlc_library.py`); a warning if QLC+'s own definition lacks the chosen mode. Without the file QLC+ loads unknown fixtures as plain dimmers (no colour, RGB effects dark). API `POST /api/quickstart/save-qxf`.
- Real-show test corpus in `tests/corpus/` (`Festival_14fix`, `Pub_6fix`, two QXFs, `expected_baseline.json`, README with baseline findings), `tests/test_corpus.py`, and `tools/doctor_prototype.py` (throw-away reference for Doctor). The QXW round-trip and Merger/Porter namespace tests now also run on the real files.
- **Workspace Doctor — read-only engine and CLI** (`core/doctor`, `python -m core.doctor file.qxw`). `check(root, qxf_defs) → Report`; every finding has an ID, severity, location and message. Checks D001–D009, D012, D015, D016 plus info I001–I003 (see `docs/doctor.md`). D006 understands intent (a scene inside a strobe/flash/audio/macro function is FX), reads fixture capabilities (a *No flash* value is neutral) and supports an allow-list. Exits non-zero on errors. On the corpus: Pub_6fix has 0 errors and 0 warnings; Festival_14fix has 1 error (duplicate VC widget ID 0). The prototype’s 31 D006 false positives are gone. 37 tests in `tests/test_doctor.py`; exact corpus counts pinned in `expected_baseline.json`.
- Corpus: `QuickStart_6fix.qxw`, a Quick Start output (2 truss spots + 4 floor PARs) generated by `tools/make_quickstart_sample.py` through the real routes, plus a golden-file test proving Quick Start output is byte-identical run to run.
- **Quick Start — PANIC RESET** button next to *PANIC / BLACKOUT*. It is a Script that stops every generated function, then starts a *Reset: neutral state* scene and leaves it running (`stoponexit:false` — by default a QLC+ script stops what it started as soon as it ends); finally the script stops itself, because QLC+ 5 builds up to spring 2026 never end a script on their own (the button stayed on and every second press did nothing). The script also waits 100 ms before ending: in **QLC+ 5.2.2** (current release) a script whose code ends before the next engine tick loses its start/stop commands, so PANIC RESET did nothing (fixed upstream in August 2026). Checked headless in QLC+ 5.2.2, 5.2.1 and 4.14.5 via the web API, and by giopas on macOS with 5.2.2: looks, chasers and RGB matrices all reset, press after press (shutter open, no effects, Pan/Tilt centred, intensity 0). A plain scene is not enough: intensity and colour are HTP in QLC+, so a scene at 0 can't pull down a look that is still running. Clears Doctor D008.
- **Quick Start — naming profiles** (`core/quick_start/profiles/nomenclature/*.json`): *Plain names* (default) or *two-letter prefix* (1st letter = fixture group A F S B R D L X, 2nd = effect S D P M \*; e.g. `AS · Red`, `AD · Color Fade`, `A* · Strobe Fast`). Buttons show the prefix too; step 4 shows the legend. Profiles are plain JSON, so you can add your own.
- **Quick Start — VC style**: *Default*, the built-in *Compact* style, or **From a reference .qxw…**: button size, gaps, header height, fonts and page size are measured from any workspace (`core/quick_start/vc_style.py`) and used for the generated Virtual Console. Colours stay meaningful (a red button is a red look).
- **Quick Start — Doctor gate**: the export runs Workspace Doctor first; errors block it and are listed (warnings don't).
- Quick Start golden files for **three reference rigs** (`tests/corpus/QuickStart_{6fix,club,multiuni}.qxw`): 6 Eurolite/PAR; a club rig with Chauvet Intimidator Spot 110 in 6-channel mode + SlimPAR 56 (two-letter prefix names, Pub_6fix style); and 8 × Spot 375Z + 60 × SlimPAR 56 over two universes (style cloned from `Pub_6fix.qxw`). All three are Doctor-clean (0 errors, 0 warnings).
- **Live QLC+ check** (`tools/qlc_check.py`, `docs/qlc-live-check.md`): opens a workspace in a real QLC+ with web access, checks every VC widget loaded, then presses every Toggle button (it must light at least one fixture) followed by PANIC RESET (twice) and compares the DMX output with the neutral scene. Opt-in test `tests/test_qlc_live.py` (runs when `QLCPLUS_BIN` is set). Verified on QLC+ 4.14.5 and 5.2.2; it catches the Submaster and 5.2.2 script bugs found on 23 Sep.
- API: `GET/POST /api/quickstart/options` (naming profile, VC style by id, reference path or upload).

### Changed

- **Quick Start, Function Porter and Show Book are no longer Alpha** (badges removed). QXW Merger stays Alpha, VC Visual Editor Beta.
- Test corpus show files renamed `Festival_14fix.qxw` and `Pub_6fix.qxw`; band, venue and song names inside replaced by neutral ones (*Band A*, *Song 01*…). Built-in VC style renamed **Compact**.

### Fixed

- Doctor D012 no longer reports "no input device patched" for MIDI inputs saved by QLC+ 5.2.1 builds as `UID="<device>"` without a `Name`.
- **Function Porter output was not deterministic**: dependencies were ordered by iterating a Python set, so new function IDs could change between runs. They now follow discovery order.
- **Function Porter didn't port EFX fixtures or script references from real QLC+ files**: it looked for `<EFXFixture>` (QLC+ saves `<Fixture>`) and for `startfunction:` (QLC+ saves `startfunction%3A`).
- **Function Porter left values for unmapped fixtures in ported scenes** (dangling fixture references, or values landing on an unrelated target fixture with the same ID). They are now left out.
- Function Porter: new function IDs start above the highest *function* ID (they started above the highest fixture address/channel count); output is indented like QLC+'s own files; RGB matrices referenced a fixture group that didn't exist in the target.
- **Quick Start used the wrong DMX channels on multi-mode fixtures.** Channel positions came from the QXF's definition order instead of the selected mode, so e.g. an Intimidator Spot 110 in 6-channel mode got its dimmer on the wrong channel. Scenes, sliders and capability detection now follow the mode's channel list.
- **Quick Start looks left moving heads dark.** Channels a look doesn't use were forced to 0 — on fixtures like the Intimidator Spot 375Z, shutter 0 means *closed*. Unused channels now get a capability-aware neutral value (*Shutter open*, *No function*, *Open*/*White*, Pan/Tilt centred) read from the fixture definition (`core/quick_start/channel_model.py`). Blackout closes the shutter on fixtures without a dimmer channel.
- **Quick Start MASTER slider held every dimmer at full.** It was a *Level* slider on the dimmer channels starting at 255, so it kept intensity up (HTP) through BLACKOUT and PANIC RESET. It is now a **Submaster** (scales the looks, never forces a channel on).
- **QLC+ 5.2.2 dropped every VC widget after a Submaster slider.** Cause: QLC+'s slider loader reads one token too many after an empty `<Level/>`; our files were written on one line, so that token was the slider's end tag. Quick Start now writes indented XML like QLC+ itself.
- Doctor reads percent-encoded Script commands (`startfunction%3A12`, as QLC+ saves them) when following function references.
- **Quick Start RGB-matrix effects stayed dark** on fixtures with a master dimmer: QLC+ ignores the matrix *DimmerControl* flag in RGB mode. Each matrix button now runs a Collection (scene opening the dimmers + the matrix). "Full Row" (no such QLC+ script) is replaced by Chase (One By One) and Even/Odd; the vertical-stripes variant is dropped. Plasma uses the *Rainbow* preset: in QLC+ 5 its default is "User Defined" colours, which with one colour stays mostly black (found by the live check on the Mac). Verified on the DMX output in QLC+ 5.2.2 and 4.14.5.
- **Quick Start sliders showed 0 at the top in QLC+ 5**: QLC+ 5 reads a missing `InvertedAppearance` as true; sliders now set it to false.
- **Quick Start sliders did nothing** on their own: RED/GREEN/BLUE raised colour with the dimmer at 0 (and DIMMER raised a black fixture). Replaced by the MASTER and per-group submasters; the meaningless *Color Fixtures* button is gone (groups replace it).
- Chaser step scenes get their own names (*Dimmer Sweep: On / Off*, *Strobe Fast: On / Off*) instead of several identical *BLACKOUT*/*ALL ON* scenes.
- **Doctor D006 false positive**: a value of 0 on a capability with no "active" words (e.g. SlimPAR 56 `Mode = 0 (RGB)`, the plain operating mode) is no longer reported as a program channel.

---

## [1.3.2] — 2026-09-23

### Removed

- Stale duplicate Quick Start files `qxw_builder-1.py`, `quick_start_routes-1.py`, `quickstart-1.js` (older copies predating a950cc8).

### Fixed

- **VC Visual Editor right panel** was cut off (the lower tools sat in a small 260-px scroll box, and the *⚙ Panel* toggle did nothing because of a broken element ID). The whole panel now scrolls, the toggle works, and the duplicate-ID warning sits at the top of the panel.
- **macOS native window crashed at start (`KeyError: 'text_select'`)** when the virtual environment lived in an iCloud-synced folder: iCloud adds "file 2.js" duplicates that pywebview tries to load. `run.sh`, the macOS app launcher and the README now use `~/.venvs/swissknife` (or `$SWK_VENV`); an existing `.venv` in the project still works.
- **Function Porter wizard showed all five steps at once and stayed on "Loading…"**: the panels' CSS `display:flex` overrode the `hidden` attribute. Now one step at a time, and step 2 lists the source functions.
- **VC Visual Editor did not react to clicks** (no select, align or drag): the tab loaded the Virtual Console but never attached the canvas mouse handlers. They are now attached on first open.
- **Brightness was slow to open** (and looked empty meanwhile): the QXF search walked the app's own folder including `.venv`. Hidden, virtualenv and cache folders are now skipped (about 1.4 s → 0.05 s on the corpus).
- **Quick Start 3D tilt defaults**: fixtures are now aimed at the performers instead of straight down/up. Truss/ceiling 45° from vertical, floor 45° uplight, mid-height horizontal; direction comes from depth (upstage fixtures tilt downstage, downstage fixtures tilt upstage). New helpers `height_zone()` / `default_x_rot()` in `core/quick_start/qxw_builder.py`; the Quick Start canvas mirrors the same rule and draws beam direction in the side view. Per-fixture override unchanged.
- Brightness → “Fetch missing QXFs from GitHub” always failed with a hidden `NameError` (`_HTTP_HEADERS` was left behind when the GitHub helpers moved to `core/gh_fetch.py`); downloads now use `gh_get_raw()`.
- **Trigger Manager no longer overwrites the loaded workspace.** “💾 Save new version” writes `<name>_v<N+1>.qxw` next to the original (skipping names that already exist) through `core/qxw_io`, so the `<!DOCTYPE Workspace>` line is kept — the old in-place `ElementTree.write()` dropped it. “Save as new file…” now really downloads a new file (both buttons used to call the in-place save).
- **QXW Merger and Function Porter found 0 fixtures / 0 functions in real QLC+ files.** Both looked up plain tag names (`Engine`, `Function`) on trees parsed with the QLC+ namespace (`xmlns="http://www.qlcplus.org/Workspace"`); their tests only used namespace-free synthetic files. They now load with `qxw_io.load_qxw(strip_namespace=True)`, and `qxw_io.qxw_bytes()` restores the namespace on output. New `tests/test_real_namespace.py`.

### Added

- **VC Visual Editor — Undo**: **↶ Undo** button and ⌘Z / Ctrl+Z, up to 100 steps, covering panel edits, align/arrange tools, copy/move, new/duplicate page and *Fix duplicate IDs*. Server-side edits are undone from snapshots of the Virtual Console (`POST /api/vc/undo`). Pending edits now survive switching to another tool and back; *Apply & Save QXW…* suggests `<name>_v<N+1>.qxw` instead of `_edited`.
- **VC Visual Editor — copy / move across pages**: select buttons or frames, pick a target page or frame (or *➕ New page…*) and click **⧉ Copy** or **➜ Move**. Copies get fresh widget IDs (`max + 1`, deterministic) and, by default, drop key/MIDI bindings so they don't fire together with the originals (tick *keep key/MIDI on copies* to keep them). Moves keep IDs and bindings. New **Pages** section: **＋ New page** (styled like the first page) and **⧉ Duplicate page**. Everything stays in memory until *Apply & Save QXW…*; pending position edits are no longer lost when switching pages. If a widget ID is used twice (e.g. Festival_14fix: the MASTER SHOW page and the “AS · Ice Arena” button are both ID 0), the Pages section shows a warning with **🩹 Fix duplicate IDs**; the first widget in document order keeps its ID, the others get new ones. Backend: `core/vc_ops.py`, `GET /api/vc/pages`, `POST /api/vc/op`; 13 tests in `tests/test_vc_ops.py`.
- **VC Visual Editor — zoom and multi-select**: pinch or ⌘/Ctrl+scroll zooms around the mouse pointer, a plain scroll pans, and ⌘+ / ⌘− / ⌘0 zoom in, zoom out and fit. Shift- or ⌘-click adds or removes a widget. Dragging from anywhere draws a selection box; before, it only worked from empty space, which the frames cover. ⌘A selects every widget on the page and Esc clears the selection.
- `tests/test_version.py`: `VERSION` must match the latest CHANGELOG release, the README title and the UI. `app.py` now reads the version from `core/workspace.VERSION` instead of a hard-coded string (it said 1.3.1 while `VERSION` said 1.3.0).
- `tools/make_tilt_check.py` → `tests/manual/tilt_check.qxw`, a 6-fixture file for checking tilt in the QLC+ 5 3D view; `tests/test_orientation.py` (18 tests).
- `core/qxw_io.py` — the single QXW reader/writer: `load_qxw()`, `qxw_bytes()`, `write_qxw()` (atomic, refuses to overwrite protected source paths), `next_version_name()` / `next_version_path()` and `suffixed_name()`. `tests/test_qxw_io.py` covers round-trip, determinism, overwrite guard, versioned names, and a guard test that fails if any other module serialises a workspace.
- GitHub Actions CI (`.github/workflows/tests.yml`): `pytest` on Python 3.11 and 3.12 for every push and pull request; status badge in the README.

### Changed

- **No more paste-a-path fields.** Every file is picked with a 📂 *Browse…* button (native dialog) and shown as a name chip; the path fields and separate *Load* buttons are gone from Start, QXW Merger, Function Porter, Dictionary, Fixtures, Show Book and Quick Start. Picking a file loads it straight away. A paste-path field reappears only when the app runs in a plain browser without a native dialog. Show Book's *Browse folder…* now opens a real folder picker. Fixes the Merger/Porter rows overflowing so the *Load* button was hidden.
- **Sessions (.qsk) now restore every tool**: besides workspace, dictionary, setlist slot files and Brightness QXF assignments, a session saves the show name and date, Brightness slider values, Function Porter source + target, QXW Merger source + destination, Show Book folder and sections, and the PDF paper sizes. Opening a session from *Open .qsk*, the recents list or drag & drop now goes through one code path (they used to restore different things). Older `.qsk` files still load. Not saved on purpose: unsaved edits inside the workspace — save those as a new `.qxw`.
- **Opening files is the same everywhere.** The header strip has **📂 Open…** and **↻ Reload** on every screen; tools that need a workspace show a “No workspace open — 📂 Open workspace…” banner instead of sending you to Start. Every *Browse…* (QXW Merger, Function Porter) now uses the native file dialog like the Start screen, so files keep their real name (no more `tmpxw7vxz61`), and uploads keep the original name too. Merger and Porter gain **⤵ Open workspace** to reuse the file open in the header. Cancelling the native dialog no longer pops up a second, browser file dialog. Trigger Manager *Save new version* on a dropped/uploaded workspace opens a Save dialog instead of an error. Rules documented in the wiki (*Sessions and Files*).
- **Uniform action buttons.** Every tool footer now follows one pattern: a note on the left says what the tool writes (green = new `.qxw`, grey = TXT/PDF/CSV only, workspace untouched), secondary exports are grey buttons, and there is **one** primary teal button on the far right. Workspace-writing actions use 💾: *Generate QXW* (Setlist, Fixtures, Brightness, Quick Start), *Save new version* (Trigger Manager), *Apply & Save QXW…* (VC Visual Editor — was a small toolbar-style button), *Save merged QXW…* (QXW Merger — was a grey “Export”), *Import & Save QXW…* (Function Porter), *Save dictionary* (Dictionary). Wrong footer notes fixed (Dictionary, Checklist, ID Browser said they wrote a `.qxw`; Tech Rider had none). `tests/test_ui_consistency.py` keeps it that way.
- **App updates always show up**: CSS/JS URLs carry a version hash (`?v=`) and static files are served with `no-cache`, so the native window no longer runs stale JavaScript after an update.
- The **Triggers** tab is renamed **Trigger Manager** (sidebar and page title), matching the docs and wiki.
- Tests consolidated under `tests/` (`test_porter.py`, `test_qxf_parser.py`, sample QXFs now in `tests/fixtures/`); `pytest.ini` added, so `python -m pytest -q` runs the whole suite from the repo root. The 27 failing Quick Start tests were stale (3-tuple `generate()` return, 400 on invalid requests, the 80d0340 VC layout and effect names) and were updated; none was a code bug.
- All workspace outputs (Setlist generate, Brightness, Fixture Configurator, Merger, Porter, Quick Start, ID Browser export, Trigger “save as new”) now go through `core/qxw_io`, so the XML declaration and `<!DOCTYPE Workspace>` are always present. Suggested file names now follow one rule: `<name>_v<N+1>.qxw` (or `<name>_v2.qxw` when the name has no `_vN`), replacing `_GIG_READY`, `_BRIGHTNESS`, `_merged`, `_imported` and `_modified`.
- Docs: `ROADMAP.md` rewritten from the new work plan; `WORKPLAN.md` added (plan of record); `DEVELOPMENT.md` gains the engineering principles, test command and git workflow; old `RELEASE_NOTES_*.md` moved to `docs/release-notes/`; `Claude outputs/` (scratch mockups) is no longer tracked.

### Security

- The native “Save As” helper (`/api/picker/save-blob`) refuses to overwrite the loaded source workspace.

---

## [1.3.1] — 2026-09-22

### Changed — UI density & shell pass

- **Global metrics strip** (`#metrics-strip`): new persistent bar at the top of the content area showing the loaded workspace name and live Fixture / Function / VC Widget counts. Populated by extending `_updateHeader()` in `app.js` — reuses `get_state()`'s existing `fixture_count` / `func_count` / `vc_widget_count` fields, no new backend endpoints.
- **Global status bar** (`#app-statusbar`): `setStatus()` now docks its messages into a persistent bar at the bottom of the content area instead of spawning a floating toast in the corner. Falls back to the previous floating-toast behavior if `#app-statusbar` isn't present.
- **Denser tables**: reduced cell padding on `.gridjs-td` (6px → 4px) and `.custom-table td` (5px → 4px) for a tighter, more workstation-like feel across Triggers, ID Browser, and Dictionary.
- `index.html`: new `.metrics-strip` and `.app-statusbar` elements as direct children of `<main id="content">`, above/below the `.screen` panes — persistent across every tool since `main` is a flex column and each `.screen` already fills remaining height.
- `style.css`: new `.metrics-strip` / `.ms-*` / `.app-statusbar` component styles built from existing design tokens.
- No breaking changes; no new dependencies.

---

## [1.3.0] — 2026-09-10

### Added — Function Porter *(Alpha)*

- **Function Porter tab**: import functions from any source `.qxw` workspace into your loaded workspace — the intelligent alternative to QXW Merger for function-level transfers
  - **Dependency resolution**: automatically detects and includes nested dependencies (Scenes inside Chasers, Chasers inside Collections, etc.) so nothing breaks on import
  - **Fixture remapping wizard**: when source fixtures don't exist in the destination, an interactive modal lets you remap each source fixture to an existing destination fixture — channels are re-mapped automatically based on QXF definitions
  - **Conflict detection**: warns when function names or IDs already exist in the destination; IDs are remapped above the highest existing ID
  - **Multi-select with filters**: browse source functions by type (Scene, Chaser, Collection, EFX, etc.) and name; tick individual items or use Select All
  - **QXF-aware channel mapping**: when fixture definitions are loaded, the porter maps channels by capability (Pan → Pan, Dimmer → Dimmer) rather than by raw offset
- New module: `core/porter.py` — dependency walker, fixture remapper, ID rewriter
- New module: `core/qxf_parser.py` — deep QXF channel parser with `decode_value()` for human-readable DMX labels (shared by Porter and Show Book)
- New API blueprint: `/api/porter/` with endpoints for loading source workspaces, analyzing dependencies, remapping fixtures, and executing the import
- New UI: sidebar entry with package icon, source workspace loader, function browser, remap modal
- New test suite: `tests/test_qxf_parser.py` — 52 unit tests for the QXF deep parser

### Added — Show Book *(Alpha)*

- **Show Book tab**: export your entire workspace as structured show paperwork — PDF or CSV — with decoded DMX values
  - **10 configurable sections**: Summary, Patch List, Function Index, Scenes (with decoded DMX channels), Chasers (with step timing), Collections, EFX, Shows, Scripts, VC Layout
  - **DMX value decoding**: when QXF fixture definitions are provided, raw DMX values (0–255) are translated to human-readable labels (e.g. "Red" → 255, "Gobo 3", "Strobe Slow→Fast @ 60%")
  - **Section picker**: checkboxes to include/exclude any section, with Select All / None buttons
  - **Live preview**: generate an in-app preview before exporting — tables with sortable columns, scene breakdowns by fixture, chaser step timing
  - **PDF export**: A4 landscape PDF with cover page, table of contents-style summary, and all selected sections — pure Python, no external PDF library
  - **CSV export**: ZIP archive with one `.csv` file per section for spreadsheet workflows
  - **Collapsible sections**: click any section header or individual item (scene, chaser, etc.) to collapse/expand its detail view; Expand All / Collapse All buttons for quick toggling
  - **Clickable Function Index**: rows for Scene, Chaser, Collection, EFX, Show, and Script types link directly to their detail entries — click to smooth-scroll, auto-expand, and highlight
  - Preview truncation: tables capped at 100 rows, scenes at 50, with a note when data is truncated
- New module: `core/showbook.py` — document generator, PDF builder, CSV/ZIP exporter
- New API blueprint: `/api/showbook/` with endpoints for preview, PDF export, CSV export, and section listing

### Changed

- `app.py`: registered `porter_bp` and `showbook_bp` blueprints
- `app.js`: added lazy initializers and invalidation hooks for Porter and Show Book tabs
- `index.html`: new sidebar entries (Function Porter, Show Book) and corresponding screen sections
- `style.css`: new component styles for Porter (`.porter-*`) and Show Book (`.sb-*`)

---

## [1.2.0] — 2026-09-06

### Added — Quick Start QXW Generator *(Alpha)*

- **Quick Start tab**: 5-step wizard that generates a ready-to-run QXW workspace from scratch in ~5 minutes, even with zero QLC+ experience
  - Step 1: Load QXF fixture definitions from local files, uploads, or the **Browse QLC+ Library** button (fetches from the [official QLC+ GitHub repository](https://github.com/mcallegari/qlcplus/tree/master/resources/fixtures) — the only external network call in the app)
  - Step 2: Interactive stage placement with a 2D top-down canvas — drag fixtures, multi-select, alignment tools (align left/right/top/bottom, distribute evenly), configurable stage dimensions, and auto DMX assignment
  - Step 3: Automatic fixture capability analysis (RGB, strobe, pan/tilt, dimmer, gobo)
  - Step 4: Intelligent VC layout preview — auto-generated macros (ALL ON/OFF, BLACKOUT), fixture group selectors, pre-configured scenes (Warm White, Cold White, Colors), skeleton effect chasers (Dimmer Sweep, Color Fade, Strobe), and four custom slots
  - Step 5: Summary and one-click `.qxw` export
- New modules: `core/quick_start/` (fixture_analyzer, vc_generator, qxw_builder, template_library)
- New API blueprint: `/api/quickstart/` with endpoints for the full wizard workflow
- New UI: sidebar entry with bolt icon, step-indicator navigation, card-based wizard layout
- New test suite: `tests/test_quick_start.py` — 60+ unit and integration tests

### Added — Show Info, Tech Rider & Setlist Enhancements

- **Show name & event date fields** on the Start screen, saved in session (`.qsk`). Used for PDF headers, export filenames, and session metadata.
- **Tech Rider Generator tab**: fixture type summary grouped by manufacturer/model/mode with PDF export
- **Setlist multi-export**: combined PDF export across multiple slots with checkboxes in the slot list UI
- **Setlist cue name resolution**: clone cue names are resolved back to their originals in multi-export

### Added — Session Management

- **Session save/load on Start page**: save and restore full workspace sessions (`.qsk`)
- **Close prompt after QXW generate**: prompts to save when switching workspaces with unsaved changes

### Fixed

- **Export in pywebview mode**: the Quick Start export button now works in native window mode (pywebview/WebKit). Switched from blob download (unsupported by WebKit) to a hidden-iframe GET request that triggers the browser's native file save. Previously the export silently failed or returned 403 Forbidden due to CSRF origin mismatch.
- **Step scrolling in pywebview**: Steps 1 and 2 now scroll when content exceeds the viewport height, so the Next button is always reachable in the native window.
- **Checklist PDF**: fixed blueprint being exported instead of the checklist table; split into two separate export buttons (blueprint PDF vs. checklist PDF)
- **Export filenames**: all export filenames are now derived from the showfile name; removed the double-save prompt dialog
- **Duplicate xmlns attribute** in `qxw_builder`: `ET.register_namespace` already adds the xmlns; the explicit `root.set("xmlns", ...)` duplicated it, causing XML parse errors
- **Inherited VC buttons in Setlist**: song functions whose VC button sits on a child look (e.g. the Scene inside a Collection) now resolve through the `contains` tree (`vc_inherited` field, cycle-safe, depth-limited). The Setlist shows the original button name for these songs; the "Has VC" pool filter also considers inherited buttons.
- **Generation integrity check**: every QXW generation now runs a sanitation pass — strips empty/dangling `<Step>` elements and unreferenced empty auto-generated setlist chasers from previous iterations, renumbers steps
- **Purge Clones improvements**: detects attribute-based clones (`SwissKnifeClone` flag) with legacy suffix as fallback; also catches structural duplicates (Scenes included) from pre-tag versions; re-points song assignments to surviving originals instead of unassigning; clarified cleanup tooltips

### Security

- **QXF file size cap**: fixture definition uploads are now rejected above 5 MB before XML parsing, preventing oversized payloads
- **Content-Disposition quoting**: the filename in download headers is now properly quoted, preventing issues with special characters in project names
- **SSH keys untracked**: removed accidentally tracked SSH keys (already in `.gitignore`)

### Documentation

- **Internet access note**: README and Quick Start section now clearly state that the "Browse QLC+ Library" button fetches fixture data from the official QLC+ GitHub repository — the only external network call in the app. All other features work entirely offline.
- **Expanded Security section**: added Network access subsection, XML size-cap mention, and Content-Disposition hardening note to README
- **Show info layout**: compact inline row with tooltips explaining purpose (PDF headers, filenames, sessions)

### Technical

- `FixtureCapabilities`: regex-based channel name analysis for capability detection
- `RigCapabilityAnalysis`: whole-rig grouping into moving_heads, color_fixtures, dimmers_only, other
- `VCLayoutGenerator`: auto-generates Scenes, Chasers, and a 4-frame VC hierarchy
- `build_qxw()`: standalone QXW XML builder — no template dependency
- Separate Quick Start rig state to avoid interfering with existing Fixture Configurator
- Refactored `pdf.py`: extracted `_build_setlist_pages` for reuse, wired `doc_date` param
- `build_table_pdf`: new generic table-to-PDF builder for Tech Rider and Checklist exports

---

## [1.1.1] — 2026-07-06

### Added — Standalone app experience

- **Quit button**: red power-icon button at the bottom of the sidebar shuts down the Flask server cleanly via `POST /api/quit`. Prompts for unsaved session changes before quitting.
- **Native window mode (pywebview)**: if `pywebview` is installed, the app opens in a native OS window (WebKit/EdgeChromium/GTK) instead of a browser tab. Closing the window stops the server. Falls back to browser mode automatically. Use `--browser` flag to force browser mode.
- **Platform launchers** (`launchers/` directory):
  - macOS: `create-macos-app.sh` generates a `.app` bundle for Launchpad / Dock.
  - Windows: `QLC_Swiss_Knife.bat` double-click launcher (hides console via `pythonw`).
  - Linux: `qlc-swiss-knife.desktop` for the application menu.
- **Session save on workspace switch**: when loading a new workspace while the current session has unsaved changes, a prompt offers to save the session named after the previous showfile (e.g. `MyShow.qsk`).

### Fixed

- **File saves in pywebview mode**: all file-save operations (QXW generate, session save, merged workspace export, brightness export, dictionary/checklist/setlist exports, CSV exports, PDF exports) now work correctly in the native window. A new `saveFileWithPicker()` helper tries: (1) `showSaveFilePicker` (Chrome/Edge), (2) native OS dialog via `/api/picker/save-blob`, (3) `<a>` download fallback. Previously, saves silently failed or showed raw file content in pywebview because browser download APIs are unavailable in the embedded WebKit view.

### Changed

- `run.sh` now passes CLI arguments to `app.py` (supports `--browser`), prints a hint when pywebview is not installed.
- VC Visual Editor statusbar version is now injected via template variable instead of hardcoded.
- Updated `.gitignore` to exclude generated `.app` bundles and sensitive files.

### Dependencies

- `pywebview>=5.0` added to `requirements.txt` as an optional dependency.

---

## [1.1.0] — 2026-07-05

### Changed — Complete GUI redesign

- **Sidebar navigation**: replaced the flat 9-tab bar with a collapsible left sidebar grouping tools into three workflow categories (Run the show, Build the rig, Workspace tools). Collapse/expand state persists in localStorage.
- **Start screen**: new landing page with personalised greeting, drag-and-drop open zone for `.qxw`/`.qsk` files, recent-files list (last 5, persisted in localStorage), about section, and workflow guide cards.
- **Design tokens**: three-theme system (dark / grey / light) now driven by CSS custom properties via `data-theme` attribute on `<html>` instead of body class swaps. All hard-coded colours replaced with token references.
- **SVG icon sprite**: all UI chrome emoji replaced with a consistent Lucide-style SVG symbol sprite (`static/icons.svg`).
- **Page headers**: every tool page gets a uniform `.page-h` header with icon tile, title, one-line description, and theme toggle.
- **Output footers**: colour-coded footer on every tool page — green for tools that write a new file (original untouched), orange for Triggers (the only tool that overwrites the loaded workspace).
- **Files panel**: sidebar footer shows loaded workspace, dictionary, and QXF file state plus session controls, replacing the old header bar and status bar.
- **Nav tooltips**: hovering any sidebar item shows a floating tooltip with the tool name and description, positioned via JS to avoid sidebar overflow clipping.

### Added

- **Triggers — Save as new file**: ghost button in the Triggers output footer to save trigger edits to a new `.qxw` file instead of overwriting the loaded one. New `POST /api/triggers/save-as-new` route.
- **Settings endpoint**: `GET /api/settings` returns `user_name` (from `settings.json` or `getpass.getuser()`) for the Start screen greeting.
- **Session drag-and-drop**: `.qsk` session files can now be dropped onto the window alongside `.qxw` workspaces.
- **Recent files**: Start screen tracks the last 5 opened files with relative timestamps.

### Removed

- Old `<header id="app-header">`, `<nav id="tab-bar">`, and `<footer id="status-bar">` replaced by sidebar and page headers.
- Emoji-based UI icons replaced by SVG sprite throughout.
- Body class theme switching (`theme-grey`, `theme-light`) replaced by `data-theme` attribute (backward-compat aliases kept).

---

## [1.0.10] — 2026-07-03

### Added — Brightness: baseline dimmer indicator

- Each fixture group now shows a coloured **⟂ X%** pill reflecting the actual peak dimmer value stored in the loaded workspace's scenes. Green = full power, red = heavily dimmed. When multiple groups are present, a **−X%** offset shows which groups are already dimmed relative to the brightest one — so you can immediately see if a previous brightness-scaling session left groups at different levels, even though all sliders start at 100%.

### Changed — VC Visual Editor promoted to top-level tab

- The VC Visual Editor has been moved from a sub-tab inside ID Browser to its own tab in the main navigation bar, between QXW Merger and Brightness. Renamed from *VC Editor* to **VC Visual Editor** with a β badge. No functionality changes.

---

## [1.0.9] — 2026-07-01

### Added — VC Layout Editor (β)

- New **VC Editor** sub-tab inside ID Browser (later promoted in v1.0.10). A canvas renders the entire Virtual Console at the correct position, size, and colour of every widget.
- **Selection**: click to select, shift-click for multi-select, drag a rubber-band rectangle.
- **Properties panel**: editable X/Y/W/H, font size, bold, background and font colour swatches.
- **Alignment**: left/centre/right, top/middle/bottom alignment of selected widgets.
- **Distribution & sizing**: equal horizontal/vertical distribution, match width/height to first selected, fit-to-text.
- **Grid arrange**: configurable columns, gap X/Y, sort order (position, A–Z, natural #, colour hue, widget ID).
- **Sort in place**: sort siblings by alpha, natural, colour, or ID within the same parent frame.
- **Snap to grid**: configurable pixel grid.
- **Alignment mask mode**: colour-codes every widget by how far it deviates from its row/column neighbours (configurable minor/major thresholds).
- **Apply & Save QXW…**: patches the in-memory XML and opens a native Save dialog — source file never overwritten.

### Fixed — ID Browser: VC Widget X/Y/W/H columns

- X, Y, W, and H were always blank in the VC Widgets table. They are now correctly read from the `<WindowState>` child element of each widget in the QXW.

---

## [1.0.8] — 2026-06-29

### Changed — Setlist: per-slot file paths replace global backup

- Each setlist slot now tracks its own `.txt` file path (mirroring how Brightness tracks QXF paths per fixture). Load a slot file with **Load Slot File** and save it with **Save Slot File**.
- The per-slot file format includes full song→function assignments (`txt_name|qxw_id|qxw_name|in|hold|out`), so Re-Match and all timing data survive a server restart.
- The all-slots global backup input has been removed.
- Session files (`.qsk`) store the per-slot paths and restore everything on load.

---

## [1.0.7] — 2026-06-27

### Added — Session / Project File (.qsk)

- Save all the file paths used in a session — workspace, dictionary, setlist backup and fixture QXF overrides — to a `.qsk` file.
- On next launch, open the session file via **Session → Open Session…** and the app re-loads everything automatically.
- A dirty-state indicator (●) appears if paths change since the last save, and closing the tab while there are unsaved changes shows a browser confirmation prompt.
- The **Change…** button next to each path pre-fills the header input so you can quickly swap to a different version of the same file without re-navigating to the folder.

---

## [1.0.6] — 2026-06-26

### Added — Brightness tab (Alpha)

- New tab for programmatic per-fixture brightness adjustment across an entire show file. Load a workspace, see every fixture type grouped by model and mode, then drag a slider to scale the Master Dimmer channel across all Scenes.
- Dimmer channel detected automatically by parsing QXF fixture-definition files from standard QLC+ install paths (macOS app bundle, Linux system install, user fixture directories). If a QXF is not found, type the dimmer offset manually or upload the QXF directly.
- **Linked-group mode**: moves all fixtures of the same model/mode together. Toggle per-fixture control with the "Link group" checkbox.
- Scale range: 0–200% (0 = channel always off, 100% = unchanged, 200% = maximum brightness, clamped to 255).
- Preview counter shows how many scenes and channel values will change before you commit.
- Output is a new file — original workspace never modified.

### Fixed — Setlist: Generate QXW saves all cuelists at once

- Clicking "Generate QXW" previously regenerated only the currently-selected cuelist slot. It now processes every slot that has at least one song with a function assignment, and outputs a single ready-to-use QXW file in one click.

### Fixed — Setlist: clone names no longer show (Setlist) suffix in QLC+

- Generated clones are now marked with a custom XML attribute (`SwissKnifeClone="<base_id>"`) rather than a name suffix, so QLC+'s Show Manager displays clean song names. The attribute is a QLC+-unknown extension that QLC+ ignores, so it has no effect on playback. Files generated by earlier versions (with the `(Setlist)` suffix) continue to be recognised for backward compatibility.

### Fixed — Setlist: cuelists with songs but no assignments no longer wiped

- When "Generate all" was introduced, a slot that contained songs but had no function assignments yet would silently clear its chaser. The generator now skips any slot without at least one assigned function, so existing cuelist content is always preserved.

---

## [1.0.5] — 2026-06-25

### Fixed — Setlist tab: assignments lost when switching slots

- Song function assignments were silently discarded whenever you clicked a different CueList slot. The slot data was re-fetched from the server on every slot switch, overwriting any in-memory changes that hadn't been explicitly saved with 💾 Save Songs. The current slot is now saved automatically (and silently) before switching, so assignments are never lost on navigation. The explicit Save Songs button still works as before.

---

## [1.0.4] — 2026-06-25

### Added — Setlist tab: multi-select songs for bulk assignment

- **Ctrl+click** (or ⌘+click on macOS) toggles individual song rows in the selection; **Shift+click** range-selects from the last anchor.
- All selected rows are highlighted. Clicking a pool function (or pressing ◀ Assign) assigns it to **all selected songs at once**.
- ✕ Clear Song also clears all selected songs in one operation.
- The timing panel shows "— N songs selected —" and disables when multiple rows are active.

### Added — Setlist tab: 🧹 Purge Clones button

- New button in the Assign section unassigns all songs currently linked to `(Setlist)` clones, clearing the slate for fresh matching. Clone function definitions remain in the workspace.

### Added — Setlist tab: 🗑 Delete Clones from WS button

- New **Workspace** section in the Actions pane with a "Delete Clones from WS" button. Unlike Purge Clones (which only unassigns songs), this **removes the `(Setlist)` clone function definitions entirely** from the in-memory XML tree and all state maps. Any songs still assigned to those clones are also unassigned. Use Generate QXW afterwards to save a clean output file without old clones — ideal for starting fresh with a different set of functions without bloating the workspace.

### Fixed — Setlist tab: auto-match prefers base functions over clones

- When both a base function (e.g. `"Stage Patter"`) and its clone (`"Stage Patter (Setlist)"`) exist in the pool, the four-stage auto-matcher now always picks the base function. Clones are still returned when they are the only candidate (e.g. in a gig-ready file where the originals have been removed).

### Fixed — Setlist tab: parent name always shown for (Setlist) clones

- Previously, the `↑ [ID] Parent Name` line below a clone assignment was silently omitted when the base function had been removed from the workspace (e.g. in a gig-ready file). It now always shows the derived base name in dimmed italic so the clone's origin is always traceable regardless of which file is loaded.

---

## [1.0.3] — 2026-06-21

### Added — Dictionary tab: VC button name & frame filters

- **VC Button name filter**: a dedicated text input next to the existing filters lets you search within the VC button caption column specifically (independent of the general search box). Useful for quickly isolating all functions assigned to a button whose caption contains a known keyword.
- **Frame filter dropdown**: a new dropdown is auto-populated from every VC frame (container) found in the loaded workspace. Selecting a frame shows only the functions whose VC buttons live inside that frame. Nested ancestry is supported — a button inside a sub-frame matches its entire ancestor chain.
- **Backend — `vc_frames` field**: `/api/dictionary/` now includes a `vc_frames` array for each entry, listing the deduplicated ancestry of VC frames for that function's button(s). The general search box also searches within frame names.

### Added — Setlist tab: VC button & description in song list

- **Inline VC button name**: each assigned song in the song list now shows the 🎛 VC button caption (in blue monospace) below the function name, pulled live from the function pool.
- **Inline description**: if a description exists for the assigned function, it is shown below the VC button line in italic grey — matching the display style already used in the function pool panel on the right.
- Both lines are only shown when the corresponding data is available; unassigned songs and functions without VC buttons or descriptions are unaffected.

### Added — Setlist tab: show parent function for (Setlist) clones

- Assigned songs that map to a `(Setlist)` clone now show a **↑ [ID] Parent Name** line below the clone name, making it immediately clear which base function the clone was generated from. This helps when re-matching a setlist that was already used once, since auto-match correctly finds the existing clone but the original function wasn't obvious.

### Fixed — Setlist tab: function pool descriptions always up-to-date

- The function pool (right panel) now re-fetches functions every time the Setlist tab is visited, instead of only on the first load. This ensures that descriptions entered or loaded in the Dictionary tab are immediately visible in the pool — which is the primary place descriptions help: identifying the right function to assign to each song.
- Added **↺ refresh button** to the QLC+ Functions panel header to manually re-fetch functions with the latest descriptions without switching tabs.
- **Browse TXT** in the Dictionary tab now syncs all imported descriptions to the server immediately (via new `/api/dictionary/bulk-update` endpoint), so the Setlist pool reflects them as soon as you hit ↺. Previously, Browse TXT was client-side only and descriptions never reached the server's shared state.

---

## [1.0.2] — 2026-06-11

### Added — Trigger Manager enhancements

- **Conflict detector — inline highlighting**: clicking 🔍 Duplicates now highlights conflicting rows directly in the table with a red left border, in addition to reporting the summary in the status bar. Hovering a highlighted row shows a tooltip. Conflict state clears automatically after a Bulk MIDI Shift or when data is reloaded.
- **Bulk MIDI Shift modal**: new ⇄ MIDI Shift button opens a dialog where you can enter a source universe + channel and a target universe + channel. All triggers bound to the source address are reassigned in one operation; the table reloads automatically and reports how many triggers were updated.
- **Assignment Matrix panel**: new ⊞ Matrix button toggles an inline grid panel showing every assigned widget (rows) against every unique key name (columns). Duplicate keys are flagged in red with a ⚠ marker in the column header. Clicking a ✓ cell or a widget row selects that trigger for editing in the side panel.

---

## [1.0.1] — 2026-06-05

### Fixed

- **Blueprint PDF — top-view Z orientation**: downstage/audience was rendered at the top of the plot and upstage/backstage at the bottom, the opposite of both the Swiss Knife canvas and the QLC+ 3D monitor. The Z axis mapping in `core/pdf.py` is now consistent with the canvas (`z = 0` → upstage/top, `z = max` → downstage/audience/bottom).
- **QXW Merger — source and destination loading**: path-only input made it impossible to load files on most systems. Both panels now have a **Browse…** button that opens a native file picker; selecting a file loads it immediately. Path entry still works as before.

---

## [1.0.0] — 2026-05-28

### Full rewrite: Tkinter → Flask web application

v1.0.0 is a ground-up rewrite of the application stack. The seven original tabs are fully ported to a browser-based single-page application (SPA) backed by a local Flask server. The user experience, feature set, and file formats are fully preserved; the delivery mechanism and architecture are new.

### Added — Flask / SPA architecture
- `app.py` — self-bootstrapping Flask entry point: auto-detects `.venv`, installs Flask guidance on first run, opens `http://localhost:5731` automatically.
- `templates/index.html` — single HTML shell with a tab bar, header, and status footer.
- `static/css/style.css` — full Catppuccin theme system: **Dark** (Mocha), **Grey** (Frappé), **Light** (Latte), toggled live with no page reload.
- `static/js/app.js` — tab switching, workspace loading (path mode + upload mode + drag-and-drop), ID Browser (Grid.js tables), CSV export.
- Per-tab JS modules: `setlist.js`, `dictionary.js`, `checklist.js`, `triggers.js`, `fixture.js`, `merger.js`.
- Blueprint-per-tab Flask routes: `workspace_routes.py`, `setlist_routes.py`, `dictionary_routes.py`, `checklist_routes.py`, `triggers_routes.py`, `fixture_routes.py`, `id_browser_routes.py`, `merger_routes.py`.
- `core/workspace.py` — QXW parser, function pool (with `find_best_match` four-stage fuzzy matching), setlist slot engine, slot-details CRUD, `generate_slot_qxw_content()` (returns bytes, not a file path).
- `core/pdf.py` — pure-Python PDF builder (no reportlab): blueprint PDF, setlist PDF, generic table PDF.
- `core/fixture.py` — rig state, QXF definition parsing, DMX auto-assign, canvas-to-workspace QXW generation.

### Added — QXW Merger tab (🔀)
- Load any two `.qxw` files independently of the main workspace via `core/merger.py`.
- Browse Fixtures, Fixture Groups, and Functions from the source file; filter by name or function type.
- Tick elements to copy; the merger assigns new IDs above the destination's highest existing ID and rewrites all internal cross-references (scene fixture vals, chaser step targets, etc.).
- Name-clash warnings displayed inline (⚠) — elements are still copied; user decides.
- Export the merged destination as a new `.qxw` via the native OS Save dialog (`showSaveFilePicker`) with `<a download>` fallback.

### Added — Setlist tab improvements
- FileBot-style three-column layout: Slot list | Song table | Function pool.
- Function pool: usage count (★N), setlist-clone indicator (✦ orange star), Used/Unused filter.
- Auto-match: maps all songs to QLC+ functions in one click using the four-stage fuzzy matcher.
- Per-song timing fields: Fade In, Hold, Fade Out (QLC+ ms values).
- QXW generation: no file written server-side — bytes streamed to browser, saved via `showSaveFilePicker`.
- PDF export: per-slot setlist PDF (paper size selector).

### Added — Header & UI
- Hover tooltips on all major buttons (`[data-tooltip]` CSS pseudo-element system).
- Theme toggle button cycles Dark → Grey → Light.
- Drag-and-drop `.qxw` anywhere on the window.

### Changed — Security hardening
- Upload handler: `.qxw` extension enforced; other extensions rejected with a clear error.
- CSRF protection: all `POST/PATCH/PUT/DELETE` requests validate `Origin` / `Host` against `localhost:5731`.
- Response headers: `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
- Exception messages: filesystem paths stripped via regex before being returned to the browser.
- Server binds to `127.0.0.1` only (localhost; never reachable from the network).

### Removed
- Tkinter desktop UI (`qlc_swiss_knife_0.7.3.py`) — superseded by the web UI. The file is kept in the repository for reference but is no longer the primary entry point.
- Output-directory input box in the header — replaced by the native OS Save dialog.

### Dependencies
- **Added:** `flask` (install once with `pip install flask` or via the provided `.venv` bootstrap).
- **Removed:** `tkinter` (no longer needed).
- Everything else (PDF generation, XML parsing, fuzzy matching) uses Python's standard library only.

---

## [0.7.3] — 2026-05-26

### New Tab: ID Browser — Functions & VC Widgets inspector

**Extended parser — `_parse_vc_node`**
The Virtual Console walker now captures every VC widget type: `Button`, `Frame`, `SoloFrame`, `Slider`, `Knob`, `SpeedDial`, `XYPad`, `Label`, `Clock`, `VUMeter`, `AudioTrigger`, `Animation`, and `CueList`. For each widget the parser stores: widget ID, type, caption, geometry (X / Y / W / H), linked function ID + name, and the full frame ancestry path. Results accumulate in a new shared list `app.vc_widgets`. The existing `vc_buttons` dict is still populated exactly as before — nothing in the other tabs is affected.

**Added — Tab 6: 🔍 ID Browser**

Two inner sub-tabs:

- **⚙ Functions** — all Engine functions from `func_detailed`. Columns: `ID`, icon, `Name`, `Type`, `Contains / Steps`.
- **🖥 VC Widgets** — all Virtual Console widgets from `vc_widgets`. Columns: `Widget ID`, icon, `Type`, `Caption`, `Func ID`, `Func Name`, `Frame Path`, `X`, `Y`, `W`, `H`.

Features shared by both sub-tabs:
- **Sortable columns**: click any column header to sort ascending; click again to reverse. Active sort column shows a ▲ / ▼ arrow.
- **Live filter**: search bar in the toolbar — filters across all visible columns simultaneously.
- **Export CSV**: dumps the currently visible view (with active filter and sort applied) to a UTF-8 CSV file via Python's built-in `csv` module — no extra dependencies.
- **Export PDF**: same raw-PDF renderer used by the Setlist tab, with a paper-size / font-size dialog. Landscape A4 default suits the wider VC Widgets table.

**Updated — status bar**
The status bar now shows `VC Widgets: N` alongside the existing workspace counts.

---

## [0.7.2] — 2026-05-26

### Security hardening release
*Fixes 9 security issues identified in a full static + manual audit of v0.7.1. No functional changes; all existing behaviour is preserved.*

**Fixed — MEDIUM: XML injection in "Export XML Code" (`export_txt`)**
The chaser name was embedded raw into an f-string XML template. A workspace with a specially crafted function name could produce an injected, malformed exported XML block. `xml.sax.saxutils.escape` (stdlib, zero new dependencies) is now applied to the name before embedding.

**Fixed — MEDIUM: Denial-of-service via oversized XML ("billion laughs")**
All four `ET.parse()` call sites (`load_qxw()`, `_parse_qxf()`, `_load_template_dialog()`, `_get_template_root()`) are replaced by a new `_safe_parse_xml()` helper that enforces a 50 MB file-size cap before handing off to the parser. Community-shared QXW/QXF files are a realistic delivery vector.

**Fixed — LOW: XPath injection via f-string query construction (6 sites)**
XPath predicates in `rename_chaser_to_cuelist()`, `SetlistSlot.save_qxw()`, `save_all_slots()`, and `DictionaryManagerTab.update_inspector()` were built by interpolating XML attribute values into f-strings. A new `_find_by_id()` helper iterates child elements directly instead, eliminating any possibility of XPath metacharacter injection.

**Fixed — LOW: Negative-index bypass in QXW generation (`_build_qxw`)**
Unassigned fixture slots stored `-1` in `_func_assignments`. The guard only blocked values ≥ `new_count`, so `-1` passed through and produced `<FixtureVal ID="-1">` — an invalid reference that silently breaks functions in QLC+. Guard changed to `0 <= idx < new_count`.

**Fixed — LOW: Unbounded file reads into memory (3 sites)**
`SetlistSlot.load_txt()`, `SetlistManagerTab.load_desc()`, and `DictionaryManagerTab.load_txt()` called `readlines()` with no size guard. A new `_safe_read_txt()` helper enforces a 5 MB cap before reading.

**Fixed — LOW: Unbounded integer parsing for DMX values (7 sites)**
Universe, address, and channel numbers from XML were converted with bare `int()` and no range validation. All sites now clamp to valid DMX ranges on parse (universe 0–255, address 0–511, channels 1–512).

**Fixed — LOW: TOCTOU race condition in file save (3 sites)**
`SetlistSlot.save_qxw()`, `SetlistManagerTab.save_all_slots()`, and `TriggerManagerTab.save_qxw()` checked `os.path.exists()` then opened with `open("w")`, creating a race window. Fixed by using Python's `'x'` (exclusive-create) open mode for new files.

**Fixed — INFORMATIONAL: Silent exception swallowing (2 sites)**
Two `except Exception: pass` clauses in `FixtureConfiguratorTab` now log a `[warn]` line to stderr instead of silently discarding errors.

**Fixed — INFORMATIONAL: Missing namespace validation in QXF parser**
If a non-QXF XML file was opened accidentally, `findtext()` calls would silently return `"Unknown"` for every field. A namespace check is now performed immediately after parsing and raises a clear `ValueError` if the root element is wrong.

**Added**
- `_safe_parse_xml(path)` — central XML parsing entry point with 50 MB size guard (replaces 4 direct `ET.parse()` call sites)
- `_safe_read_txt(path)` — central text-file reader with 5 MB size guard (replaces 3 direct `open()/readlines()` call sites)
- `_find_by_id(parent, tag_local, fid)` — safe XPath-free element lookup by ID attribute (replaces 6 f-string XPath constructions)
- `_findall_by_id(parent, tag_local, fid)` — as above, returns all matching children as a list

---

## [0.7.1] — 2026-05-22

### Setlist Manager — Chaser Step Hold Time Fix

**Fixed**
- Chaser steps with `Hold="0"` in the QXW XML were being misread as zero-duration holds. In QLC+, a value of `0` means "defer to the Chaser's Common speed setting" (effectively infinite). The parser now normalises `0` → `4294967294` (the explicit infinite sentinel) on load, so the UI displays and saves hold times correctly.
- When generating cloned Chasers, the `Speed` and `SpeedModes` blocks are now explicitly written with `Duration=4294967294`, `FadeIn=PerStep`, `FadeOut=PerStep`, and `Duration=Common`, ensuring per-step infinite hold is preserved correctly in the exported workspace.

---

## [0.7] — 2026-05-22

### Setlist Manager — Major Refactor: Multi-Slot Architecture

The Setlist Manager has been redesigned from a single-cue-list view into a **multi-slot system** where each slot corresponds to one QLC+ CueList / Chaser pair. This allows managing an entire show with multiple cue lists in a single session.

**Added**
- Inner notebook: each CueList detected in the loaded workspace gets its own dedicated tab (slot) inside the Setlist Manager.
- `+ Add Slot` and `× Remove Slot` buttons to manually add or delete slots at any time.
- Each slot shows the linked VC CueList caption for instant orientation.
- **"✎ Rename to CueList"** button: renames the underlying Chaser in the QXW XML to match its CueList caption — keeps the show file clean without manual XML editing.
- **"Unassign All"** button: clears all function assignments in the active slot in one click, with a confirmation prompt.
- Auto-link on workspace load: each slot automatically links to the CueList that matches its position.
- Per-slot PDF and TXT export, with slot label and CueList caption shown in the document header.

### Trigger Manager — VC Frame Parsing Fix

**Fixed**
- Virtual Console frame ancestry is now tracked correctly for **nested frames**. Previously, a button inside a sub-frame reported only its direct parent; it now correctly reports all enclosing frame names at every nesting level.
- The Frame filter in the Trigger Manager now works reliably regardless of how deeply buttons are nested.

---

## [0.6] — 2025

### Fixture Configurator — Function Assignment Panel

**Added**
- New collapsible **Function Assignment Panel** at the bottom of the Fixture Configurator tab.
- Displays all functions parsed from the template workspace, with their type, fixture slot count, and linked description (read from the Dictionary if loaded).
- **Intelligent auto-assignment**: when a template workspace is loaded, functions are automatically matched to rig fixtures using a multi-strategy algorithm:
  1. Name-role matching (e.g. "Front", "Back", "Wash")
  2. Spatial proximity (closest fixture to the template slot's position)
  3. Sequential fallback
- Manual override: per-function assignment can be edited directly in the panel.
- Assignment reads from the shared Dictionary when available, enriching function labels with human-readable descriptions.

---

## [0.5] — 2025

### New Tab: Fixture Configurator

**Added**
- Brand-new **Tab 5 — Fixture Configurator**: a visual stage design tool.
- Load one or more `.qxf` fixture definition files to populate a fixture library.
- Add fixture instances to the rig, set names and assign height roles (5 fixed tiers).
- **Interactive 2D top-down stage canvas**: drag fixtures to set X/Z positions visually.
- Configurable stage dimensions (width, depth, height in metres) via toolbar fields.
- **Auto-DMX**: automatically assigns consecutive universe/address values to all fixtures with one click.
- Load a `.qxw` template workspace (or reuse the one already loaded in the main shell).
- **Generate QXW**: produces a new `.qxw` file where the template's Engine/Fixture blocks are expanded to match the new rig, and 3D Monitor positions (`FxItem`) are updated from the canvas layout.
- Separate template path support: use a different workspace as a template without replacing the active working file.

---

## [0.4] — 2025

### Initial Unified Release

**Added**
- First release of QLC+ Swiss Knife as a unified single-file application.
- **Tab 1 — Setlist Manager**: build show cue lists from plain-text setlists, map to QLC+ functions, generate pristine clones, export PDF.
- **Tab 2 — Dictionary Manager**: create and edit ID→description mapping files to annotate the QLC+ function pool; shared across all tabs.
- **Tab 3 — Setup Checklist**: parse fixture patches, 3D positions, and groups from the workspace; export printable blueprint PDFs and text checklists.
- **Tab 4 — Trigger Manager**: audit and edit all Virtual Console keyboard and MIDI bindings in a spreadsheet-style table; write changes back to the workspace.
- Unified shell with shared workspace state: loading a `.qxw` file once populates all tabs simultaneously.
- Dark / light theme engine (Catppuccin-inspired palette) with per-session toggle.
- Zero external dependencies — pure Python 3 stdlib + tkinter.
- Cross-platform: Windows, macOS, Linux.
