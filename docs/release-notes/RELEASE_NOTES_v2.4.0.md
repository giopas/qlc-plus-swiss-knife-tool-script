# QLC+ Swiss Knife v2.4.0 — Doctor and Quick Start

### Added
- **Looks for fixtures without a dimmer** (scanners, simple heads): colour-wheel slots for the whole-rig colours, the closed shutter for BLACKOUT; Quick Start says which fixtures cannot make a look.
- **Profiles show where they are kept**, with an *Open folder* button.
- **Function Porter: PANIC RESET as a script** — a plain-scene PANIC RESET in the target becomes the script that stops everything first (on by default, can be unticked).
- **Doctor fixes with a choice**: D013 (give 0 ms chaser steps a duration in ms or BPM), D004 (merge a one-step chaser into its scene, or remove it), D003 (rewire broken buttons / CueLists by name), D015 (name unnamed functions from context). Always into a new file, listed in the report.
- **Sessions keep the Quick Start setup** (rig, fixture files, groups, options, stage).
- **Live QLC+ check in CI** (Docker image with QLC+ 5.2.2; advisory at first).

### Fixed
- The live check no longer calls Chase / Stripes buttons dark when the chaser merely starts on a dark step.

Your original files are never changed.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Workspace Doctor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Workspace-Doctor), [Quick Start](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Quick-Start).
