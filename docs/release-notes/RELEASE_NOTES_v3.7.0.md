# QLC+ Swiss Knife v3.7.0

## Another computer, another screen

For the day the show moves: to a stage laptop, a Raspberry Pi, a tablet or a small touchscreen.

- **Fixture definitions that travel.** A `.qxw` does not carry its fixture definitions, so on another computer a custom fixture opens as a generic dimmer. The Workspace Doctor now warns about it (D021 to D023), and **📦 Take the show elsewhere (.zip)…** in the Doctor and in Show Paperwork saves the show with every definition that is not in QLC+'s stock library, named as QLC+ looks for it. Claude's `save_show` can write the same zip.
- **Fit the Virtual Console to a screen.** The *Screen size* panel in the VC Visual Editor has more screens (HD, QHD, 4K, 7-inch touchscreens, Raspberry Pi Touch Display 2, iPads) and three ways to apply them: *Fit* keeps the buttons' shapes, *Stretch* scales width and height separately, *Page size only* leaves the widgets alone. Text scales within limits, **🔍 Check** says what would happen without changing the show, and on touch screens it names the buttons smaller than 44 px. Claude's `edit_vc` takes the same options.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
