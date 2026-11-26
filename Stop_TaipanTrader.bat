@echo off
rem Saves the game and stops the Taipan Trader server.
if not defined ST_DEV if exist "%~dp0server_address.txt" (
  echo The game runs on another machine, listed in server_address.txt.
  echo To change it, stop it there.
  pause
  exit /b 0
)
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Method POST -ContentType 'application/json' -Body '{}' http://127.0.0.1:8775/api/shutdown; Write-Host 'Taipan Trader saved and stopped.' } catch { Write-Host 'Taipan Trader was not running.' }"
timeout /t 2 /nobreak >nul
