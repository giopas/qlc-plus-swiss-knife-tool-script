# QLC+ Swiss Knife v3.5.5

## Stop on the tablet, safety hold

In Control mode the Stage Monitor page now has a *Stop* button between *Previous* and *Next*. It is the CueList's own Stop button, so it stops that list the same way QLC+ would. Hold it for 1.2 s, twice as long as the other two. It works only while the list plays or is paused. Otherwise it is greyed out, because in QLC+ a Stop on a list that is already stopped sends it back to its first step. If the CueList uses the *Play/Stop/Pause* layout, the button reads *Pause* and *Resume*, as it does in QLC+.

A new setting, *Safety hold*, decides how long *Previous* and *Next* must be held: 0.3, 0.6 (the default, as before), 1 or 1.5 seconds, or off. With it off a tap acts at once, which helps when the setlist changes mid-show and you need to skip several songs. *Stop* always needs a longer hold, at least 1.2 s, so a tap never stops a list.

Export the page again to get the button and the new hold. Read-only lists are unchanged.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
