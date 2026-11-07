### Fixed — beams that point the right way (3.17.0)

- **Stage & Meshes drew many beams in the wrong direction.** Pan was turned the wrong way and roll was applied too early, so a PAR on a PA stack turned toward the middle was drawn pointing off the stage, and ceiling spots panned to one side were drawn going to the other. The beams now turn exactly as in QLC+'s 3D view (the same rotation QLC+ uses), on the plan and in the front view. Positions were right and are unchanged.

### Added — the stage size on the cabling plan (3.17.0)

- **The cabling plot shows the stage's width and depth** as dimension lines, *(tonight)* when the plan uses a stage size of its own.
- **Over the plot**, the stage size and a link to Stage & Meshes to change it.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
