@echo off
rem Queues 4 more sea-battle pictures of Admiral Li Yue (the enemy voice for the war junks) on the live game
rem (the Pi): 3 NSFW (speaking, happy, angry) and 1 clean (sly), filed under Personas > Li Yue, tagged
rem "battle-scene li-yue-battle-3". New scenes, nothing repeated from her first ten. Run on BIGBOX.
rem Add --dry to print the prompts without queuing anything.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_li_yue_battle_third_set.py %*
echo.
pause
