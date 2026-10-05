# Roadmap

QLC+ Swiss Knife is growing from a set of helpers into a **deterministic, accurate show-file builder** for QLC+ 5: build your next show file *with the tool* — reduce a rig, port looks, generate chasers, lay out the Virtual Console, place fixtures in 3D, and validate everything before export.

The detailed, step-by-step plan (tasks, acceptance criteria, commit messages, decisions) lives in **[WORKPLAN.md](WORKPLAN.md)**. This page is the short version.

> This project is maintained in spare time; there are no committed dates. Ideas and help are welcome — open a [Feature Request](../../issues/new?template=feature_request.md) or a Pull Request.

---

## Principles

- **Never overwrite.** Every tool changes the *show in progress*; one save writes a new file (`<name>_v<N+1>.qxw`) with a report.
- **One writer.** All `.qxw` output goes through `core/qxw_io` — XML declaration and `<!DOCTYPE Workspace>` always present.
- **Deterministic.** Same input, byte-identical output; golden-file tests.
- **Doctor gates every export.** Errors block, warnings are reported.
- **Safe show content by default.** Full channel declaration, strobe/program channels at 0, a PANIC RESET, no scene shared between a VC button and a chaser step.
- **Conventions are data.** Nomenclature, palettes, screen sizes and VC templates live in shareable JSON profiles.

---

## Milestones

| Version | Theme | Highlights |
|---|---|---|
| **1.3.2** | Clean the bench | Safe single QXW writer, Trigger Manager never overwrites, 45° show-lighting tilt defaults, tests consolidated, CI |
| **1.4.0** ✅ | Out of Alpha | **Workspace Doctor** (read-only checks + CLI), Quick Start golden outputs and VC style cloning, Porter VC-widget porting and fan-in, **new rig from an existing show** (translation between fixture types), **MIDI/input control** porting, Show Book test suite with VC layout by page and Doctor summary |
| **1.5.0** ✅ | Doctor fixes + Rig Reducer | Opt-in auto-fixes (always to a new file); remove fixtures with full cascade and optional re-patch |
| **1.6.0** ✅ | Look & Chaser Builder | Fixture group × palette looks; pattern chasers (alternate, chase, ping-pong, build-up, seeded random) with BPM timing; song presets |
| **1.7.0** ✅ | VC Builder | Create/wire widgets, pages, grid snap, screen profiles, page templates, one-click setlist CueList wiring |
| **1.8.0** ✅ | Stage & meshes | OBJ meshes placed by what you see (centre, height above the floor), on the floor in one click; plan/front views with fixtures; mesh library |
| **1.9.0** ✅ | One show, every tool | The show in progress with History; Function Porter with the Merger folded in; Show Paperwork; guided routes; one screen pattern |
| **1.10.0** ✅ | Grow a rig | Copied fixtures join the show's own looks ("plays like"): scenes, sequence steps and EFX, translated between fixture types; what can't be wired is listed |
| **2.0.0** ✅ | Benchmark | The "Pub test" passed: a 14-fixture festival show rebuilt as the 6-fixture pub show with Swiss Knife only, in 12 minutes, Doctor 0 errors; fixture group editor; Compare; tutorial; the *recipe* — every change replayed by the command line to the same file |
| **2.0.1** ✅ | Paperwork for the crew | Patch sheet with DIP switches (PDF, thermal ticket, CSV); each setlist cue notes its original function and button; setlist CueList in one click; FloorShow in the test corpus |
| **2.1.0** ✅ | Show Profiles | The changes of a show done again on another show — by meaning, not IDs; in the app (History › Do it again) or `python -m core.profile build`; the recipe onto another show; Quick Start tilt buttons and `_vN` names |
| **2.2.0** ✅ | UI polish | After an outside review: "Apply will …" next to each Apply, guided routes first on Start, labelled header cards, the History card, ⌘K / Ctrl+K palette, readable tables, semantic colours and one spacing / type scale in every theme |
| **2.2.1** ✅ | UI polish, finished | "Apply will …" in the Porter footers, the Porter step 3 stage maps folded (mapping first), one type scale in tokens, the white-window fix |
| **2.3.0** | New-show flow | Fixtures open as the show, a guided *New show* route, profiles that start a show from nothing and a step editor, Setlist with the functions in a drawer, old routes retired |
| **2.4.0** | Doctor and Quick Start | PANIC RESET fix in the Porter, D002 / D003 / D004 / D013 / D015 fixes, Quick Start options kept, live check in CI |
| **2.5.0** | Looks and Stage | Beats tempo, moving-head positions, own palettes, matrix patterns for pixel bars; fixture aiming, mesh thumbnails, hide / show and copy meshes |
| **2.6.0** | Paperwork, setlists, MIDI | MIDI / input mapping manager, setlist import and a tablet setlist, tech rider with patch, tilt and meshes |
| **2.7.0** | Language and sharing | Interface in English, Italian and French; a community library of templates, palettes and profiles |
| **2.8.0** | Install like an app | Packages for macOS, Windows and Linux built on each release, with an update check; running from sources stays |
| **2.9.0** | MCP server | Claude Desktop / Cowork drive the same tools — the AI proposes, the tools write, the Doctor validates; ships inside the package (`--mcp`) |

## After 2.9

Nothing scheduled.
