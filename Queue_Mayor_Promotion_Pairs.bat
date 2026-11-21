@echo off
rem Queue_Mayor_Promotion_Pairs.bat - fresh Promotion Story pictures for all ten lady mayors, on the live game (the Pi).
rem Per mayor: FOUR NSFW pictures that lead the viewer along one soap-opera scene, a little more undressed at every
rem step (the gasp, the confession, the swoon, the surrender - the last one fully nude, glamour-style, never explicit),
rem plus ONE clean twin (fully dressed, hand on heart) for family-friendly screens.
rem 10 mayors x (4 nsfw + 1 clean) = 50 pictures, filed in Media Library > Ports > (port) as role "mayor_congrats".
rem Run it on BIGBOX with the Pi switched on. Extra options go straight through, e.g. --dry (print, queue nothing),
rem --only clean, --only nsfw, --port manila, --server http://192.168.1.69:8765
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_mayor_promotion_pairs.py %*
echo.
pause
