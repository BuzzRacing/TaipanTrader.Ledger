@echo off
rem Adds clean poses 3 and 4 of Tilly for every weather (calm, fair, squalls, typhoon) = 8 pictures.
rem The first Queue_Weather_Pictures.bat run made clean poses 1 and 2, so nothing is made twice.
rem Run on BIGBOX. Deploy first (Deploy_To_Pi.bat): the tool stops if the Pi has no weather glass yet.
rem   Queue_Weather_More_Clean.bat --dry    print the 8 prompts, queue nothing
cd /d "%~dp0"
set "PY=python"
where python >/dev/null 2>/dev/null || set "PY=py"
%PY% tools\queue_weather_pictures.py --only clean --from 3 %*
echo.
pause
