@echo off
rem Queues an NSFW + clean PAIR of "hungry" pictures for every Port Authority officer (her tell for a big lie
rem at the desk): 10 officers x 2 = 20 pictures on the live game (the Pi). From each officer's own cast prompt,
rem filed under Personas > (her name), tagged "hungry" (NSFW) and "hungry, clean" (not NSFW). Run on BIGBOX.
rem Extra options go straight through, e.g.  Queue_TaxLady_Hungry_Pairs.bat --count 2   or   --dry   or   --only clean
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_persona_pairs.py --who officer_ --mood hungry %*
echo.
pause
