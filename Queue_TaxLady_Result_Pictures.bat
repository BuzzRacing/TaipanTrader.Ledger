@echo off
rem Queues the Port Authority's wide 16:9 TAX-RESULT pictures on the live game (the Pi). Run on BIGBOX.
rem For every tax lady (10 port officers + Mrs. Marlowe) and each result (good = delighted, bad = furious):
rem   1 NSFW + 1 clean picture, filed under Personas > (her name), role "Tax result, good" / "Tax result, bad",
rem   tagged "tax-result" (clean ones "tax-result, clean").  11 women x 2 results x 2 = 44 pictures.
rem The full-width result screen at her desk shows only these; until one exists it uses her portrait pictures.
rem It also saves the Recipe "Tax lady result pictures" in Admin > Media Library > Recipes, to top them up later.
rem RUN Deploy_To_Pi.bat FIRST: the live game must know the two new roles (the tool checks and stops if not).
rem Extra options go straight through, e.g.  --dry   or   --who officer_saigon   or   --result good   or   --only clean
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_tax_result_pictures.py %*
echo.
pause
