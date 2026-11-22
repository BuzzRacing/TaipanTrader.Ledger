@echo off
rem Opens a PREVIEW of the Voyage Certificate (21 Nov 2026) in your browser, drawn by the game's own painter
rem with this PC's pictures, fonts and wording, and invented figures. No game is loaded and nothing is saved.
rem The browser opens by itself. Leave this window open while you look; close it to stop the preview.
rem The other looks you can try (a bad finish, rivals, another port) are listed in this window when it starts.
rem If it stops, the reason is shown here and kept in cache\preview_certificate.log.
title Voyage Certificate preview
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\preview_certificate.py
echo.
echo The preview has stopped. If you did not stop it, the reason is above and in cache\preview_certificate.log.
echo.
pause
