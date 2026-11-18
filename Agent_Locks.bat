@echo off
rem Shows which files the Claude agents have checked out in this folder.
rem Double-click it. You can also clear every lock (for example after a crash).
setlocal
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"

:show
cls
echo ============================================================
echo  Crimson Ledger - agent file locks
echo ============================================================
echo.
%PY% "tools\agent_locks\file_lock.py" status
echo.
echo  R = refresh    C = clear ALL locks    Q = quit
choice /c RCQ /n /m "Choose: "
if errorlevel 3 goto end
if errorlevel 2 goto clear
goto show

:clear
echo.
echo Only clear locks when no agent is mid-edit (or one has crashed).
choice /c YN /n /m "Clear every lock now? (Y/N): "
if errorlevel 2 goto show
%PY% "tools\agent_locks\file_lock.py" clear
timeout /t 2 /nobreak >nul
goto show

:end
endlocal
