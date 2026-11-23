@echo off
rem Adds 15 new Port Authority lines for the clean-customs receipt (the "Stamped and sealed... I could get used to you" one):
rem 10 suggestive (innuendo, never explicit; each has its own clean family wording) and 5 clean on every screen.
rem Changes trade_text.py (new bank m.customs_clean.0-14), engine.py (the receipt draws from it) and cast.py (the officer reads it).
rem Backups go to cache\customs_clean_backup\. Safe to run again.
rem
rem   Add_Customs_Clean_Lines.bat          apply it
rem   Add_Customs_Clean_Lines.bat check    just test that the patch fits, change nothing
rem
rem Run it when no agent is mid-edit on engine.py or cast.py (the lock list is shown first). Then restart the server or
rem run Deploy_To_Pi.bat. The voice records each new line the first time it is heard, then replays it for free.
setlocal
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"

echo Who holds files right now:
%PY% "tools\agent_locks\file_lock.py" status
echo.
if /i "%~1"=="check" (
  %PY% "tools\add_customs_clean_lines.py" --check
) else (
  %PY% "tools\add_customs_clean_lines.py"
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
