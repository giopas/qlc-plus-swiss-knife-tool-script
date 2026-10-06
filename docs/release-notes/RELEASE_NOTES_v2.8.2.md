# QLC+ Swiss Knife v2.8.2 — update check, fixed

Found on the first live try of *Update and restart*.

### Added
- **Check now** under the menu, next to *Check for updates*: asks GitHub again (the app otherwise remembers the answer for 12 hours) and tells you whether you have the latest version, or opens the update card.

### Fixed
- The update arrow in the top bar was always visible; now it shows only when a newer version is out.
- Tooltips in the top bar opened upwards, outside the window, and could not be read; they now open below.

Same tools, same files, same shows.

*Status: the packages are built and smoke-tested by GitHub Actions; the macOS and Windows ones and the in-app update on those systems have only been tried by giopas on the Mac so far — please report anything odd.*

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
