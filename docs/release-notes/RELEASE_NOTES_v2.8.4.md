# QLC+ Swiss Knife v2.8.4 — Update and restart, fixed on macOS

First live try of *Update and restart* on the Mac (v2.8.2 → v2.8.3): the new app downloaded, the Dock icon jumped, and it did not open. The update was a `.zip`, and unpacking it broke the app's internal symbolic links.

### Fixed
- The macOS update is now a `.tar.gz`, which keeps the links; versions 2.8.2 and 2.8.3 can use it. The `.dmg` (first install) is unchanged. Unpacking a `.zip` also restores symbolic links now.
- **If your Mac app stopped opening after an update**, install this version from the `.dmg` once (drag it to Applications, replacing the old one).

*Status: Windows and Linux updates are not affected. The macOS update has only been tried by giopas — please report anything odd.*

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
