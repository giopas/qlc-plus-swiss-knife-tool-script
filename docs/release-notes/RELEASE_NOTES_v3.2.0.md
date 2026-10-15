# QLC+ Swiss Knife v3.2.0

Shows made with QLC+ 5.0 to 5.2 open in QLC+ 5.3 as they are. What they lack is what the 5.3 Show Wizard gives a new show. This release adds a tool that gives it to them, step by step, without touching your looks.

## Upgrade to QLC+ 5.3

A new tool in *Check & fix*, and a guided route *Upgrade a show to QLC+ 5.3*. Tick what you want and press ✓ Apply to the show:

- folders for every function, so QLC+ 5 shows the function list as a tree: looks per group, each chaser with its own steps, effects, collections, the setlist and its songs, the PANIC RESET;
- palettes named and valued like the Show Wizard's: Dimmer Full, Half and Off, the Shutter palettes your fixtures can take, and a Color palette for each colour your looks use;
- an All Fixtures group when no group holds the whole rig;
- group grids that follow the stage (not ticked by default, because it changes how your RGB matrices run);
- for moving heads, Position3D palettes for the stage centre, the audience and each musician model you placed in Stage & Meshes (QLC+ 5.3);
- a new Virtual Console page with one frame and a page per group: an intensity slider, the group's looks, its effects, and an XY pad that aims the moving heads at a point on the stage floor;
- hiding the page-switch dimmers and locking the fixtures in 2D and 3D (QLC+ 5.3).

Pick QLC+ 5.2.2 as the target and the steps only 5.3 understands are greyed out. The XY pads list their fixtures one by one, so in 5.2.2 they work as plain pan/tilt pads.

Your scenes keep declaring every channel. The tool adds palettes and XY pads, and never generates scenes that set only part of a fixture. Nothing is removed, and the upgrade is one step in the History you can undo. On a show made by the Show Wizard it points you to Wizard Repair instead. Claude can run it too (`upgrade_show`).

## Doctor

A new information code, I008, lists what a show holds that QLC+ 5.2.2 ignores: Position3D palettes, locked fixtures, XY pads in floor mode, BPM speed dials and EFX dimmer control. Useful when the same show has to run on a computer that still has 5.2.2.

Swiss Knife supports QLC+ 5.2.2 to 5.3.x.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
