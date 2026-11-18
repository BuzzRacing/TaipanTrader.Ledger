@echo off
rem Sends your latest code from D:\SeaTrader to the live game on the Pi, then restarts it.
rem   Copies:  the .py files, web pages/scripts/styles, web\assets, web\fonts, pi\, tools\, tests\
rem   Adds:    new pictures and videos in web\media (nothing on the Pi is overwritten or deleted)
rem   Never touches the Pi's game data: saves, journal, captains, config, cache, web\uploads.
rem The game saves before it restarts; players' screens reconnect by themselves.
rem Report: pi\deploy_report.txt
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "PIDIR=/home/madlively/SeaTrader"
set "LOG=%~dp0pi\deploy_report.txt"
echo Crimson Ledger - deploy to the Pi  %DATE% %TIME% > "%LOG%"

ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "test -e %PIDIR%/server.py && echo READY" > "%TEMP%\st_pi_state.txt" 2>> "%LOG%"
set "PISTATE="
set /p PISTATE=<"%TEMP%\st_pi_state.txt"
if not "%PISTATE%"=="READY" goto notmoved

echo [1/3] Sending the code...
tar -cf - --exclude ./.git --exclude ./.browser --exclude ./.agent-locks --exclude ./.claude --exclude ./.pytest_cache --exclude __pycache__ --exclude ./Artwork --exclude ./Inspiration_Artwork --exclude ./server_address.txt --exclude ./debug.log --exclude "*.lnk" --exclude ./saves --exclude ./journal --exclude ./captains --exclude ./config --exclude ./cache --exclude ./web/uploads --exclude ./web/media --exclude ./pi/move_report.txt --exclude ./pi/deploy_report.txt --exclude ./pi/pi_check_report.txt --exclude ./pi/name_report.txt -C "%~dp0." . | ssh -o BatchMode=yes %PI% "tar -xf - -C %PIDIR% && sed -i 's/\r$//' %PIDIR%/run.sh %PIDIR%/pi/*.sh && echo CODE_OK" >> "%LOG%" 2>&1
findstr /c:"CODE_OK" "%LOG%" >nul || goto failed

echo [2/3] Adding new media...
if exist "%~dp0web\media" (
  tar -cf - -C "%~dp0web" media | ssh -o BatchMode=yes %PI% "tar -xf - --skip-old-files -C %PIDIR%/web && echo MEDIA_OK" >> "%LOG%" 2>&1
)

echo [3/3] Restarting the game on the Pi...
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
ssh -o BatchMode=yes %PI% "journalctl -u seatrader -n 8 --no-pager" >> "%LOG%" 2>&1
echo DEPLOY_DONE>> "%LOG%"
echo.
echo Live on sea.trade.
goto end

:notmoved
echo The Pi has no Crimson Ledger yet (or could not be reached). Run Move_To_Pi.bat first.>> "%LOG%"
echo The Pi has no Crimson Ledger yet, or could not be reached. Run Move_To_Pi.bat first.
goto end
:failed
echo CODE COPY FAILED.>> "%LOG%"
echo The code copy failed; the Pi keeps running the previous version. See pi\deploy_report.txt.
goto end
:down
echo THE GAME DID NOT COME BACK.>> "%LOG%"
ssh -o BatchMode=yes %PI% "journalctl -u seatrader -n 40 --no-pager" >> "%LOG%" 2>&1
echo The game did not come back after the restart. The reason is in pi\deploy_report.txt.
goto end

:end
echo Report: %LOG%
echo.
pause
endlocal
