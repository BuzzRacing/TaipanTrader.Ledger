@echo off
rem Adds five opium-only and five marijuana-only buy lines to the comprador's bank (NSFW wording; family-friendly screens keep one clean line).
rem Changes trade_text.py (the new banks m.bought.opium.0-4 and m.bought.marijuana.0-4) and engine.py (a bulk purchase of a cargo with its own
rem bank draws from it). Backups go to cache\opium_buy_backup\. Safe to run again.
rem
rem   Add_Opium_Buy_Lines.bat          apply it
rem   Add_Opium_Buy_Lines.bat check    just test that the patch fits, change nothing
rem
rem Run it when no agent is mid-edit on engine.py (the lock list is shown first). Then restart the server or
rem run Deploy_To_Pi.bat. "Bulk" is BULK_MIN in trade_text.py (50 units by default).
setlocal
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"

echo Who holds files right now:
%PY% "tools\agent_locks\file_lock.py" status
echo.
if /i "%~1"=="check" (
  %PY% "tools\add_opium_buy_lines.py" --check
) else (
  %PY% "tools\add_opium_buy_lines.py"
)
if errorlevel 1 goto end
if /i "%~1"=="check" goto end
if exist "tests\house_voice_test.py" (
  echo.
  echo Running the house voice test...
  %PY% "tests\house_voice_test.py"
)
:end
echo.
pause
endlocal
