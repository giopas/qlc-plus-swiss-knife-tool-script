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

VENV_PY="$SCRIPT_DIR/.venv/bin/python3"
SYSTEM_PY="$(command -v python3 || command -v python || echo '')"

# ── First run: create venv + install Flask if missing ─────────────────────────
if [ ! -f "$VENV_PY" ]; then
    echo ""
    echo "⚙  First run — setting up virtual environment..."
    if [ -z "$SYSTEM_PY" ]; then
        echo "ERROR: python3 not found. Install Python 3 from https://python.org"
        exit 1
    fi
    "$SYSTEM_PY" -m venv .venv
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
    echo "     $SCRIPT_DIR/.venv/bin/pip install pywebview"
    echo ""
fi

# ── Launch ─────────────────────────────────────────────────────────────────────
echo ""
echo "⚡  Starting QLC+ Swiss Knife..."
exec "$VENV_PY" "$SCRIPT_DIR/app.py" "$@"
