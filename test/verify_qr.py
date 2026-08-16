"""Verify js/qrcode.js produces real, scannable QR Codes.

Three independent checks over every generated matrix:

1. Decode it with zxing-cpp -- the decoder family phone camera apps use -- and
   confirm the payload round-trips. This is the check that matters in the
   nursery: a label either scans or it does not.

2. Compare every function-pattern module (finders, separators, timing,
   alignment, version information, dark module) against segno, an independent
   third-party encoder.

3. Confirm automatic version selection always picks the smallest version that
   fits, so labels stay as coarse -- and as easy to scan -- as possible.

Format-information modules are excluded from check 2 because they encode the
chosen mask, and the data region is excluded because segno's write_padding_bits
appends a spurious zero byte whenever the bit stream is already byte-aligned,
which in byte mode it always is. That padding sits after the terminator so both
encoders still decode identically, but it rules segno out as a byte-exact
reference. Check 1 covers the data region instead.

Usage:
    pip install segno zxing-cpp numpy
    python3 test/verify_qr.py
"""

import json
import pathlib
import subprocess
import sys

import numpy as np
import segno
import zxingcpp

HERE = pathlib.Path(__file__).resolve().parent
SCALE = 8
QUIET = 4


def render(rows: list[str]) -> np.ndarray:
    """Turn a matrix of '0'/'1' rows into a black-on-white image with a quiet zone."""
    size = len(rows)
    grid = np.array([[255 - 255 * int(bit) for bit in row] for row in rows], dtype=np.uint8)
    canvas = np.full((size + 2 * QUIET, size + 2 * QUIET), 255, dtype=np.uint8)
    canvas[QUIET:QUIET + size, QUIET:QUIET + size] = grid
    return np.kron(canvas, np.ones((SCALE, SCALE), dtype=np.uint8))


def format_positions(size: int) -> set[tuple[int, int]]:
    """Modules carrying format information, which varies with the chosen mask."""
    spots = set()
    for i in range(9):
        spots.add((8, i))
        spots.add((i, 8))
    for i in range(8):
        spots.add((8, size - 1 - i))
        spots.add((size - 1 - i, 8))
    return spots


def main() -> int:
    payload = subprocess.run(
        ["node", str(HERE / "emit_matrices.js")],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    data = json.loads(payload)
    cases = data["cases"]

    decode_failures: list[str] = []
    pattern_failures: list[str] = []
    decoded = 0
    matched = 0

    for case in cases:
        label = f"v{case['version']}-{case['ecc']} {case['text'][:24]!r}"

        # --- check 1: does it scan back to the payload?
        result = zxingcpp.read_barcode(render(case["rows"]))
        text = result.text if result else ""
        if text == case["text"]:
            decoded += 1
        else:
            decode_failures.append(f"{label}: decoded {text[:40]!r}")

        # --- check 2: do the function patterns match segno?
        reference = segno.make(
            case["text"], version=case["version"], error=case["ecc"],
            mode="byte", boost_error=False,
        )
        ref_rows = ["".join(str(bit) for bit in row) for row in reference.matrix]
        skip = format_positions(case["size"])
        mismatch = None
        for r in range(case["size"]):
            for c in range(case["size"]):
                if case["reserved"][r][c] != "1" or (r, c) in skip:
                    continue
                if case["rows"][r][c] != ref_rows[r][c]:
                    mismatch = f"row {r} col {c}: got {case['rows'][r][c]}, segno {ref_rows[r][c]}"
                    break
            if mismatch:
                break
        if mismatch:
            pattern_failures.append(f"{label}: {mismatch}")
        else:
            matched += 1

    problems = data["versionProblems"]
    total = len(cases)
    print(f"scan round-trip   : {decoded}/{total} matrices decoded back to their payload")
    print(f"function patterns : {matched}/{total} matched segno exactly")
    print(f"version selection : {'minimal for all 400 payloads' if not problems else 'FAILED'}")

    failures = decode_failures + pattern_failures + problems
    if failures:
        print("\nFailures:", file=sys.stderr)
        for line in failures[:20]:
            print("  " + line, file=sys.stderr)
        if len(failures) > 20:
            print(f"  ...and {len(failures) - 20} more", file=sys.stderr)
        return 1

    print("\nPASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
