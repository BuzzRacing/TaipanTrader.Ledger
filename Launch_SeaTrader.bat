@echo off
rem SeaTrader launcher. Opens the game in a full-screen window.
rem   Launch_SeaTrader.bat          player screen
rem   Launch_SeaTrader.bat board    harbor board (for a second monitor or TV)
rem
rem By default the game server runs on this computer and is started if needed.
rem To use a server on another machine (for example a Raspberry Pi), put its
rem address on one line in server_address.txt next to this file, e.g.
rem   192.168.1.50:8765
setlocal
cd /d "%~dp0"
set "PORT=8765"
set "HOST=localhost:%PORT%"
set "REMOTE="
if exist "server_address.txt" set /p HOST=<"server_address.txt"
set "HOST=%HOST: =%"
set "HOST=%HOST:http://=%"
if "%HOST:~-1%"=="/" set "HOST=%HOST:~0,-1%"
echo %HOST%| find ":" >nul
if errorlevel 1 set "HOST=%HOST%:%PORT%"
if /i not "%HOST:~0,9%"=="localhost" if not "%HOST:~0,4%"=="127." set "REMOTE=1"

set "PAGE="
set "PROFILE=player"
if /i "%~1"=="board" set "PAGE=board"
if /i "%~1"=="board" set "PROFILE=board"
set "URL=http://%HOST%/%PAGE%"

call :ping
if not errorlevel 1 goto open
if defined REMOTE goto unreachable

set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
%PY% --version >nul 2>nul
if errorlevel 1 goto nopython

echo Starting the SeaTrader server...
start "SeaTrader Server" /min %PY% server.py --port %PORT%
set /a TRIES=0
:wait
call :ping
if not errorlevel 1 goto open
set /a TRIES+=1
if %TRIES% geq 30 goto failed
timeout /t 1 /nobreak >nul
goto wait

:open
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist "%EDGE%" goto edge
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" goto chrome
start "" "%URL%"
goto end

:edge
start "" "%EDGE%" --kiosk "%URL%" --edge-kiosk-type=fullscreen --no-first-run --user-data-dir="%~dp0.browser\%PROFILE%"
goto end

:chrome
start "" "%CHROME%" --kiosk "%URL%" --no-first-run --user-data-dir="%~dp0.browser\%PROFILE%"
goto end

:unreachable
echo.
echo Could not reach the SeaTrader server at %HOST%
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
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://%HOST%/api/info; exit 0 } catch { exit 1 }"
exit /b %errorlevel%

:end
endlocal
exit /b 0
