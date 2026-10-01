# QLC+ Swiss Knife v1.10.0 — new fixtures join the show

### New
- **Function Porter — the copies in the show's own looks.** Fixtures copied from another show used to play only the functions ported with them; in the looks the show already had, they stayed dark. Step 3 now lets each copy **play like** an existing fixture:
  - Every scene and sequence step that lights that fixture lights the copy too, in the same colour and level. Values are translated when the fixture types differ (RGB PAR → RGBW spot, colour wheel…), and every channel is declared. EFX follow too.
  - Chasers, cue lists, collections and buttons play those scenes, so they follow with no change.
  - The suggested choice is the nearest fixture **at the same level, on the same side** of the stage, so ceiling lights follow ceiling lights.
  - What is not wired is listed, with what to do: RGB matrices stay on their own group (their pattern would change), scripts and *Channels* sliders, a missing fixture definition, and the copies you leave dark.
- How-to on the wiki: *Add ceiling lights to a floor show* (Function Porter page).

### Changed
- The README is a presentation of the project; the history is in the CHANGELOG. All screenshots are new.
- The naming profile *two-letter prefix* has the id `prefix`. An older session that used it needs the profile picked again once.

### Fixed
- The VC Visual Editor's title still said *BETA*.

Your original files are never changed.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Function Porter](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Function-Porter).
