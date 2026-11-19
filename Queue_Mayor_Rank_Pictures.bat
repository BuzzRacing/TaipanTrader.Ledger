@echo off
rem Queues every port's lady mayor congratulating a captain on the three ranks above Taipan:
rem Tai-Pan of the China Seas, Merchant Lord and Hong Master. 30 pictures (10 ports x 3), each filed
rem under that rank's own Mayor role in Media Library > Ports. Run on BIGBOX; Admin there needs no password.
rem Deploy_To_Pi.bat first, so the Pi knows the three new ranks' Mayor roles.
rem Optional: Queue_Mayor_Rank_Pictures.bat http://192.168.1.69:8765 hong_master   (one rank only)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_mayor_rank_pictures.py %*
echo.
pause
