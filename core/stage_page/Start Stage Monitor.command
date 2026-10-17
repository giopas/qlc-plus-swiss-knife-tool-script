#!/bin/bash
# QLC+ Swiss Knife — Stage Monitor: double-click to serve this folder to the tablet.
# Uses QLC Swiss Knife if it is installed (no Python needed), else Python 3.
# Close this window to stop.
cd "$(dirname "$0")" || exit 1
for app in "/Applications/QLC Swiss Knife.app" "$HOME/Applications/QLC Swiss Knife.app"; do
  if [ -x "$app/Contents/MacOS/QLC Swiss Knife" ]; then
    exec "$app/Contents/MacOS/QLC Swiss Knife" --serve-stage "$PWD"
  fi
done
# /usr/bin/python3 is only a stub until the Command Line Tools are installed: do not trigger their installer
if command -v python3 >/dev/null 2>&1 && { [ "$(command -v python3)" != "/usr/bin/python3" ] || xcode-select -p >/dev/null 2>&1; }; then
  exec python3 serve_stage.py
fi
echo "The Stage Monitor needs QLC Swiss Knife in Applications, or Python 3."
echo "Install one of them, or serve this folder with any web server."
read -r -p "Press Return to close."
