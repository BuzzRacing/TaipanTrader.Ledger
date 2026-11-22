@echo off
rem Queues wide 16:9 WALLPAPER master shots for the Accounting Ledger's faded backdrops (21 Nov 2026), on the live game (the Pi). Run on BIGBOX.
rem Each page of the Ledger lays one of these under the linen, faded and multiplied into the paper:
rem   The Purse         left Bookkeeper, right Banker
rem   The Counting House left Moneylender, right Shipwright
rem   Dues and Duties    left Comprador (warehouses), right Tax Lady (Port Authority)
rem Until a wallpaper exists for someone the Ledger uses her portrait instead, so nothing is missing in the meantime.
rem Default: 8 women x topless, nude and clean = 24 pictures, filed under Personas > (her name), role wallpaper,
rem tagged "master-shot, wallpaper, <look>" (the clean ones are the only ones a family-friendly screen sees).
rem Extra options go straight through, e.g.  --dry   or   --count 2   or   --tiers nude,clean   or   --who bookkeeper,banker
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_master_shots.py --who bookkeeper,banker,lender,shipwright,comprador,taxlady,mayor,agent %*
echo.
pause
