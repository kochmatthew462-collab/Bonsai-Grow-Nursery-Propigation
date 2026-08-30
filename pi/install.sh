#!/usr/bin/env bash
# One-time install on the Raspberry Pi. Run from this directory:
#   bash install.sh
# Works for any user account, not just the classic 'pi'.
set -euo pipefail

DEST="$HOME/plantmon"
RUN_USER="$(id -un)"

echo "== enabling I2C (needs a reboot if it was off) =="
sudo raspi-config nonint do_i2c 0

echo "== installing dependencies =="
sudo apt-get update -qq
# Raspberry Pi OS Bookworm and later refuse system-wide pip installs
# (PEP 668), so the Python dependencies come from apt. The pip fallback
# only runs on older releases where the apt package does not exist yet.
sudo apt-get install -y -qq i2c-tools python3-requests
sudo apt-get install -y -qq python3-smbus2 || pip3 install --user smbus2

echo "== installing to $DEST =="
mkdir -p "$DEST"
cp sensord.py sensors.py store.py cloud.py "$DEST/"
if [ ! -f "$DEST/config.json" ]; then
  cp config.example.json "$DEST/config.json"
  echo "!! Edit $DEST/config.json before starting:"
  echo "   credentials from the app's Sync page, your plant ids, probe calibration."
fi

echo "== what the bus can see (expect 29, 5c, 68, 70 from the HAT; 48 its ADC; 49/4a/4b yours) =="
i2cdetect -y 1 || true

echo "== installing the service (running as $RUN_USER) =="
sed -e "s|^User=.*|User=$RUN_USER|" -e "s|/home/pi|$HOME|g" plantmon.service |
  sudo tee /etc/systemd/system/plantmon.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable plantmon

echo
echo "Next: edit $DEST/config.json, test one cycle with"
echo "    python3 $DEST/sensord.py --config $DEST/config.json --once --no-cloud"
echo "then start for real with:  sudo systemctl start plantmon"
echo "and watch it with:         journalctl -u plantmon -f"
