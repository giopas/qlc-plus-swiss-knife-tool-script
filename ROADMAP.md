# Roadmap

QLC+ Swiss Knife is growing from a set of helpers into a **deterministic, accurate show-file builder** for QLC+ 5: build your next show file *with the tool* — reduce a rig, port looks, generate chasers, lay out the Virtual Console, place fixtures in 3D, and validate everything before export.

The detailed, step-by-step plan (tasks, acceptance criteria, commit messages, decisions) lives in **[WORKPLAN.md](WORKPLAN.md)**. This page is the short version.

> This project is maintained in spare time; there are no committed dates. Ideas and help are welcome — open a [Feature Request](../../issues/new?template=feature_request.md) or a Pull Request.

---

## Principles

- **Never overwrite.** Every tool writes a new file (`<name>_v<N+1>.qxw`, or `<name>_doctor.qxw` for Doctor fixes).
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
| **1.4.0** | Out of Alpha | **Workspace Doctor** (read-only checks + CLI), Quick Start golden outputs and VC style cloning, Porter VC-widget porting and fan-in, Show Book test suite |
| **1.5.0** | Doctor fixes + Rig Reducer | Opt-in auto-fixes (always to a new file); remove fixtures with full cascade and optional re-patch |
| **1.6.0** | Look & Chaser Builder | Fixture group × palette looks; pattern chasers (alternate, chase, ping-pong, build-up, seeded random) with BPM timing; song presets |
| **1.7.0** | VC Builder | Create/wire widgets, pages, grid snap, screen profiles, page templates, one-click setlist CueList wiring |
| **1.8.0** | Stage & meshes | OBJ meshes in the 3D monitor; unified fixture + mesh placement |
| **2.0.0** | Benchmark | The "Pub test": rebuild a 6-fixture pub show from a 14-fixture festival show using only Swiss Knife, Doctor-clean |

## After 2.0

Show Profiles (one JSON per show), a command-line build pipeline, an MCP server so AI assistants can drive the deterministic tools, a MIDI/input mapping manager, audio-trigger helper, setlist import and tablet setlist, tech-rider integration, functional workspace diff, packaged builds for macOS/Windows, localisation (EN/IT/FR), and upstream bug reports to QLC+.
