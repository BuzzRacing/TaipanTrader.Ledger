@echo off
rem Queues a new profile picture and a congratulations picture (arms open in gratitude) for every
rem port's lady mayor on the live game (the Pi): 20 pictures. Run on BIGBOX; Admin there needs no password.
rem Deploy_To_Pi.bat first, so the Pi knows the "Mayor congratulations" role.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_mayor_pictures.py %*
echo.
pause
