@echo off
rem Queues very wide 1860 SOUTH CHINA SEA "swimsuit edition" banners for the Dashboard masthead: Madame Anahit and Celeste x 5 scenes
rem (cove, lagoon, sandbar, moonlit, storm). All cloth is period cloth: wet vintage cotton and linen, nothing modern.
rem
rem   TOPLESS is the default look and usually gets the BEST results (composed glamour in wet vintage cotton bathing drawers).
rem   Add the daring vintage cloth costume too:   Queue_Masthead_Banners.bat --looks topless,vintage
rem
rem Default = topless x 5 scenes x 2 women = 10 pictures; with both looks = 20. 16:5 is the widest the farm makes; she is dead centre as a low band.
rem Other options:  --scenes cove,lagoon   --count 3   --who gamemaster   --rating no   --dry (prints the prompts only)   Run on BIGBOX.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_masthead_banners.py %*
echo.
echo Watch them arrive in Admin ^> Media Library (jobs). Star the ones you like; the Dashboard uses any tagged masthead-banner.
pause
