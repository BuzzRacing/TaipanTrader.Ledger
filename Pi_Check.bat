@echo off
rem Step 1 of the Pi move: a read-only look at mad-pihole (192.168.1.69).
rem Changes nothing on the Pi except saving a Pi-hole Teleporter backup,
rem which is copied into D:\Mad-PiHole\teleporter-backup.
rem The full report is written to pi\pi_check_report.txt.
setlocal
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "REPORT=%~dp0pi\pi_check_report.txt"

echo Checking the Pi... (this takes about a minute)
echo Crimson Ledger - Pi check  %DATE% %TIME% > "%REPORT%"

ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "bash -s" < "%~dp0pi\check_remote.sh" >> "%REPORT%" 2>&1
if errorlevel 255 (
  echo.>> "%REPORT%"
  echo SSH to %PI% FAILED.>> "%REPORT%"
)

echo.>> "%REPORT%"
echo ===== Copying the Teleporter backup to D:\Mad-PiHole\teleporter-backup =====>> "%REPORT%"
scp -o BatchMode=yes %PI%:/tmp/pi-hole_*_teleporter_*.zip "D:\Mad-PiHole\teleporter-backup" >> "%REPORT%" 2>&1
if errorlevel 1 (echo Teleporter copy FAILED.>> "%REPORT%") else (echo Teleporter copy OK.>> "%REPORT%")

echo.>> "%REPORT%"
echo ===== Folder sizes on BIGBOX (D:\SeaTrader) =====>> "%REPORT%"
powershell -NoProfile -Command "Get-ChildItem -Directory 'D:\SeaTrader' -Force | ForEach-Object { $s=(Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; '{0,-24} {1,10:N1} MB' -f $_.Name, ($s/1MB) }" >> "%REPORT%" 2>&1

echo.>> "%REPORT%"
echo ===== Is the game running on BIGBOX? =====>> "%REPORT%"
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://127.0.0.1:8765/api/info; 'Yes, on localhost:8765' } catch { 'No' }" >> "%REPORT%" 2>&1

echo.
echo Done. Tell Claude "check done".
echo Report: %REPORT%
echo.
pause
endlocal
