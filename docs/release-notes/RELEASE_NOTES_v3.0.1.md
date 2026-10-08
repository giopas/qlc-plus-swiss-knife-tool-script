# QLC+ Swiss Knife v3.0.1

This release comes from describing a real show with Claude. The Dictionary can now draft descriptions by itself and hand the job to Claude, the setlist cue notes name the button that plays each cue, and Claude's tools are documented where Claude can read them.

## Dictionary

- **✨ Draft descriptions** fills every empty description from the show itself. A scene says which colours it shows and on which fixtures, a chaser says how it changes, a collection or script says what it starts, and a helper scene says which step of which chaser it is. The colours are read from the fixture definitions. Descriptions you wrote stay as they are.
- **💾 Save as new file** writes `<show>_dictionary.txt` next to the show, or `_v2` when the name is taken.
- **🤖 Ask Claude…** opens a window with a request to paste in Claude Desktop. Choose what Claude writes and whether it shows you the lines first, copy, paste. Swiss Knife cannot start Claude: Claude Desktop starts Swiss Knife.
- *Browse TXT* is now **📂 Load dictionary…**.

## Setlist

- Each cue note names the button that plays the same look, such as `↪ [5225] button: XM · TMO Drive`, or says what the cue plays when no button does.
- Swiss Knife's own notes are rewritten when they no longer match the show (renumbered functions, a new button), when a show opens and before saving. Notes you typed in QLC+ are never touched.
- *Load Slot File* and *Save Slot File* are now **Load setlist…** and **Save setlist…**. The QLC+ functions button is easier to spot, and with the list closed the songs take the free space.

## Claude

- A `guide` tool explains every other tool, with its arguments and an example. The same text is the new wiki page *Claude's tools*.
- Ready requests in Claude Desktop: write the Dictionary, check and fix a show, adapt a show to fewer fixtures, add buttons for looks that have none.
- `dictionary_set` can draft the descriptions Claude does not write itself, and `list_shows` can search and page through many shows.

## Fixes

- The Doctor no longer reports the originals of setlist copies as unused (D016), and D012 names the widgets bound to an unpatched controller.
- Tooltips are no longer cut off at the top of the window or by narrow columns.

After *Update and restart*, quit and reopen Claude Desktop so it starts the new Swiss Knife. To get the ready requests in Claude Desktop, reinstall the connection from *🔌 Connect to Claude*.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
