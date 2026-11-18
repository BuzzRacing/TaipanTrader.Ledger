# Second look: what the apps (not Resolve-DnsName) get for sea.trade, and what Pi-hole saw. Read-only.
function Section($t) { "`n===== $t =====" }

Section "curl.exe in use"
Get-Command curl.exe -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }

Section "App-style lookups (getaddrinfo), x5"
1..5 | ForEach-Object {
  try { ([System.Net.Dns]::GetHostAddresses('sea.trade') | ForEach-Object { $_.IPAddressToString }) -join ', ' } catch { 'FAILED ' + $_.Exception.Message }
}

Section "Resolve-DnsName without -DnsOnly (A and AAAA)"
try { Resolve-DnsName sea.trade -ErrorAction Stop | Format-Table Name, Type, IPAddress, Section -AutoSize | Out-String } catch { $_.Exception.Message }
try { Resolve-DnsName sea.trade -Type AAAA -Server 192.168.1.69 -ErrorAction Stop | Format-Table Name, Type, IPAddress -AutoSize | Out-String } catch { "AAAA via Pi-hole: " + $_.Exception.Message }

Section "nslookup with the default server"
nslookup sea.trade 2>&1 | Out-String

Section "curl -v http://sea.trade/api/info"
& curl.exe -v -s -o NUL --noproxy "*" --max-time 5 http://sea.trade/api/info 2>&1 | Select-String -Pattern 'Trying|Connected|Host:|HTTP/|resolve|Could' | ForEach-Object { $_.Line }

Section "Proxy settings"
netsh winhttp show proxy | Out-String
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue |
  Select-Object ProxyEnable, ProxyServer, ProxyOverride, AutoConfigURL | Format-List | Out-String
"HTTP_PROXY=$env:HTTP_PROXY  HTTPS_PROXY=$env:HTTPS_PROXY  ALL_PROXY=$env:ALL_PROXY  NO_PROXY=$env:NO_PROXY"

Section "Name Resolution Policy Table"
Get-DnsClientNrptPolicy -ErrorAction SilentlyContinue | Format-Table Namespace, NameServers, DirectAccessDnsServers -AutoSize | Out-String
Get-DnsClientNrptRule -ErrorAction SilentlyContinue | Format-Table Namespace, NameServers, DnsSecEnabled -AutoSize | Out-String

Section "Pi-hole's own log of sea.trade lookups today (from the Pi)"
$sql = "SELECT datetime(timestamp,'unixepoch','localtime') AS t, client, type, status, reply_type, forward FROM queries WHERE domain='sea.trade' AND timestamp > strftime('%s','now','-3 hours') ORDER BY timestamp DESC LIMIT 40;"
$sql | ssh -o BatchMode=yes -o ConnectTimeout=10 madlively@192.168.1.69 "sudo -n pihole-FTL sqlite3 -header -column /etc/pihole/pihole-FTL.db" 2>&1 | Out-String
"(status 2/3 = answered by forwarding upstream or from cache; local records usually show reply_type 4 = IP)"
"Pi-hole config check:"
ssh -o BatchMode=yes madlively@192.168.1.69 "sudo -n pihole-FTL --config dns.hosts | tr ',' '\n' | grep -i sea; dig +short @127.0.0.1 sea.trade A; dig +short @127.0.0.1 sea.trade AAAA; echo HTTPS:; dig +short @127.0.0.1 sea.trade HTTPS" 2>&1 | Out-String

"`n===== DONE ====="
