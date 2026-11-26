@echo off
rem Queues 60 NEW sea-battle pictures on the live game (the Pi): Madam Shek Yu-lan and Admiral Li Yue each get
rem 10 new battle scenes, and every scene is made 3 times: 1 clean + 2 NSFW (sultry, nothing explicit).
rem Filed under Personas > Madam Shek / Admiral Li Yue, tagged "battle-scene shek-battle-4" / "li-yue-battle-4".
rem Run on BIGBOX. Extra options pass through:
rem   --dry                 print the prompts without queuing anything
rem   --only shek           (or --only liyue) just one of the two women
rem   --only-kind clean     (or --only-kind nsfw) just the clean or just the NSFW pictures
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_shek_liyue_battle_set4.py %*
echo.
pause
