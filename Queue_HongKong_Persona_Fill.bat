@echo off
rem Queue_HongKong_Persona_Fill.bat - reviews every Hong Kong persona's pictures on the live game (the Pi) and
rem fills the gaps so each has 1 clean + 5 NSFW. Covers the cast whose home port is Hong Kong (Personas > her
rem name) and the port's own keeper, shipmaster, mayor and taxlady (Ports > Hong Kong).
rem It prints the review first, then asks: 1 = per woman, 2 = per woman and picture role, Enter = queue nothing.
rem Safe to run again: filed pictures and jobs still on the farm are counted, so it only adds what is short.
rem Run on BIGBOX with the Pi switched on. Extra options go straight through, e.g.
rem   --review (review only)   --dry (print prompts)   --nsfw 8   --clean 2   --who bookmaker,mayor   --max 40
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_port_persona_fill.py --port hongkong %*
echo.
pause
