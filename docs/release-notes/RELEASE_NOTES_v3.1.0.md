# QLC+ Swiss Knife v3.1.0

QLC+ 5.3.0 has a new Show Wizard that builds a whole show in a few steps. This release makes Swiss Knife read those shows correctly and adds a tool that finishes them.

## Wizard shows are safe in Swiss Knife

The Show Wizard builds most of its looks as *palette scenes*: a fixture group and a palette, with no channel values. Swiss Knife 3.0.3 read them as empty, and a few of its tools damaged them. Now:

- The Workspace Doctor reads palettes. Palette scenes are no longer empty, and colour, gobo or shutter buttons that are meant to be combined (*layer scenes*) are listed once instead of being "fixed" into full looks.
- Two new Doctor checks: D019 finds a scene or XY pad that uses a palette or group that does not exist (fixed by default), and D020 finds a palette that sets nothing on its fixtures.
- The Rig Reducer cleans palette scenes, XY pads and the wizard's frame pages when it removes fixtures, and keeps the dimmers that switch the pages.
- The Function Porter brings a palette scene's group and palettes along. In 3.0.3 a ported palette scene could end up pointing at the wrong group and palette.
- Compare and the Dictionary drafts read what a palette scene does. The page-switch dimmers stay out of the patch sheet, the tech rider and the crew checklist.

## Wizard Repair

A new tool in *Check & fix*, and a guided route *Finish a QLC+ wizard show*. Tick what you want and press ✓ Apply to the show:

- the Color Rainbow, Split Color and Strobe Chase chasers, which QLC+ 5.3.0 forgets to create;
- strobe and colour values for fixtures the wizard's palettes don't reach (a Sharpy's strobe, a colour wheel);
- a PANIC RESET button next to Blackout on every page;
- buttons for the matrices, positions, dimmer levels and blinder hits the wizard left off the console;
- group grids that follow the stage, so matrix effects on the side columns run the same way on both sides;
- hiding the page-switch dimmers, locking the fixtures in 2D and 3D, captions for the gobo buttons.

Nothing is removed, and every repair is a step in the History you can undo. Claude can run it too (`wizard_repair`).

Swiss Knife supports QLC+ 5.2.2 to 5.3.x.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
