@echo off
rem Queues family-friendly cargo pictures on the live game (the Pi): Fireworks (for Opium) and Ironware
rem (for Arms), 3 each, on plain muslin like the product-shot set. Filed to Media Library > Cargo with the
rem "family" role: shown only while family-friendly is on. Run on BIGBOX after Deploy_To_Pi.bat.
rem Optional: Queue_Family_Cargo_Pictures.bat [server] [count] [only]
rem   e.g.  Queue_Family_Cargo_Pictures.bat http://192.168.1.69:8765 5 opium
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_family_cargo_pictures.py %*
echo.
pause
