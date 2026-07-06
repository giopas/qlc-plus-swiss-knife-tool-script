# Release Notes — v1.1.1

## Standalone App Experience

### Quit Button (UI)
A **Quit** button now sits at the bottom of the sidebar (power icon, red accent). Clicking it prompts for unsaved session changes, sends `POST /api/quit` to shut down the Flask server cleanly, and shows a "shut down" screen. Works in both browser and native window mode.

### Native Window Mode (pywebview)
If [pywebview](https://pywebview.flowrl.com/) is installed, the app opens in a **native OS window** instead of a browser tab — no URL bar, no browser chrome, and a real close button that shuts down the server on exit. Falls back to browser mode automatically if pywebview is not installed.

- Install: `.venv/bin/pip install pywebview` (optional)
- Force browser mode: `python3 app.py --browser`

### Platform Launchers
Ready-to-use launchers for all three platforms, located in the `launchers/` directory:

| Platform | File | What it does |
|---|---|---|
| **macOS** | `launchers/create-macos-app.sh` | Creates a `.app` bundle you can double-click or drag to `/Applications` |
| **Windows** | `launchers/QLC_Swiss_Knife.bat` | Double-click launcher that hides the console window (uses `pythonw`) |
| **Linux** | `launchers/qlc-swiss-knife.desktop` | `.desktop` file for the app menu |

### Session Save on Workspace Switch
When you load a new workspace while the current session has unsaved changes, the app now **prompts to save the session** with a filename matching the previous showfile (e.g. `MyShow.qsk`). This prevents losing session state when switching between shows.

### Misc
- Hardcoded version string in VC Visual Editor statusbar now uses the template variable.
- Updated `.gitignore` to exclude generated `.app` bundles and sensitive files.
