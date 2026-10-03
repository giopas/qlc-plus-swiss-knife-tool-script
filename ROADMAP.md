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
| **2.2.0** | Install like an app | Packages for macOS, Windows and Linux built on each release, with an update check; running from sources stays |

## After 2.2

An MCP server so AI assistants can drive the deterministic tools, a MIDI/input mapping manager, audio-trigger helper, setlist import and tablet setlist, tech-rider integration, localisation (EN/IT/FR), and upstream bug reports to QLC+.
