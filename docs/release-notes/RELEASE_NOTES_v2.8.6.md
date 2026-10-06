# QLC+ Swiss Knife v2.8.6 — Windows: it starts, and there is an installer

### Fixed
- The first Windows package stopped at start with `UnicodeEncodeError ... '\u26a1'`. The start message can no longer break on a Windows console.

### Added
- **Windows installer** — `QLC-Swiss-Knife-2.8.6-windows-x64-setup.exe`: no administrator needed, Start menu entry, optional desktop shortcut, uninstall from *Apps & features*. Windows shows its *unknown publisher* warning once (the app is not signed yet): *More info › Run anyway*.
- The `.zip` is still there if you prefer to unzip it anywhere.

*Status: the Windows package and installer are built and tested by GitHub Actions (silent install, start, uninstall); giopas is the first to try them on a real Windows PC — please report anything odd.*

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
