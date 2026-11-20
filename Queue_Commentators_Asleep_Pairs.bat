@echo off
rem Queues an NSFW + clean PAIR of "asleep" pictures for the sea battle's commentators, for the waiting screen
rem (C2, "Still fighting"): Powder O'Rourke (bosun) and the enemy seat, Admiral Li Yue (pirate, her war junks)
rem and Madam Shek Yu-lan (agent, the pirate junks). Each is dozing slumped against the mainmast, portrait
rem framing (3:4). 3 personas x 2 = 6 pictures on the live game (the Pi), from each one's own cast prompt,
rem filed under Personas > (her name) as Idle pictures, tagged "asleep" (NSFW) and "asleep, clean" (not NSFW).
rem Run on BIGBOX. Extra options go straight through, e.g.  --count 2   or   --dry   or   --only clean
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_persona_pairs.py --who bosun,pirate,agent --tag asleep --roles idle --mood "fast asleep, sitting slumped back against the ship's mainmast on the open deck at sea, eyes fully closed, head tipped back and resting on the mast, lips softly parted, arms loosely folded, utterly relaxed and dozing through a long wait, rigging and furled sails behind her, soft overcast light, vertical portrait framing" %*
echo.
pause
