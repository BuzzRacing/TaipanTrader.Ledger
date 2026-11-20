@echo off
rem Queues 11 sea-battle pictures of Madam Shek Yu-lan (the enemy voice for ordinary pirate junks) on the
rem live game (the Pi): 10 NSFW (3 speaking, 2 happy, 2 angry, 3 sly) and 1 clean, filed under
rem Personas > Madam Shek, tagged "battle-scene shek-battle". Run on BIGBOX.
rem Add --dry to print the prompts without queuing anything.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_shek_battle_pictures.py %*
echo.
pause
