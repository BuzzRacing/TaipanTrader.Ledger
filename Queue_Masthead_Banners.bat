@echo off
rem Queues very wide SWIMSUIT-EDITION banners for the Dashboard masthead: Madame Anahit and Celeste x 5 scenes (cove, lagoon, sandbar, moonlit, storm) = 10 pictures.
rem 16:5 is the widest the farm makes; she is dead centre as a low horizontal band and the scene runs out both sides. Run on BIGBOX.
rem Options go straight through, e.g.  --scenes cove,lagoon --count 3   or   --who gamemaster   or   --dry (prints the prompts only)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_masthead_banners.py %*
echo.
echo Watch them arrive in Admin ^> Media Library (jobs). Star the ones you like; the Dashboard uses any tagged masthead-banner.
pause
