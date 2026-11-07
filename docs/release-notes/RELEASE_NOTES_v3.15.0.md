### Added — single fixtures by radio in Cabling (3.15.0)

- **A fixture can get its DMX by radio.** Click it on the plan and choose *by radio, a receiver of its own* under *Gets DMX*. The first time, the wireless transmitter goes on a free output of the splitter (or of the interface when no splitter is fed) and stands next to it. Every fixture sent by radio gets its own receiver, which stands by the fixture (on its truss when the fixture hangs), so two fixtures on opposite sides of the stage no longer share a cable.
- **The plan shows it.** A fixture fed by radio has a dashed violet ring and the word *radio* on the plot, a *radio* tag in its chain, and its box says which receiver feeds it. The receivers (RX) and the transmitter (TX) are drawn as small boxes, and the legend explains the dashed lines.
- **Cables and terminators follow.** The radio link needs no cable. The chains the fixtures left are walked again, so the fixture now last on each of them gets the terminator, and each fixture by radio gets one at the end of its own short chain. A transmitter with no thru ends its line itself, so it needs none.
- **The counts follow too.** One transmitter can feed any number of receivers. When the plan needs more receivers than tonight's kit has, the rest go on the shopping list. The pick list counts one receiver per fixture by radio, and the load-in order says where each one goes.
- **Claude** can wire the same: a chain from a free splitter output to the transmitter, then one chain per fixture from the transmitter through a receiver.

### Changed — a cabling plot you can read (3.15.0)

- **Cable lengths on tags.** Each length (and *to buy*, *venue*, *borrowed*) sits on a small white tag in the colour of its chain. The tag goes on its cable when there is room. Otherwise it moves beside the cable, away from fixtures, names, boxes, other cables and other tags, and a thin line with a dot points back to the cable it belongs to. Tags never cover each other.
- **Fixture names where they are free.** A name goes under its fixture, or above or beside it when another fixture or box is in the way.
- **Every word has a white halo**, so it stays readable where it crosses a line or the band floor.
- The legend at the bottom was cut off at the right edge. It now stays inside the picture.

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
