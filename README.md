# QLC+ Swiss Knife v3.0.1

<p align="center"><img src="static/logo/icon-512.png" alt="QLC+ Swiss Knife logo" width="140"></p>

[![tests](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/actions/workflows/tests.yml/badge.svg)](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/actions/workflows/tests.yml)

**Build, adapt, check and document QLC+ 5 shows.** Swiss Knife opens your QLC+ workspace (`.qxw`) in a native window or your browser and does the long, fiddly jobs for you: a new show from your fixtures, the same show on a smaller or different rig, looks and chasers, the Virtual Console, the 3D stage, tonight's setlist, a health check, and the paperwork for the venue and the crew. You can also connect Claude, which then uses the same tools on the folders you choose.

Swiss Knife is tested with QLC+ 5.x: the output has been opened and run in QLC+ 5.2.2 and 5.3.0.

> ⚠️ **Independent project.** Swiss Knife is not affiliated with, endorsed by or connected to the QLC+ project or its team. All credit for QLC+ goes to the [QLC+ team](https://www.qlcplus.org/). Swiss Knife works on top of QLC+ workspace files.

![A festival show becomes a pub show: the guided route in Swiss Knife](screenshots/route.gif)

*A real festival show rebuilt for a small pub (6 PARs, tonight's 34 songs) in 12 minutes with the guided route. Step by step: [the tutorial](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Tutorial-Big-Venue-to-Pub).*

---

## How it works

1. **Open a show.** It becomes the **show in progress**, a working copy in memory.
2. **Use any tool, in any order, as often as you like.** The main button of each tool is **✓ Apply to the show**. The header counts the changes and shows the Workspace Doctor's verdict on the show as it is now.
3. **Go back** to any step in the **History** (undo, redo).
4. **💾 Save as new file…** writes `<name>_v<N+1>.qxw` with one report of every change and a *recipe* that the command line can replay to the same file. The file you opened is never overwritten.
5. **Do it again on another show.** Save your changes as a **Show Profile** and apply it to tonight's venue, next month's rig or a friend's show, in the app (History › *Do it again*) or from the command line: `python -m core.profile build Pub.profile.json --show Venue.qxw`. Each step finds what it changes by name, type and place, and tells you what it left out. See [Show Profiles](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Profiles).
6. **Ask Claude to do it.** *🔌 Connect to Claude* in the menu connects Claude Desktop or Claude Code to Swiss Knife. Claude can then open a show, run the Doctor, shrink a rig, port functions, build looks and chasers, edit the Virtual Console, turn a setlist into a chaser, compare two shows and draft the Dictionary descriptions. See [Claude and your shows](#claude-and-your-shows) below.

For jobs that take several tools, *guided routes* (for example *adapt a show to a new venue*) list the steps above the tools. See the [tutorial](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Tutorial-Big-Venue-to-Pub). Every tool has a **?** that opens its page in the [wiki](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/).

---

## The tools

The tools are grouped by job and numbered 1 to 6, like the side menu and the Start screen.

| | Tool | What it does |
|---|---|---|
| **1 · New show** | [Quick Start](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Quick-Start) | A ready-to-run show from your fixtures: looks, effects, fixture groups, PANIC RESET and a Virtual Console, in about five minutes. Fixtures without a dimmer get colour-wheel looks. |
| | [Fixtures](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Fixture-Configurator) | Place and patch a rig on a 2D stage, print a blueprint PDF, or save a rig-only workspace. |
| **2 · Adapt a show** | [Rig Reducer](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Rig-Reducer) | Keep the fixtures of a smaller rig. Everything that used the others is cleaned up, and you can re-patch. |
| | [Function Porter](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Function-Porter) | Bring looks, chasers, effects and their buttons from another show, with fixtures, groups and meshes. Copied fixtures can join the show's own looks (*plays like*), other fixture types are translated by capability, 14 fixtures can fan in to 6, and key and MIDI bindings come along. |
| | [Brightness](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Brightness) | Scale the master dimmer of each fixture type across every scene. Colours stay as they are. |
| **3 · Create** | [Look Builder](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Look-Builder) | Looks from a palette for your fixture groups, and chasers from a pattern with BPM or beats timing, moving-head positions, your own palettes, pixel-bar matrices, song presets and a playable preview. |
| | [VC Visual Editor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/VC-Visual-Editor) | The Virtual Console as a canvas: add and wire widgets, pages, templates and screen sizes, align, distribute and sort. |
| | [Stage & Meshes](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Stage-and-Meshes) | The 3D stage from above and from the front. Put band members and set pieces on the floor, aim fixtures at a mesh, hide meshes, and make and edit fixture groups. |
| | [Library](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Community-Library) | Share VC templates, palettes, look presets, naming profiles, VC styles and Show Profiles as one plain file, and install what other QLC+ users shared. Items are checked first, and there is no server. |
| **4 · Run the show** | [Setlist](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Setlist-Manager) | Tonight's songs from a text file, the clipboard or a CSV, matched to functions with fades, in the setlist CueList. Setlist PDFs, and one HTML page for a tablet on stage. |
| | [Trigger Manager](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Trigger-Manager) | Every keyboard and MIDI binding in one table: clashes, gaps, bulk MIDI shift, the input device of each universe and a MIDI simulator. |
| | [Dictionary](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Dictionary-Manager) | A description for every function, shown in the other tools. Swiss Knife drafts them from the show's colours and steps, and Claude can write them. |
| **5 · Check & fix** | [Workspace Doctor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Workspace-Doctor) | Finds broken references, scenes that leave channels unset, strobe left on, a PANIC RESET that cannot reset and more, and fixes them. Also from the command line. |
| | [Compare](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Compare) | This show next to another one, by what they do: patch, groups, looks (decoded colour and level), chasers, VC pages, setlist. |
| | [ID Browser](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/ID-Browser) | Every function and VC widget in sortable, filterable tables, with CSV and PDF export. |
| **6 · Document** | [Show Paperwork](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Paperwork) | The paper for each reader: a tech rider for the venue (it never carries your show's internals), a crew checklist for load-in, a patch sheet with DIP-switch diagrams (also as a thermal-printer ticket), and a show book for you, with a stage plot. PDF or CSV. |

**Language.** The interface speaks English, Italian and French. Pick it at the bottom of the left menu ([Language](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Language)). Shows, reports and the wiki stay as they are.

---

## Claude and your shows

Swiss Knife can act as an MCP server, which is the way Claude Desktop and Claude Code use outside tools. Once connected, you ask in plain language ("open Festival_14fix, run the Doctor and fix what is safe, save it as a new file") and Claude uses the same tools you use in the window. It can also write a description for every function in the Dictionary: the **🤖 Ask Claude…** button there gives you the request to paste in Claude Desktop.

Claude has a `guide` tool that explains any other tool, with its arguments and an example, and the connection offers Claude Desktop a few ready requests (write the Dictionary, check and fix a show, adapt a show to fewer fixtures, add buttons for looks that have none). The wiki page [Claude's tools](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Claude-Tools) lists every tool with the same text Claude reads.

**What Claude can reach.** Claude gets the folders you list and Swiss Knife's tools, nothing else on your computer. It cannot browse your disk, run commands, open other programs or use the network. A path outside your folders is refused. Claude only writes new files (the show, its report, its recipe, a dictionary `.txt`), never overwrites or deletes one, and every change is a History step you can undo. The Doctor refuses a result with new errors, as it does in the window.

**To connect Claude Desktop**, start Swiss Knife once, open *🔌 Connect to Claude* in the menu and click **Connect Claude Desktop**. Claude Desktop opens an install window and asks which folders to share. The same `…-claude.mcpb` file is attached to every release if you prefer to double-click it. The wiki page [Connect Claude to Swiss Knife](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Connect-Claude-to-Swiss-Knife) has the steps, example requests and troubleshooting, including the way for Claude Code.

---

## Screenshots

| | | |
|---|---|---|
| ![Quick Start](screenshots/02-quick-start.png) | ![Fixtures](screenshots/03-fixtures.png) | ![Rig Reducer](screenshots/04-rig-reducer.png) |
| Quick Start: the Virtual Console it will build | Fixtures | Rig Reducer: what will change |
| ![Function Porter](screenshots/05-function-porter.png) | ![Brightness](screenshots/06-brightness.png) | ![Look Builder](screenshots/07-look-builder.png) |
| Function Porter: map the fixtures | Brightness | Look Builder |
| ![VC Visual Editor](screenshots/08-vc-editor.png) | ![Stage & Meshes](screenshots/09-stage-meshes.png) | ![Setlist](screenshots/10-setlist.png) |
| VC Visual Editor | Stage & Meshes | Setlist |
| ![Trigger Manager](screenshots/11-trigger-manager.png) | ![Dictionary](screenshots/12-dictionary.png) | ![Workspace Doctor](screenshots/13-workspace-doctor.png) |
| Trigger Manager | Dictionary | Workspace Doctor |
| ![ID Browser](screenshots/14-id-browser.png) | ![Show Paperwork](screenshots/15-show-paperwork.png) | ![History](screenshots/16-show-in-progress.png) |
| ID Browser | Show Paperwork: tech rider with stage plot | The show in progress and its History |
| ![Start](screenshots/01-start.png) | ![Compare](screenshots/17-compare.png) | ![Library](screenshots/18-library.png) |
| Start: what do you want to do? | Compare: the rebuilt show next to the hand-made one | Library |

---

## Install

**Download, unzip, double-click** from the [latest release](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/releases/latest):

| Computer | File | Then |
|---|---|---|
| macOS, Apple silicon (M1 and later) | `QLC-Swiss-Knife-<version>-macos-arm64.dmg` | drag *QLC Swiss Knife* to Applications |
| macOS, Intel | `QLC-Swiss-Knife-<version>-macos-x86_64.dmg` | the same |
| Windows 10/11 | `QLC-Swiss-Knife-<version>-windows-x64-setup.exe` | run the installer (no administrator needed; Start menu entry, uninstaller). Or the `…-windows-x64.zip`: unzip, run `QLC Swiss Knife.exe` |
| Linux | `QLC-Swiss-Knife-<version>-linux-x64.tar.gz` | unpack, run `QLC-Swiss-Knife` (opens in your browser) |
| Claude Desktop (optional) | `QLC-Swiss-Knife-<version>-claude.mcpb` | double-click it after Swiss Knife is installed and has been started once |

The apps are not signed, so the system asks once. On macOS, right-click the app and choose *Open* (or run `xattr -dr com.apple.quarantine "/Applications/QLC Swiss Knife.app"`). On Windows, choose *More info › Run anyway*. Each release has a `SHA256SUMS` file to check the download.

When a newer version is out, a badge appears in the header. **Update and restart** downloads it, checks it and starts it again, and your shows and settings stay as they are. You can switch the check off with *Check for updates* under the menu. Details: [Installing and updating](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Installing-and-updating).

You can also run Swiss Knife from the sources (below). It is the same app, and the badge then tells you to run `git pull`.

---

## Requirements (to run from the sources)

| Requirement | Details |
|---|---|
| Python | 3.8 or newer |
| Flask | `pip install flask`, the only required dependency |
| pywebview | `pip install pywebview`, optional, enables native window mode |
| Browser | Chrome or Edge recommended (for the native Save dialog); Firefox and Safari also work |
| QLC+ workspace | `.qxw` format (QLC+ 5.x; checked with 5.2.2 and 5.3.0) |

---

## Install and run

### macOS / Linux, first time only

```bash
git clone https://github.com/giopas/qlc-plus-swiss-knife-tool-script.git
cd qlc-plus-swiss-knife-tool-script
python3 -m venv ~/.venvs/swissknife
source ~/.venvs/swissknife/bin/activate
python -m pip install -r requirements.txt   # flask + pywebview (native window)
python app.py
```

> **macOS: keep the virtual environment outside iCloud.** If the project lives in an iCloud-synced folder (Documents, Desktop), a `.venv` inside it gets "file 2.js" duplicates and the native window crashes with `KeyError: 'text_select'`. The commands above put it in `~/.venvs/swissknife`, and `run.sh` and the macOS app launcher use that location automatically.

### macOS / Linux, every later run

```bash
cd qlc-plus-swiss-knife-tool-script
python3 app.py              # native window (if pywebview is installed)
python3 app.py --browser    # force browser mode
```

> `bash run.sh` finds the virtual environment automatically (`~/.venvs/swissknife`, or `.venv` in the project), so you do not need to activate it.
>
> If `pip` is not found, use `pip3`, or skip the `source` step and call the venv's pip directly:
> ```bash
> .venv/bin/pip install flask
> .venv/bin/pip install pywebview
> ```

---

### Windows (Command Prompt), first time only

```bat
git clone https://github.com/giopas/qlc-plus-swiss-knife-tool-script.git
cd qlc-plus-swiss-knife-tool-script
python -m venv .venv
.venv\Scripts\activate.bat
pip install flask
pip install pywebview
python app.py
```

> `pywebview` is optional. It opens the app in a native window instead of a browser tab. Skip it if you prefer browser mode.

### Windows (Command Prompt), every later run

```bat
cd qlc-plus-swiss-knife-tool-script
python app.py
python app.py --browser
```

> The first command opens a native window if pywebview is installed. Use `--browser` to force browser mode.

---

The app opens `http://localhost:5731` automatically. Press **Ctrl+C** or use the **Quit** button in the sidebar to stop it.

> **Native window mode:** install `pywebview` to get a standalone-app experience:
> ```bash
> .venv/bin/pip install pywebview    # macOS / Linux
> .venv\Scripts\pip install pywebview  # Windows
> ```
> Use `python3 app.py --browser` to force browser mode.
>
> **Platform launchers:** the `launchers/` directory has a macOS `.app` builder, a Windows `.bat` and a Linux `.desktop` file.

### Loading a workspace

- **Start screen:** drag a `.qxw` file anywhere onto the window, or use the **Open Workspace** and **Open Session** buttons.
- **📂 Open…** in the header works from any tool. In a plain browser without a native file dialog, paste the full path into the Start screen's path field and click **Load**.
- **Recent files:** workspaces you opened before appear in the Start screen's recents panel.

---

## Supported platforms

| Platform | Status |
|---|---|
| Windows 10/11 | ✅ Tested |
| macOS 12+ | ✅ Tested |
| Linux (Ubuntu / Debian) | ✅ Tested |

---

## Privacy and security

Everything runs on your computer. The app listens on `127.0.0.1` only, so your network cannot reach it, and it checks the origin of every request.

The internet is used in three optional ways. Once at start, the update check asks GitHub which version is the latest; nothing about you or your shows is sent, and you can switch it off under the menu. Swiss Knife can fetch a fixture definition from the official QLC+ fixture library on GitHub. The ID Browser can load its table library.

The Claude connection is off until you set it up. When it is on, Claude gets only the folders you list and Swiss Knife's tools (see [Claude and your shows](#claude-and-your-shows)). Details: [DEVELOPMENT.md](DEVELOPMENT.md#security).

---

## Documentation

- **[Wiki](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/):** every tool, step by step.
- **[CHANGELOG.md](CHANGELOG.md):** what changed in each version.
- **[WORKPLAN.md](WORKPLAN.md):** where the project stands and what comes next.
- **[DEVELOPMENT.md](DEVELOPMENT.md):** architecture, project structure and tests.

---

## Early release: please report bugs

Swiss Knife is tested on real shows and by an automated test suite, but it is young. Please report anything odd on the [Issues page](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/issues). Every report helps.

---

## Contributing

Bug reports, suggestions and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before you open an issue or send code.

---

## License

Swiss Knife is released under the **MIT License**. See [LICENSE](LICENSE) for the full text. In short, you may use, modify and distribute it, attribution is appreciated, and there is no warranty.

---

## Support QLC+

**This tool would not exist without QLC+.** If Swiss Knife is useful to you, QLC+ is useful to you too, and a small team of volunteers builds and maintains it in their free time.

**Please consider donating to the QLC+ project.** Even a small contribution helps keep QLC+ alive and pays for new features, so that this open-source lighting software stays available to everyone, from bedroom DJs to professional stage crews.

👉 **[Donate to QLC+ on GitHub](https://github.com/mcallegari/qlcplus)**: look for the **Sponsor** button on the repository page.

If QLC+ has ever saved you time, money or a gig, give something back.

---

## Acknowledgements

All credit for **QLC+**, the lighting control software this tool is built around, belongs to the [QLC+ development team](https://github.com/mcallegari/qlcplus). Swiss Knife is an independent community project and is not part of the official QLC+ project.
