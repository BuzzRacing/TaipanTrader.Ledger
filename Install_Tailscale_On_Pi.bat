@echo off
rem Puts Tailscale on the Pi (mad-pihole, 192.168.1.69) so Crimson Ledger can be reached from outside the
rem house by the devices you approve. No router changes, no open ports, nothing exposed to the public internet.
rem
rem   Install_Tailscale_On_Pi.bat           install Tailscale if needed, sign the Pi in, then check the game
rem   Install_Tailscale_On_Pi.bat status    just look: change nothing
rem
rem What it does to the Pi: installs Tailscale from tailscale.com's official script, then runs
rem "tailscale up --hostname=mad-pihole --accept-dns=false". accept-dns=false matters: it leaves Pi-hole
rem as the Pi's own DNS and the house's DNS exactly as it is. The game, Caddy, Home Assistant and Pi-hole
rem are not touched or restarted.
rem
rem Signing in: the first run prints a login address in this window. Open it on any device and sign in with
rem your Tailscale account (the same one your other machines use). Safe to run again.
rem Report: pi\tailscale_report.txt
setlocal
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "PIDIR=/home/madlively/SeaTrader"
set "LOG=%~dp0pi\tailscale_report.txt"
set "MODE=%~1"
if not exist "%~dp0pi" mkdir "%~dp0pi"
echo Crimson Ledger - Tailscale on the Pi  %DATE% %TIME%  (%MODE%)> "%LOG%"

echo [1/5] Reaching the Pi...
ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "echo READY" > "%TEMP%\ct_ts_state.txt" 2>> "%LOG%"
set "PISTATE="
set /p PISTATE=<"%TEMP%\ct_ts_state.txt"
if not "%PISTATE%"=="READY" (
  echo The Pi could not be reached. Nothing was changed.
  echo PI NOT REACHED>> "%LOG%"
  goto end
)

if /i "%MODE%"=="status" goto facts

echo [2/5] Checking for Tailscale on the Pi...
set "HAVE="
ssh -o BatchMode=yes %PI% "command -v tailscale >/dev/null && echo HAVE || echo MISSING" > "%TEMP%\ct_ts_have.txt" 2>> "%LOG%"
set /p HAVE=<"%TEMP%\ct_ts_have.txt"
if "%HAVE%"=="HAVE" (
  echo Tailscale is already installed.
  echo already installed>> "%LOG%"
  goto signin
)
echo Installing Tailscale. This takes a minute or two...
ssh -o BatchMode=yes %PI% "command -v curl >/dev/null || sudo -n apt-get install -y curl; curl -fsSL https://tailscale.com/install.sh | sudo -n sh" >> "%LOG%" 2>&1
set "HAVE="
ssh -o BatchMode=yes %PI% "command -v tailscale >/dev/null && echo HAVE || echo MISSING" > "%TEMP%\ct_ts_have.txt" 2>> "%LOG%"
set /p HAVE=<"%TEMP%\ct_ts_have.txt"
if not "%HAVE%"=="HAVE" (
  echo The install did not finish. Nothing else was changed. See pi\tailscale_report.txt
  echo INSTALL FAILED>> "%LOG%"
  goto end
)
echo installed>> "%LOG%"

:signin
echo [3/5] Signing the Pi in...
set "TSIP="
ssh -o BatchMode=yes %PI% "sudo -n tailscale ip -4 2>/dev/null | head -n 1" > "%TEMP%\ct_ts_ip.txt" 2>> "%LOG%"
set /p TSIP=<"%TEMP%\ct_ts_ip.txt"
if defined TSIP (
  echo Already signed in.
  echo already signed in>> "%LOG%"
  goto facts
)
echo.
echo A login address is about to appear below. Open it on any device, sign in to Tailscale, and approve
echo the Pi. This window carries on by itself once you have.
echo.
ssh -t %PI% "sudo tailscale up --hostname=mad-pihole --accept-dns=false"
echo.

:facts
echo [4/5] Reading the Pi's Tailscale address...
set "TSIP="
ssh -o BatchMode=yes %PI% "sudo -n tailscale ip -4 2>/dev/null | head -n 1" > "%TEMP%\ct_ts_ip.txt" 2>> "%LOG%"
set /p TSIP=<"%TEMP%\ct_ts_ip.txt"
if not defined TSIP (
  echo The Pi is not signed in to Tailscale yet. Run this again and finish the sign-in.
  echo NOT SIGNED IN>> "%LOG%"
  goto end
)
echo Tailscale address: %TSIP%>> "%LOG%"
ssh -o BatchMode=yes %PI% "sudo -n tailscale status 2>&1 | head -n 12" >> "%LOG%" 2>&1

echo [5/5] Checking the game...
set "LOCAL="
ssh -o BatchMode=yes %PI% "curl -s -m 5 -o /dev/null -w '%%{http_code}' http://127.0.0.1:8765/api/info" > "%TEMP%\ct_ts_local.txt" 2>> "%LOG%"
set /p LOCAL=<"%TEMP%\ct_ts_local.txt"
set "OVERTS="
ssh -o BatchMode=yes %PI% "curl -s -m 5 -o /dev/null -w '%%{http_code}' http://%TSIP%:8765/api/info" > "%TEMP%\ct_ts_over.txt" 2>> "%LOG%"
set /p OVERTS=<"%TEMP%\ct_ts_over.txt"
set "PW="
ssh -o BatchMode=yes %PI% "cd %PIDIR% && python3 -c 'import config; print(config.has_password())'" > "%TEMP%\ct_ts_pw.txt" 2>> "%LOG%"
set /p PW=<"%TEMP%\ct_ts_pw.txt"
echo Game on the Pi itself: %LOCAL%>> "%LOG%"
echo Game over the Tailscale address: %OVERTS%>> "%LOG%"
echo Admin password set: %PW%>> "%LOG%"

echo.
echo The Pi's Tailscale address is %TSIP%
if "%LOCAL%"=="200" (echo Game on the Pi: running.) else (echo Game on the Pi: NOT answering, it said "%LOCAL%".)
if "%OVERTS%"=="200" (echo Game over Tailscale: answering.) else (echo Game over Tailscale: NOT answering, it said "%OVERTS%".)
if /i "%PW%"=="True" (echo Admin password: set.) else (echo Admin password: NOT set. Run Pi_Admin_Password.bat before anyone else connects.)
echo.
echo Away from home, on a device signed in to your Tailscale account, play at:
echo     http://%TSIP%:8765
echo crimson.ledger only works inside the house, so away from home use the address above.
echo.
echo Before you share it with anyone else, read the notes Claude gave you: the Pi also runs Home Assistant,
echo Caddy, Pi-hole and SSH, and sharing the Pi shares every port unless you limit it to 8765 in Tailscale.
echo Tell Claude "tailscale done" when this has finished.

:end
echo.
echo Report: %LOG%
echo.
pause
endlocal
