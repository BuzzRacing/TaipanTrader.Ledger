#!/usr/bin/env bash
# Read-only survey of mad-pihole for the Crimson Ledger move (step 1).
# Run from BIGBOX by Pi_Check.bat:  ssh madlively@192.168.1.69 "bash -s" < pi/check_remote.sh
# Changes nothing except writing a Pi-hole Teleporter backup zip into /tmp.

section() { echo; echo "===== $1 ====="; }

section "Machine"
hostname
cat /proc/device-tree/model 2>/dev/null; echo
. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
uname -r
uptime
timedatectl show -p Timezone --value 2>/dev/null

section "Memory"
free -h

section "Disk"
df -h / /home 2>/dev/null
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null

section "Python"
command -v python3 && python3 --version

section "Listening ports (who holds what)"
sudo -n ss -ltnp 2>/dev/null || ss -ltn

section "Web servers / proxies installed"
for b in caddy nginx lighttpd apache2 haproxy traefik node; do
  p="$(command -v $b 2>/dev/null)"; [ -n "$p" ] && echo "$b: $p"
done
systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null | awk '{print $1}'

section "Home folder"
ls -la ~

section "Anything home-automation / home.power"
ls -d ~/*ome* ~/*utomation* /opt/* /srv/* 2>/dev/null
systemctl list-unit-files --no-pager --no-legend 2>/dev/null | grep -i -E "home|power|govee|seatrader|caddy|nginx" || echo "(no matching services)"
grep -r -l -i "home.power" /etc/systemd/system /etc/caddy /etc/nginx 2>/dev/null || echo "(home.power not found in service/proxy configs)"

section "Pi-hole versions"
pihole -v 2>/dev/null || pihole version 2>/dev/null

section "Pi-hole web server port"
sudo -n pihole-FTL --config webserver.port 2>/dev/null
sudo -n pihole-FTL --config webserver.domain 2>/dev/null

section "Pi-hole local DNS records (dns.hosts)"
sudo -n pihole-FTL --config dns.hosts 2>/dev/null

section "Pi-hole CNAME records"
sudo -n pihole-FTL --config dns.cnameRecords 2>/dev/null

section "Pi-hole extra dnsmasq lines"
sudo -n pihole-FTL --config misc.dnsmasq_lines 2>/dev/null

section "Name check from the Pi"
for n in home.power sea.trade; do
  echo -n "$n -> "; getent hosts "$n" || echo "(no answer)"
done

section "Existing SeaTrader on the Pi"
ls -la ~/SeaTrader 2>/dev/null | head -20 || echo "(none)"
systemctl status seatrader --no-pager 2>/dev/null | head -5 || echo "(no seatrader service)"

section "Who runs port 80 (Caddy) and the home-automation apps"
for pid in $(pgrep -x caddy) $(sudo -n ss -ltnp 2>/dev/null | grep -E ':(8123|8989|8081|8056) ' | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u); do
  echo "--- pid $pid: $(ps -o user=,cmd= -p $pid 2>/dev/null)"
  systemctl status "$pid" --no-pager 2>/dev/null | head -4
done
echo "--- docker containers"
sudo -n docker ps --format '{{.Names}}  {{.Image}}  {{.Ports}}' 2>/dev/null || echo "(docker not readable)"

section "/opt/home-automation"
ls -la /opt/home-automation 2>/dev/null
echo "--- Caddy config files"
for f in /etc/caddy/Caddyfile $(sudo -n find /opt/home-automation /etc/caddy -maxdepth 3 -iname '*caddy*' -type f 2>/dev/null); do
  [ -f "$f" ] && { echo ">>> $f"; sudo -n cat "$f"; echo; }
done
systemctl list-unit-files --no-pager --no-legend 2>/dev/null | grep -i -E "caddy|home-auto|automation" || true

section "Teleporter backup"
rm -f /tmp/pi-hole_*_teleporter_*.zip
cd /tmp && sudo -n pihole-FTL --teleporter 2>&1 | tail -3
sudo -n chown "$(id -un)" /tmp/pi-hole_*_teleporter_*.zip 2>/dev/null
ls -la /tmp/pi-hole_*_teleporter_*.zip 2>/dev/null

echo
echo "===== DONE ====="
