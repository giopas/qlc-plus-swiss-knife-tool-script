# QLC+ Swiss Knife v3.5.4

## Ask before replacing, step notes

Swiss Knife never writes over a file, with one exception: exporting the Stage Monitor page again into the same folder. That now asks first. Swiss Knife lists the files from the earlier export and replaces them only when you say yes; *Cancel* keeps the earlier page. Claude's `stage_monitor` tool stops in the same way and asks you before it replaces anything. Files the Stage Monitor did not write are never replaced, and the show is never touched.

A new option, *Show step notes*, decides whether the notes written on the CueList's steps in QLC+ (a key, a capo, who counts in) appear under each name on the tablet. They are on by default.

The mode of each cue list now says what it does: *Read-only* shows the cues, *Control* adds Previous and Next buttons that need a long press. The wiki page *Stage Monitor* explains when to choose which.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
