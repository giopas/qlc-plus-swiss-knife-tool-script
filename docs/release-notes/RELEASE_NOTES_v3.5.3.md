# QLC+ Swiss Knife v3.5.3

## Stage Monitor at the gig

Fixes from the first try with a phone on the Mac's own Wi-Fi.

- `serve_stage.py` prints every address of the computer, its own Wi-Fi first, so you no longer get the home network's address by mistake.
- Chrome on Android often asks for `https://` by itself, and then the page shows `ERR_SSL_PROTOCOL_ERROR`. The script and the Serve screen now say which device did it and which `http://` address to type.
- At the gig you only need QLC+ (started with `-w`) and the page server. Swiss Knife is for exporting the page at home. The Serve screen and the wiki now say so.
- The wiki explains how to make a Wi-Fi network from the Mac with no internet: the port you share from needs a link, and one command tells you whether the network started.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
