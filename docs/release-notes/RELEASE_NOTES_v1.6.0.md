# QLC+ Swiss Knife v1.6.0 — looks and chasers, by palette and pattern

### New
- **Look & Chaser Builder** (sidebar → Build the rig → *Look Builder*):
  - **Looks** — tick fixture groups and palette colours (*warm*, *cold*, *scenic* or your own from a colour picker): one scene per group × colour. The colour is set by what each fixture can do — RGB/RGBW mixing, the nearest colour-wheel slot, or the dimmer — so the same "Amber" works on PARs and moving heads. **Every channel is declared** (shutter open, pan/tilt centred, everything else neutral), so no look inherits leftovers from the previous one.
  - **Chasers** — pick a fixture group and a pattern: *all-hit*, *left/right* (halves or odd/even), *chase*, *ping-pong*, *build-up* or *random* (seeded — the same seed always gives the same chaser). Colours change per step or per fixture; the fixtures that are off go dark or show a background colour. Timing in **ms** or **BPM + note length** (1/1 … 1/16); **cut** or **fade**.
  - **Song presets** — save a chaser recipe by name and reuse it in the next show; five built-in to start from.
  - **Simulated DMX preview** — each fixture's colour per step, decoded from the values that will be written; **▶ Play** runs it at the step time.
  - Names follow your naming profile (*plain* or *TheBand*), functions are filed in a *Look Builder* folder, and an optional new VC page gets coloured buttons. An existing PANIC RESET script also stops the new looks and chasers. The Workspace Doctor checks the result.

### Fixed
- A new VC page (VC Visual Editor, Function Porter) no longer copies the key/MIDI bindings of the first page.

Your original files are never changed: every result is a new `<name>_v<N+1>.qxw`, with a report next to it.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Look Builder](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Look-Builder).
