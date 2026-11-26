@echo off
rem Queues the WHOLE cargo catalog in the "gold" muslin product-shot style, with the product LARGE in the frame
rem (camera close, the item fills about 80 percent of the picture), on the live game (the Pi):
rem   the original nine, the six Cargo Tiers luxuries, and the two family-friendly stand-ins (Fireworks, Ironware).
rem 3 per cargo = 51 pictures. Filed to Media Library > Cargo (role "icon", or "family" for the stand-ins),
rem tagged "muslin product-shot large". They join the pictures already there; nothing is replaced or deleted.
rem Run on BIGBOX; Admin there needs no password. Run Deploy_To_Pi.bat first so the Pi knows the six luxuries.
rem Optional: Queue_Gold_Style_Cargo_Pictures.bat [server] [count] [only] [--dry]
rem   only = one cargo (e.g. gold), or "luxuries" (the six new ones), or "family" (the two stand-ins)
rem   e.g.  Queue_Gold_Style_Cargo_Pictures.bat http://192.168.1.69:8765 5 gold
rem         Queue_Gold_Style_Cargo_Pictures.bat --dry     (prints the prompts, queues nothing)
cd /d "%~dp0"
set "PY=python"
where python >/dev/null 2>/dev/null || set "PY=py"
%PY% tools\queue_gold_style_cargo_pictures.py %*
echo.
pause
