@echo off
rem Sets the Admin password for the game on the Pi (crimson.ledger).
rem You type it here, hidden. It goes to the Pi inside the SSH connection (never on a
rem command line, never saved on this PC) and is stored salted and hashed in
rem config/admin.json on the Pi. Takes effect at once; no restart needed.
rem Leave it blank to cancel.
setlocal
cd /d "%~dp0"
echo Set the Admin password for Crimson Ledger on the Pi.
echo BIGBOX never needs it; iPads and other devices sign in with it.
echo.
powershell -NoProfile -Command ^
  "$a = Read-Host 'New password' -AsSecureString; $b = Read-Host 'Type it again' -AsSecureString;" ^
  "$p1 = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($a));" ^
  "$p2 = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($b));" ^
  "if ($p1 -eq '') { Write-Host 'Cancelled. Nothing changed.'; exit 2 }" ^
  "if ($p1 -ne $p2) { Write-Host 'The two did not match. Nothing changed.'; exit 3 }" ^
  "$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($p1));" ^
  "$py = 'import base64, config' + [char]10 + 'config.set_password(base64.b64decode(''' + $b64 + ''').decode(''utf-8''))' + [char]10 + 'print(''PASSWORD_SET'' if config.has_password() else ''FAILED'')' + [char]10;" ^
  "$out = $py | ssh -o BatchMode=yes -o ConnectTimeout=10 madlively@192.168.1.69 'cd /home/madlively/SeaTrader && python3 -' 2>&1 | Out-String;" ^
  "if ($out -match 'PASSWORD_SET') { Write-Host ''; Write-Host 'Admin password set on the Pi. Other devices sign in at http://crimson.ledger/admin'; exit 0 } else { Write-Host 'Could not set it:'; Write-Host $out; exit 1 }"
echo.
pause
endlocal
