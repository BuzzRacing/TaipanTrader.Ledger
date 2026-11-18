@echo off
rem Step 4 of the move: makes http://sea.trade open Crimson Ledger on the Pi.
rem Adds sea.trade to Pi-hole's local names and a sea.trade rule to Caddy (home.power blinks
rem for a moment while Caddy restarts). Pi-hole backups are taken before and after and copied
rem to D:\Mad-PiHole\teleporter-backup. Safe to run twice. Report: pi\name_report.txt
setlocal
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "LOG=%~dp0pi\name_report.txt"
echo Crimson Ledger - sea.trade  %DATE% %TIME% > "%LOG%"

echo Setting up sea.trade on the Pi... (about 30 seconds)
ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "bash -s" < "%~dp0pi\sea_trade_name.sh" >> "%LOG%" 2>&1
scp -o BatchMode=yes %PI%:/tmp/pi-hole_*_teleporter_*.zip "D:\Mad-PiHole\teleporter-backup" >> "%LOG%" 2>&1
findstr /c:"NAME_SCRIPT_DONE" "%LOG%" >nul || goto failed

echo.>> "%LOG%"
echo ===== Checks from BIGBOX =====>> "%LOG%"
ipconfig /flushdns >nul
nslookup sea.trade 192.168.1.69 >> "%LOG%" 2>&1
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://sea.trade/api/info; 'sea.trade from BIGBOX: OK'; exit 0 } catch { 'sea.trade from BIGBOX: FAILED ' + $_.Exception.Message; exit 1 }" >> "%LOG%" 2>&1
if errorlevel 1 goto nobigbox
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://home.power/; 'home.power from BIGBOX: HTTP ' + $r.StatusCode } catch { 'home.power from BIGBOX: ' + $_.Exception.Message }" >> "%LOG%" 2>&1

> "%~dp0server_address.txt" echo sea.trade
echo server_address.txt now says sea.trade>> "%LOG%"
echo SEA_TRADE_DONE>> "%LOG%"
echo.
echo Done. Crimson Ledger is at http://sea.trade
echo Tell Claude "named".
goto end

:failed
echo The setup on the Pi stopped early. Details are in pi\name_report.txt.
goto end
:nobigbox
echo The Pi is set up, but this PC could not open http://sea.trade yet. Details are in pi\name_report.txt.
echo The launchers still use 192.168.1.69:8765.
goto end

:end
echo Report: %LOG%
echo.
pause
endlocal
