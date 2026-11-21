@echo off
rem Queues 12 shipyard pictures of Tang Wai-lin (Master Shipwright & Queen of the Keel) on the live game
rem (the Pi): 10 NSFW (2 portrait, 3 speaking, 2 happy, 1 angry, 2 sly) and 2 clean (portrait, speaking),
rem filed under Personas > Tang Wai-lin, tagged "shipyard tang-shipyard". Run on BIGBOX.
rem Add --dry to print the prompts without queuing anything.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_tang_shipyard_pictures.py %*
echo.
pause
