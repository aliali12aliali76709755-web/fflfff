#!/usr/bin/env bash
# تشغيل على macOS / Linux:  bash start.sh
set -e
cd "$(dirname "$0")"
PY=python3
command -v $PY >/dev/null || { echo "[X] Python 3.10+ is required."; exit 1; }
$PY -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || { echo "[X] Python 3.10+ is required."; exit 1; }
[ -d .venv ] || { echo "[1/3] Creating virtual environment..."; $PY -m venv .venv; }
echo "[2/3] Installing requirements (first run takes a few minutes)..."
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
echo "[3/3] Starting the bot server. Press Ctrl+C to stop."
exec .venv/bin/python run.py
