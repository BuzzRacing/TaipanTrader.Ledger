#!/usr/bin/env bash
# Gives Taipan Trader its friendly address on this Pi (default taipantrader.ledger), like crimson.ledger and atomic.ledger.
# Run from BIGBOX by Pi_Set_TaipanTrader_URL.bat:  ssh madlively@192.168.1.69 "bash -s -- NEW [OLD ...]" < pi/set_name.sh
# Installs or restarts the taipantrader service (port 8775) first. Crimson Ledger and Atomic Ledger are left alone.
#   1. Pi-hole backup (Teleporter zip in /tmp; the .bat copies it to D:\Mad-PiHole)
#   2. Pi-hole local DNS (dns.hosts): drops entries for the OLD names, adds "192.168.1.69 NEW"; every other entry kept
#   3. Caddy (/opt/home-automation/caddy/Caddyfile): replaces the game's rule with one for NEW (dated backup kept),
#      validates, restarts the caddy container (home.power blinks for a moment); old file restored if invalid
#   4. Restarts the game so its join screen shows http://NEW
# Safe to run again.
set -uo pipefail
NEW="${1:-taipantrader.ledger}"; shift || true
OLDS="$*"
IP="192.168.1.69"
CADDYFILE="/opt/home-automation/caddy/Caddyfile"
GAME="/home/madlively/TaipanTrader"
step() { echo; echo "===== $1 ====="; }
fail() { echo "FAILED: $1"; exit 1; }

step "Pi-hole backup (before)"
rm -f /tmp/pi-hole_*_teleporter_*.zip
(cd /tmp && sudo -n pihole-FTL --teleporter 2>&1 | tail -1)
sudo -n chown "$(id -un)" /tmp/pi-hole_*_teleporter_*.zip 2>/dev/null

step "Local DNS records"
sudo -n python3 - "$IP" "$NEW" $OLDS <<'PY' || fail "could not update dns.hosts"
import json, subprocess, sys, tomllib
ip, new, olds = sys.argv[1], sys.argv[2], set(sys.argv[3:])
with open("/etc/pihole/pihole.toml", "rb") as f:
    hosts = list(tomllib.load(f)["dns"]["hosts"])
keep = [e for e in hosts if not (olds & set(e.split()[1:]))]
dropped = [e for e in hosts if e not in keep]
if not any(new in e.split()[1:] for e in keep):
    keep.append("{} {}".format(ip, new))
if keep == hosts:
    print("nothing to change")
    sys.exit(0)
r = subprocess.run(["pihole-FTL", "--config", "dns.hosts", json.dumps(keep)], capture_output=True, text=True)
if r.returncode:
    print(r.stderr.strip() or r.stdout.strip()); sys.exit(1)
print("removed:", dropped or "nothing")
print("now has: {} {}".format(ip, new), "({} entries before, {} now)".format(len(hosts), len(keep)))
PY
sudo -n pihole reloaddns 2>&1 | tail -1
sleep 2
for n in "$NEW" $OLDS home.power; do echo -n "$n from Pi-hole -> "; dig +short @127.0.0.1 "$n" A | tr '\n' ' '; echo; done
echo -n "$NEW on the public internet (should be empty) -> "; dig +short @1.1.1.1 "$NEW" A | tr '\n' ' '; echo

step "Caddy rule"
[ -f "$CADDYFILE" ] || fail "$CADDYFILE not found"
BAK="$CADDYFILE.before-$NEW-$(date +%Y-%m-%d_%H-%M-%S)"
sudo -n cp -p "$CADDYFILE" "$BAK" || fail "could not back up the Caddyfile"
echo "backup: $BAK"
sudo -n python3 - "$CADDYFILE" "$NEW" $OLDS <<'PY' || fail "could not edit the Caddyfile"
import re, sys
path, new, olds = sys.argv[1], sys.argv[2], sys.argv[3:]
text = open(path, encoding="utf-8").read()
# Remove the managed block, and any older game rule (comment lines + "http://NAME { ... }") for old or new names.
text = re.sub(r"\n*# --- Taipan Trader \(managed by pi/set_name\.sh\) ---.*?# --- end Taipan Trader ---\n?", "\n", text, flags=re.S)
for name in olds + [new]:
    n = re.escape(name)
    text = re.sub(r"\n*(?:#[^\n]*\n)*http://" + n + r" \{\n.*?\n\}\n?", "\n", text, flags=re.S)
block = ("\n# --- Taipan Trader (managed by pi/set_name.sh) ---\n"
         "# http://{0}  ->  Taipan Trader (taipantrader service on :8775). Plain http, local LAN only.\n"
         "# Caddy passes the visitor's address on (X-Forwarded-For); the game trusts it only from this Pi.\n"
         "http://{0} {{\n\treverse_proxy 127.0.0.1:8775\n}}\n"
         "# --- end Taipan Trader ---\n").format(new)
text = text.rstrip("\n") + "\n" + block
with open(path, "w", encoding="utf-8") as f:   # same file, so a container mounting just this file sees it
    f.write(text)
PY
out="$(sudo -n docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1)"; rc=$?
echo "$out" | tail -2
if [ $rc -ne 0 ]; then
  sudo -n sh -c "cat '$BAK' > '$CADDYFILE'"
  fail "the new Caddyfile did not validate; the old one was put back and Caddy was not restarted"
fi
echo "--- Caddyfile now:"
sudo -n cat "$CADDYFILE"

step "Restart Caddy"
sudo -n docker restart caddy >/dev/null && echo "caddy restarted" || fail "could not restart caddy"
sleep 3

step "Taipan Trader service on :8775, showing http://$NEW to players"
if [ -f "$GAME/pi/install.sh" ]; then
  (cd "$GAME" && bash pi/install.sh 8775 "http://$NEW" 2>&1 | grep -E "running|did not" )
else
  echo "(game not installed on the Pi yet)"
fi
sleep 3

step "Checks on the Pi"
echo -n "$NEW through Caddy:  "; curl -s -m 5 -H "Host: $NEW" http://127.0.0.1/api/info | head -c 60; echo
for o in $OLDS; do echo -n "$o through Caddy (should be empty): "; curl -s -m 5 -H "Host: $o" http://127.0.0.1/api/info | head -c 60; echo; done
echo -n "home.power through Caddy: HTTP "; curl -s -m 5 -o /dev/null -w "%{http_code}" -H "Host: home.power" http://127.0.0.1/; echo

step "Pi-hole backup (after)"
(cd /tmp && sudo -n pihole-FTL --teleporter 2>&1 | tail -1)
sudo -n chown "$(id -un)" /tmp/pi-hole_*_teleporter_*.zip 2>/dev/null
echo
echo "===== NAME_SCRIPT_DONE ====="
