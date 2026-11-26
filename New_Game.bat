@echo off
rem Archives the current game into the saves folder and starts a fresh one.
if not defined ST_DEV if exist "%~dp0server_address.txt" (
  echo The game runs on another machine, listed in server_address.txt.
  echo To change it, use the host's new game button on the Ledger tab.
  pause
  exit /b 0
)
setlocal
cd /d "%~dp0"
echo This will end the current game and start a new one.
echo The old game is kept in the saves folder.
choice /c YN /m "Start a new game"
if errorlevel 2 exit /b 0
call "%~dp0Stop_TaipanTrader.bat"
set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
%PY% server.py --archive-only
call "%~dp0Launch_TaipanTrader.bat"
endlocal
