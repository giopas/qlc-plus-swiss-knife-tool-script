# QLC+ Swiss Knife v3.5.0

## Stage Monitor

A page for a tablet on stage: the cue playing now in big type, and the one after it, live from QLC+.

It is for the player who moves through the setlist with a MIDI pedal and cannot see the laptop. When the setlist changes during the show, one look down tells you which song the lights are on.

![The Stage Monitor page on a tablet while a pedal moves through the setlist](https://raw.githubusercontent.com/giopas/qlc-plus-swiss-knife-tool-script/main/screenshots/stage-monitor.gif)

- Choose the cue lists, their labels and order, hide the steps that are not songs and rename the others.
- Text from S to XL. Besides dark and high contrast, two colour choices keep the tablet dark on stage: a black screen with only the current song lit, in white or in grey.
- Export the page, press Serve, and type the address shown on the tablet. QLC+ has to be started with web access (`qlcplus -w`).
- If QLC+ or the Wi-Fi drops, the page goes grey with a red dot and reconnects by itself.
- Read-only by default. Control mode adds Previous and Next buttons that need a long press.
- Claude can set it up too, with the new `stage_monitor` tool.

The wiki page *Stage Monitor* explains the network: the Mac's own Wi-Fi with Internet Sharing, and the same on Linux and Windows.

## Also

- `python3 tools/shots.py stage` retakes the Stage Monitor pictures and the GIF, in any language.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
