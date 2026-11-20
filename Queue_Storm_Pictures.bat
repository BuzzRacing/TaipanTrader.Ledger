@echo off
rem Queues the storm pictures on the live game (the Pi): 6 battered Roxana pictures (Personas > Roxana, role "storm")
rem and 8 broken ships (Ships, role "wrecked"). 14 pictures. Run on BIGBOX; Admin there needs no password.
rem Deploy the storm update to the Pi first (Deploy_To_Pi.bat), or the Pi won't know the roles yet.
rem Optional: Queue_Storm_Pictures.bat http://192.168.1.69:8765 ships     (or roxana)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_storm_pictures.py %*
echo.
pause
