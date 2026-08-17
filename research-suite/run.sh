#!/usr/bin/env bash
# Start the suite. Creates a virtual environment on first run, and refreshes it
# whenever requirements.txt changes.
#
# That second part matters more than it looks. The first version installed only
# when .venv was absent, so pulling a commit that added a dependency left a
# stale environment — and because the new dependency was optional and guarded,
# nothing failed loudly. The feature just quietly did not work, and the reason
# was invisible. A hash of requirements.txt stored beside the venv turns that
# into a two-second reinstall.
set -euo pipefail
cd "$(dirname "$0")"

STAMP=".venv/.requirements-sha"

hash_requirements() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum requirements.txt | cut -d' ' -f1
  else
    shasum -a 256 requirements.txt | cut -d' ' -f1   # macOS
  fi
}

if [ ! -d .venv ]; then
  echo "First run — creating a virtual environment and installing dependencies."
  python3 -m venv .venv
  ./.venv/bin/python -m pip install --quiet --upgrade pip
  ./.venv/bin/python -m pip install --quiet -r requirements.txt
  hash_requirements > "$STAMP"
elif [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$(hash_requirements)" ]; then
  echo "Dependencies changed since the last run — updating."
  ./.venv/bin/python -m pip install --quiet -r requirements.txt
  hash_requirements > "$STAMP"
fi

exec ./.venv/bin/python -m app.main
