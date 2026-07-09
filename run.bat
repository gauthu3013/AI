@echo off
REM ============================================================
REM  Monsoon Twin - one-click launcher for Windows
REM  Double-click this file to install dependencies (first run)
REM  and start the app, then it opens in your browser.
REM ============================================================
cd /d "%~dp0"
title Monsoon Twin

echo.
echo   Monsoon Twin - Digital Twin for Monsoon Preparedness
echo   ----------------------------------------------------
echo.
echo   Installing dependencies (first run may take a minute)...
echo.

python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo   [!] Python was not found or pip failed.
  echo       Install Python 3.10+ from https://www.python.org/downloads/
  echo       During install, TICK "Add python.exe to PATH", then run this again.
  echo.
  pause
  exit /b 1
)

echo.
echo   Starting the server and opening http://localhost:8000 ...
echo   Keep this window open while you use the app.
echo   To stop: press Ctrl+C, or just close this window.
echo.

REM Open the browser a few seconds after the server has had time to start.
start "" /min cmd /c "timeout /t 3 >nul & start "" http://localhost:8000"

python -m uvicorn app.main:app --port 8000

pause
