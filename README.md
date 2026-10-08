# QLC+ Swiss Knife — v2.9.0

<p align="center"><img src="static/logo/icon-512.png" alt="QLC+ Swiss Knife logo" width="140"></p>

[![tests](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/actions/workflows/tests.yml/badge.svg)](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/actions/workflows/tests.yml)

**Build, adapt, check and document QLC+ 5 shows.** Swiss Knife opens your QLC+ workspace (`.qxw`) in a browser or a native window and does the long, fiddly jobs for you — a new show from your fixtures, the same show on a smaller or different rig, looks and chasers, the Virtual Console, the 3D stage, tonight's setlist, a health check, and the paperwork for the venue and the crew.

> ⚠️ **Independent project** — not affiliated with, endorsed by, or connected to the QLC+ project or its team. All credit for QLC+ goes to the [QLC+ team](https://www.qlcplus.org/). Swiss Knife works *on top of* QLC+ workspace files.

![A festival show becomes a pub show — the guided route in Swiss Knife](screenshots/route.gif)

*A real festival show rebuilt for a small pub — 6 PARs, tonight's 34 songs — in 12 minutes, with the guided route. Step by step: [the tutorial](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Tutorial-Big-Venue-to-Pub).*

---

## How it works

1. **Open a show** — it becomes the **show in progress**, a working copy in memory.
2. **Use any tool, in any order, as often as you need.** Each tool's main button is **✓ Apply to the show**; the header counts the changes and shows the Workspace Doctor's verdict on the show as it is now.
3. **Go back** to any step in the **History** (undo, redo).
4. **💾 Save as new file…** writes `<name>_v<N+1>.qxw` with one report of every change, and a *recipe* that the command line can replay to the same file. **The file you opened is never overwritten.**
5. **Claude can use the same tools.** *🔌 Connect to Claude* (under the menu) lets Claude Desktop or Claude Code open, check, fix and build on your shows through MCP. Claude gets only the folders you list and Swiss Knife itself, nothing else on your computer, and it always saves a new file. See the wiki page *Connect Claude to Swiss Knife*.
5. **Do it again on another show.** Save the changes as a **Show Profile** and apply it to tonight's venue, next month's rig or a friend's show — in the app (History › *Do it again*) or from the command line: `python -m core.profile build Pub.profile.json --show Venue.qxw`. Each step finds what it changes by name, type and place, and tells you what it left out. See [Show Profiles](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Profiles).

For jobs that take several tools, *guided routes* (e.g. *adapt a show to a new venue*) show the steps above the tools — see the [tutorial](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Tutorial-Big-Venue-to-Pub). Every tool has a **?** that opens its page of the [wiki](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/).

---

## The tools

Grouped by job, numbered 1–6 like the side menu and the Start screen.

| | Tool | What it does |
|---|---|---|
| **1 · New show** | [Quick Start](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Quick-Start) | A ready-to-run show from your fixtures: looks, effects, fixture groups, PANIC RESET and a Virtual Console, in about five minutes. |
| | [Fixtures](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Fixture-Configurator) | Place and patch a rig on a 2D stage; blueprint PDF; a rig-only workspace. |
| **2 · Adapt a show** | [Rig Reducer](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Rig-Reducer) | Keep the fixtures of a smaller rig; everything that used the others is cleaned up; re-patch. |
| | [Function Porter](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Function-Porter) | Bring looks, chasers, effects and their buttons — and fixtures and groups — from another show; copied fixtures can join the show's own looks (*plays like*); other fixture types translated by capability; 14 → 6 fixtures (fan-in); key/MIDI bindings come along. |
| | [Brightness](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Brightness) | Scale the master dimmer of each fixture type across every scene; colours untouched. |
| **3 · Create** | [Look Builder](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Look-Builder) | Looks from a palette for your fixture groups; chasers from a pattern with BPM timing, song presets and a playable preview. |
| | [VC Visual Editor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/VC-Visual-Editor) | The Virtual Console as a canvas: add and wire widgets, pages, templates, screen sizes; align, distribute, sort. |
| | [Stage & Meshes](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Stage-and-Meshes) | The 3D stage from above and from the front: put band members and set pieces on the floor, place them around the fixtures; make and edit fixture groups. |
| | [Library](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Community-Library) | Share your VC templates, palettes, look presets, naming profiles, VC styles and Show Profiles as one plain file — and install what other QLC+ users shared (checked first; no server). |
| **4 · Run the show** | [Setlist](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Setlist-Manager) | Tonight's songs matched to functions, with fades, into the setlist CueList; setlist PDFs. |
| | [Trigger Manager](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Trigger-Manager) | Every keyboard and MIDI binding in one table: clashes, gaps, bulk MIDI shift. |
| | [Dictionary](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Dictionary-Manager) | A description for every function, shown everywhere. |
| **5 · Check & fix** | [Workspace Doctor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Workspace-Doctor) | Broken references, scenes that leave channels unset, strobe left on, a PANIC RESET that can't reset… found and fixed. Also from the command line. |
| | [Compare](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Compare) | This show next to another one, by what they do: patch, groups, looks (decoded colour and level), chasers, VC pages, setlist. |
| | [ID Browser](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/ID-Browser) | Every function and VC widget in sortable, filterable tables; CSV and PDF. |
| **6 · Document** | [Show Paperwork](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Paperwork) | The paper for each reader: tech rider for the venue (never carries your show's internals), crew checklist for load-in, patch sheet with DIP-switch diagrams (also as a thermal-printer ticket), show book for you — with a stage plot; PDF or CSV. |

---

**Language.** The interface speaks English, Italian and French — pick it at the bottom of the left menu ([Language](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Language)). Shows, reports and the wiki stay as they are.

## Screenshots

| | | |
|---|---|---|
| ![Quick Start](screenshots/02-quick-start.png) | ![Fixtures](screenshots/03-fixtures.png) | ![Rig Reducer](screenshots/04-rig-reducer.png) |
| Quick Start — the Virtual Console it will build | Fixtures | Rig Reducer — what will change |
| ![Function Porter](screenshots/05-function-porter.png) | ![Brightness](screenshots/06-brightness.png) | ![Look Builder](screenshots/07-look-builder.png) |
| Function Porter — map the fixtures | Brightness | Look Builder |
| ![VC Visual Editor](screenshots/08-vc-editor.png) | ![Stage & Meshes](screenshots/09-stage-meshes.png) | ![Setlist](screenshots/10-setlist.png) |
| VC Visual Editor | Stage & Meshes | Setlist |
| ![Trigger Manager](screenshots/11-trigger-manager.png) | ![Dictionary](screenshots/12-dictionary.png) | ![Workspace Doctor](screenshots/13-workspace-doctor.png) |
| Trigger Manager | Dictionary | Workspace Doctor |
| ![ID Browser](screenshots/14-id-browser.png) | ![Show Paperwork](screenshots/15-show-paperwork.png) | ![History](screenshots/16-show-in-progress.png) |
| ID Browser | Show Paperwork — tech rider with stage plot | The show in progress and its History |
| ![Start](screenshots/01-start.png) | ![Compare](screenshots/17-compare.png) | ![Library](screenshots/18-library.png) |
| Start — what do you want to do? | Compare — the rebuilt show next to the hand-made one | |

---

## Install

**Download, unzip, double-click** — from the [latest release](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/releases/latest):

| Computer | File | Then |
|---|---|---|
| macOS, Apple silicon (M1 and later) | `QLC-Swiss-Knife-<version>-macos-arm64.dmg` | drag *QLC Swiss Knife* to Applications |
| macOS, Intel | `QLC-Swiss-Knife-<version>-macos-x86_64.dmg` | the same |
| Windows 10/11 | `QLC-Swiss-Knife-<version>-windows-x64-setup.exe` | run the installer (no administrator needed; Start menu entry, uninstaller). Or the `…-windows-x64.zip`: unzip, run `QLC Swiss Knife.exe` |
| Linux | `QLC-Swiss-Knife-<version>-linux-x64.tar.gz` | unpack, run `QLC-Swiss-Knife` (opens in your browser) |

The first releases are **not signed**, so the system asks once: macOS — right-click the app › *Open* (or `xattr -dr com.apple.quarantine "/Applications/QLC Swiss Knife.app"`); Windows — *More info › Run anyway*. Each release has a `SHA256SUMS` file to check the download. When a newer version is out, a badge appears in the header; **Update and restart** downloads it, checks it and starts it again (your shows and settings are not touched). Switch the check off with *Check for updates* under the menu. Details: [Installing and updating](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Installing-and-updating).

Or **run from the sources** (below) — same app, and the badge then says `git pull`.

---

## Requirements (to run from the sources)

| Requirement | Details |
|---|---|
| Python | 3.8 or newer |
| Flask | `pip install flask` — the only required dependency |
| pywebview | `pip install pywebview` — *optional*, enables native window mode |
| Browser | Chrome or Edge recommended (for native Save dialog); Firefox/Safari also work |
| QLC+ workspace | `.qxw` format (QLC+ 5.x; checked with 5.2.2 and 5.3.0) |

---

## Install and run

### macOS / Linux — first time only

```bash
git clone https://github.com/giopas/qlc-plus-swiss-knife-tool-script.git
cd qlc-plus-swiss-knife-tool-script
python3 -m venv ~/.venvs/swissknife
source ~/.venvs/swissknife/bin/activate
python -m pip install -r requirements.txt   # flask + pywebview (native window)
python app.py
```

> **macOS: keep the virtual environment outside iCloud.** If the project lives in an iCloud-synced folder (Documents, Desktop), a `.venv` inside it gets "file 2.js" duplicates and the native window crashes with `KeyError: 'text_select'`. That's why the commands above put it in `~/.venvs/swissknife`; `run.sh` and the macOS app launcher use that location automatically.

### macOS / Linux — every subsequent run

```bash
cd qlc-plus-swiss-knife-tool-script
python3 app.py              # native window (if pywebview is installed)
python3 app.py --browser    # force browser mode
```

> `bash run.sh` finds the virtual environment automatically (`~/.venvs/swissknife`, or `.venv` in the project) — no need to activate it manually.
>
> **Tip:** if `pip` is not found, use `pip3` instead — or skip the `source .venv/bin/activate` step and call the venv pip directly:
> ```bash
> .venv/bin/pip install flask
> .venv/bin/pip install pywebview
> ```

---

### Windows (Command Prompt) — first time only

```bat
git clone https://github.com/giopas/qlc-plus-swiss-knife-tool-script.git
cd qlc-plus-swiss-knife-tool-script
python -m venv .venv
.venv\Scripts\activate.bat
pip install flask
pip install pywebview
python app.py
```

> `pywebview` is optional — it opens the app in a native window instead of a browser tab. Skip it if you prefer browser mode.

### Windows (Command Prompt) — every subsequent run

```bat
cd qlc-plus-swiss-knife-tool-script
python app.py
python app.py --browser
```

> The first command opens a native window (if pywebview is installed). Use `--browser` to force browser mode instead.

---

The app opens `http://localhost:5731` automatically. Press **Ctrl+C** or use the **Quit** button in the sidebar to quit.

> **Native window mode:** install `pywebview` for a standalone-app experience:
> ```bash
> .venv/bin/pip install pywebview    # macOS / Linux
> .venv\Scripts\pip install pywebview  # Windows
> ```
> Use `python3 app.py --browser` to force browser mode.
>
> **Platform launchers:** see the `launchers/` directory for macOS `.app`, Windows `.bat`, and Linux `.desktop` files.

### Loading a workspace

- **Start screen** — drag a `.qxw` file anywhere onto the window, or use the **Open Workspace** / **Open Session** buttons.
- **📂 Open…** in the header, from any tool. In a plain browser without a native file dialog, paste the full path in the Start screen's path field and click **Load**.
- **Recent files** — previously opened workspaces appear in the Start screen's recents panel.

---

## Supported Platforms

| Platform | Status |
|---|---|
| Windows 10/11 | ✅ Tested |
| macOS 12+ | ✅ Tested |
| Linux (Ubuntu / Debian) | ✅ Tested |

---

## Privacy and security

Everything runs on your computer. The app listens on `127.0.0.1` only (not reachable from your network) and checks the origin of every request. The only internet access is optional: once at start, the update check asks GitHub which version is the latest (nothing about you or your shows is sent; switch it off under the menu), fetching a fixture definition from the official QLC+ fixture library on GitHub, and the ID Browser's table library. Details in [DEVELOPMENT.md](DEVELOPMENT.md#security).

---

## Documentation

- **[Wiki](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/)** — every tool, step by step.
- **[CHANGELOG.md](CHANGELOG.md)** — what changed in each version.
- **[WORKPLAN.md](WORKPLAN.md)** — where the project is going.
- **[DEVELOPMENT.md](DEVELOPMENT.md)** — architecture, project structure, tests.

---

## ⚗️ Early release — please report bugs

Swiss Knife is tested on real shows and by an automated test suite, but it is young. **Please report anything odd on the [Issues page](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/issues)** — every report helps.

---

## Contributing

Bug reports, feature suggestions, and pull requests are warmly welcome!
Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or submitting code.

---

## License

This project is released under the **MIT License** — see [LICENSE](LICENSE) for the full text.
In short: free to use, modify, and distribute. Attribution appreciated. No warranties provided.

---

## Support QLC+

**This tool would not exist without QLC+.** If you find the Swiss Knife useful, it means QLC+ is useful to you too — and QLC+ is built and maintained by a tiny team of volunteers who give their time for free.

**Please consider donating to the QLC+ project.** Even a small contribution helps keep QLC+ alive, fund development of new features, and ensure this incredible open-source lighting software remains available for everyone — from bedroom DJs to professional stage crews.

👉 **[Donate to QLC+ on GitHub](https://github.com/mcallegari/qlcplus)** — look for the **Sponsor** button on the repository page.

Every euro, dollar, or coffee counts. If QLC+ has ever saved you time, money, or a gig — give something back. The developers deserve it.

---

## Acknowledgements

All credit for **QLC+** — the lighting control software this tool is built around — belongs to the [QLC+ development team](https://github.com/mcallegari/qlcplus). This script is an independent community contribution and is not part of the official QLC+ project.
