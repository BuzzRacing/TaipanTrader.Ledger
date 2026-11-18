@echo off
rem Switches on the agent file locks for this folder. Double-click it once.
rem It copies tools\agent_locks\settings.json to .claude\settings.json, which is
rem where Claude Code looks for project hooks. Run it again after updating it.
setlocal
cd /d "%~dp0"
if not exist "tools\agent_locks\settings.json" goto missing
if not exist ".claude" mkdir ".claude"
if not exist ".claude\settings.json" goto copy
fc /b "tools\agent_locks\settings.json" ".claude\settings.json" >nul 2>nul
if not errorlevel 1 goto already
copy /y ".claude\settings.json" ".claude\settings.json.bak" >nul
echo Your old .claude\settings.json was saved as .claude\settings.json.bak

:copy
copy /y "tools\agent_locks\settings.json" ".claude\settings.json" >nul
if errorlevel 1 goto failed
echo.
echo Agent file locks are switched on for this folder.
goto done

:already
echo.
echo Agent file locks were already switched on. Nothing changed.

:done
echo Close and reopen any Claude Code windows already working here so they pick it up.
echo Use Agent_Locks.bat to see which files are checked out.
echo.
pause
exit /b 0

:missing
echo.
echo tools\agent_locks\settings.json is missing, so nothing was installed.
echo.
pause
exit /b 1

:failed
echo.
echo Could not write .claude\settings.json. Nothing was changed.
echo.
pause
exit /b 1
