"""Sensor drivers for the cabinet monitor.

Hardware this is written for (the ordered materials):

  Waveshare Sense HAT (B), all I2C:
    SHTC3    0x70  air temperature and relative humidity
    LPS22HB  0x5c  barometric pressure
    TCS34725 0x29  colour / ambient light (lux is derived)
    ICM20948 0x68  motion - not used
    ADS1015  0x48  the HAT's own ADC - not used, see below

  3x ADS1115 16-bit ADC boards, carrying the capacitive moisture probes.
    The HAT's own ADC usually occupies 0x48, so strap the external boards
    off it:  ADDR->VDD = 0x49, ADDR->SDA = 0x4a, ADDR->SCL = 0x4b.
    Confirm with `i2cdetect -y 1` before trusting any reading.

Every read is guarded: a sensor that fails returns None and the daemon
carries on with the rest. Nothing here raises for a wiring fault.

Mock mode (--mock) replaces the whole bus with plausible synthetic values so
the daemon, summaries, merge and tests all run on a machine with no GPIO.
"""

from __future__ import annotations

import math
import random
import time

# smbus2 exists only on the Pi; the mock path must import cleanly anywhere.
try:
    from smbus2 import SMBus, i2c_msg
except ImportError:                                    # pragma: no cover
    SMBus = None
    i2c_msg = None

I2C_BUS = 1

SHTC3_ADDR = 0x70
LPS22HB_ADDR = 0x5C
TCS34725_ADDR = 0x29


class Shtc3:
    """Air temperature (F) and relative humidity (%)."""

    def __init__(self, bus):
        self.bus = bus

    def read(self):
        try:
            # Wake, measure (normal power, no clock stretch, T first), sleep.
            self.bus.write_i2c_block_data(SHTC3_ADDR, 0x35, [0x17])
            time.sleep(0.001)
            self.bus.write_i2c_block_data(SHTC3_ADDR, 0x78, [0x66])
            time.sleep(0.015)
            msg = i2c_msg.read(SHTC3_ADDR, 6)
            self.bus.i2c_rdwr(msg)
            data = list(msg)
            raw_t = (data[0] << 8) | data[1]
            raw_h = (data[3] << 8) | data[4]
            self.bus.write_i2c_block_data(SHTC3_ADDR, 0xB0, [0x98])
            temp_c = -45.0 + 175.0 * raw_t / 65535.0
            return {
                "tempF": round(temp_c * 9 / 5 + 32, 1),
                "rh": round(100.0 * raw_h / 65535.0, 1),
            }
        except Exception:
            return None


class Lps22hb:
    """Barometric pressure (hPa)."""

    def __init__(self, bus):
        self.bus = bus
        self.started = False

    def read(self):
        try:
            if not self.started:
                self.bus.write_byte_data(LPS22HB_ADDR, 0x10, 0x10)  # 1 Hz
                self.started = True
                time.sleep(1.1)
            data = self.bus.read_i2c_block_data(LPS22HB_ADDR, 0x28 | 0x80, 3)
            raw = (data[2] << 16) | (data[1] << 8) | data[0]
            return {"pressureHpa": round(raw / 4096.0, 1)}
        except Exception:
            return None


class Tcs34725:
    """Ambient light as lux, via the standard TAOS coefficients.

    Placement matters more than the maths: mount the HAT at canopy height of
    the top shelf, facing the strips, or the number describes the wrong place.
    """

    ATIME = 0xD5          # ~103 ms integration
    GAIN = 0x01           # 4x

    def __init__(self, bus):
        self.bus = bus
        self.started = False

    def read(self):
        try:
            if not self.started:
                self.bus.write_byte_data(TCS34725_ADDR, 0x80 | 0x01, self.ATIME)
                self.bus.write_byte_data(TCS34725_ADDR, 0x80 | 0x0F, self.GAIN)
                self.bus.write_byte_data(TCS34725_ADDR, 0x80 | 0x00, 0x03)  # PON | AEN
                self.started = True
                time.sleep(0.25)
            data = self.bus.read_i2c_block_data(TCS34725_ADDR, 0x80 | 0x14, 8)
            clear = (data[1] << 8) | data[0]
            red = (data[3] << 8) | data[2]
            green = (data[5] << 8) | data[4]
            blue = (data[7] << 8) | data[6]
            if clear == 0:
                return {"lux": 0}
            atime_ms = (256 - self.ATIME) * 2.4
            gain_x = {0x00: 1, 0x01: 4, 0x02: 16, 0x03: 60}[self.GAIN]
            cpl = (atime_ms * gain_x) / 408.6
            lux = (-0.32466 * red + 1.57837 * green + -0.73191 * blue) / cpl
            return {"lux": max(0, int(lux))}
        except Exception:
            return None


class Ads1115:
    """One ADS1115: four single-ended channels, 4.096 V range, single-shot."""

    def __init__(self, bus, addr):
        self.bus = bus
        self.addr = addr

    def read_channel(self, channel):
        try:
            config = (
                0x8000                       # start single conversion
                | (0x4000 | (channel << 12)) # AINx vs GND
                | 0x0200                     # PGA +/-4.096 V
                | 0x0100                     # single-shot
                | 0x0080                     # 128 SPS
                | 0x0003                     # comparator off
            )
            self.bus.write_i2c_block_data(self.addr, 0x01, [config >> 8, config & 0xFF])
            time.sleep(0.02)
            data = self.bus.read_i2c_block_data(self.addr, 0x00, 2)
            raw = (data[0] << 8) | data[1]
            if raw > 0x7FFF:
                raw -= 0x10000
            return max(0, raw)
        except Exception:
            return None


class RealSensors:
    """The wired-in cabinet: HAT sensors plus moisture probes on the ADCs."""

    def __init__(self, moisture_channels):
        self.bus = SMBus(I2C_BUS)
        self.shtc3 = Shtc3(self.bus)
        self.lps = Lps22hb(self.bus)
        self.tcs = Tcs34725(self.bus)
        self.adcs = {}
        self.moisture_channels = moisture_channels   # [{addr, channel, plantId, dry, wet}]

    def _adc(self, addr):
        if addr not in self.adcs:
            self.adcs[addr] = Ads1115(self.bus, addr)
        return self.adcs[addr]

    def read(self):
        out = {"air": {}, "moistureRaw": {}, "moisture": {}}
        for part in (self.shtc3.read(), self.lps.read(), self.tcs.read()):
            if part:
                out["air"].update(part)
        for probe in self.moisture_channels:
            raw = self._adc(probe["addr"]).read_channel(probe["channel"])
            if raw is None:
                continue
            out["moistureRaw"][probe["plantId"]] = raw
            out["moisture"][probe["plantId"]] = calibrate(raw, probe)
        return out


def calibrate(raw, probe):
    """Raw ADC counts to percent, from the probe's own dry/wet calibration.

    Capacitive probes read HIGH dry and LOW wet. The percent this yields is
    the probe's own scale: calibrate dry-in-air = 0 and submerged = 100, then
    sanity-check against the handheld meter before trusting the bands.
    """
    dry = probe.get("dry", 26000)
    wet = probe.get("wet", 11000)
    if dry == wet:
        return None
    pct = 100.0 * (dry - raw) / (dry - wet)
    return round(max(0.0, min(100.0, pct)), 1)


class MockSensors:
    """Synthetic but plausible cabinet: a warm day cycle, drying pots."""

    def __init__(self, moisture_channels, seed=42):
        self.rng = random.Random(seed)
        self.moisture_channels = moisture_channels
        self.t0 = time.time()

    def read(self):
        hours = (time.time() - self.t0) / 3600.0
        day_phase = math.sin(hours / 24.0 * 2 * math.pi)
        out = {
            "air": {
                "tempF": round(74 + 3 * day_phase + self.rng.uniform(-0.4, 0.4), 1),
                "rh": round(55 - 4 * day_phase + self.rng.uniform(-1, 1), 1),
                "pressureHpa": round(1008 + self.rng.uniform(-0.5, 0.5), 1),
                "lux": max(0, int(9200 + 500 * day_phase + self.rng.uniform(-150, 150))),
            },
            "moistureRaw": {},
            "moisture": {},
        }
        for index, probe in enumerate(self.moisture_channels):
            dry = probe.get("dry", 26000)
            wet = probe.get("wet", 11000)
            level = 0.55 - 0.1 * index - 0.02 * hours   # slowly drying
            raw = int(dry - (dry - wet) * max(0.05, min(0.95, level)))
            out["moistureRaw"][probe["plantId"]] = raw
            out["moisture"][probe["plantId"]] = calibrate(raw, probe)
        return out


def make_sensors(config, mock=False):
    channels = config.get("moisture", [])
    if mock or SMBus is None:
        return MockSensors(channels)
    return RealSensors(channels)
