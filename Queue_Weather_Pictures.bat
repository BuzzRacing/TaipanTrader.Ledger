@echo off
rem Queues the weather-girl pictures for the Newspaper's weather glass on the live game (the Pi):
rem Tilly Marsh (the Gazette Crier) on the quay in a calm, fair weather, squalls and a typhoon.
rem For each kind of weather: 4 NSFW (nude) + 2 clean = 24 pictures in all, filed under
rem Personas > Tilly Marsh, role "weather", tagged "weather, weather-<kind>" (", clean" on the clean ones).
rem Run on BIGBOX. DEPLOY FIRST (Deploy_To_Pi.bat): the tool stops if the Pi has no weather glass yet.
rem   Queue_Weather_Pictures.bat --dry              print the prompts, queue nothing
rem   Queue_Weather_Pictures.bat --kinds typhoon    one kind only (calm, fair, squalls, typhoon)
rem   Queue_Weather_Pictures.bat --nsfw 2 --clean 1 fewer poses per kind (0 to 4 each)
rem   Queue_Weather_Pictures.bat --only clean       just the clean ones (or --only nsfw)
rem   Queue_Weather_Pictures.bat --only clean --from 3   add clean poses 3 and 4 (the first run made 1 and 2)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_weather_pictures.py %*
echo.
pause
