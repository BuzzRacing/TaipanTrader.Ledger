@echo off
rem Copies the live game's data from the Pi into D:\SeaTrader_PiBackup\<date>:
rem   saves, journal, captains, config and cache (the paid voice clips).
rem Keeps the last 14 days. The live game keeps running.
rem   Pull_Pi_Backup.bat            back up now
rem   Pull_Pi_Backup.bat register   also run it every night at 3:17 (Windows Task Scheduler)
rem   Pull_Pi_Backup.bat quiet      back up without waiting for a key (used by the nightly task)
setlocal
set "PI=madlively@192.168.1.69"
set "PIDIR=/home/madlively/SeaTrader"
set "ROOT=D:\SeaTrader_PiBackup"

if /i "%~1"=="register" (
  schtasks /create /tn "Crimson Ledger Pi Backup" /tr "\"%~f0\" quiet" /sc daily /st 03:17 /f
  if errorlevel 1 (echo Could not register the nightly task.) else (echo Nightly backup registered: every day at 3:17.)
)

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "STAMP=%%d"
set "DEST=%ROOT%\%STAMP%"
if not exist "%DEST%" mkdir "%DEST%"
set "LOG=%ROOT%\backup_log.txt"

echo Backing up the Pi's game to %DEST% ...
ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "cd %PIDIR% && tar -cf - saves journal captains config cache" | tar -xf - -C "%DEST%"
if errorlevel 1 (
  echo %STAMP%  FAILED>> "%LOG%"
  echo The backup FAILED. Is the Pi on?
  rmdir /s /q "%DEST%" 2>nul
) else (
  echo %STAMP%  OK>> "%LOG%"
  echo Backup OK.
  powershell -NoProfile -Command "Get-ChildItem '%ROOT%' -Directory | Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-14) } | Remove-Item -Recurse -Force"
)

if /i not "%~1"=="quiet" pause
endlocal
