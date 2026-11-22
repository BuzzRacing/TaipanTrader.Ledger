@echo off
rem Queue_Nagasaki_Mayor_Pictures.bat - five dramatic NSFW PROFILE pictures of the Lady Mayor of Nagasaki (waist-up, not promotional), on the live game (the Pi).
rem   1 the duel     dawn cutlass duel on the Dejima quay          (completely topless)
rem   2 the typhoon  on the harbour-office roof, storm lantern     (completely naked, chain of office only)
rem   3 the raid     boarding axe through seized contraband        (completely topless)
rem   4 the dive     rising from the night harbour, strongbox key  (completely naked)
rem   5 the bonfire  burning the town's ledger of debts            (completely naked, gloves and chain)
rem Glamour styling, never explicit. Filed in Media Library > Ports > Nagasaki, role mayor (her profile picture), NSFW, tag nagasaki-action.
rem Run it on BIGBOX with the Pi switched on. Extra options go straight through, e.g.
rem   --dry (print the prompts, queue nothing)   --count 2 (two of each)   --only 2,5   --server http://192.168.1.69:8765
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_nagasaki_mayor_pictures.py %*
echo.
pause
