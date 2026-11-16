@echo off
rem Saves the game and stops the SeaTrader server.
if exist "%~dp0server_address.txt" (
  echo The game runs on another machine, listed in server_address.txt.
  echo To change it, stop it there.
  pause
  exit /b 0
)
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Method POST -ContentType 'application/json' -Body '{}' http://127.0.0.1:8765/api/shutdown; Write-Host 'SeaTrader saved and stopped.' } catch { Write-Host 'SeaTrader was not running.' }"
timeout /t 2 /nobreak >nul
