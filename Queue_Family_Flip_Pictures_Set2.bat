@echo off
rem Queues the SECOND set of Family Friendly FLIP pictures (Captain's Options > Table settings), on the live game (the Pi). Run on BIGBOX.
rem Set 1 (Queue_Family_Flip_Pictures.bat) did taxlady, mayor, bookkeeper, banker. This set adds six more, a mix of
rem heritage, age and trade, each in two SQUARE states from her own cast prompt:
rem   SAFE    buttoned up, demure and refined      filed not-NSFW, tags "square nsfw-or-safe, safe, clean"
rem   UNSAFE  caught in a state of undress,        filed NSFW,     tags "square nsfw-or-safe, unsafe"
rem           but not exposed
rem   narrator   Roxana Cama, First Mate (Parsi, Bombay)
rem   bosun      Peggy "Powder" O'Rourke, Bosun and Master Gunner (Irish, Cork)
rem   lender     Madam Wu Lian, Moneylender (Chinese, Hong Kong)
rem   customs    Inspector Arabella Vane, Customs (English)
rem   bookmaker  Isabel "Fan-Tan Bella" da Rocha, Bookmaker (Portuguese)
rem   thieves    Kamala "Magpie" Pillai, Pickpocket Queen (Indian)
rem = 12 pictures. Filed under Personas > (her name). Options picks a persona with BOTH a safe and an unsafe picture
rem tagged "nsfw-or-safe", so these join the first four in the rotation. No deploy needed (no new roles or cast).
rem Extra options go straight through, e.g.  Queue_Family_Flip_Pictures_Set2.bat --count 2   or   --dry
rem   or   --only unsafe   or   --who bosun,thieves  (a later --who replaces the six above)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_family_flip_pictures.py --who narrator,bosun,lender,customs,bookmaker,thieves %*
echo.
pause
