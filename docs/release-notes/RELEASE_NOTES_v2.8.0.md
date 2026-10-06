# QLC+ Swiss Knife v2.8.0 — Install like an app

### Added
- **Download and double-click**: packages for macOS (Apple silicon and Intel), Windows and Linux are attached to this release, with a `SHA256SUMS` file. Running from the sources works exactly as before.
- **Update check**: once at start Swiss Knife asks GitHub which version is the latest — nothing about you or your shows is sent, and you can switch it off. A badge appears in the header when a newer version is out.
- **Update and restart**: the packaged app downloads the new version, checks its SHA-256, swaps itself and starts again. Your shows and settings are not touched.

The packages are **not signed**: on macOS right-click › *Open* the first time (or `xattr -dr com.apple.quarantine "/Applications/QLC Swiss Knife.app"`); on Windows *More info › Run anyway*.

Full details: [CHANGELOG](../../CHANGELOG.md). Wiki: [Installing and updating](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Installing-and-updating).

**Status:** the packages are built and smoke-tested by GitHub Actions; the macOS and Windows ones and the in-app update on those systems have not been tried live yet — please report anything odd.
