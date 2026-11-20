@echo off
rem Queues a clean product-shot set of every cargo (opium, gold, silk, porcelain, arms, spices, tea, rice,
rem general cargo), each item alone on a plain muslin backdrop, 3 per cargo, on the live game (the Pi).
rem Filed to Media Library > Cargo with the "icon" role, tagged "muslin". Run on BIGBOX; Admin there needs no password.
rem Optional: Queue_Muslin_Cargo_Pictures.bat [server] [count] [only]
rem   e.g.  Queue_Muslin_Cargo_Pictures.bat http://192.168.1.69:8765 5 tea
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_muslin_cargo_pictures.py %*
echo.
pause
