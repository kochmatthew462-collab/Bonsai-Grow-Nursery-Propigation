#!/usr/bin/env python3
"""Cabinet monitor daemon for Koch's Tree Nursery Tracker.

    python3 sensord.py --config config.json          # run forever
    python3 sensord.py --config config.json --once   # one cycle, then print
    python3 sensord.py --config config.json --mock   # no hardware needed

The loop, once a minute by default:
  1. read every sensor (each guarded - a dead probe never stops the rest)
  2. append to the raw SQLite log
  3. drive the relay schedules (humidifier sessions, fan) if enabled
  4. every live_interval, push the small live document
  5. every push_interval, merge today's summary entries into the nursery

Sensor readings REPLACE nothing a person entered: they are separate entries
with their own deterministic ids (sensor-<plant>-<date>), exactly like the
app's derived drip log. Hand checks and sensor summaries live side by side.

RELAY SAFETY. The relay outputs here are for LOW-VOLTAGE loads only - the
USB fan, the humidifier's DC side. Mains wiring through a bare hobby relay
board is a shock and fire hazard; the grow lights and the drip pump already
have their own timers and stay on them. Every relay ships disabled in the
example config, and this daemon will not invent a schedule you did not write.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date, datetime

import sensors as sensors_mod
import store as store_mod
from cloud import Cloud, merge_entries_into, now_iso

log = logging.getLogger("plantmon")

try:                                                   # pragma: no cover
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None


class Relays:
    """Schedule-driven relay outputs, reported but never remote-controlled.

    Schedules live HERE, on the Pi, the same way the drip schedule lives in
    the GrowHub: the device that owns the hardware owns the timing. The app
    only ever sees the reported state. Sessions are local wall-clock HH:MM,
    with an optional month list (1-12) so the bench packet's seasonal
    humidifier table maps one-to-one.
    """

    def __init__(self, config, mock=False):
        self.relays = [r for r in config.get("relays", []) if r.get("enabled")]
        self.mock = mock or GPIO is None
        self.states = {}
        if not self.mock and self.relays:
            GPIO.setmode(GPIO.BCM)
            for relay in self.relays:
                GPIO.setup(relay["pin"], GPIO.OUT)

    def tick(self, now):
        for relay in self.relays:
            want = self._scheduled_on(relay, now)
            if self.states.get(relay["name"]) != want:
                self.states[relay["name"]] = want
                log.info("relay %s -> %s", relay["name"], "ON" if want else "off")
                if not self.mock:
                    # Hobby relay boards are almost always active-low.
                    level = (not want) if relay.get("active_low", True) else want
                    GPIO.output(relay["pin"], 1 if level else 0)
        return dict(self.states)

    @staticmethod
    def _scheduled_on(relay, now):
        hhmm = now.strftime("%H:%M")
        for session in relay.get("sessions", []):
            months = session.get("months")
            if months and now.month not in months:
                continue
            if session["from"] <= hhmm < session["to"]:
                return True
        return False


def load_config(path):
    with open(path) as handle:
        config = json.load(handle)
    for key in ("projectId", "apiKey", "code"):
        if not config.get(key):
            raise SystemExit("config is missing %r - copy config.example.json "
                             "and fill in the same values the app's Sync page uses" % key)
    return config


def build_live(reading, relay_states, chill, config):
    live = {
        "at": now_iso(),
        "air": reading.get("air", {}),
        "moisture": reading.get("moisture", {}),
        "moistureRaw": reading.get("moistureRaw", {}),
        "relays": relay_states,
    }
    if chill is not None and config.get("chill_plant_id"):
        live["chill"] = {config["chill_plant_id"]: chill}
    return live


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--mock", action="store_true", help="synthetic sensors, no GPIO")
    parser.add_argument("--once", action="store_true", help="one cycle, print, exit")
    parser.add_argument("--no-cloud", action="store_true", help="log locally only")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    config = load_config(args.config)
    poll_s = config.get("poll_seconds", 60)
    live_s = config.get("live_interval_seconds", 300)
    push_s = config.get("push_interval_seconds", 1800)

    db = store_mod.open_db(config.get("db_path", "plantmon.db"))
    cabinet = sensors_mod.make_sensors(config, mock=args.mock)
    relays = Relays(config, mock=args.mock)
    cloud = None if args.no_cloud else Cloud(config)

    last_live = 0.0
    last_push = 0.0

    while True:
        now = datetime.now()
        reading = cabinet.read()
        store_mod.log_reading(db, now, reading)
        relay_states = relays.tick(now)
        chill = store_mod.chill_hours(db, date.today())

        if args.once:
            print(json.dumps(build_live(reading, relay_states, chill, config), indent=2))
            print(json.dumps(store_mod.daily_entries(db, date.today(), config), indent=2))
            return

        if cloud and time.time() - last_live >= live_s:
            try:
                cloud.push_live(build_live(reading, relay_states, chill, config))
                last_live = time.time()
            except Exception as error:
                log.warning("live push failed, will retry: %s", error)

        if cloud and time.time() - last_push >= push_s:
            try:
                entries = store_mod.daily_entries(db, date.today(), config)
                if entries:
                    snapshot = cloud.fetch_nursery()
                    cloud.push_nursery(merge_entries_into(snapshot, entries))
                    log.info("merged %d sensor entries into the nursery", len(entries))
                last_push = time.time()
            except Exception as error:
                log.warning("nursery push failed, will retry: %s", error)

        time.sleep(poll_s)


if __name__ == "__main__":
    main()
