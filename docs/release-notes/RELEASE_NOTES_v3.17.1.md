### Fixed — loading a setlist keeps the looks already assigned (3.17.1)

- **Load setlist… no longer drops the looks.** A show that already plays a setlist opens with each song matched to its look. Loading a setlist `.txt` (for example one with a BPM per song) used to replace that list with names only, so every song lost its look and Apply left them all out, tempo included. Now a song with the same name keeps its look, fades and hold; the file brings the order, the new songs and the BPMs. A fade or hold the file sets itself wins. Songs still without a look are matched by name right away, and the status line says how many kept their look, how many were matched and how many are left. The same applies to *Import / paste…* when it replaces the songs, and to a file opened without the native picker (which now also reads `Song | 128 BPM`).
- **Re-Match gives the original look, not the copy.** After an Apply, the show has copies of the looks named like the songs, so Re-Match picked the copy (a song matched to itself). It now gives the look the copy was made from, as the list does when the show opens.

### Added — the tablet's screen stays on (3.17.1)

- **The Stage Monitor page keeps the tablet's screen on.** It plays a tiny silent video in a loop, so phones and tablets do not dim or lock the screen while the page is open. This works on the plain `http` address the page uses, where the browser's own keep-awake feature is not allowed. Touch the page once after it opens to start it. ☀ in the corner shows it is on; tap it to turn it off and on again. The tablet remembers the choice.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).

