"""Local storage and summarisation for the cabinet monitor.

Two layers, deliberately different lifetimes:

  RAW      every poll, into SQLite on the Pi's SD card. Cheap, unlimited,
           never leaves the Pi. This is the record the olive handbook wished
           for: "a logger recording hourly through the winter gives you an
           actual chill-hour count rather than a guess."

  SUMMARY  one entry per plant per day, pushed into the shared nursery
           document. The nursery ships as a single Firestore document with a
           1 MiB ceiling, so summaries are MINIMAL entries - only the keys
           they carry (about 150 bytes each), not the app's full null-padded
           schema. The app treats missing keys and nulls identically.

Daily fields, matched to the app's existing metrics and conventions:
  tempLow / tempHigh   min and max air temperature since midnight
  humidity             median RH
  light                the day's maximum lux (the strips make it a plateau)
  moisture             latest calibrated percent per mapped plant
  chill                cumulative hours below 45 F this season, on the one
                       plant configured as the chill tree (the olive)
"""

from __future__ import annotations

import sqlite3
import statistics
from datetime import date, datetime, timedelta

CHILL_THRESHOLD_F = 45.0
# The olive banks chill from the move-in through late winter.
CHILL_START = (11, 1)    # Nov 1
CHILL_END = (3, 1)       # Mar 1 (exclusive)

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    ts      TEXT NOT NULL,
    tempF   REAL,
    rh      REAL,
    pressureHpa REAL,
    lux     INTEGER
);
CREATE INDEX IF NOT EXISTS readings_ts ON readings (ts);
CREATE TABLE IF NOT EXISTS moisture (
    ts      TEXT NOT NULL,
    plantId TEXT NOT NULL,
    raw     INTEGER,
    pct     REAL
);
CREATE INDEX IF NOT EXISTS moisture_ts ON moisture (plantId, ts);
"""


def open_db(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def log_reading(db, now, reading):
    air = reading.get("air", {})
    db.execute(
        "INSERT INTO readings (ts, tempF, rh, pressureHpa, lux) VALUES (?, ?, ?, ?, ?)",
        (now.isoformat(), air.get("tempF"), air.get("rh"),
         air.get("pressureHpa"), air.get("lux")),
    )
    for plant_id, pct in reading.get("moisture", {}).items():
        db.execute(
            "INSERT INTO moisture (ts, plantId, raw, pct) VALUES (?, ?, ?, ?)",
            (now.isoformat(), plant_id,
             reading.get("moistureRaw", {}).get(plant_id), pct),
        )
    db.commit()


def day_bounds(day):
    start = datetime(day.year, day.month, day.day)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def air_summary(db, day):
    """Min/max/median air figures for one calendar day, or None if silent."""
    start, end = day_bounds(day)
    rows = db.execute(
        "SELECT tempF, rh, lux FROM readings WHERE ts >= ? AND ts < ?",
        (start, end),
    ).fetchall()
    temps = [r[0] for r in rows if r[0] is not None]
    rhs = [r[1] for r in rows if r[1] is not None]
    luxes = [r[2] for r in rows if r[2] is not None]
    if not temps and not rhs and not luxes:
        return None
    out = {}
    if temps:
        out["tempLow"] = round(min(temps), 1)
        out["tempHigh"] = round(max(temps), 1)
    if rhs:
        out["humidity"] = round(statistics.median(rhs), 1)
    if luxes:
        out["light"] = int(max(luxes))
    return out


def latest_moisture(db, day):
    """The last calibrated reading of the day, per plant."""
    start, end = day_bounds(day)
    rows = db.execute(
        "SELECT plantId, pct FROM moisture WHERE ts >= ? AND ts < ? AND pct IS NOT NULL "
        "ORDER BY ts",
        (start, end),
    ).fetchall()
    out = {}
    for plant_id, pct in rows:
        out[plant_id] = pct
    return out


def chill_season_start(day):
    """The Nov 1 that opened the season containing `day`, or None outside it."""
    if (day.month, day.day) >= CHILL_START:
        return date(day.year, *CHILL_START)
    if (day.month, day.day) < CHILL_END:
        return date(day.year - 1, *CHILL_START)
    return None


def chill_hours(db, day):
    """Cumulative hours below 45 F from the season's start through `day`.

    An hour counts when its mean recorded temperature is below the threshold,
    which is what "hours below 45 F" means when you have a real logger rather
    than a daily guess.
    """
    season_start = chill_season_start(day)
    if season_start is None:
        return None
    start = datetime(season_start.year, season_start.month, season_start.day).isoformat()
    _, end = day_bounds(day)
    rows = db.execute(
        "SELECT substr(ts, 1, 13) AS hour, AVG(tempF) FROM readings "
        "WHERE ts >= ? AND ts < ? AND tempF IS NOT NULL GROUP BY hour",
        (start, end),
    ).fetchall()
    return sum(1 for _, mean in rows if mean is not None and mean < CHILL_THRESHOLD_F)


def daily_entries(db, day, config):
    """The minimal sensor entries for one day, ready to merge.

    Ids are deterministic (sensor-<plant>-<date>), so re-pushing the same day
    UPDATES the entry rather than duplicating it - the same idempotency rule
    the app's drip log uses, and what lets tempLow/tempHigh tighten all day.
    """
    stamp = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
    day_iso = day.isoformat()
    entries = []

    air = air_summary(db, day)
    moisture = latest_moisture(db, day)
    chill_plant = config.get("chill_plant_id")

    def base(plant_id):
        # No note field: across a year of entries a label string is ~80 KB of
        # the 1 MiB document. The app labels auto == 'sensor' entries itself.
        return {
            "id": "sensor-%s-%s" % (plant_id, day_iso),
            "plantId": plant_id,
            "at": day_iso + "T12:00:00.000Z",
            "auto": "sensor",
            "updatedAt": stamp,
        }

    for plant_id in config.get("air_plant_ids", []):
        if not air:
            break
        entry = base(plant_id)
        entry.update(air)
        if plant_id in moisture:
            entry["moisture"] = moisture.pop(plant_id)
        entries.append(entry)

    for plant_id, pct in moisture.items():
        entry = base(plant_id)
        entry["moisture"] = pct
        if air and plant_id == chill_plant:
            # The chill tree's winter station carries its own air record too.
            entry.update(air)
        entries.append(entry)

    if chill_plant:
        hours = chill_hours(db, day)
        if hours is not None:
            found = [e for e in entries if e["plantId"] == chill_plant]
            if found:
                found[0]["chill"] = hours
            else:
                entry = base(chill_plant)
                entry["chill"] = hours
                entries.append(entry)

    return entries
