"""Tests for the cabinet monitor's logic - everything except the wires.

The one that matters most is the cross-language merge check: the Pi and the
web app both rewrite the same shared nursery document, so their merge rules
must agree EXACTLY on who wins, or the two would slowly shred each other's
data. This runs the same fixture through Python's merge and through the real
js/store.js under node, and diffs the results.

Hardware is not testable here; the drivers are exercised on the Pi with
`sensord.py --once`. Everything downstream of a reading is covered.

Usage:  python3 pi/test_pi.py   (from the repo root; needs node on PATH)
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from datetime import date, datetime, timedelta

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cloud
import sensors
import store

CHECKS = []


def check(name, condition, detail=""):
    CHECKS.append((name, bool(condition), detail))


# ------------------------------------------------------------- summaries

def test_summaries():
    db = store.open_db(":memory:")
    day = date(2026, 12, 10)

    # A winter day: cold overnight (chill), warm under the lights.
    for hour in range(24):
        temp = 42.0 if hour < 8 else 56.0            # 8 hours below 45 F
        store.log_reading(db, datetime(2026, 12, 10, hour, 30), {
            "air": {"tempF": temp, "rh": 48 + hour % 5, "pressureHpa": 1005,
                    "lux": 8800 if 7 <= hour < 19 else 0},
            "moisture": {"olive1": 40.0 - hour * 0.5},
            "moistureRaw": {"olive1": 20000},
        })

    air = store.air_summary(db, day)
    check("air min/max", air["tempLow"] == 42.0 and air["tempHigh"] == 56.0, str(air))
    check("day light is the plateau", air["light"] == 8800, str(air["light"]))
    check("chill counts hourly means below 45F",
          store.chill_hours(db, day) == 8, str(store.chill_hours(db, day)))
    check("no chill season in summer",
          store.chill_hours(db, date(2026, 7, 10)) is None)
    check("chill season spans the new year",
          store.chill_season_start(date(2027, 1, 15)) == date(2026, 11, 1))

    config = {"air_plant_ids": ["bench1"], "chill_plant_id": "olive1"}
    entries = store.daily_entries(db, day, config)
    by_plant = {e["plantId"]: e for e in entries}
    check("bench entry carries air", by_plant["bench1"]["tempHigh"] == 56.0)
    check("olive entry carries moisture, air and chill",
          by_plant["olive1"]["chill"] == 8 and "moisture" in by_plant["olive1"]
          and by_plant["olive1"]["tempLow"] == 42.0,
          str(by_plant["olive1"]))
    check("entry ids are deterministic",
          by_plant["olive1"]["id"] == "sensor-olive1-2026-12-10")
    check("entries are minimal, not null-padded",
          "ph" not in by_plant["olive1"] and len(json.dumps(by_plant["olive1"])) < 300,
          "%d bytes" % len(json.dumps(by_plant["olive1"])))

    # Re-running the same day must produce the same ids (idempotent merge).
    again = store.daily_entries(db, day, config)
    check("re-summarising keeps the same ids",
          sorted(e["id"] for e in again) == sorted(e["id"] for e in entries))


# ------------------------------------------------------------ calibration

def test_calibration():
    probe = {"dry": 26000, "wet": 11000}
    check("dry probe reads 0", sensors.calibrate(26000, probe) == 0.0)
    check("wet probe reads 100", sensors.calibrate(11000, probe) == 100.0)
    check("midpoint reads 50", sensors.calibrate(18500, probe) == 50.0)
    check("out-of-range clamps", sensors.calibrate(30000, probe) == 0.0
          and sensors.calibrate(5000, probe) == 100.0)
    check("degenerate calibration returns None",
          sensors.calibrate(20000, {"dry": 15000, "wet": 15000}) is None)


def test_mock_sensors():
    mock = sensors.MockSensors([{"plantId": "p1", "dry": 26000, "wet": 11000}])
    reading = mock.read()
    check("mock produces air and moisture",
          "tempF" in reading["air"] and "p1" in reading["moisture"], str(reading))


# ------------------------------------------------------- merge equivalence

NODE_MERGE = r"""
const store = {};
global.window = {
  localStorage: {
    _v: null,
    getItem() { return this._v; },
    setItem(k, v) { this._v = v; },
    removeItem() {}
  },
  alert() {}
};
require(process.argv[2]);
const S = global.window.BonsaiStore;
const [base, incoming] = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
S.replaceAll(base);
S.mergeSnapshot(incoming);
process.stdout.write(JSON.stringify(S.snapshot()));
"""


def test_merge_matches_js(tmpdir):
    base = {
        "version": 1,
        "plants": [
            {"id": "p1", "name": "Old name", "updatedAt": "2026-08-01T00:00:00Z"},
            {"id": "p2", "name": "Deleted on device", "updatedAt": "2026-08-05T00:00:00Z",
             "deletedAt": "2026-08-05T00:00:00Z"},
        ],
        "entries": [
            {"id": "e1", "plantId": "p1", "at": "2026-08-01T12:00:00Z",
             "moisture": 40, "updatedAt": "2026-08-01T12:00:00Z"},
            {"id": "sensor-p1-2026-08-10", "plantId": "p1", "at": "2026-08-10T12:00:00Z",
             "tempHigh": 75, "auto": "sensor", "updatedAt": "2026-08-10T09:00:00Z"},
        ],
        "completions": [],
    }
    incoming = {
        "version": 1,
        "plants": [
            {"id": "p1", "name": "Newer name", "updatedAt": "2026-08-09T00:00:00Z"},
            {"id": "p2", "name": "Resurrection attempt", "updatedAt": "2026-08-01T00:00:00Z"},
        ],
        "entries": [
            # The Pi updates its own sensor entry with a newer stamp...
            {"id": "sensor-p1-2026-08-10", "plantId": "p1", "at": "2026-08-10T12:00:00Z",
             "tempHigh": 78, "tempLow": 61, "auto": "sensor",
             "updatedAt": "2026-08-10T15:00:00Z"},
            # ...and adds a brand new one.
            {"id": "sensor-p1-2026-08-11", "plantId": "p1", "at": "2026-08-11T12:00:00Z",
             "moisture": 44, "auto": "sensor", "updatedAt": "2026-08-11T09:00:00Z"},
        ],
        "completions": [],
    }

    python_result = cloud.merge_snapshot(base, incoming)

    fixture = tmpdir / "merge-fixture.json"
    fixture.write_text(json.dumps([base, incoming]))
    script = tmpdir / "merge.js"
    script.write_text(NODE_MERGE)
    js_result = json.loads(subprocess.run(
        ["node", str(script), str(HERE.parent / "js" / "store.js"), str(fixture)],
        capture_output=True, text=True, check=True,
    ).stdout)

    def normalise(snapshot):
        return {
            "plants": sorted(snapshot["plants"], key=lambda r: r["id"]),
            "entries": sorted(snapshot["entries"], key=lambda r: r["id"]),
            "completions": sorted(snapshot.get("completions", []), key=lambda r: r["id"]),
        }

    check("python merge == js merge, byte for byte",
          normalise(python_result) == normalise(js_result),
          json.dumps(normalise(python_result))[:120])

    winners = {p["id"]: p for p in python_result["plants"]}
    check("newest edit wins", winners["p1"]["name"] == "Newer name")
    check("tombstone survives a resurrection attempt",
          "deletedAt" in winners["p2"], str(winners["p2"]))
    updated = {e["id"]: e for e in python_result["entries"]}
    check("sensor entry updated in place, not duplicated",
          updated["sensor-p1-2026-08-10"]["tempHigh"] == 78
          and len(python_result["entries"]) == 3)


# ------------------------------------------------------------------ size

def test_year_of_entries_fits():
    """A year of daily summaries for 6 plants must sit far under the 1 MiB doc."""
    db = store.open_db(":memory:")
    config = {"air_plant_ids": ["zone"], "chill_plant_id": "olive"}
    entries = []
    start = date(2026, 1, 1)
    for offset in range(365):
        day = start + timedelta(days=offset)
        store.log_reading(db, datetime(day.year, day.month, day.day, 12), {
            "air": {"tempF": 70.0, "rh": 55.0, "pressureHpa": 1005, "lux": 9000},
            "moisture": {p: 45.0 for p in ["olive", "a", "b", "c", "d"]},
            "moistureRaw": {},
        })
        entries.extend(store.daily_entries(db, day, config))
    body = json.dumps({"version": 1, "plants": [], "entries": entries, "completions": []},
                      separators=(",", ":"))
    check("a year of summaries stays small",
          len(body) < 400 * 1024, "%d KB for %d entries" % (len(body) // 1024, len(entries)))


# ---------------------------------------------------------------- relays

def test_relay_schedule():
    import sensord
    relay = {
        "name": "humidifier", "enabled": True, "pin": 5,
        "sessions": [
            {"from": "07:00", "to": "08:00", "months": [11, 12, 1, 2, 3]},
            {"from": "06:00", "to": "06:30", "months": [6, 7, 8]},
        ],
    }
    on = sensord.Relays._scheduled_on
    check("winter session fires in January",
          on(relay, datetime(2027, 1, 10, 7, 30)) is True)
    check("winter session silent in July",
          on(relay, datetime(2026, 7, 10, 7, 30)) is False)
    check("summer session fires in July",
          on(relay, datetime(2026, 7, 10, 6, 15)) is True)
    check("off outside any session",
          on(relay, datetime(2027, 1, 10, 9, 0)) is False)


def main():
    import tempfile
    test_summaries()
    test_calibration()
    test_mock_sensors()
    with tempfile.TemporaryDirectory() as tmp:
        test_merge_matches_js(pathlib.Path(tmp))
    test_year_of_entries_fits()
    test_relay_schedule()

    width = max(len(name) for name, _, _ in CHECKS)
    failed = 0
    for name, ok, detail in CHECKS:
        print("  %s  %s  %s" % ("PASS" if ok else "FAIL", name.ljust(width),
                                detail if not ok else ""))
        failed += 0 if ok else 1
    print("\n%d/%d checks passed" % (len(CHECKS) - failed, len(CHECKS)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
