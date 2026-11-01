### Added — VC Editor and Song Builder extras (3.10.0)

- **Resize a widget by dragging.** Pick a widget or frame, grab one of the eight handles and drag. It snaps to the grid (you choose the grid size in the **Grid** box) and stays inside its frame. One drag is one step for Undo.
- **Four new widgets:** Knob, XY pad, Speed dial and Clock. They are written the way QLC+ 5.3 writes them. In a show made with an older QLC+, the tool offers the upgrade to 5.3, and only does it when you click.
- **Page templates keep keys and MIDI.** Before a template is added, the tool lists every key and MIDI input it brings and warns about any the show already uses. A clash is never written.
- **Click track.** In the Song Builder, **Make a click track** makes a sound file that clicks on every beat at the song's tempo, with a higher, louder click on the first beat of each bar. Choose Beep, Wood block or Soft tick. It never replaces a file that exists.
- **A picture of any Show** (read only) from the Setlist and from the Doctor's findings: one row per track, one bar per item.
- Screenshots 26 and 27, the wiki, the README and all seven languages are updated.

### Changed

- **The Setlist screen is now called Setlist Manager** in the menu, the page title, the guided routes and the texts that mention it, in all seven languages.

### Fixed

- **Setlist:** the list of QLC+ functions shows each function once. The copies the Setlist makes for its cues are no longer listed beside the originals; a ✦ beside an original says it has a copy.
- **Song Builder:** building a song again now also updates the Setlist's copy of it. Before, the copy lost its lights and its new music.
- **VC Editor:** a widget can be resized to the right and downwards even when two items share an ID; the Grid box is in the toolbar (the mask limits are now labelled *Mask ±*); the upgrade note stays until you click *Not now*; the duplicate-ID message names the widgets and says where the *Fix duplicate IDs* button is.
- The wiki's Setlist page no longer mentions *Split Show…*, dropped in 3.9.8.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
