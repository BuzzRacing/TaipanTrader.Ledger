@echo off
rem Queues NSFW + clean PAIRS of pictures for the House's bookkeeper, Mademoiselle Celeste Vautrin
rem (the Accounting Ledger, 20 Nov 2026), on the live game (the Pi). Run on BIGBOX.
rem From her own cast prompt: sultry, erotic adult glamour for the NSFW set (openly nude), and a clean,
rem fully dressed twin of every picture for family-friendly screens. Filed under Personas > her name.
rem   portrait  x3 pairs  her plain come-hither portraits: the Ledger's rail button and her page header
rem   happy     x2 pairs  the books show a profit
rem   angry     x2 pairs  the books show a loss
rem   sly       x2 pairs  nothing much either way, or deep in debt
rem   speaking  x2 pairs  while she reads her line aloud
rem = 22 pictures. Extra options go straight through, e.g.  Queue_Bookkeeper_Pairs.bat --dry   or   --only clean
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_persona_pairs.py --who bookkeeper --mood portrait --tag portrait --roles portrait --count 3 %*
%PY% tools\queue_persona_pairs.py --who bookkeeper --mood ledger_happy --tag happy --roles happy --count 2 %*
%PY% tools\queue_persona_pairs.py --who bookkeeper --mood ledger_angry --tag angry --roles angry --count 2 %*
%PY% tools\queue_persona_pairs.py --who bookkeeper --mood ledger_sly --tag sly --roles sly --count 2 %*
%PY% tools\queue_persona_pairs.py --who bookkeeper --mood speaking --tag speaking --roles speaking --count 2 %*
echo.
pause
