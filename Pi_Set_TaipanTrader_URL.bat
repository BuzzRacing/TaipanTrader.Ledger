@echo off
rem Puts Taipan Trader on the mad-pihole Pi (192.168.1.69) at http://taipantrader.ledger, like crimson.ledger
rem and atomic.ledger: copies the game to ~/TaipanTrader, runs it as the taipantrader service on port 8775,
rem adds the Pi-hole local DNS name and the Caddy rule. Crimson Ledger and Atomic Ledger are not touched.
rem A Pi-hole backup is taken before and after. Report: pi\taipan_url_report.txt
setlocal
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "NAME=taipantrader.ledger"
set "LOG=%~dp0pi\taipan_url_report.txt"
echo Taipan Trader on the Pi  %DATE% %TIME%> "%LOG%"
echo Copying the game to the Pi...
tar --exclude=.git --exclude=.browser --exclude=__pycache__ --exclude=saves --exclude=cache --exclude=.pytest_cache --exclude=captains --exclude=journal -czf - . | ssh -o BatchMode=yes %PI% "mkdir -p ~/TaipanTrader && tar -xzf - -C ~/TaipanTrader" >> "%LOG%" 2>&1
if errorlevel 1 (echo Could not copy the game to the Pi. See %LOG% & pause & exit /b 1)
echo Setting up the service, the DNS name and the Caddy rule...
ssh -o BatchMode=yes %PI% "bash -s -- %NAME%" < "%~dp0pi\set_name.sh" >> "%LOG%" 2>&1
findstr /c:"NAME_SCRIPT_DONE" "%LOG%" >nul
if errorlevel 1 (echo Something went wrong. See %LOG% & pause & exit /b 1)
> "%~dp0server_address.txt" echo %NAME%
echo.
echo Done. Taipan Trader is at http://%NAME%  (the launchers on this PC now open it there).
echo To use the copy on this PC instead, delete server_address.txt.
pause
endlocal
