# QLC+ Swiss Knife v3.5.3

## Stage Monitor at the gig

At the gig you now double-click one file. The export writes **Start Stage Monitor** next to the page (`.command` on macOS, `.bat` on Windows, `.sh` on Linux). It opens a small window that:

- serves the page to the tablet and shows the address to type, the computer's own Wi-Fi first;
- says whether QLC+ answers, and if not, the exact command to start it with `-w` and your show;
- lists each device that opens the page, and tells you when one asked for `https://` by mistake (Chrome on Android often does), with the `http://` address to type instead.

It runs on the installed Swiss Knife, so no Python is needed, and Swiss Knife itself can stay closed. *📂 Show the folder* on the Stage Monitor screen opens the folder.

The wiki now explains what to run at home and at the gig, and how to make a Wi-Fi network from the Mac without internet: the port you share from needs a link, and one command tells you whether the network started.

After updating, export the page once more so the folder gets Start Stage Monitor.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
