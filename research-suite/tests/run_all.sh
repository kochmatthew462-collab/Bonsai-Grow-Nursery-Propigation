#!/usr/bin/env bash
# Every test runs offline: no network, no API keys, no credentials.
set -uo pipefail
cd "$(dirname "$0")/.."
status=0
for suite in tests/test_*.py; do
  echo "── $suite"
  python3 "$suite" || status=1
done
exit $status
