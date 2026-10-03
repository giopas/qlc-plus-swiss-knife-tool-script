# QLC+ Swiss Knife v2.1.0 — Show Profiles: do it again, on another show

You adapted a show for a pub: kept six PARs, fixed what the Doctor found, made a group, built looks, added a page. Next month it's another venue, another rig — or a friend wants the same treatment for their show. **Save those changes as a profile and apply it there.**

### New — Show Profiles
- **History › ↻ Do it again**:
  - **★ Save as a profile…** keeps the changes you made, with a name and a description.
  - **▶ Apply** runs a profile on the show you have open. Every step becomes a step of the History, so undo works.
- **By meaning, not by IDs.** Each step finds what it changes by what it is:
  - *the Scene "Song 22"*;
  - *the fixture "Drums"* — or the fixture at the same address on another rig;
  - *the group "Band Pair"*;
  - *the CueList on the page "Setlist"*.
  
  Workspace Doctor fixes become *the same kinds of fixes* on the new show.
- **Nothing is guessed silently.** A step that needs something the show doesn't have is left out and named, with the reason. Pairings by address are listed.
- **Files as parameters**: a setlist `.txt`, another show for the Function Porter or a mesh is asked for when you apply the profile (or found next to it). VC page templates travel inside the profile. A profile holds no paths of your computer, so you can share it.
- **From the command line**:
  ```
  python -m core.profile build Pub.profile.json --show Venue.qxw
  ```
  This saves `Venue_v2.qxw` with its report and recipe, and prints the Doctor's verdict. The venue file is never changed. Also `show`, `list`, and `make` (a profile from a recipe).
- **The recipe**:
  - **📋 Save the recipe…** from the History, without saving the show.
  - `python -m core.recipe replay <recipe> --onto Other.qxw` replays it on another show.
  - On the same show it still gives the same file, byte for byte.

### Changed
- **Quick Start › Placement**: *Beam (tilt)* buttons — Down, Across, Up, Auto — for the selected fixtures or all.
- **Quick Start** saves as `<project>_v1.qxw`, then `_v2`…, like every other tool.
- **Fixtures** keeps each fixture's tilt; a new one follows its height (truss down, floor up) instead of a fixed 65°.

Installable packages, planned as 2.1, are now **2.2**.

Your original files are never changed.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Show Profiles](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Show-Profiles) · [Recipe](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Recipe) · [Quick Start](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Quick-Start).
