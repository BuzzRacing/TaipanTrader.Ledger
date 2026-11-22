@echo off
rem Queues a side-by-side TEST of the v2 persona prompts (persona_prompts_v2.py) on the live game (the Pi):
rem Bookkeeper, Batavia officer, Powder and Mrs. Marlowe x 3 looks (topless, nude, clean) = 12 pictures,
rem filed under Personas > (her name), tagged "v2-test, <look>". Compare with her existing pictures. Run on BIGBOX.
rem Extra options go straight through, e.g.  --dry   or   --count 2   or   --who bookkeeper --tiers boudoir,topless
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_v2_prompt_test.py %*
echo.
pause
