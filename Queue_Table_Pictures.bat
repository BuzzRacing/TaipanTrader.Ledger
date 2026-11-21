@echo off
rem Queues the Table pictures on the live game (the Pi): 8 ship classes painted top-down (3 each, Ships, role "topdown")
rem and 4 luxurious period fabrics for the player mat (Scenes > "Table: the period fabric under the player mat").
rem Run on BIGBOX; Admin there needs no password. Deploy the Table update to the Pi first (Deploy_To_Pi.bat), or the Pi will not know the new slots.
rem Optional: Queue_Table_Pictures.bat http://192.168.1.69:8765 ships     (or fabric)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_table_pictures.py %*
echo.
pause
