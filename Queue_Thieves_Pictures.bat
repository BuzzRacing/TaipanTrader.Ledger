@echo off
rem Queues pictures of Kamala "Magpie" Pillai (key "thieves", the Thieves: pickpocket queen), the face of the Accounting Ledger's Thieves tile.
rem   1. Wallpapers: clean, topless and nude x2 each = 6 pictures (role wallpaper, tags master-shot / wallpaper / look).
rem   2. Portraits, speaking: nude + clean pair x3 = 6 pictures (roles portrait, speaking). The Ledger tile uses her portraits.
rem   3. Portraits, sly: nude + clean pair x2 = 4 pictures (role portrait, tag sly).
rem Clean ones are not NSFW and are the only ones a Family-friendly screen shows. 16 pictures on the live game (the Pi). Run on BIGBOX.
rem Run Deploy_To_Pi.bat FIRST so the Pi knows her (she joins a saved cast once, on the Pi's next settings validation).
rem Extra options go to every step, e.g.  --dry  (prints the prompts, queues nothing)
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
echo.
echo === 1 of 3: wallpapers ===
%PY% tools\queue_master_shots.py --who thieves --tiers clean,topless,nude --count 2 %*
echo.
echo === 2 of 3: speaking portraits ===
%PY% tools\queue_persona_pairs.py --who thieves --mood speaking --roles portrait,speaking --count 3 %*
echo.
echo === 3 of 3: sly portraits ===
%PY% tools\queue_persona_pairs.py --who thieves --mood sly --roles portrait --count 2 %*
echo.
echo Watch them arrive in Admin ^> Media Library (jobs). The Accounting Ledger picks them up on its next reload.
pause
