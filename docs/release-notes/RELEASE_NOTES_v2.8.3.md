# QLC+ Swiss Knife v2.8.3 — QLC+ 5.3.0 compatibility

QLC+ 5.3.0 saves Script commands in a new form (`Engine.stopFunction(6);` instead of `stopfunction:6`). Files it saves are fine, and QLC+ 5.3.0 opens the old form too — but the tools did not understand the new one.

### Fixed
- **Doctor:** no more false *unreferenced function* warning on the PANIC RESET scene of a file saved by QLC+ 5.3.0.
- **Function Porter, Look Builder, Doctor fixes, Rig Reducer:** dependencies, renumbering and clean-up of dead references work on both forms of script command. When a PANIC RESET script is extended, the new stop commands follow that script's style.
- New scripts are still written in the old form, which QLC+ 5.2 and 5.3 both open.

### Also
- The live-check tool finds QLC+ 5.3 on macOS; the workflows run on Ubuntu 24.04.

This is also the first update you can install from inside v2.8.2 with *Update and restart*.

*Status: the packages are built and smoke-tested by GitHub Actions; the macOS and Windows ones have only been tried by giopas on the Mac so far — please report anything odd.*

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
