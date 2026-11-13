### Added — the Song Builder plays the music and a click together (3.20.0)

Asked on the QLC+ forum: a click for the drummer on a separate output while the main output stays clean. The Song Builder is still not a mixer: one music track and one click, with no volumes.

- **Music and click together.** Block 2 is now *Music and click*. Tick **Click track** and press **Make the click track**: the click goes on a track of its own called *Click*, beside the music, instead of replacing it. With no music, the click is the only sound, as before.
- **The click on its own output.** The box next to it takes the name of a sound device, for example the interface that feeds the drummer's in-ears. Swiss Knife writes it where QLC+ keeps it (`<Source Device="…">` on the click's Audio function, read in QLC+'s `Audio::loadXML`), so QLC+ plays the click there and the music on the main output. The list offers the outputs already used in the show. Changing the output and building again moves the click Swiss Knife made; a sound of the same file that you made yourself is never changed.
- **The first beat of the music.** Most recordings do not start on the beat at 0:00. **First beat at** says where bar 1 starts (`0:01.250`). The first part still starts at 0:00 and also covers the time before it; its length, every bar and beat after it, and the click count from the first beat. Before it, the clicks are counted back at the same tempo, so a pick-up bar has its click too. *To the end* and `until 1:20` still count from 0:00. The bar shows where bar 1 starts.
- **Find the tempo.** A button listens to the music and fills in the tempo and the first beat: an onset curve of the sound, a comb of beats slid over it at every phase for the exact BPM (a whole number when it fits as well), and the beats with the most harmony change, kick drum and accent as bar 1. The line under it offers half and double the tempo, and says *Not sure* when the beat is weak or uneven. It reads `.wav`, `.mp3`, `.ogg`, `.flac` and `.aiff` (the first six minutes); `.m4a` cannot be read. It is a proposal, checked by ear with the click.
- **Two optional add-ons for it.** Finding the tempo needs `numpy` and `soundfile` (which carries its own libsndfile with MP3). The downloaded apps include them, and the release build's `--smoke` check makes a click track and hears its tempo back. Run from the sources without them, the button says `pip install numpy soundfile`, and everything else works as before.
- **Doctor I010.** A sound sent to an output of its own is listed as information: if that device is not connected when the show runs, QLC+ plays the sound on the main output without a word (`AudioPluginCache::getOutputDeviceInfo` falls back to the default device), so a click could come out of the PA. Check it at the venue.
- **Claude.** The `song_builder` tool takes `first_beat` and `click` {path, device}, and `find_tempo=true` proposes the tempo and the first beat of the music without changing anything; `click=true` makes the file, which then goes in `click`, not `music`. Its description no longer says the click ignores a part's own tempo (it follows it since 3.13.0).
- Warnings: a click track shorter than the song (*make it again*), a click file not found, a first beat after the end of the music.
- New: `core/tempo_detect.py`, `POST /api/songbuilder/tempo` (reads only), `GET /api/songbuilder/devices`. A song built before keeps its table as it was. Tests: `tests/test_song_click_3200.py`, `tests/test_tempo_detect_3200.py` (songs made by the tests, the tool's own click tracks, MP3, FLAC and OGG). 25 new screen strings in the seven languages. Wiki: *Song Builder*, *Workspace Doctor*, *Claude Tools*.

### Fixed — the video of a release (CI only)

- **A release's own video run no longer skips itself.** Called by `release.yml`, `pitch.yml` saw the tag's `push` event and took the release for a commit pushed to `main`, so it skipped making the video while showing green. It now skips only a push to `main` with no tag given, and a change to `pitch.yml` itself runs it once for the latest release.

### Added — the pitch video on every release (the app does not change)

- **The pitch video and the slides are made and attached to each release by GitHub.** A new workflow runs `tools/make_pitch_video.py` with the online voice after every release and attaches `QLC_Swiss_Knife_Pitch.mp4` and `QLC_Swiss_Knife_Pitch.pdf`; it also refreshes them when the slides or the screenshots change. The README opens with *See it in two minutes*, linking to the latest ones. The files are not in the repository, and *Update and restart* ignores them.
- **The video plays in the browser.** A file attached to a release is always downloaded, so the README picture now opens a small page on GitHub Pages that plays the latest video, with the slides and the download next to it. It is published again after every release.
- **The Claude slide** says that Claude can even start a new show from scratch.
- `make_pitch_video.py`: `--strict-voice` (never a video without a voice) and `--poster` (the README picture).

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
