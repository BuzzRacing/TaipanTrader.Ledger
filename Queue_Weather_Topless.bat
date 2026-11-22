@echo off
rem Second weather batch for the Newspaper's weather glass: Tilly Marsh, 24 pictures in all.
rem For each weather (calm, fair, squalls, typhoon): 5 TOPLESS (filed NSFW, tag topless) + 1 clean (pose 5, new).
rem Filed under Personas > Tilly Marsh, role "weather", tagged "weather, weather-<kind>". Nothing made before is repeated.
rem Run on BIGBOX. Deploy first (Deploy_To_Pi.bat): the tool stops if the Pi has no weather glass yet.
rem   Queue_Weather_Topless.bat --dry               print the 24 prompts, queue nothing
rem   Queue_Weather_Topless.bat --kinds typhoon     one kind only (calm, fair, squalls, typhoon)
rem   Queue_Weather_Topless.bat --only topless      just the topless ones (or --only clean)
rem   Queue_Weather_Topless.bat --topless 3 --clean 0   fewer per kind
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_weather_topless.py %*
echo.
pause
