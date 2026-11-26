@echo off
rem Gives Taipan Trader on the Pi (http://taipantrader.ledger) its own look: jade and porcelain blue,
rem IM Fell English and Caslon lettering (tools\taipan_theme.py). Only the theme changes; the old settings
rem are kept on the Pi as config\settings.before-theme.json. Restarts the game, so a turn in progress is saved first.
setlocal
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
scp -q tools\taipan_theme.py %PI%:TaipanTrader/tools/ || (echo Could not reach the Pi. & pause & exit /b 1)
scp -q web\fonts\* %PI%:TaipanTrader/web/fonts/
ssh -o BatchMode=yes %PI% "cd ~/TaipanTrader && cp config/settings.json config/settings.before-theme.json && python3 tools/taipan_theme.py && sudo systemctl restart taipantrader && sleep 3 && systemctl is-active taipantrader"
echo.
echo Done. Refresh http://taipantrader.ledger to see the new look.
pause
endlocal
