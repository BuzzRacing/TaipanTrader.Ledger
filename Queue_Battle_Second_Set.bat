@echo off
rem Queues a second picture for every sea-battle moment that has only one, for pirate junks, war junks
rem and the flagship (about 25 pictures), on the live game (the Pi). Each copies that moment's own prompt with
rem a fresh camera angle, so the look stays the same. Run on BIGBOX. Add --dry to print the prompts only.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_battle_second_set.py %*
echo.
pause
