@echo off
rem Gives the Pi's game the Inworld voice key, so the cast speaks again.
rem On BIGBOX the key came from the Windows INWORLD_API_KEY setting; the Pi service
rem cannot see that, so voices were switched off there. This writes the key into
rem config/voice_key.json on the Pi (deploys never touch config/), restarts the
rem game (it saves first) and checks voices are on. The key is never shown.
rem Report: pi\voice_key_report.txt
setlocal
cd /d "%~dp0"
set "PI=madlively@192.168.1.69"
set "PIDIR=/home/madlively/SeaTrader"
set "LOG=%~dp0pi\voice_key_report.txt"
echo Crimson Ledger - voice key to the Pi  %DATE% %TIME% > "%LOG%"

if "%INWORLD_API_KEY%"=="" goto nokey

echo [1/3] Sending the voice key to the Pi...
(echo {"key": "%INWORLD_API_KEY%"}) | ssh -o BatchMode=yes -o ConnectTimeout=10 %PI% "umask 077; mkdir -p %PIDIR%/config && cat > %PIDIR%/config/voice_key.json && echo KEY_OK" >> "%LOG%" 2>&1
findstr /c:"KEY_OK" "%LOG%" >nul || goto sendfailed

echo [2/3] Restarting the game on the Pi (it saves first)...
ssh -o BatchMode=yes %PI% "sudo systemctl restart seatrader && sleep 3 && systemctl is-active seatrader" >> "%LOG%" 2>&1

echo [3/3] Checking voices are on...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 20;$i++){ try { $r=Invoke-RestMethod -TimeoutSec 3 http://192.168.1.69:8765/api/info; if($r.voice.enabled){$ok=$true; break} } catch {}; Start-Sleep 1 }; if($ok){ 'VOICES_ON' } else { 'VOICES_STILL_OFF' }" >> "%LOG%" 2>&1
ssh -o BatchMode=yes %PI% "journalctl -u seatrader -n 8 --no-pager" >> "%LOG%" 2>&1
findstr /c:"VOICES_ON" "%LOG%" >nul || goto stilloff
echo.
echo Voices are ON on the Pi. Refresh the game screens and tap once (iPads need a tap before sound).
goto end

:nokey
echo No INWORLD_API_KEY on this PC.>> "%LOG%"
echo This PC has no INWORLD_API_KEY setting, so there is no key to send.
echo Open Admin, go to Cast and Voices, and paste the Inworld key there instead.
goto end
:sendfailed
echo SEND FAILED.>> "%LOG%"
echo Could not write the key on the Pi. Details are in pi\voice_key_report.txt.
goto end
:stilloff
echo The key is on the Pi but voices still report OFF. Details are in pi\voice_key_report.txt.
echo Check Admin, Cast and Voices: the Voices switch must be on.
goto end

:end
echo Report: %LOG%
echo.
pause
endlocal
