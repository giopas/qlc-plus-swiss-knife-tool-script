### Fixed — the update card (3.14.1)

- **No download for Apple-silicon Macs in 3.13.0 and 3.14.0.** GitHub retired the macOS 14 build machine, so the release build for Apple silicon stopped with an error and the Mac `.zip` and `.dmg` were missing from those two releases; on such a Mac, *Update and restart* had nothing to download and did not appear. The build now runs on macOS 15. 3.14.1 is the first release with every download again.
- **Update and restart was also missing** when Swiss Knife checked for updates in the minutes after a release, while GitHub was still building the downloads. That answer was kept for 12 hours, so the card showed only *Open the release page*. Now such an answer is asked again after 10 minutes, and the card says the download is still being prepared and to press *Check now* a little later.
- **The release notes in the card** are shown with their headings, bold text and bullets, instead of raw `###` and `**` marks.

If your Swiss Knife shows a newer version but no *Update and restart* button, press **Check now** under the side menu.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
