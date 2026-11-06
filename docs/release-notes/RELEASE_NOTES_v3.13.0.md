### Added — Song Builder: tempo changes within a song (3.13.0)

- **A part can set its own tempo.** Fill in a BPM on any row of the Song Builder table and, from that part onward, the song runs at that tempo, until another part sets its own. Leave it empty to keep the tempo already running. Made for a song with a bridge or an outro at a different speed, instead of one BPM for the whole song.
- **Bars, beats and `until`.** A part's length in bars or beats, and an `until bar 17` / `until beat 33` target, now follow the tempo in force at each point, part by part, instead of one BPM for the whole song.
- **The coloured bar** shows a small ♩ BPM mark on a part whose tempo differs from the one before it; the preview (apply=false) also gives each part's tempo.
- Claude's `song_builder` tool takes the same optional `bpm` on a part; the wiki *Song-Builder* page is updated.
- Not yet followed: the click track (3.10.0) still runs at the song's own BPM throughout, even when a part sets its own.

### Added — ready for QLC+ 5.3.1 (3.13.0)

QLC+ 5.3.1 came out on 5 November 2026. Two of its changes reach the show files, and Swiss Knife now reads, checks and upgrades shows for it.

- **Pages saved without a number.** QLC+ 5.3.1 no longer writes the Virtual Console pages' ID in the file. Swiss Knife finds pages by that ID (Pages, Function Porter, Look Builder, group pages, Compare, the Doctor), so it now gives each page one when it opens a show, the same one every time. QLC+ 5.3.1 ignores it when reading; QLC+ 5.2.2 and 5.3.0 need it.
- **Fixtures that cross universes.** The setting now has two choices, *Pixel* (whole heads only) and *Fill* (straight on). QLC+ 5.3.1 reads the old setting as *Pixel*, older versions as straight on, so a pixel bar can end up on other addresses. Swiss Knife places the channels as QLC+ 5.3.1 does.
- **Workspace Doctor.** D009 (address overlap) checks a fixture that crosses universes in the next universe too. New **D026**: a fixture runs past channel 512 without crossing universes, so QLC+ moves it to address 1. New **D027**: the old cross-universe setting gives other addresses in QLC+ 5.3.1; the fix writes *Fill*, which keeps the 5.3.0 addresses in every version (ticked by default).
- **Upgrade to QLC+ 5.3** follows the latest QLC+: the target reads *QLC+ 5.3.1 (latest)*, a new step *Cross-universe fixtures for QLC+ 5.3.1* does the same as the D027 fix, and the screen says when a show was saved by a QLC+ newer than the one Swiss Knife knows. Claude's `upgrade_show` tool takes the new step.
- Nothing to do for the other 5.3.1 changes: bindings on Animation widget presets and colours on 3D items are read and kept as they are.
- The wiki pages *Workspace Doctor* and *Upgrade Older Shows* and the seven languages are updated.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
