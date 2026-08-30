# Cabinet monitor — Raspberry Pi 3B+

The Pi reads the cabinet's sensors around the clock and behaves as **one more
device on the nursery**: it merges daily summary entries into the same shared
document the phones sync, and writes a small live document the app renders as
the **Live sensors** card. No port forwarding, no server of yours on the
internet, nothing new to secure — the Pi uses the same three credentials the
app's Sync page uses.

What it adds that hands cannot:

- **A real chill-hour count.** The olive handbook: *"a logger recording hourly
  through the winter gives you an actual chill-hour count rather than a
  guess."* This is that logger. Hours below 45 °F are counted from the raw
  record, Nov 1 – Mar 1, and land on the olive's daily entry.
- **True daily low/high** air temperature — not "coldest since I looked."
- **Continuous moisture** on five pots, calibrated per probe.
- **A liveness check**: the app calls the Pi stale, loudly, after 15 quiet
  minutes. A dead logger that looks alive is the worst failure mode a winter
  record can have.

## The parts, and where each one goes

| Part | Role |
|---|---|
| Pi 3B+, case, 5V 2.5A PSU | the machine |
| Waveshare Sense HAT (B) | air temp + RH (SHTC3), pressure (LPS22HB), light (TCS34725) — all I²C |
| 40-pin 1-to-2 GPIO expander | lets the HAT and the jumper wiring share the header |
| 3× ADS1115 ADC boards | the moisture probes' analog-to-digital conversion |
| 5× capacitive moisture probes | one per monitored pot |
| SunFounder 8-ch relay shield | optional: humidifier / fan schedules — **low voltage only**, see below |

## Wiring

Everything except the probes is I²C: just **3V3, GND, SDA (pin 3), SCL
(pin 5)**, shared by all boards via the expander.

**ADS1115 addresses.** The HAT's own onboard ADC typically sits at `0x48`, so
strap the three external boards off it with their ADDR pin:

| Board | ADDR pin to | Address | Carries probes |
|---|---|---|---|
| #1 | VDD | `0x49` | 1–4 |
| #2 | SDA | `0x4a` | 5 (channels 1–3 spare) |
| #3 | SCL | `0x4b` | spare — future probes |

**Each moisture probe:** VCC → 3V3, GND → GND, AOUT → an ADS1115 `A0…A3`.
Power probes from **3V3, not 5V** — the ADS1115 inputs must never see more
than its supply.

**Verify before trusting anything:**

```bash
i2cdetect -y 1
```

Expect `29` (light), `5c` (pressure), `68` (IMU, unused), `70` (temp/RH),
`48` (HAT ADC, unused) and your `49 4a 4b`. A missing address is a wiring
problem; fix it before starting the daemon.

**Sensor placement is half the measurement.** Mount the HAT at canopy height
of the top shelf — the packet's probe-placement logic (the top box is the
warmest, driest sentinel) applies to this sensor exactly as it did to the old
probe. Push each moisture probe to mid-root-zone up to its line, and **never
submerge above the line** — the electronics are at the top.

### ⚠ Relays: low voltage only

The relay shield switches the **USB fan and the humidifier's DC side** —
loads a hobby board handles safely. **Do not put 120 V mains through a bare
relay board**: unenclosed mains on a bench with water is a shock and fire
hazard, and the grow lights and drip pump already have their own timers —
leave them on them. Every relay ships `"enabled": false` in the example
config; the daemon will never invent a schedule you did not write. The
example humidifier sessions are the bench packet's own seasonal table.

## Install

```bash
# on the Pi, in this folder (clone the repo or copy pi/ over)
bash install.sh
nano ~/plantmon/config.json     # credentials, plant ids, calibration
python3 ~/plantmon/sensord.py --config ~/plantmon/config.json --once --no-cloud
sudo systemctl start plantmon
journalctl -u plantmon -f
```

The install works for any user account (it writes the service for whoever
runs it), and on Raspberry Pi OS Bookworm and later the Python dependencies
come from apt, since those releases refuse system-wide pip installs.

`config.json` needs:

1. **Credentials** — the same Project ID, Web API Key and nursery code from
   the app's Sync page. Treat the file like a password; it is one.
2. **Plant ids** — from each plant's page (`id k3m9x2` in the subtitle).
   `air_plant_ids` is usually one designated bench plant; `chill_plant_id`
   is the olive.
3. **Probe calibration** — for each probe, read the raw counts with the probe
   **dry in air** (`dry`) and **submerged to the line** (`wet`), via
   `--once --no-cloud`. Percent is that probe's own scale: sanity-check it
   against your handheld meter before leaning on the moisture bands, and
   recalibrate after repotting into a different mix.

## What lands where

- **Raw readings** (every minute): SQLite on the Pi, forever, never uploaded.
- **Live document** (every 5 min): current air, moisture, relays, chill —
  the app's Live sensors card, staleness-checked.
- **Daily summaries** (merged every 30 min): one *minimal* entry per plant
  per day — `tempLow`/`tempHigh`, median `humidity`, day-max `light`, latest
  `moisture`, cumulative `chill` — updating in place all day under a
  deterministic id, exactly like the app's drip log. Hand checks and sensor
  entries coexist; nothing a person typed is ever overwritten.

Sizing: a year of summaries for six plants is ~250 KB of the shared
document's 1 MiB. Export a JSON backup yearly and prune old sensor entries
if you ever approach the app's 800 KB warning.

## Honest limits

- The Pi measures the cabinet, not the outdoors — the weather card still
  covers the container trees in season.
- A reading proves the sensor saw water, not that the tree is watered — a
  probe pulled loose reads dry forever. The daily glance survives automation.
- `test_pi.py` proves everything downstream of a reading (summaries, chill
  maths, merge equivalence with the app, sizes, schedules) but cannot prove
  your wiring; `--once` and `i2cdetect` do that on the bench.
