# QLC+ Swiss Knife v3.5.2

## macOS packages again

3.5.1 was published without its macOS packages. One of its tests opened a real browser on the macOS build machines, the test failed there, and the macOS builds stopped. 3.5.2 has every package.

What 3.5.1 changed is in here too: in the Stage Monitor, *👁 Preview* opens the page in your browser, also when Swiss Knife runs in its own window. It now opens a browser only when you press the button, so the tests never do. When you use Swiss Knife in a browser tab, the preview opens in a new tab of that browser, which is the right place even when Swiss Knife runs on another machine.

On a Mac with 3.5.0, *Update and restart* goes straight to 3.5.2.

Full details: [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
