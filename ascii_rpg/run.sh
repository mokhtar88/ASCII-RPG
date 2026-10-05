#!/bin/sh
# Inkbound Realms - double-click / ./run.sh to play (macOS/Linux).
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "[!] Python 3.10+ not found. Install it, then re-run this file."
  exit 1
fi
if ! python3 -c "import pygame, pypdf, numpy" 2>/dev/null; then
  echo "[*] First run: installing game libraries..."
  python3 -m pip install -r requirements.txt || exit 1
fi
exec python3 main.py
