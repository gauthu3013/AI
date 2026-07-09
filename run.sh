#!/usr/bin/env bash
# ============================================================
#  Monsoon Twin - one-click launcher for macOS / Linux
#  Run with:  ./run.sh   (or: bash run.sh)
# ============================================================
set -e
cd "$(dirname "$0")"

echo
echo "  Monsoon Twin - Digital Twin for Monsoon Preparedness"
echo "  ----------------------------------------------------"
echo
echo "  Installing dependencies (first run may take a minute)..."
echo

python3 -m pip install -r requirements.txt

echo
echo "  Starting the server and opening http://localhost:8000 ..."
echo "  Keep this window open while you use the app."
echo "  To stop: press Ctrl+C."
echo

# Open the browser a few seconds after the server has had time to start.
( sleep 3; python3 -m webbrowser "http://localhost:8000" >/dev/null 2>&1 ) &

exec python3 -m uvicorn app.main:app --port 8000
