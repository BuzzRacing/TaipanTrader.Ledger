@echo off
rem Restart test: reboots the Pi, then checks that DNS, Crimson Ledger, home.power and
rem Home Assistant all come back by themselves. While the Pi restarts (about a minute)
rem the whole house has no DNS. The game saves before the Pi goes down.
rem Report: pi\reboot_report.txt
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "LOG=%~dp0pi\reboot_report.txt"
echo Crimson Ledger - Pi restart test  %DATE% %TIME% > "%LOG%"

echo While the Pi restarts (about a minute) the whole house has no DNS.
choice /c YN /m "Restart the Pi now"
if errorlevel 2 (echo Cancelled.>> "%LOG%" & echo Cancelled. & goto end)

echo ===== Before =====>> "%LOG%"
ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "uptime; systemctl is-active seatrader pihole-FTL docker; sudo -n docker ps --format '{{.Names}} {{.Status}}'" >> "%LOG%" 2>&1
echo Restarting the Pi...
ssh -o BatchMode=yes %PI% "sudo -n systemctl reboot" >> "%LOG%" 2>&1
timeout /t 20 /nobreak >nul

echo Waiting for the Pi to come back...
set /a TRIES=0
:waitdns
powershell -NoProfile -Command "try { $r = Resolve-DnsName crimson.ledger -Server 192.168.1.69 -DnsOnly -QuickTimeout -ErrorAction Stop; exit 0 } catch { exit 1 }"
if not errorlevel 1 goto dnsup
set /a TRIES+=1
if !TRIES! geq 60 goto dnsdown
timeout /t 3 /nobreak >nul
goto waitdns
:dnsup
set /a DNS_SECONDS=20+TRIES*3
echo DNS back after about !DNS_SECONDS! seconds.>> "%LOG%"

set /a TRIES=0
:waitgame
curl.exe -s -f -o nul --noproxy "*" --max-time 3 http://crimson.ledger/api/info
if not errorlevel 1 goto gameup
set /a TRIES+=1
if !TRIES! geq 40 goto gamedown
timeout /t 3 /nobreak >nul
goto waitgame
:gameup
echo Game back at http://crimson.ledger/>> "%LOG%"
timeout /t 15 /nobreak >nul

echo.>> "%LOG%"
echo ===== After =====>> "%LOG%"
ssh -o BatchMode=yes %PI% "uptime; systemctl is-active seatrader pihole-FTL docker; sudo -n docker ps --format '{{.Names}} {{.Status}}'; journalctl -u seatrader -b --no-pager | grep -E 'Resumed|Started a new|Could not' | tail -3" >> "%LOG%" 2>&1
curl.exe -s --noproxy "*" --max-time 5 -o nul -w "crimson.ledger: HTTP %%{http_code}\n" http://crimson.ledger/api/info >> "%LOG%" 2>&1
curl.exe -s --noproxy "*" --max-time 5 -o nul -w "home.power: HTTP %%{http_code}\n" http://home.power/ >> "%LOG%" 2>&1
powershell -NoProfile -Command "foreach ($n in 'google.com','claude.ai') { try { $null = Resolve-DnsName $n -Server 192.168.1.69 -DnsOnly -ErrorAction Stop; $n + ' via Pi-hole: OK' } catch { $n + ' via Pi-hole: FAILED' } }" >> "%LOG%" 2>&1
echo REBOOT_TEST_DONE>> "%LOG%"
echo.
echo Done. Tell Claude "rebooted".
goto end

:dnsdown
echo DNS DID NOT COME BACK within about 3 minutes.>> "%LOG%"
echo The Pi's DNS has not come back after about 3 minutes. Check that the Pi has power.
goto end
:gamedown
echo GAME DID NOT COME BACK.>> "%LOG%"
ssh -o BatchMode=yes %PI% "systemctl status seatrader --no-pager | head -12; journalctl -u seatrader -b -n 30 --no-pager" >> "%LOG%" 2>&1
echo DNS is back but the game is not. Details are in pi\reboot_report.txt.
goto end

:end
echo Report: %LOG%
echo.
pause
endlocal
