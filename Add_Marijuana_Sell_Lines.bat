@echo off
rem Adds five marijuana-only SELL lines to the comprador's bank (NSFW wording; family-friendly screens, where it is Hemp, keep one clean line).
rem Changes trade_text.py (the new bank m.sold.marijuana.0-4) and engine.py (a bulk sale at a profit draws from it).
rem Run Add_Marijuana_Buy_Lines.bat first. Backups go to cache\marijuana_sell_backup\. Safe to run again.
rem
rem   Add_Marijuana_Sell_Lines.bat          apply it
rem   Add_Marijuana_Sell_Lines.bat check    just test that the patch fits, change nothing
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
  %PY% "tools\add_marijuana_sell_lines.py" --check
) else (
  %PY% "tools\add_marijuana_sell_lines.py"
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
