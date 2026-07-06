@echo off
REM ──────────────────────────────────────────────────────────────────────────
REM  QLC+ Swiss Knife — Windows launcher
REM  Double-click this file to start the app.
REM  No console window stays open (uses pythonw if available).
REM ──────────────────────────────────────────────────────────────────────────

cd /d "%~dp0\.."

REM ── Find Python in venv or system ──────────────────────────────────────────
set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
set "VENV_PYW=%~dp0..\.venv\Scripts\pythonw.exe"

if not exist "%VENV_PY%" (
    echo First run — setting up virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Python not found. Install Python 3 from https://python.org
        pause
        exit /b 1
    )
)

REM ── Install Flask if needed ────────────────────────────────────────────────
"%VENV_PY%" -c "import flask" 2>nul
if errorlevel 1 (
    echo Installing Flask...
    "%VENV_PY%" -m pip install --quiet flask
)

REM ── Launch (use pythonw to hide console if possible) ───────────────────────
if exist "%VENV_PYW%" (
    start "" "%VENV_PYW%" app.py
) else (
    start "" "%VENV_PY%" app.py
)
