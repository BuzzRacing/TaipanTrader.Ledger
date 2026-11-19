@echo off
rem Queues the late-game pictures (19 Nov 2026) on the live game (the Pi): the great house (empty plot,
rem Townhouse, Mansion, Palace), Port Shares, the Mayor's commissions, the Flagship and her sea-battle set.
rem 39 pictures, filed into the Media Library as they finish. Run on BIGBOX; Admin there needs no password.
rem Optional: Queue_Late_Game_Pictures.bat http://127.0.0.1:8765 flagship   (dev server, one group only)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_late_game_pictures.py %*
echo.
pause
