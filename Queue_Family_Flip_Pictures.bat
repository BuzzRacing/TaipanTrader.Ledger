@echo off
rem Queues the Family Friendly FLIP pictures (Captain's Options > Table settings), on the live game (the Pi). Run on BIGBOX.
rem Four personas, each in two SQUARE states, from her own cast prompt:
rem   SAFE    buttoned up, demure and refined      filed not-NSFW, tags "square nsfw-or-safe, safe, clean"
rem   UNSAFE  caught in a state of undress,        filed NSFW,     tags "square nsfw-or-safe, unsafe"
rem           but not exposed
rem   taxlady    Mrs. Evelyn Marlowe, the Registrar
rem   mayor      Her Worship the Mayor
rem   bookkeeper Mademoiselle Celeste Vautrin
rem   banker     Moira Haig, the Chief Cashier
rem = 8 pictures. Filed under Personas > (her name). Each time Options opens it picks one persona with both a safe and
rem an unsafe picture tagged "nsfw-or-safe", and a tap on the picture flips Safe / Unsafe.
rem Extra options go straight through, e.g.  Queue_Family_Flip_Pictures.bat --count 2   or   --dry   or   --who bookkeeper
rem   or   --only unsafe
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_family_flip_pictures.py %*
echo.
pause
