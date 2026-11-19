@echo off
rem Queues the sea battle right-hand seat pictures on the live game (the Pi): 22 mood pictures,
rem 11 for Admiral Li Yue and 11 for Madam Shek Yu-lan. Run on BIGBOX; Admin there needs no password.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_battle_seat_pictures.py %*
echo.
pause
