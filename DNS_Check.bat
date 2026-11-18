@echo off
rem Read-only: finds out why sea.trade sometimes goes to GoDaddy on this PC.
rem Report: pi\dns_report.txt
echo Checking how this PC looks up sea.trade...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pi\dns_check.ps1" > "%~dp0pi\dns_report.txt" 2>&1
echo Done. Tell Claude "dns done".
pause
