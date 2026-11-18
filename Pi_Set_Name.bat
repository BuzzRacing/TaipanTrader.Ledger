@echo off
rem Sets the game's friendly address on the Pi and removes old ones.
rem   NAME = the address players type (http://NAME)
rem   OLD  = earlier addresses to take out of Pi-hole and Caddy
rem Pi-hole backups are taken before and after and copied to D:\Mad-PiHole\teleporter-backup.
rem Caddy restarts, so home.power blinks for a moment. Safe to run twice. Report: pi\name_report.txt
setlocal
cd /d "%~dp0"
set "NAME=crimson.ledger"
set "OLD=sea.trade"
set "PI=madlively@192.168.1.69"
set "LOG=%~dp0pi\name_report.txt"
echo Crimson Ledger - address %NAME%  %DATE% %TIME% > "%LOG%"

echo Setting the game's address to http://%NAME% ... (about 30 seconds)
ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "bash -s -- %NAME% %OLD%" < "%~dp0pi\set_name.sh" >> "%LOG%" 2>&1
scp -o BatchMode=yes %PI%:/tmp/pi-hole_*_teleporter_*.zip "D:\Mad-PiHole\teleporter-backup" >> "%LOG%" 2>&1
findstr /c:"NAME_SCRIPT_DONE" "%LOG%" >nul || goto failed

echo.>> "%LOG%"
echo ===== Checks from BIGBOX (the way browsers look names up) =====>> "%LOG%"
ipconfig /flushdns >nul
powershell -NoProfile -Command "try { ([System.Net.Dns]::GetHostAddresses('%NAME%') | %% { $_.IPAddressToString }) -join ', ' } catch { 'lookup FAILED' }" >> "%LOG%" 2>&1
curl.exe -s -o nul --noproxy "*" --max-time 5 -w "http://%NAME% -> HTTP %%{http_code} from %%{remote_ip}\n" http://%NAME%/api/info >> "%LOG%" 2>&1
curl.exe -s -f -o nul --noproxy "*" --max-time 5 http://%NAME%/api/info
if errorlevel 1 goto nobigbox

> "%~dp0server_address.txt" echo %NAME%
echo server_address.txt now says %NAME%>> "%LOG%"
echo NAME_DONE>> "%LOG%"
echo.
echo Done. Crimson Ledger is at http://%NAME%/
echo Tell Claude "named".
goto end

:failed
echo The setup on the Pi stopped early. Details are in pi\name_report.txt.
goto end
:nobigbox
echo The Pi is set up, but this PC could not open http://%NAME% yet. Details are in pi\name_report.txt.
goto end

:end
echo Report: %LOG%
echo.
pause
endlocal
