# Why does sea.trade sometimes go to GoDaddy on this PC? Read-only (flushes the DNS cache once).
# Run by DNS_Check.bat. Report: pi\dns_report.txt
function Section($t) { "`n===== $t =====" }

Section "DNS servers per network adapter (IPv4 and IPv6)"
Get-DnsClientServerAddress | Where-Object { $_.ServerAddresses } |
  Format-Table InterfaceAlias, AddressFamily, @{n='Servers';e={$_.ServerAddresses -join ', '}} -AutoSize | Out-String -Width 200

Section "Network adapters that are up"
Get-NetAdapter | Where-Object Status -eq 'Up' | Format-Table Name, InterfaceDescription, InterfaceMetric -AutoSize | Out-String -Width 200
Get-NetIPInterface -AddressFamily IPv4 | Where-Object ConnectionState -eq 'Connected' |
  Sort-Object InterfaceMetric | Format-Table InterfaceAlias, InterfaceMetric -AutoSize | Out-String -Width 200

Section "Windows encrypted DNS (DoH) servers"
try { Get-DnsClientDohServerAddress | Format-Table -AutoSize | Out-String -Width 200 } catch { "(not available)" }

Section "hosts file lines for sea.trade / home.power"
Select-String -Path "$env:windir\System32\drivers\etc\hosts" -Pattern 'sea\.trade|home\.power' | ForEach-Object { $_.Line }
"(end)"

Section "Cached answer before flushing"
Get-DnsClientCache -Entry sea.trade -ErrorAction SilentlyContinue | Format-Table Entry, Data, TimeToLive -AutoSize | Out-String
ipconfig /flushdns | Out-Null
"(cache flushed)"

Section "Lookups"
foreach ($q in @(@('sea.trade', $null), @('sea.trade', '192.168.1.69'), @('sea.trade', '1.1.1.1'), @('home.power', $null))) {
  $name, $srv = $q
  $label = if ($srv) { "$name via $srv" } else { "$name via Windows" }
  try {
    $r = if ($srv) { Resolve-DnsName $name -Type A -Server $srv -DnsOnly -ErrorAction Stop } else { Resolve-DnsName $name -Type A -DnsOnly -ErrorAction Stop }
    "{0,-28} -> {1}" -f $label, (($r | Where-Object IPAddress | ForEach-Object IPAddress) -join ', ')
  } catch { "{0,-28} -> FAILED {1}" -f $label, $_.Exception.Message }
}
"Windows lookup x5 (looking for answers that flip between servers):"
1..5 | ForEach-Object { ipconfig /flushdns | Out-Null; try { (Resolve-DnsName sea.trade -Type A -DnsOnly -ErrorAction Stop | Where-Object IPAddress | ForEach-Object IPAddress) -join ', ' } catch { 'FAILED' } }

Section "What answers http://sea.trade"
$curl = (Get-Command curl.exe -ErrorAction SilentlyContinue).Source
if ($curl) { & $curl -s -o NUL --noproxy "*" --max-time 5 -w "HTTP %{http_code} from %{remote_ip}" http://sea.trade/api/info; "" } else { "(no curl.exe)" }

Section "Edge secure DNS settings"
foreach ($k in 'HKLM:\SOFTWARE\Policies\Microsoft\Edge', 'HKCU:\SOFTWARE\Policies\Microsoft\Edge') {
  $p = Get-ItemProperty $k -ErrorAction SilentlyContinue
  if ($p) { "$k  DnsOverHttpsMode=$($p.DnsOverHttpsMode)  BuiltInDnsClientEnabled=$($p.BuiltInDnsClientEnabled)" } else { "$k  (no policy)" }
}
foreach ($f in "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Local State", "D:\SeaTrader\.browser\player\Local State") {
  if (Test-Path $f) {
    try { $j = Get-Content $f -Raw | ConvertFrom-Json; "{0}: dns_over_https mode={1} templates={2}" -f $f, $j.dns_over_https.mode, $j.dns_over_https.templates }
    catch { "${f}: (unreadable)" }
  } else { "${f}: (not found)" }
}
"`n===== DONE ====="
