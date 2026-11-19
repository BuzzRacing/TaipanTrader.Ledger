@echo off
rem Shrinks Crimson Ledger's game pictures: every big PNG/JPG in web\media and web\uploads becomes a
rem WebP of the same name (same size in pixels, about 93%% smaller), and the Media Library, settings,
rem saves and records are updated to the new names. Safe to run again whenever new pictures pile up.
rem
rem   Shrink_Images.bat          this PC (D:\SeaTrader), then the live game on the Pi
rem   Shrink_Images.bat pc       this PC only
rem   Shrink_Images.bat pi       the Pi only
rem   Shrink_Images.bat check    just report what would be converted here
rem
rem Old files are kept, not deleted, in D:\SeaTrader_PNG_Originals\PC_<date> and \Pi_<date>.
rem The Pi's game is stopped for a few minutes while its pictures are converted here on BIGBOX
rem (the Pi has no image tools), then started again. Report: pi\shrink_report.txt
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "PIDIR=/home/madlively/SeaTrader"
set "KEEP=D:\SeaTrader_PNG_Originals"
set "WORK=%KEEP%\_pi_work"
set "LOG=%~dp0pi\shrink_report.txt"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=all"
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "STAMP=%%d"
echo Crimson Ledger - shrink images  %DATE% %TIME%  (%MODE%)> "%LOG%"

set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% -c "import PIL" 2>nul
if errorlevel 1 (
  echo Installing Pillow, the image library this needs...
  %PY% -m pip install --user pillow >> "%LOG%" 2>&1
  %PY% -c "import PIL" 2>nul || (echo Could not install Pillow. See pi\shrink_report.txt & goto end)
)

if /i "%MODE%"=="check" (
  %PY% tools\shrink_images.py --dry-run
  goto end
)
if /i "%MODE%"=="pi" goto pi

rem ---------------------------------------------------------------- this PC --
echo.
echo === This PC: D:\SeaTrader ===
echo === This PC ===>> "%LOG%"
%PY% tools\shrink_images.py --check-port 8765 --originals "%KEEP%\PC_%STAMP%" > "%TEMP%\ct_shrink_pc.txt" 2>&1
set "RC=!errorlevel!"
type "%TEMP%\ct_shrink_pc.txt"
type "%TEMP%\ct_shrink_pc.txt" >> "%LOG%"
if not "!RC!"=="0" (
  echo This PC was not changed. The Pi is left alone too.
  goto end
)
if /i "%MODE%"=="pc" goto end

rem ------------------------------------------------------------------ the Pi --
:pi
echo.
echo === The live game on the Pi ===
echo === The Pi ===>> "%LOG%"
ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "test -e %PIDIR%/server.py && echo READY" > "%TEMP%\ct_pi_state.txt" 2>> "%LOG%"
set "PISTATE="
set /p PISTATE=<"%TEMP%\ct_pi_state.txt"
if not "%PISTATE%"=="READY" (
  echo The Pi could not be reached. Nothing there was changed.
  echo PI NOT REACHED>> "%LOG%"
  goto end
)
if exist "%WORK%" rmdir /s /q "%WORK%"
mkdir "%WORK%"

echo [1/5] Stopping the game on the Pi (it saves first)...
ssh -o BatchMode=yes %PI% "sudo -n systemctl stop seatrader && echo STOPPED" >> "%LOG%" 2>&1
findstr /c:"STOPPED" "%LOG%" >nul || (echo Could not stop the game on the Pi. Nothing there was changed. & goto end)

echo [2/5] Copying the Pi's pictures and records here (about 1 GB the first time)...
ssh -o BatchMode=yes %PI% "cd %PIDIR% && tar -cf - web/media web/uploads config saves captains journal" | tar -xf - -C "%WORK%" 2>> "%LOG%"
if not exist "%WORK%\config\media.json" (
  echo Copying from the Pi failed. Nothing there was changed.
  goto pistart
)

echo [3/5] Converting...
%PY% tools\shrink_images.py --root "%WORK%" --originals "%KEEP%\Pi_%STAMP%" --lists "%WORK%" > "%TEMP%\ct_shrink_pi.txt" 2>&1
set "RC=!errorlevel!"
type "%TEMP%\ct_shrink_pi.txt"
type "%TEMP%\ct_shrink_pi.txt" >> "%LOG%"
if not "!RC!"=="0" (
  echo Converting failed. Nothing on the Pi was changed.
  goto pistart
)
if not exist "%WORK%\shrink_push.txt" (
  echo Nothing to do on the Pi.
  goto pistart
)

echo [4/5] Sending the new pictures and records back...
tar -cf - -C "%WORK%" -T "%WORK%\shrink_push.txt" | ssh -o BatchMode=yes %PI% "tar -xf - -C %PIDIR% && echo PUSH_OK" >> "%LOG%" 2>&1
findstr /c:"PUSH_OK" "%LOG%" >nul || (
  echo Sending back FAILED. The Pi keeps its old pictures and records. See pi\shrink_report.txt
  goto pistart
)
rem Only now are the old files removed on the Pi (copies are kept in %KEEP%\Pi_%STAMP%).
ssh -o BatchMode=yes %PI% "cd %PIDIR% && xargs -d '\n' rm -f -- && echo RM_OK" < "%WORK%\shrink_remove.txt" >> "%LOG%" 2>&1
rem So new generated pictures are saved as WebP on the Pi too (needs the latest media.py: Deploy_To_Pi.bat).
ssh -o BatchMode=yes %PI% "python3 -c 'import PIL' 2>/dev/null || sudo -n apt-get install -y python3-pil >/dev/null 2>&1; python3 -c 'import PIL' && echo PILLOW_OK || echo PILLOW_MISSING" >> "%LOG%" 2>&1
rmdir /s /q "%WORK%"

:pistart
echo [5/5] Starting the game on the Pi...
ssh -o BatchMode=yes %PI% "sudo -n systemctl start seatrader" >> "%LOG%" 2>&1
set /a TRIES=0
:waitpi
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://192.168.1.69:8765/api/info; exit 0 } catch { exit 1 }"
if not errorlevel 1 goto up
set /a TRIES+=1
if !TRIES! geq 30 goto down
goto waitpi
:up
echo SHRINK_DONE>> "%LOG%"
echo.
echo Live again on http://crimson.ledger/
goto end
:down
echo THE GAME DID NOT COME BACK.>> "%LOG%"
ssh -o BatchMode=yes %PI% "journalctl -u seatrader -n 40 --no-pager" >> "%LOG%" 2>&1
echo The game did not come back after starting. The reason is in pi\shrink_report.txt.

:end
echo Report: %LOG%
echo.
if /i not "%~2"=="quiet" pause
endlocal
