#!/usr/bin/env bash
# One-time install on the Raspberry Pi. Run from this directory:
#   bash install.sh
set -euo pipefail

echo "== enabling I2C (needs a reboot if it was off) =="
sudo raspi-config nonint do_i2c 0

echo "== installing dependencies =="
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip i2c-tools
pip3 install --user smbus2 requests

echo "== installing to /home/pi/plantmon =="
mkdir -p /home/pi/plantmon
cp sensord.py sensors.py store.py cloud.py /home/pi/plantmon/
if [ ! -f /home/pi/plantmon/config.json ]; then
  cp config.example.json /home/pi/plantmon/config.json
  echo "!! Edit /home/pi/plantmon/config.json before starting:"
  echo "   credentials from the app's Sync page, your plant ids, probe calibration."
fi

echo "== what the bus can see (expect 29, 5c, 68, 70 from the HAT; 48 its ADC; 49/4a/4b yours) =="
i2cdetect -y 1 || true

echo "== installing the service =="
sudo cp plantmon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable plantmon

echo
echo "Next: edit config.json, test one cycle with"
echo "    python3 /home/pi/plantmon/sensord.py --config /home/pi/plantmon/config.json --once --no-cloud"
echo "then start for real with:  sudo systemctl start plantmon"
echo "and watch it with:         journalctl -u plantmon -f"
