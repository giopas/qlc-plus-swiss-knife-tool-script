# QLC+ Swiss Knife v2.0.1 — paperwork for the crew, notes in the cue list

What came after the pub test: the sheet the crew needs at the rig, cue lists that say what each cue stands for, and a setlist for a show that has none — plus the fixes from the first test of all this.

### New
- **Patch sheet** (Show Paperwork › *🔌 Patch sheet — for the crew at the rig*): every fixture by universe and address — address range, channels, name, fixture, mode, ID — with a **DIP-switch diagram** drawn like the real part (blue body, white levers, ON = up; 9 or 10 switches) and the switches to turn ON. An event / venue line and your **logo** (PNG or JPEG) at the top. Never carries the show's internals, so it's safe to hand to the venue.
  - **Thermal printer ticket**: one long PDF 58 or 80 mm wide, or plain text (32 / 48 characters a line) for printer apps.
  - **CSV** in the ZIP, with the columns proposed in QLC+ issue #2086 first.
  - Inspired by OH Show's QLC+ patch tools; the DIP switches match theirs on the same show.
- **Notes in the setlist cue list.** Each cue the Setlist builds gets a note naming the **original** function and the button that plays it, e.g. `↪ [2328] Song 22 — buttons: CS · Soft Yellow`. QLC+ saves step notes and shows them in the cue list, so they survive a relaunch. Notes you typed in QLC+ are kept.
  - *In QLC+ 5, a note you type is kept only after **Enter**, and QLC+ doesn't mark the show as changed — save it yourself.*
- **A setlist CueList in one click** for a show that has none (e.g. fresh from Quick Start): from the **Setlist** (*▶ ＋ Add a setlist CueList*) or from the **VC Editor**, where the **▶ Setlist cue list** box now sits at the top of *＋ Add & wire*. The CueList gets a new, empty chaser *Setlist*, placed where it doesn't cover your buttons.
- **Workspace Doctor D008**: a VC button with the action *Stop All* or *Blackout* counts as a panic button.
- **A third real show in the test corpus** (`FloorShow_8fix.qxw`, anonymised). It found a real slip: a static look that leaves the PARs' strobe at 30.

### Fixed
- **Setlist**: a song with no function was dropped from the cue list without a word. Applying now says which songs were left out, and the show report lists them.
- **VC Editor**: a new CueList is wide enough (720 × 420) for every QLC+ column, the *Note* included.

Your original files are never changed.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Show Paperwork](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Paperwork) · [Setlist Manager](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Setlist-Manager) · [VC Visual Editor](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/VC-Visual-Editor).
