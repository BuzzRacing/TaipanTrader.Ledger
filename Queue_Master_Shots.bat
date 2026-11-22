@echo off
rem Queues wide 16:9 WALLPAPER master shots (persona_prompts_v2.py): each woman alone in a dramatic scene of her own world.
rem Default: Bookkeeper, Batavia officer, Powder and Mrs. Marlowe x topless, nude and clean = 12 pictures on the live game (the Pi),
rem filed under Personas > (her name), role wallpaper, tagged "master-shot, wallpaper, <look>". Run on BIGBOX.
rem Extra options go straight through, e.g.  --dry   or   --who all --tiers nude   or   --count 2   or   --mood dare
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_master_shots.py %*
echo.
pause
