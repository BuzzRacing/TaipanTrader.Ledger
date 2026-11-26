#!/usr/bin/env bash
# Removes the Taipan Trader service. The game folder and saves are left alone.
set -euo pipefail
sudo systemctl disable --now taipantrader.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/taipantrader.service
sudo systemctl daemon-reload
echo "Taipan Trader service removed. Your game folder and saves were not touched."
