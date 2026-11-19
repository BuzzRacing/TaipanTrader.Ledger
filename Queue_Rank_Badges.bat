@echo off
rem Queues new Crimson Ledger rank badges on the live game (the Pi): 3 per rank, 30 in all.
rem Then star your favourite for each rank in Admin > Media Library > Rank Badges.
rem Run on BIGBOX; Admin there needs no password.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_rank_badges.py %*
echo.
pause
