#!/usr/bin/env bash
# Idempotent dependency setup for the marketing-file-analyzer.
# Safe to run repeatedly and against a cached/partially-prepared VM.
set -euo pipefail

cd "$(dirname "$0")/.."

# Ensure the Python venv module is available (the default image may lack it).
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  echo "Installing python3-venv system package..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
fi

# Create the virtual environment once; reuse it on subsequent runs.
if [ ! -x ".venv/bin/python" ]; then
  echo "Creating virtual environment (.venv)..."
  python3 -m venv .venv
fi

echo "Installing Python dependencies..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "Install complete."
