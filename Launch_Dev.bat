@echo off
rem Opens the TEST copy of the game on this computer (BIGBOX), even when
rem server_address.txt points the other launchers at the Pi (sea.trade).
rem Its saves are test games only; the live game is on the Pi.
rem   Launch_Dev.bat          player screen
rem   Launch_Dev.bat board    harbor board
rem   Launch_Dev.bat admin    admin page
rem   Launch_Dev.bat stop     save and stop the test server
rem   Launch_Dev.bat new      archive the test game and start a fresh one
setlocal
set "ST_DEV=1"
if /i "%~1"=="stop" (call "%~dp0Stop_TaipanTrader.bat" & exit /b)
if /i "%~1"=="new" (call "%~dp0New_Game.bat" & exit /b)
call "%~dp0Launch_TaipanTrader.bat" %*
endlocal
