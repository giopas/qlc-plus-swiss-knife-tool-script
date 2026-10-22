# QLC+ Swiss Knife v3.9.8

<p align="center"><img src="static/logo/icon-512.png" alt="QLC+ Swiss Knife logo" width="140"></p>

[![tests](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/actions/workflows/tests.yml/badge.svg)](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/actions/workflows/tests.yml)

**Swiss Knife is a free app that does the long, fiddly jobs on QLC+ 5 show files.** You open a show once, use the tools you need, and save the result as a new file. The file you opened is never changed. It runs on your own computer, and the few things that use the internet are optional (see [Privacy and security](#privacy-and-security)).

> ⚠️ **Independent project.** Swiss Knife is not affiliated with, endorsed by or connected to the QLC+ project or its team. All credit for QLC+ goes to the [QLC+ team](https://www.qlcplus.org/). Swiss Knife works on top of QLC+ workspace files.

![A festival show becomes a pub show: the guided route in Swiss Knife](screenshots/route.gif)

*A real festival show rebuilt for a small pub (6 lights, tonight's 34 songs) in 12 minutes with the guided route. Step by step: [the tutorial](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Tutorial-Big-Venue-to-Pub).*

---

## Who it is for

Anyone who plays lights with [QLC+](https://www.qlcplus.org/): a band that runs its own lights, a small venue, a DJ, a theatre or church crew, a technician who moves one show between rigs. You do not need to program anything.

A typical use: your band plays a festival with 14 lights, then a pub with 6. Instead of rebuilding the show by hand, you open the festival show, tick the 6 lights the pub has, and Swiss Knife cleans up everything that used the others. It also makes tonight's setlist, checks the show for mistakes and prints the paper for the venue.

Swiss Knife is tested with QLC+ 5.2.2 and 5.3.0. If a word in this page is new to you, the wiki has a page that explains each one: [Words used here](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Words-used-here).

---

## Your first ten minutes

1. **Install it (3 minutes).** Download the file for your computer from the [latest release](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/releases/latest) and open it, as in [Install](#install) below. The system asks once because the app is not signed.
2. **Open a show (1 minute).** Click **Open…** at the top, or drop a `.qxw` file onto the window. Swiss Knife loads it as the **show in progress**, a working copy in memory.
3. **Look at the Doctor's verdict (1 minute).** The top bar tells you whether the show has errors or warnings. Click it to see each one in plain words.
4. **Try one tool (4 minutes).** Open **Rig Reducer** in the side menu, untick a few lights and read what it will change. If you have no show yet, start with **Quick Start** instead: pick your lights and it builds a ready-to-play show.
5. **Save (1 minute).** Click **Save as new file…**. You get `<name>_v2.qxw` and a report next to it. Open it in QLC+ and press a button.

Stuck? Every tool has a **?** that opens its page in the [wiki](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/).

---

## How it works

1. **Open a show.** It becomes the show in progress.
2. **Use any tool, in any order, as often as you like.** The main button of each tool is **✓ Apply to the show**. The top bar counts the changes and shows the Doctor's verdict on the show as it is now.
3. **Go back** to any step in the **History** (undo and redo).
4. **Save as new file…** writes `<name>_v<N+1>.qxw` with one report of every change and a *recipe*, a record that Swiss Knife can replay to get the same file again. The file you opened is never overwritten.
5. **Do it again on another show.** Save your changes as a **Show Profile** and apply it to another venue, a new rig or a friend's show, in the app (History, *Do it again*) or from the command line: `python -m core.profile build Pub.profile.json --show Venue.qxw`. See [Show Profiles](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Profiles).
6. **Ask Claude to do it.** *Connect to Claude* in the menu lets Claude Desktop or Claude Code use the same tools on the folders you choose. See [Claude and your shows](#claude-and-your-shows).

For a job that takes several tools, the Start screen has *guided routes* such as *Adapt a show to a new venue*. They list the steps above the tools. The [tutorial](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Tutorial-Big-Venue-to-Pub) walks through one.

---

## The tools

The tools are in six groups, numbered 1 to 6 like the side menu and the Start screen. Each name links to its wiki page.

| | Tool | What it is for |
|---|---|---|
| **1 · New show** | [Quick Start](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Quick-Start) | Pick your lights and get a ready-to-play show: looks, effects, groups, a PANIC RESET button and a Virtual Console. About five minutes. |
| | [Fixtures](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Fixture-Configurator) | Place your lights on a stage plan, give them DMX addresses and print a blueprint. |
| **2 · Adapt a show** | [Rig Reducer](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Rig-Reducer) | Make a show for a smaller rig. Tick the lights you will have and everything that used the others is cleaned up. |
| | [Function Porter](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Function-Porter) | Bring looks, chasers and their buttons from another show, even when the lights are different models. |
| | [Brightness](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Brightness) | Make one type of light brighter or dimmer in every scene. Colours stay as they are. |
| **3 · Create** | [Look Builder](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Look-Builder) | Looks and effects for each group of lights, with their buttons: colours, gobos, strobes, chasers and movement. A look is greyed out when a group cannot do it. |
| | [VC Visual Editor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/VC-Visual-Editor) | Lay out the Virtual Console, the screen of buttons you play, on a canvas. Fit it to a tablet or a small touchscreen. |
| | [Stage & Meshes](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Stage-and-Meshes) | The 3D stage: put the band and the set pieces on it, aim lights at them, make groups of lights, and save a stage layout. |
| | [Library](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Community-Library) | Share templates, palettes, presets, profiles and your cable kit as one plain file. There is no server. |
| **4 · Run the show** | [Setlist](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Setlist-Manager) | Tonight's songs from a text file, matched to your chasers, in a cue list you step through with a key or a pedal. A tempo for each song, and PDFs. |
| | [Song Builder](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Song-Builder) | A song as a table of parts (intro, verse, chorus…): pick a scene or chaser, a length in seconds, bars or beats, and a repeat for each. It makes one Show with the music, shown as a bar so you see what is still free. |
| | [Trigger Manager](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Trigger-Manager) | Every key and MIDI control in one table, with clashes and gaps marked. |
| | [Dictionary](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Dictionary-Manager) | A short description for every function, shown in the other tools. |
| | [Tablet on stage](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Tablet-on-stage) | A page for a tablet on stage: the cue playing now and the next one, a card for each song (tuning, tempo, who starts) and a view for each player. It follows QLC+ live, or it is one simple page that needs no network. |
| | [Cabling](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Cabling) | Plan the DMX cables with the kit you own: which cable goes where, adapters and terminators. A plot, a pick list, labels and a load-in order. |
| **5 · Check & fix** | [Workspace Doctor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Workspace-Doctor) | Reads the show for mistakes, explains each one and fixes what you tick. Also from the command line. |
| | [Wizard Repair](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Wizard-Repair) | Finishes a show made by the QLC+ 5.3 Show Wizard: the effects it loses, buttons it leaves out, a PANIC RESET on every page. |
| | [Upgrade to QLC+ 5.3](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Upgrade-Older-Shows) | Gives a show made with QLC+ 5.0 to 5.2 what QLC+ 5.3 offers: folders, palettes, a page per group. Your looks keep every channel. |
| | [Compare](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Compare) | Put two shows side by side and see what differs in what they do. |
| | [ID Browser](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/ID-Browser) | Every function and Virtual Console widget in a table you can sort and filter, with CSV and PDF export. |
| **6 · Document** | [Show Paperwork](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Paperwork) | The paper for each reader: a tech rider for the venue, a checklist for the crew, a patch sheet for whoever sets the addresses, and a show book for you. PDF or CSV. |

**Language.** The interface speaks English, Italian, French, German, Spanish, Portuguese, Japanese and Chinese. Pick it at the bottom of the left menu ([Language](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Language)). Shows, reports and the wiki stay as they are.

---

## Claude and your shows

Swiss Knife can work with Claude, the AI assistant, through Claude Desktop or Claude Code. Once connected, you ask in plain words ("open Festival_14fix, run the Doctor and fix what is safe, save it as a new file") and Claude uses the same tools you use in the window. This works through MCP, the way these programs talk to outside tools.

**What Claude can reach.** Only the folders you list and Swiss Knife's tools. It cannot browse your disk, run commands, open other programs or use the network, and a path outside your folders is refused. Claude writes new files only and never deletes one. There are a few exceptions you confirm first: a page from an earlier Stage Monitor export, the cabling plan next to the show, and your cabling kit. Every change is a History step you can undo, and the Doctor refuses a result with new errors, as it does in the window.

**To connect Claude Desktop**, start Swiss Knife once, open *Connect to Claude* in the menu and click **Connect Claude Desktop**. Claude Desktop opens an install window and asks which folders to share. The same `…-claude.mcpb` file is attached to every release if you prefer to double-click it. The wiki page [Connect Claude to Swiss Knife](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Connect-Claude-to-Swiss-Knife) has the steps, example requests and the way for Claude Code. [Claude's tools](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Claude-Tools) lists every tool with the text Claude reads.

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
| ![Stage Monitor](screenshots/19-stage-monitor.png) | ![The Stage Monitor page on a tablet](screenshots/20-stage-page.png) | ![The Stage Monitor page, black with a white song](screenshots/21-stage-page-black.png) |
| Stage Monitor: the cue lists and the page | On the tablet, live from QLC+ | Black, white song: for a dark stage |
| ![Cabling: the plan](screenshots/22-cabling-plan.png) | ![Cabling: my kit](screenshots/23-cabling-kit.png) | ![Cabling: checks and export](screenshots/24-cabling-check.png) |
| Cabling: three alternatives and the chains on the stage | Cabling: my kit, every show | Cabling: the checks, the load-in order and the files for the crew |

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
- **Open…** in the header works from any tool. In a plain browser without a native file dialog, paste the full path into the Start screen's path field and click **Load**.
- **Recent files:** workspaces you opened before appear in the Start screen's recents panel.

---

## Supported platforms

| Platform | Status |
|---|---|
| Windows 10/11 | Tested |
| macOS 12+ | Tested |
| Linux (Ubuntu / Debian) | Tested |

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

**[Donate to QLC+ on GitHub](https://github.com/mcallegari/qlcplus)**: look for the **Sponsor** button on the repository page.

If QLC+ has ever saved you time, money or a gig, give something back.

---

## Acknowledgements

All credit for **QLC+**, the lighting control software this tool is built around, belongs to the [QLC+ development team](https://github.com/mcallegari/qlcplus). Swiss Knife is an independent community project and is not part of the official QLC+ project.
