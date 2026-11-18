@echo off
rem Read-only, second look at sea.trade lookups on this PC and in Pi-holes log.
rem Report: pi\dns_report2.txt
echo Checking...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pi\dns_check2.ps1" > "%~dp0pi\dns_report2.txt" 2>&1
echo Done. Tell Claude "dns2 done".
pause
