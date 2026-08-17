#!/usr/bin/env bash
# Start the suite. Creates a virtual environment on first run.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "First run — creating a virtual environment and installing dependencies."
  python3 -m venv .venv
  ./.venv/bin/python -m pip install --quiet --upgrade pip
  ./.venv/bin/python -m pip install --quiet -r requirements.txt
fi

exec ./.venv/bin/python -m app.main
