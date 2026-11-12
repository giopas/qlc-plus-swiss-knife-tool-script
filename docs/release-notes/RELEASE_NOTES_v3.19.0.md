### Added — Claude starts a show from scratch (3.19.0)

- **A new show from nothing, straight from Claude.** Tell Claude which fixtures you have and where, and it makes the show: the patch, the groups, the functions and the Virtual Console that the Quick Start makes, checked by the Doctor and saved as a new file (`Club_night_v1.qxw`). The folder can be empty or not exist yet; it is made inside a folder you shared. The new show is then the show in progress, so Claude can go on with looks, buttons, a setlist and save the next version. New Claude tool `new_show`; `preview=true` shows the patch first and writes nothing.
- **Claude finds the fixtures by name.** New Claude tool `find_fixtures` searches QLC+'s fixture library on your computer (only read, never changed) and the `.qxf` files in your shared folders, and gives the modes with their channel counts.
- **Addresses and places.** A fixture line can have its own universe and start address; the others go in the first free channels. A line can hang at a place on the stage, otherwise it is spread across it.
- **Nothing is written over.** A taken name becomes `_v2`. A fixture definition QLC+ lacks is put next to the show, but a different file of the same name already there is left alone and named in the answer.
- **An empty folder says what to do.** `list_shows` in a folder with no shows points to `new_show`. Claude Desktop offers a new ready request, *Start a new show from scratch*.

### Changed — a tidier, more readable Swiss Knife (3.19.0)

A review of every screen, in the three colour themes and in a small window, found thirteen things to fix. All of them are fixed here. Nothing changes in what a button writes.

- **Open and Save always stay on screen.** In a narrow window the header used to push **Open…** and **Save as new file…** off the right edge. Now the file name and the show's state give way first; below 1280 px History and Undo keep only their icons and Save reads **Save…**.
- **The side menu shows all the tools again.** The files, the colours, the language, the update check, **Connect to Claude** and the session file fold into one **Settings** row at the bottom (closed at first, then as you leave it). **Recent tools** moved from the menu to the top of **Go to… (⌘K)**.
- **One place for the colours.** The moon button on every tool's header is gone; **Settings › Colours** switches dark, grey and light.
- **Easier to read in a dark room.** The quietest grey text (ID columns, table headers, notes, the version) is lighter in every theme and now passes the same 4.5:1 contrast as the rest; coloured words (Scene and Collection tags, *✓ QXF*, warnings, the status line) use the theme's readable shades; nothing is smaller than 11 px.
- **Workspace Doctor.** *Show them / Hide them* stays on one line, long findings keep a margin on the right, and **Fix selected in the show** stays at the bottom right. **Copy Report** and **Take the show elsewhere (.zip)…** moved to the bar above the findings.
- **Every tool ends the same way.** Song Builder got the footer of the other tools: **Build the Show** at the bottom right, waiting for a name and saying so. The VC Visual Editor's **Apply to the show** waits until a widget is moved, resized or recoloured; Compare's main button reads **Compare again** and waits for the other show. Look Builder's **Add to the show** is now **Apply to the show**, like everywhere else.
- **Lists in the dark theme are dark.** The Doctor's options, the Upgrade target and the Porter's fan-out mode were white system boxes.
- **Stage plots without overlaps.** In Fixtures and the Function Porter, a fixture's name moves above or beside its dot when another name is in the way, never leaves the plot, and a long name ends with *…*. *AUDIENCE* sits at the side of its band.
- **One filled button per screen in the Setlist Manager.** *Show QLC+ functions* is outlined, *Assign* lights up when it can be used, and **Apply to the show** stays the one filled button.
- **Empty screens say what to do.** The Function Porter's empty source has its own **Browse…** button; Wizard Repair, on a show the wizard did not make, offers **Open the Doctor**.
- **Bigger click targets.** Small buttons, the links under Settings, the ribbon's links, the colour chips and the Song Builder's row buttons are at least 24 px high.
- **Start.** The banner about the show is as wide as the cards under it.
- **Screen readers.** Every **?**, **✕** and icon-only button has a name.
- Guards: `tests/test_ui_review_3190.py`; `test_tokens_contrast.py` now asks 4.5:1 of the faint text too; `test_ui_lint.py` also checks the `font:` shorthand. Thirteen new screen strings in the seven languages. Wiki: *Home*, *Show in Progress*, *Look Builder*, *Song Builder*, *Workspace Doctor*, *Installing and updating*, *Connect Claude to Swiss Knife*, *Tutorial Big Venue to Pub*.

### Fixed — updating both apps at once (3.18.2)

- **Swiss Knife and QLC+ Stage Monitor no longer remove each other's update.** Both download into a temporary folder next to the app; each app, when it started, removed every such folder, so Stage Monitor restarting after its update could remove Swiss Knife's download halfway (*Could not update: No such file or directory*). Each app now names its folders after itself and removes only its own, and only once they are 15 minutes old.
- **The release build tries `hdiutil` again** when macOS says the disk image is busy (v3.18.1 lost its Apple Silicon files to it until the job was run again).
- **A server left running through an update now says so.** If Swiss Knife was updated while Claude Desktop kept its MCP server running, a tool could fail with *Error -3 while decompressing data: incorrect header check*, which looked like a damaged show. The tool now answers that its own files changed and that Claude Desktop must be quit completely and reopened.

### Added — a pitch video (a tool for the repository, the app does not change)

- **`tools/make_pitch_video.py`** makes a short vertical video about Swiss Knife from the README screenshots and GIFs, with captions, a voice (macOS `say`, `espeak-ng` or `edge-tts`) and a groove made from Swiss Knife's own click sounds. `--stills` also writes one picture per slide and a PDF. It needs Pillow and ffmpeg; Swiss Knife itself still needs neither. The files go to `dist/marketing/`.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
