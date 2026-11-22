@echo off
rem Queues the VOYAGE CERTIFICATE's custom pictures (21 Nov 2026) on the live game (the Pi). Run on BIGBOX.
rem The certificate is the 1920x1080 wallpaper at the end of the game: home port behind, home Mayor on the left,
rem the woman who defined the voyage on the right. Three sets, all wide 16:9:
rem   backdrops  one scene of each port, calm and dark in the middle where the words go (scenery only, clean)
rem   mayors     each port's Mayor in the LEFT third of the frame, the rest dark and empty      1 nude + 1 clean
rem   personas   Powder, Li Yue, Madam Shek, Madam Wu, Mrs. Marlowe, Madame Anahit and every Port Authority
rem              officer in the RIGHT third of the frame                                        1 nude + 1 clean
rem Default = 10 backdrops + 20 Mayors + 32 personas = 62 pictures, tagged "certificate" (the clean ones are the
rem only ones a family-friendly screen sees). Nothing is replaced or deleted.
rem Until the certificate itself is on the Pi, Madam Wu and Mrs. Marlowe are held back (the Accounting Ledger would
rem use their certificate pictures as page backdrops). Run this again later, or add --all to queue them now.
rem
rem Try it first:      Queue_Certificate_Pictures.bat --dry                 (prints every prompt, queues nothing)
rem One port only:     Queue_Certificate_Pictures.bat --ports hongkong      (its backdrop, Mayor and officer: 5 pictures)
rem Other options:     --sets backdrops,mayors,personas   --who bosun,pirate   --tiers topless,clean   --count 2
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_certificate_pictures.py %*
echo.
pause
