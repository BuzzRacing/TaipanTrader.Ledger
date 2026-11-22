@echo off
rem Queues pictures of the Table's Game Master, Madame Anahit Sarkissian (persona_prompts_v2.py, key "gamemaster"):
rem wide 16:9 wallpaper master shots at four looks (sultry, topless, nude, clean), 2 each = 8 pictures on the live game (the Pi),
rem filed under Personas > her name, role wallpaper, tagged "master-shot, wallpaper, <look>". Clean is not NSFW. Run on BIGBOX.
rem Deploy_To_Pi.bat FIRST, so the Pi knows her. Extra options go straight through, e.g.  --dry   or   --count 1   or   --tiers clean   or   --mood wink
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_master_shots.py --who gamemaster --tiers sultry,topless,nude,clean --count 2 %*
echo.
pause
