# QLC+ Swiss Knife v1.4.1 — Porter MIDI fixes

Fixes from the first real-show test of v1.4.0.

### Fixed
- **Function Porter: "Source wins" and the MIDI universe mapping had no effect** when used from the app — the options never reached the Porter, so exports always used *keep unless already used*: a ported setlist CueList lost its MIDI Next / Previous while the old one kept them. Also fixed for *Copy the input patch* and *Also copy bindings onto matching target widgets*.

### Improved
- **Step 4 warns before export** which key/MIDI bindings of the ported widgets the target already uses, and what the chosen policy will do with them.
- **A ported page keeps its layout** on the new page when it fits (no more spill-over onto a "(2)" page).

Full details: [CHANGELOG](../../CHANGELOG.md).
