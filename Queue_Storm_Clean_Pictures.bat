@echo off
rem Queues 6 clean (family-friendly) battered Roxana pictures on the live game (the Pi): Personas > Roxana, role "storm",
rem tagged "storm, clean". Run on BIGBOX; Admin there needs no password.
rem Deploy the storm update to the Pi first (Deploy_To_Pi.bat), or the Pi won't know the role yet.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_storm_clean_pictures.py %*
echo.
pause
