# ⚡ QLC+ Swiss Knife — v0.7.3 (Legacy Tkinter Edition)

> 🗄️ **This branch is the legacy desktop application (Tkinter / pure Python).**
> It is preserved for historical reference and may receive independent fixes or forks in the future.
> **Active development has moved to the [`main` branch](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/tree/main),
> which hosts the v1.0+ Flask web UI.**

---

**A unified, ergonomic toolkit for QLC+ 5.x — pure Python, zero external dependencies.**

> ⚠️ **Independent Project Notice**
> This project is **not affiliated with, endorsed by, or officially connected to the QLC+ project or its development team** in any way. All credit for QLC+ itself goes to the [QLC+ team](https://www.qlcplus.org/). This script is an independent community utility that works *on top of* QLC+ workspace files (`.qxw`).

---

## Screenshots

| Setlist Manager | Dictionary |
|:---:|:---:|
| ![Setlist Manager](screenshots/tab1_setlist_manager.png) | ![Dictionary](screenshots/tab2_dictionary.png) |

| Setup Checklist | Triggers |
|:---:|:---:|
| ![Setup Checklist](screenshots/tab3_setup_checklist.png) | ![Triggers](screenshots/tab4_triggers.png) |

| Fixture Configurator | ID Browser |
|:---:|:---:|
| ![Fixture Configurator](screenshots/tab5_fixture_configurator.png) | ![ID Browser](screenshots/tab6_id_browser.png) |

---

## What is it?

QLC+ Swiss Knife is a single-file Python 3 desktop application that brings six essential live-production utilities together under one roof. Instead of juggling separate scripts or manual XML editing, you get a clean tabbed interface that reads your `.qxw` workspace and lets you manage it visually.

It runs on **Windows, macOS, and Linux** with nothing more than a standard Python 3 installation (tkinter included).

---

## Features

### 🎵 Setlist Manager
Build complete show cue lists from a plain-text setlist. The **multi-slot architecture** gives each QLC+ CueList its own tab — manage an entire show with multiple cue lists in a single session. Map songs to QLC+ functions, generate pristine cloned cue sequences, rename Chasers to match their CueList caption, and export per-slot **PDFs** — all without touching the XML by hand.

### 📖 Dictionary Manager
Create and maintain `ID → description` mapping files that annotate your QLC+ function pool with human-readable labels. Shared across all tabs so your annotations stay consistent throughout the session.

### 📋 Setup Checklist
Parse fixture patches, 3D stage positions, groups, and universe assignments directly from the workspace. Export **printable blueprint PDFs** and text checklists — ideal for pre-show setup or handing off to crew.

### 🎛 Trigger Manager
Audit and edit all **Virtual Console keyboard and MIDI bindings** in a spreadsheet-style table. Correctly resolves nested VC frame ancestry so the Frame filter works at any nesting depth. Spot conflicts, fix missing assignments, and write changes back to the workspace.

### 🔧 Fixture Configurator
Design your stage rig from scratch. Load `.qxf` fixture definitions, add instances to a rig table, and **drag them on a 2D top-down canvas** to set positions. Configure stage dimensions, auto-assign DMX addresses, then load a `.qxw` template and **generate a ready-to-use workspace** with all fixture blocks and 3D monitor positions populated from your canvas layout.

### 🔍 ID Browser
Inspect every function and Virtual Console widget in your workspace at a glance. Both sub-tabs support **live filtering**, **click-to-sort** column headers, **Export CSV**, and **Export PDF**.

---

## Requirements

| Requirement | Version |
|---|---|
| Python | 3.8 or newer |
| tkinter | Included with standard Python |
| QLC+ workspace | `.qxw` format (QLC+ 5.x) |

No `pip install` needed. No virtual environment required.

---

## Quick Start

```bash
# Clone this branch
git clone --branch legacy-tkinter https://github.com/giopas/qlc-plus-swiss-knife-tool-script.git
cd qlc-plus-swiss-knife-tool-script

# Run the app — no setup needed
python3 qlc_swiss_knife_0.7.3.py
```

On **Windows** you can also double-click the `.py` file if Python is associated with `.py` files.

---

## Supported Platforms

| Platform | Status |
|---|---|
| Windows 10/11 | ✅ Tested |
| macOS (12+) | ✅ Tested |
| Linux (Ubuntu/Debian) | ✅ Tested |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full history of changes across all versions.

---

## License

This project is released under the **MIT License** — see [LICENSE](LICENSE) for the full text.

---

## Acknowledgements

All credit for **QLC+** belongs to the [QLC+ development team](https://github.com/mcallegari/qlcplus). This is an independent community contribution.
