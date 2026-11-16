#!/usr/bin/env bash
# Installs SeaTrader as a service on a Raspberry Pi (or any Linux with systemd).
# The game then starts at boot and restarts itself if it ever stops.
#
#   cd ~/SeaTrader && bash pi/install.sh          # port 8765
#   bash pi/install.sh 9000                       # another port
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${1:-8765}"
RUN_AS="${SUDO_USER:-$(id -un)}"
PY="$(command -v python3 || true)"

if [ -z "$PY" ]; then
  echo "python3 was not found. Install it with: sudo apt install python3"
  exit 1
fi
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
  echo "SeaTrader needs Python 3.8 or newer. This Pi has: $("$PY" --version)"
  exit 1
fi
if [ ! -f "$DIR/server.py" ]; then
  echo "server.py was not found in $DIR"
  exit 1
fi

echo "Installing the SeaTrader service (folder: $DIR, user: $RUN_AS, port: $PORT)"
sudo tee /etc/systemd/system/seatrader.service >/dev/null <<EOF
[Unit]
Description=SeaTrader game server
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_AS
WorkingDirectory=$DIR
ExecStart="$PY" -u "$DIR/server.py" --port $PORT
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable seatrader.service
sudo systemctl restart seatrader.service
sleep 2

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if systemctl is-active --quiet seatrader.service; then
  echo ""
  echo "SeaTrader is running and will start at every boot."
  echo "  Players:       http://${IP:-<this Pi>}:$PORT"
  echo "  Harbor board:  http://${IP:-<this Pi>}:$PORT/board"
  echo ""
  echo "On the Windows PC, put this one line in server_address.txt next to the"
  echo "launchers so they open the Pi's game:   ${IP:-<this Pi>}:$PORT"
  echo ""
  echo "Logs:    journalctl -u seatrader -f"
  echo "Stop:    sudo systemctl stop seatrader"
  echo "Remove:  bash pi/uninstall.sh"
else
  echo "The service did not start. See why with: journalctl -u seatrader -n 30"
  exit 1
fi
