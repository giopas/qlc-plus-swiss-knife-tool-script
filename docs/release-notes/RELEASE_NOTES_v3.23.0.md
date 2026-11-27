### Added: Copy Colours

- **Copy Colours** (side menu, 2 · Adapt a show). One light takes the colours another light shows, in every scene and sequence step of the show in progress. Choose *Front Left (Singer)* takes the colours of *Drums Floor*, and wherever the drums go blue, the singer's light goes blue too. Several lights can change in one step.
- *Keep its own brightness* (the default): its dimmer is not touched, and a light without a dimmer stays as bright as it was. A look where either light is dark is left as it is. *Same brightness as the other*: it also takes the other light's level, so it looks the same everywhere.
- *Also add it to the looks it is not in*: in the looks that light the other fixture only, it is added and plays like the other one there (the Function Porter's *plays like*).
- Different models are translated: RGB to RGBW, and RGB to the nearest slot of a moving head's colour wheel. Its position, strobe and gobo stay as they are. Every channel of the light is declared, so no old value leaks in.
- Left as they are, and said on the right: the PANIC RESET looks, palette looks (QLC+ 5.3) and RGB matrices. Doing it twice changes nothing more. The Doctor checks the result, and Apply is one step of the History.
- Claude's `copy_colours` tool (with `preview`), also a `batch` step; guide entry and a *Usual sequences* line; the recipe replays it on another show by what the lights are.
- Wiki: new page *Copy Colours*, a row in *Home*; *Claude Tools* regenerated. 27 new screen strings in the seven languages.
- Tests: `tests/test_colour_copy_3230.py` (15).

---

Downloads for macOS, Windows and Linux, the Claude Desktop file (.mcpb) and the checksums are below. The whole history is in the [CHANGELOG](https://github.com/giopas/qlc-plus-swiss-knife-tool-script/blob/main/CHANGELOG.md).
