@echo off
rem QLC+ Swiss Knife - Stage Monitor: double-click to serve this folder to the tablet.
rem Uses QLC Swiss Knife if it is installed (no Python needed), else Python 3. Close this window to stop.
cd /d "%~dp0"
title Stage Monitor
for %%P in ("%ProgramFiles%\QLC Swiss Knife" "%LocalAppData%\Programs\QLC Swiss Knife") do (
  if exist "%%~P\QLC Swiss Knife MCP.exe" (
    "%%~P\QLC Swiss Knife MCP.exe" --serve-stage "%~dp0."
    goto :end
  )
)
where py >nul 2>nul && (py serve_stage.py & goto :end)
where python >nul 2>nul && (python serve_stage.py & goto :end)
echo The Stage Monitor needs QLC Swiss Knife or Python 3.
:end
pause
