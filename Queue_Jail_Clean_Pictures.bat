@echo off
rem Queues a clean (not NSFW) photo of each port's warden on the live game (the Pi): 10 pictures, their
rem original dressed prompts, tagged "jail warden, clean". Family-friendly screens show these. Run on BIGBOX.
rem Deploy the jail update to the Pi first (Deploy_To_Pi.bat), or the Pi won't know the wardens yet.
rem Optional: Queue_Jail_Clean_Pictures.bat [server]
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_jail_clean_pictures.py %*
echo.
pause
