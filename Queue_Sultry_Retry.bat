@echo off
rem Re-queues the SULTRY look only, rebuilt pose-first (persona_prompts_v2.py, 21 Nov 2026) after the first round was "too covered and stiff".
rem Six women x 2 pictures = 12 on the live game (the Pi), role portrait, NSFW, tagged "v2-test, sultry, sultry-v2". Run on BIGBOX.
rem Compare with the first round (tag v2-test, sultry, without sultry-v2). Extra options pass through, e.g. --dry or --count 3
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_v2_prompt_test.py --tiers sultry --who bookkeeper,officer_batavia,bosun,taxlady,pirate,officer_hongkong --count 2 --tag sultry-v2 %*
echo.
pause
