### Added — QLC+ Stage Monitor, the companion app (3.18.0)

- **A small app for the gig, its own download from the same release.** It opens a folder that the Stage Monitor exported and serves the page to the tablets. A light says whether QLC+ is ready: not running, running without web access (`-w`), another program on its port, another show open (it names the cue lists it cannot find), or ready. It only asks QLC+ for the state of the page's cue lists and never moves one. It shows this computer's addresses, one address for each player's view and a QR code, and warns when a tablet asks for `https://`.
- **Print the setlist** as a PDF in the page's folder: *Big, to tape to the floor* (A4 portrait, the song names as large as fits, the tempo and tuning on the right, a tuning change in orange) or *With the song cards* (A4 landscape: tempo, tuning, who starts, note, each player's line).
- **It updates itself.** Once at start it asks GitHub for the latest release (nothing about you or your shows; *Check for updates* switches it off). When a newer version is out, a card offers **Update and restart**: the download is checked against `SHA256SUMS`, swapped after the app quits and started again on the same folder. It uses Swiss Knife's updater set up for this app, so it looks only for `QLC-Stage-Monitor-…` downloads and keeps its own settings: each app updates only itself.
- **In the eight languages of Swiss Knife.** The first time it uses the language the page was exported in.
- **Its own icon**: Swiss Knife's tile, ring and knife, with a tablet in the ring.
- **Built from the same repository and released with Swiss Knife** (`stage_app/`, `packaging/stagemonitor.spec`, its own Windows installer). It reads only what Swiss Knife exports and uses only the Stage Monitor's server, the QR code and the PDF writer of Swiss Knife; a test fails if it imports anything else, or if Swiss Knife ever imports it. The release builds and smoke-tests both apps on every system.

### Changed — the Stage Monitor hands over to the companion app (3.18.0)

- **Open in QLC+ Stage Monitor** on the *Send to the tablet* tab opens the exported folder in the app (and stops Swiss Knife's own server on that folder first, so the port is free). When the app is not installed, the button reads **Get QLC+ Stage Monitor** and opens the release page; **▶ Serve** and *Start Stage Monitor* in the folder work as before. Run from the sources, Swiss Knife starts the app from the same sources (`python3 qlc_stage_monitor.py`).
- **Claude's `stage_monitor` tool** has `open_app`: it opens the exported folder in QLC+ Stage Monitor, or says where to download it.

---

Downloads for macOS, Windows and Linux are below: **QLC-Swiss-Knife-…** is Swiss Knife, **QLC-Stage-Monitor-…** is the new companion app (optional), plus the Claude Desktop file (.mcpb) and the checksums. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
