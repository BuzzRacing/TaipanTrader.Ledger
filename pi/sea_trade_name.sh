#!/usr/bin/env bash
# Step 4 of the move: makes http://sea.trade open Crimson Ledger on this Pi.
# Run from BIGBOX by Pi_SeaTrade_Name.bat:  ssh madlively@192.168.1.69 "bash -s" < pi/sea_trade_name.sh
#   1. Pi-hole backup (Teleporter zip in /tmp, copied to D:\Mad-PiHole by the .bat)
#   2. Adds "192.168.1.69 sea.trade" to Pi-hole's local DNS records (dns.hosts), keeping every other entry
#   3. Adds a sea.trade rule to Caddy (/opt/home-automation/caddy/Caddyfile), keeping a copy of the old file,
#      checks the new file, then restarts the caddy container (home.power blinks for a moment)
#   4. Restarts the game so its join screen shows http://sea.trade
# Safe to run twice: anything already in place is left alone.
set -uo pipefail
IP="192.168.1.69"
NAME="sea.trade"
CADDYFILE="/opt/home-automation/caddy/Caddyfile"
GAME="/home/madlively/SeaTrader"
step() { echo; echo "===== $1 ====="; }
fail() { echo "FAILED: $1"; exit 1; }

step "Pi-hole backup (before)"
rm -f /tmp/pi-hole_*_teleporter_*.zip
(cd /tmp && sudo -n pihole-FTL --teleporter 2>&1 | tail -1)
sudo -n chown "$(id -un)" /tmp/pi-hole_*_teleporter_*.zip 2>/dev/null

step "Local DNS record"
sudo -n python3 - "$IP" "$NAME" <<'PY' || fail "could not update dns.hosts"
import json, subprocess, sys, tomllib
ip, name = sys.argv[1], sys.argv[2]
with open("/etc/pihole/pihole.toml", "rb") as f:
    hosts = list(tomllib.load(f)["dns"]["hosts"])
if any(name in entry.split()[1:] for entry in hosts):
    print("already there:", [e for e in hosts if name in e.split()[1:]])
    sys.exit(0)
new = hosts + ["{} {}".format(ip, name)]
r = subprocess.run(["pihole-FTL", "--config", "dns.hosts", json.dumps(new)], capture_output=True, text=True)
print(r.stdout.strip() or r.stderr.strip())
if r.returncode:
    sys.exit(1)
print("added: {} {}  ({} entries before, {} now)".format(ip, name, len(hosts), len(new)))
PY
sudo -n pihole reloaddns 2>&1 | tail -1
sleep 2
echo -n "$NAME from Pi-hole -> "; dig +short @127.0.0.1 "$NAME" 2>/dev/null || getent hosts "$NAME"
echo -n "home.power from Pi-hole -> "; dig +short @127.0.0.1 home.power 2>/dev/null || getent hosts home.power

step "Caddy rule"
[ -f "$CADDYFILE" ] || fail "$CADDYFILE not found"
if sudo -n grep -q "http://$NAME" "$CADDYFILE"; then
  echo "sea.trade rule already in the Caddyfile"
else
  BAK="$CADDYFILE.before-seatrade-$(date +%Y-%m-%d_%H-%M-%S)"
  sudo -n cp -p "$CADDYFILE" "$BAK" || fail "could not back up the Caddyfile"
  echo "backup: $BAK"
  # Append in place (same file), so a container that mounts just this file still sees the change.
  sudo -n tee -a "$CADDYFILE" >/dev/null <<EOF

# http://$NAME  ->  Crimson Ledger (seatrader service on :8765). Plain http, local LAN only.
# Caddy passes the visitor's address on (X-Forwarded-For); the game trusts it only from this Pi.
http://$NAME {
	reverse_proxy 127.0.0.1:8765
}
EOF
  out="$(sudo -n docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1)"; rc=$?
  echo "$out" | tail -3
  if [ $rc -ne 0 ]; then
    sudo -n sh -c "cat '$BAK' > '$CADDYFILE'"
    fail "the new Caddyfile did not validate; the old one was put back and Caddy was not restarted"
  fi
fi
echo "--- Caddyfile now:"
sudo -n cat "$CADDYFILE"

step "Restart Caddy"
sudo -n docker restart caddy >/dev/null && echo "caddy restarted" || fail "could not restart caddy"
sleep 3

step "Game shows http://sea.trade to players"
if [ -f "$GAME/pi/install.sh" ]; then
  (cd "$GAME" && bash pi/install.sh 8765 "http://$NAME" 2>&1 | tail -4)
else
  echo "(game not installed on the Pi yet; run Move_To_Pi.bat first)"
fi
sleep 2

step "Checks on the Pi"
echo -n "sea.trade through Caddy:  "; curl -s -m 5 -H "Host: $NAME" http://127.0.0.1/api/info | head -c 60; echo
echo -n "home.power through Caddy: HTTP "; curl -s -m 5 -o /dev/null -w "%{http_code}" -H "Host: home.power" http://127.0.0.1/; echo
echo -n "game on :8765:            "; curl -s -m 5 http://127.0.0.1:8765/api/info | head -c 60; echo

step "Pi-hole backup (after)"
(cd /tmp && sudo -n pihole-FTL --teleporter 2>&1 | tail -1)
sudo -n chown "$(id -un)" /tmp/pi-hole_*_teleporter_*.zip 2>/dev/null
ls /tmp/pi-hole_*_teleporter_*.zip
echo
echo "===== NAME_SCRIPT_DONE ====="
