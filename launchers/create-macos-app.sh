#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  create-macos-app.sh
#  Creates a macOS .app bundle for QLC+ Swiss Knife.
#
#  Usage:
#    cd qlc-plus-swiss-knife-tool-script
#    bash launchers/create-macos-app.sh
#
#  The .app bundle is created in the project root.  You can drag it to
#  /Applications or keep it wherever you like.  Double-click to launch.
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="QLC+ Swiss Knife"
APP_DIR="$PROJECT_DIR/${APP_NAME}.app"

echo "⚙  Creating ${APP_NAME}.app …"

# ── Build the .app structure ─────────────────────────────────────────────────
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# ── Launcher script ──────────────────────────────────────────────────────────
cat > "$APP_DIR/Contents/MacOS/launch" << 'LAUNCHER'
#!/usr/bin/env bash
# Resolve the project directory (the .app lives inside it or nearby)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$PROJECT_DIR"

# Virtualenv location: $SWK_VENV, else ~/.venvs/swissknife if it exists, else
# ./.venv if it exists; new installs on macOS go to ~/.venvs/swissknife because
# iCloud-synced folders (Documents, Desktop) create "file 2.js" duplicates inside
# a venv, which crashes pywebview (KeyError: 'text_select').
if [ -n "$SWK_VENV" ]; then VENV_DIR="$SWK_VENV"
elif [ -x "$HOME/.venvs/swissknife/bin/python3" ]; then VENV_DIR="$HOME/.venvs/swissknife"
elif [ -x "$PROJECT_DIR/.venv/bin/python3" ]; then VENV_DIR="$PROJECT_DIR/.venv"
elif [ "$(uname)" = "Darwin" ]; then VENV_DIR="$HOME/.venvs/swissknife"
else VENV_DIR="$PROJECT_DIR/.venv"
fi
VENV_PY="$VENV_DIR/bin/python3"
SYSTEM_PY="$(command -v python3 || command -v python || echo '')"

# Create venv if needed
if [ ! -f "$VENV_PY" ]; then
    if [ -z "$SYSTEM_PY" ]; then
        osascript -e 'display alert "Python 3 not found" message "Install Python 3 from python.org to use QLC+ Swiss Knife." as critical'
        exit 1
    fi
    mkdir -p "$(dirname "$VENV_DIR")"
    "$SYSTEM_PY" -m venv "$VENV_DIR"
fi

# Install Flask if needed
if ! "$VENV_PY" -c "import flask" 2>/dev/null; then
    "$VENV_PY" -m pip install --quiet flask
fi

# Launch
exec "$VENV_PY" "$PROJECT_DIR/app.py"
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/launch"

# ── Info.plist ───────────────────────────────────────────────────────────────
cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>QLC+ Swiss Knife</string>
  <key>CFBundleDisplayName</key>
  <string>QLC+ Swiss Knife</string>
  <key>CFBundleIdentifier</key>
  <string>com.giopas.qlc-swiss-knife</string>
  <key>CFBundleVersion</key>
  <string>1.1.1</string>
  <key>CFBundleExecutable</key>
  <string>launch</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.15</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

echo "✓  Created: ${APP_DIR}"
echo ""
echo "   Double-click '${APP_NAME}.app' to launch, or drag it to /Applications."
echo "   Tip: install pywebview for a native window experience:"
echo "     .venv/bin/pip install pywebview"
