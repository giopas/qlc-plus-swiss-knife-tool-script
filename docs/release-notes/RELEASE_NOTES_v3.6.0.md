# QLC+ Swiss Knife v3.6.0

## Plan the DMX cables

![Cabling: the kit, the stage, three alternatives and the checks](https://raw.githubusercontent.com/giopas/qlc-plus-swiss-knife-tool-script/main/screenshots/cabling.gif)

**Cabling** is a new screen in *4 · Run the show*. It plans the DMX cables of the show in progress with the kit you own: which splitter output feeds which fixtures, in what order, which cable goes where, the adapters and terminators you need, and what is missing. It reads the show and never changes it; the plan is kept next to the show in `<show>.cabling.json`.

- **My kit** is what you own: interfaces, splitters, nodes, wireless units, adapters, terminators, cables and your fixtures, in metres or feet. Add fixtures from the QLC+ library on your computer, from the show, from QLC+ on GitHub or by hand, or ask Claude from a photo of the fixture's back panel. Export it as a file and import it on another computer. A wishlist keeps what a plan found missing until you have it; then one click puts it in your kit. Each show starts from a copy, *Tonight's kit*, where you can mark the venue's fixtures as house rig.
- **Places**: where the computer stands (where you stand, front of house with the mixer remote, or let the planner choose), the splitter, outlets, walkways, fixtures found on the day, and tonight's stage size when the venue's stage is not the show's. The band floor (every mesh plus the space you set round it) is kept clear where it can be; a mesh the cables may cross can be left out.
- **Plan**: two or three alternatives, such as a splitter on stage, at the computer, one daisy chain, a long feed, a node on the network, or wireless to the stage. Each is compared on cable, longest hop, crossings, adapters and what is missing. Change any chain by hand.
- **Check and export**: 24 checks with a fix or a line on the shopping list, then a cabling plot, a pick list, cable labels and a load-in order. The crew checklist in Show Paperwork carries them too.

Claude gets a `cabling` tool and two ready requests: *Plan the DMX cabling for tonight* and *Add a fixture to my kit*.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md) and the wiki page [Cabling](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/wiki/Cabling).
