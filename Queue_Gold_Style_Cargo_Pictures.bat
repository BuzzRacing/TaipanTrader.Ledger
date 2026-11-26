@echo off
rem Queues Taipan Trader's cargo catalog in the "gold" muslin product-shot style, product LARGE in the frame,
rem on the Taipan Trader server (http://taipantrader.ledger on the Pi).
rem Clean only: Opium and Arms get just their family stand-ins (Fireworks, Ironware); every other cargo gets an icon.
rem Cargoes the server does not have yet are skipped. 3 per cargo, filed to Media Library > Cargo, tagged
rem "muslin product-shot large". They join the pictures already there; nothing is replaced or deleted.
rem Run on BIGBOX; the Taipan Trader Admin trusts it without a password.
rem Optional: Queue_Gold_Style_Cargo_Pictures.bat [server] [count] [only] [--dry]
rem   only = one cargo (e.g. gold), or "luxuries", or "family" (the two stand-ins)
rem   e.g.  Queue_Gold_Style_Cargo_Pictures.bat http://taipantrader.ledger 5 gold
rem         Queue_Gold_Style_Cargo_Pictures.bat http://127.0.0.1:8775     (the copy on this PC)
rem         Queue_Gold_Style_Cargo_Pictures.bat --dry                     (prints the prompts, queues nothing)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_gold_style_cargo_pictures.py %*
echo.
pause
