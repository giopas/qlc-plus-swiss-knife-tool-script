#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  QLC+ Swiss Knife — launcher
#  Double-click this file (or run: bash run.sh) to start the app.
#  No need to activate the venv manually.
#
#  Options:
#    --browser    Force browser mode (skip native window even if pywebview installed)
# ─────────────────────────────────────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Virtualenv location: $SWK_VENV, else ~/.venvs/swissknife if it exists, else
# ./.venv if it exists; new installs on macOS go to ~/.venvs/swissknife because
# iCloud-synced folders (Documents, Desktop) create "file 2.js" duplicates inside
# a venv, which crashes pywebview (KeyError: 'text_select').
if [ -n "$SWK_VENV" ]; then VENV_DIR="$SWK_VENV"
elif [ -x "$HOME/.venvs/swissknife/bin/python3" ]; then VENV_DIR="$HOME/.venvs/swissknife"
elif [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then VENV_DIR="$SCRIPT_DIR/.venv"
elif [ "$(uname)" = "Darwin" ]; then VENV_DIR="$HOME/.venvs/swissknife"
else VENV_DIR="$SCRIPT_DIR/.venv"
fi
VENV_PY="$VENV_DIR/bin/python3"
SYSTEM_PY="$(command -v python3 || command -v python || echo '')"

# ── First run: create venv + install Flask if missing ─────────────────────────
if [ ! -f "$VENV_PY" ]; then
    echo ""
    echo "⚙  First run — setting up virtual environment..."
    if [ -z "$SYSTEM_PY" ]; then
        echo "ERROR: python3 not found. Install Python 3 from https://python.org"
        exit 1
    fi
    mkdir -p "$(dirname "$VENV_DIR")"
    "$SYSTEM_PY" -m venv "$VENV_DIR"
    echo "✓  Virtual environment created."
fi

# ── Install / upgrade Flask inside the venv if needed ─────────────────────────
if ! "$VENV_PY" -c "import flask" 2>/dev/null; then
    echo "⚙  Installing Flask..."
    "$VENV_PY" -m pip install --quiet flask
    echo "✓  Flask installed."
fi

# ── Optional: install pywebview for native window mode ────────────────────────
if ! "$VENV_PY" -c "import webview" 2>/dev/null; then
    echo ""
    echo "ℹ  pywebview is not installed — the app will open in your browser."
    echo "   For a native window experience, run:"
    echo "     $VENV_DIR/bin/pip install \"pywebview\""
    echo ""
fi

# ── Launch ─────────────────────────────────────────────────────────────────────
echo ""
echo "⚡  Starting QLC+ Swiss Knife..."
exec "$VENV_PY" "$SCRIPT_DIR/app.py" "$@"
