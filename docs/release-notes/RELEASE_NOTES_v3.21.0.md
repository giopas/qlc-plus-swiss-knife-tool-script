### Added — Brightness and QLC+ palette looks

- **Brightness shows the palette looks.** Shows made by the QLC+ 5.3 Show Wizard build most looks from a fixture group and a Dimmer palette (*Dimmer Full*, *Dimmer Half*), with no level of their own. Brightness always left them as they were, and only the History said so. A bar under the toolbar now says how many looks of the scaled lights take their dimmer from a palette, and which palettes.
- **Also scale the Dimmer palettes** (off by default) makes those looks follow. When only the scaled lights use a palette, the palette is scaled. When other lights share it, a scaled copy is made (*Dimmer Full 70%*) and only the looks of the scaled lights point to it; the other lights keep the original. A look that mixes lights at different levels stays as it is and is counted. A fanned palette has its end value scaled too. Lights with no dimmer channel do not count, since a Dimmer palette does nothing on them.
- The footer and the History step count the palette looks that follow.

### Added — the Function Porter's mapping as a file

- **Save mapping… / Load mapping…** in step 3 keep the targets of each light, the lights not ported, Mirror Pan and the step's options in a small file (`<source>_to_<target>.portermap.json`). Loaded in the next port between the same rigs, lights are found by ID and name, then by name with model and mode, then by name; a show that numbers its lights differently still works. Lights the file does not know are auto-mapped, and the status line says how many. QLC+'s Fixture Remap cannot reopen a mapping once it is made.
- New: `core/porter_map.py`, `POST /api/porter/map/export` and `POST /api/porter/map/import`.

### Docs — what QLC+ already does

- **New wiki page *Swiss Knife and QLC+*.** Tool by tool: what QLC+ has built in (Fixture Remap, palettes, channel modifiers, the Show Wizard), when to use QLC+ itself, and what Swiss Knife adds. With how to swap one light model for another, and short sections on palettes and channel modifiers. Linked from Home, the README and the tool pages.
- *Function Porter*: **Function Porter or QLC+ Fixture Remap?**, a side-by-side table, and the mapping file.
- *Rig Reducer*: **Why not delete the lights in QLC+?**
- *Brightness*: the palette looks and the new option, and **Brightness, palettes and channel modifiers** (which of the three to use when). Swiss Knife does not make channel modifiers: QLC+ keeps your own curves as files on each computer.
- *Upgrade to QLC+ 5.3* and *Look Builder*: the palettes they add do not drive the looks you already have.
- *Cabling*: what it is for, and that CAD tools such as Vectorworks Spotlight, with MVR and GDTF, do the rig drawing in professional work.
- *Words used here*: palette (now any saved value), palette look, Fixture Remap, channel modifier.
- **Claude's guide**: when a request fits a feature QLC+ already has (Fixture Remap, a Dimmer palette, a channel modifier), Claude says so before using a tool. *Claude Tools* regenerated.

### Changed

- The **?** links can open a section of a wiki page (`Brightness#…`). The help route still accepts only wiki page names, now with an optional lowercase anchor.
- 26 new screen strings in the seven languages.
- Tests: `tests/test_brightness_palettes_3210.py`, `tests/test_porter_map_3210.py`, and the help route's anchor in `tests/test_ui_consistency.py`.

### Added — share the video page

- **Share buttons on the video page.** Under the video: *Share the video* (the phone's own share menu, shown only where the browser has one), *Send on WhatsApp* and *Copy the link*. They send the link to the page, never the video file, so in WhatsApp it comes as a preview card and the video plays in the browser with nothing to download. The message says what Swiss Knife is, then the video link, then the download page of the latest release.
- **When the video ends**, a card over it offers *Download Swiss Knife* (free, for Mac, Windows and Linux) and *Watch again*. It goes away when the video plays.

### Fixed — the video page's link preview

- **Shared links to the video page had no picture.** Its `og:image` was a relative URL, which WhatsApp and the other chat apps ignore. `og:url`, `og:image` and `og:video` are now absolute, with `og:image:alt`, `og:site_name`, `og:video:type` and a large Twitter card.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
