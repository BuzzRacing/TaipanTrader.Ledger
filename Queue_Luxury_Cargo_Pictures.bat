@echo off
rem Queues clean muslin product-shot pictures of the six new Cargo Tiers luxuries on the Taipan Trader server (taipantrader.ledger):
rem   Merchant batch: camphor, sandalwood, ginseng.   Merchant Prince batch: jade, pearls, ambergris.
rem 3 per cargo, filed to Media Library > Cargo with the "icon" role, tagged "muslin product-shot". Same look as
rem Queue_Muslin_Cargo_Pictures.bat. Run on BIGBOX; Admin there needs no password.
rem Deploy the Cargo Tiers data to the Pi first (Deploy_To_Pi.bat), or the Pi will not know the six new cargoes.
rem Optional: Queue_Luxury_Cargo_Pictures.bat [server] [count] [only] [--dry]
rem   e.g.  Queue_Luxury_Cargo_Pictures.bat http://taipantrader.ledger 5 pearls
rem         Queue_Luxury_Cargo_Pictures.bat --dry     (prints the prompts, queues nothing)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_luxury_cargo_pictures.py %*
echo.
pause
