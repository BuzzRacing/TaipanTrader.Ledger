@echo off
rem Queues the Legends' pictures on the live game (the Pi), 20 Nov 2026. Run on BIGBOX.
rem Deploy the Legends update to the Pi first (Deploy_To_Pi.bat), or the Pi will not know the new people and scenes.
rem   1. The picture behind each chapter (Scenes > "Legend: ..."): 19 scenes x 2 = 38 pictures (the Palace's 4 and the second set's 15), nobody in them.
rem   2. NSFW + clean PAIRS of the three storytellers and each Legend's own characters, from their cast prompts:
rem        portrait x3 pairs, speaking x3 pairs, sly x2 pairs each; now also the second set's four characters = 128 pictures (Personas > her name).
rem Extra options go to the pairs, e.g.  Queue_Legend_Pictures.bat --dry   or   --only clean
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_legend_pictures.py
%PY% tools\queue_persona_pairs.py --who teller_,legend_ --mood "looking straight at the viewer as she begins her story, a slow knowing smile" --tag portrait --roles portrait --count 3 %*
%PY% tools\queue_persona_pairs.py --who teller_,legend_ --mood speaking --tag speaking --roles speaking --count 3 %*
%PY% tools\queue_persona_pairs.py --who teller_,legend_ --mood sly --tag sly --roles sly --count 2 %*
echo.
pause
