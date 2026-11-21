@echo off
rem Puts the cast portraits back on the live game on the Pi.
rem   Sends tools\relink_portraits.py, runs it there, and restarts the game only if something was relinked.
rem   Only blank portrait links change; the Pi's settings are backed up to config/backups first.
rem Report: pi\relink_report.txt
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "PIDIR=/home/madlively/SeaTrader"
set "LOG=%~dp0pi\relink_report.txt"
echo Crimson Ledger - relink cast portraits on the Pi  %DATE% %TIME% > "%LOG%"

echo [1/3] Sending the relink script...
scp -o BatchMode=yes -o ConnectTimeout=10 "%~dp0tools\relink_portraits.py" %PI%:%PIDIR%/tools/relink_portraits.py >> "%LOG%" 2>&1
if errorlevel 1 goto failed

echo [2/3] Relinking...
ssh -o BatchMode=yes %PI% "cd %PIDIR% && python3 tools/relink_portraits.py" >> "%LOG%" 2>&1
type "%LOG%"
findstr /c:"RELINKED" "%LOG%" >nul || goto nochange

echo [3/3] Restarting the game on the Pi so it picks up the portraits...
ssh -o BatchMode=yes %PI% "sudo -n systemctl restart seatrader" >> "%LOG%" 2>&1
set /a TRIES=0
:waitpi
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://192.168.1.69:8765/api/info; exit 0 } catch { exit 1 }"
if not errorlevel 1 goto up
set /a TRIES+=1
if !TRIES! geq 30 goto down
goto waitpi

:up
echo RELINK_DONE>> "%LOG%"
echo.
echo Portraits are back. Reload the admin page (F5) before saving anything there.
goto end

:nochange
echo.
echo Nothing needed relinking on the Pi (see above).
goto end
:failed
echo COULD NOT REACH THE PI.>> "%LOG%"
echo Could not reach the Pi. See pi\relink_report.txt.
goto end
:down
echo THE GAME DID NOT COME BACK.>> "%LOG%"
ssh -o BatchMode=yes %PI% "journalctl -u seatrader -n 40 --no-pager" >> "%LOG%" 2>&1
echo The game did not come back after the restart. The reason is in pi\relink_report.txt.
goto end

:end
echo Report: %LOG%
echo.
pause
endlocal
