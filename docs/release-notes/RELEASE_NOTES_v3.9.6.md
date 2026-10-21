The wiki and the README, rewritten so that a reader of 10 or 15 can follow each feature. No change to the app's behaviour.

### Documentation (3.9.6: plain-language wiki and README)

No change to the app, to `core/` behaviour or to what any button writes. The words change.

- **README.** Three sentences on what Swiss Knife is, who it is for, a first ten minutes (install, open, look at the Doctor, try one tool, save), the six tool groups in one plain line each, and a short Claude section. Installation, privacy and licence text are as before.
- **Words used here** (new wiki page). About 60 terms in one sentence each, grouped by the signal, the show, playing it, the stage and Swiss Knife's own words, with a table that shows how long one chaser step lasts at a given BPM and Beats per step.
- **Every wiki page now has the same shape.** An *In one minute* box with a real gig as the example, *Before you start*, an example where the page had none, *If it does not work* with the three usual causes, and *Words used here* with the terms of that page. The stubs (Show Book, Setup Checklist, Tech Rider) are unchanged.
- **Tablet on stage** is documented in its own wiki page, `Tablet-on-stage` (the old `Stage-Monitor` page stays as a pointer): the two modes, song cards, the Next song banner, views by role, and the QR code. The tool's **?** button opens it, and the Setlist page points to it.
- Button names in the wiki and README follow the app since 3.9.5, with no emoji. A few very long sentences on Cabling, Look Builder and the tablet page are cut in two.
- `tools/plain_check.py` (advisory): average and longest sentence per page, dashes used as connectors, terms used before they are explained, pages without the box. `tests/test_plain_check.py` covers it.
- `core/mcp_guide.py`: only the heading and the box of the generated *Claude's tools* wiki page changed. The text Claude reads with the `guide` tool is as before.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
