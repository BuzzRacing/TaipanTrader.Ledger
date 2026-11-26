@echo off
rem Sends this PC's Taipan Trader code to the Pi (http://taipantrader.ledger) and restarts the game there.
rem Copies the code, pages, fonts and tools. Never copies the Pi's own settings, picture library, saves, captains,
rem voice key or admin password: those stay as they are on the Pi. Then lays Taipan's look over the Pi's settings
rem (tools\taipan_theme.py: colours, fonts, hidden NSFW switch; the old settings are kept as
rem config\settings.before-theme.json). Restarting saves the game in progress first.
setlocal
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
echo Sending Taipan Trader to the Pi...
tar --exclude=.git --exclude=.browser --exclude=__pycache__ --exclude=.pytest_cache --exclude=saves --exclude=cache --exclude=captains --exclude=journal --exclude=web/media --exclude=web/uploads --exclude=config --exclude=server_address.txt -czf - . | ssh -o BatchMode=yes %PI% "mkdir -p ~/TaipanTrader && tar -xzf - -C ~/TaipanTrader"
if errorlevel 1 (echo Could not reach the Pi. & pause & exit /b 1)
ssh -o BatchMode=yes %PI% "cd ~/TaipanTrader && cp config/settings.json config/settings.before-theme.json && python3 tools/taipan_theme.py && sudo systemctl restart taipantrader && sleep 3 && systemctl is-active taipantrader"
echo.
echo Done. Refresh http://taipantrader.ledger to see the changes.
pause
endlocal
