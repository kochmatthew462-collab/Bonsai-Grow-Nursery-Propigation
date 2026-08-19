#!/usr/bin/env bash
# Start the suite. Creates a virtual environment on first run, and refreshes it
# whenever requirements.txt changes.
#
# Everything below the first line exists because of a failure that looks like
# "it won't start" and says nothing about why: no python3 on PATH, a Python too
# old for the syntax this code uses, or a venv left stale by a git pull that
# added a dependency. Each one now names itself.
#
# If this script will not run at all — "bad interpreter", "command not found",
# or "permission denied" — try `bash run.sh`, which skips the shebang and the
# executable bit. On Windows use `.\run.ps1` in PowerShell instead.
set -euo pipefail
cd "$(dirname "$0")"

# --- find a usable Python -----------------------------------------------------
# python3 first, then python: minimal installs and some Windows/WSL setups have
# only one of the two, and "python3: command not found" is a dead end for
# anyone who does in fact have Python.
# An explicit override wins outright, and is checked the same way — naming a
# Python that is also too old should say so, not fail later and obscurely.
PY=""
for candidate in ${KRS_PYTHON:-} python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PY="$candidate"
      break
    fi
    found=$("$candidate" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null || echo "?")
    echo "  Found $candidate (version $found), but this needs Python 3.11 or newer." >&2
  fi
done

if [ -z "$PY" ]; then
  cat >&2 <<'MSG'

  Could not find Python 3.11 or newer.

  This suite uses syntax that older versions cannot parse, so it will not run
  on 3.10 or below — the failure would be a confusing SyntaxError deep in an
  import rather than anything useful.

    macOS    brew install python@3.12
    Ubuntu   sudo apt install python3.12 python3.12-venv
    Windows  https://www.python.org/downloads/  (then use run.ps1, not run.sh)

  If you have a newer Python under another name, point this at it:
    KRS_PYTHON=python3.12 bash run.sh

MSG
  exit 1
fi

# --- create or refresh the environment ----------------------------------------
STAMP=".venv/.requirements-sha"

hash_requirements() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum requirements.txt | cut -d' ' -f1
  else
    shasum -a 256 requirements.txt | cut -d' ' -f1   # macOS ships shasum, not sha256sum
  fi
}

if [ ! -d .venv ]; then
  echo "First run — creating a virtual environment and installing dependencies."
  if ! "$PY" -m venv .venv; then
    echo "  Could not create a virtual environment. On Debian and Ubuntu the" >&2
    echo "  venv module ships separately: sudo apt install python3-venv" >&2
    exit 1
  fi
  ./.venv/bin/python -m pip install --quiet --upgrade pip
  ./.venv/bin/python -m pip install --quiet -r requirements.txt
  hash_requirements > "$STAMP"
elif [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$(hash_requirements)" ]; then
  # A pull that adds a dependency must not leave the venv behind. The first
  # version installed only when .venv was absent, and because the dependency
  # added was optional and guarded, nothing failed loudly — the feature it
  # backed simply did not work, with nothing on screen to say why.
  echo "Dependencies changed since the last run — updating."
  ./.venv/bin/python -m pip install --quiet -r requirements.txt
  hash_requirements > "$STAMP"
fi

exec ./.venv/bin/python -m app.main
