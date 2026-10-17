#!/bin/sh
# QLC+ Swiss Knife — Stage Monitor: run (or double-click) to serve this folder to the tablet.
# Uses Python 3, or QLC Swiss Knife if it is on the PATH or in ~/QLC-Swiss-Knife. Ctrl+C stops it.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then exec python3 serve_stage.py; fi
for sk in "$(command -v QLC-Swiss-Knife)" "$HOME/QLC-Swiss-Knife/QLC-Swiss-Knife"; do
  if [ -n "$sk" ] && [ -x "$sk" ]; then exec "$sk" --serve-stage "$PWD"; fi
done
echo "The Stage Monitor needs Python 3 or QLC Swiss Knife."
