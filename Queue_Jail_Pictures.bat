@echo off
rem Queues the jail pictures on the live game (the Pi): one photo of each port's warden (Personas)
rem and one jail cell for each port (Ports, role "jail_cell"). 20 pictures. Run on BIGBOX; Admin there needs no password.
rem Deploy the jail update to the Pi first (Deploy_To_Pi.bat), or the Pi won't know the wardens yet.
rem Optional: Queue_Jail_Pictures.bat [server] [only]   e.g.  Queue_Jail_Pictures.bat http://192.168.1.69:8765 cells
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_jail_pictures.py %*
echo.
pause
