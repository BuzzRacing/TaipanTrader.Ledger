@echo off
rem Queue_Port_Persona_Fill.bat - the same review-and-fill as Queue_HongKong_Persona_Fill.bat, for any port.
rem   Queue_Port_Persona_Fill.bat manila            review Manila's personas, then ask what to queue
rem   Queue_Port_Persona_Fill.bat saigon --review   review only
rem With no port it lists the ports and asks. Target is 1 clean + 5 NSFW (change with --clean N --nsfw N).
rem Run on BIGBOX with the Pi switched on. See tools\queue_port_persona_fill.py for every option.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
set "PORT=%~1"
if "%PORT%"=="" (
  %PY% tools\queue_port_persona_fill.py --list-ports
  set /p "PORT=Which port? "
)
if "%PORT%"=="" goto :end
shift
set "REST="
:more
if "%~1"=="" goto :run
set "REST=%REST% %1"
shift
goto :more
:run
%PY% tools\queue_port_persona_fill.py --port %PORT% %REST%
:end
echo.
pause
