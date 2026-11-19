@echo off
rem Queues 10 town crier pictures of Roxana Cama on the live game (the Pi), each a different
rem town crier moment, filed to her persona by mood. Run on BIGBOX; Admin there needs no password.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_roxana_crier_pictures.py %*
echo.
pause
