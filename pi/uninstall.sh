#!/usr/bin/env bash
# Removes the SeaTrader service. The game folder and saves are left alone.
set -euo pipefail
sudo systemctl disable --now seatrader.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/seatrader.service
sudo systemctl daemon-reload
echo "SeaTrader service removed. Your game folder and saves were not touched."
