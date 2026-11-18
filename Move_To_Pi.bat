@echo off
rem ONE-TIME MOVE of Crimson Ledger to the Pi (mad-pihole, 192.168.1.69).
rem   1. Stops the game on this PC (it saves first).
rem   2. Copies everything to /home/madlively/SeaTrader on the Pi: code, the game
rem      in progress, records, Captains, settings, voice clips, media and uploads.
rem      Not copied: .git, .browser, .agent-locks, caches, Artwork, Inspiration_Artwork.
rem   3. Installs the seatrader service (starts at boot, restarts if it stops).
rem   4. Checks the Pi answers, then points the launchers at it (server_address.txt).
rem Refuses to run if the Pi already has a live game, so it can never overwrite one.
rem After this, use Deploy_To_Pi.bat for updates. Report: pi\move_report.txt
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "PIDIR=/home/madlively/SeaTrader"
set "LOG=%~dp0pi\move_report.txt"
echo Crimson Ledger - move to the Pi  %DATE% %TIME% > "%LOG%"

echo Checking the Pi...
ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "test -e %PIDIR%/saves/current.json && echo HAS_GAME || echo EMPTY" > "%TEMP%\st_pi_state.txt" 2>> "%LOG%"
if errorlevel 255 goto nossh
set /p PISTATE=<"%TEMP%\st_pi_state.txt"
echo Pi state: %PISTATE%>> "%LOG%"
if "%PISTATE%"=="HAS_GAME" goto already

echo.
echo This stops the game on this PC (it saves first) and moves everything to the Pi.
choice /c YN /m "Move Crimson Ledger to the Pi now"
if errorlevel 2 goto cancelled

echo.
echo [1/4] Stopping the game on this PC...
set "ST_DEV=1"
call "%~dp0Stop_SeaTrader.bat" >> "%LOG%" 2>&1
set "ST_DEV="
set /a TRIES=0
:waitstop
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8765/api/info; exit 0 } catch { exit 1 }"
if errorlevel 1 goto stopped
set /a TRIES+=1
if !TRIES! geq 15 goto stillrunning
timeout /t 1 /nobreak >nul
goto waitstop
:stopped
echo Game on this PC stopped and saved.>> "%LOG%"

echo [2/4] Copying to the Pi (about 1.2 GB, a few minutes)...
ssh -o BatchMode=yes %PI% "mkdir -p %PIDIR%" >> "%LOG%" 2>&1
tar -cf - --exclude ./.git --exclude ./.browser --exclude ./.agent-locks --exclude ./.claude --exclude ./.pytest_cache --exclude __pycache__ --exclude ./Artwork --exclude ./Inspiration_Artwork --exclude ./server_address.txt --exclude ./debug.log --exclude "*.lnk" -C "%~dp0." . | ssh -o BatchMode=yes %PI% "tar -xf - -C %PIDIR% && sed -i 's/\r$//' %PIDIR%/run.sh %PIDIR%/pi/*.sh && echo COPY_OK" >> "%LOG%" 2>&1
findstr /c:"COPY_OK" "%LOG%" >nul || goto copyfailed
ssh -o BatchMode=yes %PI% "du -sh %PIDIR%; ls %PIDIR%/saves | head" >> "%LOG%" 2>&1

echo [3/4] Installing the service on the Pi...
ssh -o BatchMode=yes %PI% "cd %PIDIR% && bash pi/install.sh 8765" >> "%LOG%" 2>&1
if errorlevel 1 goto installfailed

echo [4/4] Checking the game answers on the Pi...
set /a TRIES=0
:waitpi
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://192.168.1.69:8765/api/info; exit 0 } catch { exit 1 }"
if not errorlevel 1 goto piup
set /a TRIES+=1
if !TRIES! geq 30 goto pidown
timeout /t 1 /nobreak >nul
goto waitpi
:piup
> "%~dp0server_address.txt" echo 192.168.1.69:8765
echo Pi answers on 192.168.1.69:8765. server_address.txt now points the launchers there.>> "%LOG%"
ssh -o BatchMode=yes %PI% "journalctl -u seatrader -n 15 --no-pager" >> "%LOG%" 2>&1
echo MOVE_DONE>> "%LOG%"
echo.
echo Done. Crimson Ledger now runs on the Pi at http://192.168.1.69:8765
echo Next: Pi_SeaTrade_Name.bat sets up http://sea.trade
echo Tell Claude "moved".
goto end

:nossh
echo Could not reach the Pi over SSH.>> "%LOG%"
echo Could not reach the Pi over SSH. Nothing was changed.
goto end
:already
echo The Pi already has a live game; nothing was copied.>> "%LOG%"
echo The Pi already has a live Crimson Ledger game, so nothing was copied.
echo Use Deploy_To_Pi.bat to send code updates.
goto end
:cancelled
echo Cancelled by the user.>> "%LOG%"
echo Cancelled. Nothing was changed.
goto end
:stillrunning
echo The game on this PC did not stop; nothing was copied.>> "%LOG%"
echo The game on this PC did not stop, so nothing was copied. Close its window and try again.
goto end
:copyfailed
echo COPY FAILED.>> "%LOG%"
echo The copy did not finish. The game on this PC is untouched; start it with Launch_SeaTrader.bat.
goto end
:installfailed
echo INSTALL FAILED.>> "%LOG%"
echo Installing the service failed. Details are in pi\move_report.txt.
goto end
:pidown
echo THE PI DID NOT ANSWER.>> "%LOG%"
ssh -o BatchMode=yes %PI% "journalctl -u seatrader -n 40 --no-pager" >> "%LOG%" 2>&1
echo The game did not answer on the Pi. Details are in pi\move_report.txt.
goto end

:end
echo Report: %LOG%
echo.
pause
endlocal
