@echo off
rem Queues RECLINING wide pictures for the Dashboard masthead (a woman lying back across the banner, tagged "masthead, reclining").
rem Default: Madame Anahit (gamemaster) and Celeste (bookkeeper) x clean and topless x2 = 8 pictures on the live game (the Pi). Run on BIGBOX.
rem Run Deploy_To_Pi.bat first so the Pi has current persona prompts. Extra options go straight through, e.g.  --dry  or  --who gamemaster --tiers clean
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_masthead_shots.py %*
echo.
echo Watch them arrive in Admin ^> Media Library (jobs). The Dashboard picks them up on its next reload.
pause
