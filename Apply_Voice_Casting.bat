@echo off
rem Applies the Easy-pass voice casting (see the Project doc "SeaTrader Voice Casting Easy Pass") to the
rem LIVE game on the Pi. Only each persona's voice_id changes; nothing else in settings.json is touched.
rem Casting lives on the Pi, so this does not touch D:\SeaTrader's own copy.
rem
rem   Apply_Voice_Casting.bat          apply it (the Pi's game is stopped for a few seconds and restarted)
rem   Apply_Voice_Casting.bat check    just show what would change, touch nothing
rem
rem Safe to run again: it only changes personas whose voice is not already the planned one.
rem The Pi's old settings.json is kept in D:\SeaTrader_PiBackup\voice_casting_<date>\.
rem Each persona's first line in a new voice is one paid Inworld request, then cached. Report: pi\voice_casting_report.txt
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "PIDIR=/home/madlively/SeaTrader"
set "ROOT=D:\SeaTrader_PiBackup"
set "LOG=%~dp0pi\voice_casting_report.txt"
set "MODE=%~1"
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "STAMP=%%d"
set "WORK=%ROOT%\voice_casting_%STAMP%"
if not exist "%~dp0pi" mkdir "%~dp0pi"
echo Crimson Ledger - voice casting  %DATE% %TIME%  (%MODE%)> "%LOG%"

set "PY=python"
where python >nul 2>nul || set "PY=py"

ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "test -e %PIDIR%/server.py && echo READY" > "%TEMP%\ct_vc_state.txt" 2>> "%LOG%"
set "PISTATE="
set /p PISTATE=<"%TEMP%\ct_vc_state.txt"
if not "%PISTATE%"=="READY" (
  echo The Pi could not be reached. Nothing was changed.
  echo PI NOT REACHED>> "%LOG%"
  goto end
)
if not exist "%WORK%" mkdir "%WORK%"

if /i "%MODE%"=="check" goto pull

echo [1/5] Stopping the game on the Pi (it saves first)...
ssh -o BatchMode=yes %PI% "sudo -n systemctl stop seatrader && echo STOPPED" >> "%LOG%" 2>&1
findstr /c:"STOPPED" "%LOG%" >nul || (echo Could not stop the game on the Pi. Nothing was changed. & goto end)

:pull
echo [2/5] Copying the Pi's settings and voice list here...
ssh -o BatchMode=yes %PI% "cat %PIDIR%/config/settings.json" > "%WORK%\settings.json" 2>> "%LOG%"
ssh -o BatchMode=yes %PI% "cat %PIDIR%/config/voice_library.json" > "%WORK%\voice_library.json" 2>> "%LOG%"
if not exist "%WORK%\settings.json" (
  echo Copying from the Pi failed. Nothing was changed.
  goto pistart
)
for %%f in ("%WORK%\settings.json") do if %%~zf lss 1000 (
  echo The copy of settings.json looks empty. Nothing was changed.
  goto pistart
)
for %%f in ("%WORK%\voice_library.json") do if %%~zf lss 1000 (
  echo The Pi has no voice list yet. Press Fetch the voice list on the Voice Library page first. Nothing was changed.
  goto pistart
)

echo [3/5] Working out the changes...
if /i "%MODE%"=="check" (
  %PY% tools\apply_voice_casting.py --settings "%WORK%\settings.json" --library "%WORK%\voice_library.json" --dry-run
  goto end
)
%PY% tools\apply_voice_casting.py --settings "%WORK%\settings.json" --library "%WORK%\voice_library.json" --out "%WORK%\settings_new.json" > "%TEMP%\ct_vc_out.txt" 2>&1
set "RC=!errorlevel!"
type "%TEMP%\ct_vc_out.txt"
type "%TEMP%\ct_vc_out.txt" >> "%LOG%"
if not "!RC!"=="0" (
  echo The casting was NOT applied. The Pi keeps its settings.
  goto pistart
)
if not exist "%WORK%\settings_new.json" (
  echo No changes to send.
  goto pistart
)

echo [4/5] Sending the new settings back...
ssh -o BatchMode=yes %PI% "cat > %PIDIR%/config/settings.json.new" < "%WORK%\settings_new.json" >> "%LOG%" 2>&1
ssh -o BatchMode=yes %PI% "cd %PIDIR%/config && python3 -c 'import json;json.load(open(\"settings.json.new\"))' && mv settings.json.new settings.json && echo PUSH_OK" >> "%LOG%" 2>&1
findstr /c:"PUSH_OK" "%LOG%" >nul || (
  echo Sending back FAILED. The Pi keeps its old settings. See pi\voice_casting_report.txt
  goto pistart
)
echo CASTING_APPLIED>> "%LOG%"

:pistart
if /i "%MODE%"=="check" goto end
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
echo.
findstr /c:"CASTING_APPLIED" "%LOG%" >nul && echo Casting applied. Live again on http://crimson.ledger/admin  (Voice Library) || echo Nothing was changed. The game is running again.
goto end
:down
echo THE GAME DID NOT COME BACK.>> "%LOG%"
ssh -o BatchMode=yes %PI% "journalctl -u seatrader -n 40 --no-pager" >> "%LOG%" 2>&1
echo The game did not come back after starting. The reason is in pi\voice_casting_report.txt.

:end
echo Report: %LOG%
echo.
if /i not "%~2"=="quiet" pause
endlocal
