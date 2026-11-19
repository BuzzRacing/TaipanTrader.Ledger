@echo off
rem Queues 10 battle-scene pictures of Peggy "Powder" O'Rourke on the live game (the Pi), each a different
rem sea-battle moment, filed to her persona by mood. Run on BIGBOX; Admin there needs no password.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_powder_battle_pictures.py %*
echo.
pause
