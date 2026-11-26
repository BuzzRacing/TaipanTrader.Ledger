@echo off
rem Taipan Trader launcher. Opens the game in a full-screen window.
rem   Launch_TaipanTrader.bat          player screen
rem   Launch_TaipanTrader.bat board    harbor board (for a second monitor or TV)
rem   Launch_TaipanTrader.bat table    harbor view: the game from above, on a table (TV)
rem   Launch_TaipanTrader.bat dashboard  the pit box: timing tower, ledger book, dials, tape (TV)
rem   Launch_TaipanTrader.bat admin    admin command center (an ordinary browser window)
rem
rem By default the game server runs on this computer and is started if needed.
rem To use a server on another machine (for example a Raspberry Pi), put its
rem address on one line in server_address.txt next to this file, e.g.
rem   taipantrader.ledger   (the Pi, through its proxy)
rem   192.168.1.50:8775
rem Launch_Dev.bat always opens the copy on this computer instead.
setlocal
cd /d "%~dp0"
set "PORT=8775"
set "HOST=localhost:%PORT%"
set "REMOTE="
rem The Pi's address. A name without a port (taipantrader.ledger) is sent straight there,
rem so the launcher works even if this PC's own name lookup goes wrong.
set "PI_IP=192.168.1.69"
rem ST_DEV is set by Launch_Dev.bat: always use the copy on this computer.
if not defined ST_DEV if exist "server_address.txt" set /p HOST=<"server_address.txt"
set "HOST=%HOST: =%"
set "HOST=%HOST:http://=%"
if "%HOST:~-1%"=="/" set "HOST=%HOST:~0,-1%"
rem A bare IP or localhost gets the game port added; a name like taipantrader.ledger is used as it is
rem (the Pi's proxy answers it on the normal web port).
echo %HOST%| find ":" >nul
if errorlevel 1 (echo %HOST%| findstr /r /i "^[0-9] ^localhost$" >nul && set "HOST=%HOST%:%PORT%")
if /i not "%HOST:~0,9%"=="localhost" if not "%HOST:~0,4%"=="127." set "REMOTE=1"

set "PAGE="
set "PROFILE=player"
if /i "%~1"=="board" set "PAGE=board"
if /i "%~1"=="board" set "PROFILE=board"
if /i "%~1"=="table" set "PAGE=table.html"
if /i "%~1"=="table" set "PROFILE=table"
if /i "%~1"=="dashboard" set "PAGE=dashboard.html"
if /i "%~1"=="dashboard" set "PROFILE=dashboard"
if /i "%~1"=="admin" set "PAGE=admin"
if defined ST_DEV set "PROFILE=dev-%PROFILE%"
set "PIN_DNS="
set "PIN_CURL="
echo %HOST%| find ":" >nul
if errorlevel 1 set "PIN_DNS=--host-resolver-rules="MAP %HOST% %PI_IP%""
if errorlevel 1 set "PIN_CURL=--resolve %HOST%:80:%PI_IP%"
set "URL=http://%HOST%/%PAGE%"

call :ping
if not errorlevel 1 goto open
if defined REMOTE goto unreachable

set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
%PY% --version >nul 2>nul
if errorlevel 1 goto nopython

echo Starting the Taipan Trader server...
start "Taipan Trader Server" /min %PY% server.py --port %PORT%
set /a TRIES=0
:wait
call :ping
if not errorlevel 1 goto open
set /a TRIES+=1
if %TRIES% geq 30 goto failed
timeout /t 1 /nobreak >nul
goto wait

:open
if /i "%PAGE%"=="admin" if not defined PIN_DNS start "" "%URL%"
if /i "%PAGE%"=="admin" if not defined PIN_DNS goto end
rem Admin on the Pi opens in its own ordinary Edge window, also pinned to the Pi.
if /i "%PAGE%"=="admin" set "PROFILE=admin"
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist "%EDGE%" goto edge
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" goto chrome
start "" "%URL%"
goto end

:edge
if /i "%PAGE%"=="admin" (start "" "%EDGE%" %PIN_DNS% --no-first-run --user-data-dir="%~dp0.browser\admin" "%URL%" & goto end)
start "" "%EDGE%" %PIN_DNS% --kiosk "%URL%" --edge-kiosk-type=fullscreen --no-first-run --autoplay-policy=no-user-gesture-required --user-data-dir="%~dp0.browser\%PROFILE%"
goto end

:chrome
if /i "%PAGE%"=="admin" (start "" "%CHROME%" %PIN_DNS% --no-first-run --user-data-dir="%~dp0.browser\admin" "%URL%" & goto end)
start "" "%CHROME%" %PIN_DNS% --kiosk "%URL%" --no-first-run --autoplay-policy=no-user-gesture-required --user-data-dir="%~dp0.browser\%PROFILE%"
goto end

:unreachable
echo.
echo Could not reach the Taipan Trader server at %HOST%
echo Check that it is switched on and that server_address.txt has the right address.
echo To run the game on this computer instead, delete server_address.txt.
echo.
pause
exit /b 1

:nopython
echo.
echo Python 3 was not found on this computer.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
echo.
pause
exit /b 1

:failed
echo.
echo The server did not start. Run this to see why:
echo     %PY% server.py
echo.
pause
exit /b 1

:ping
rem curl first (pinned to the Pi for a friendly name); PowerShell only if curl is missing.
where curl.exe >nul 2>nul
if errorlevel 1 goto pingps
curl.exe -s -f -o nul --noproxy "*" %PIN_CURL% --max-time 3 http://%HOST%/api/info
exit /b %errorlevel%
:pingps
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://%HOST%/api/info; exit 0 } catch { exit 1 }"
exit /b %errorlevel%

:end
endlocal
exit /b 0
