@echo off
rem Brings the latest Crimson Ledger code (GitHub BuzzRacing/SeaTrader, branch main) into Taipan Trader,
rem then checks Taipan Trader's own rules: family-friendly only, no NSFW pictures, a mixed cast.
rem Push Crimson Ledger to GitHub first (D:\SeaTrader), or its newest work will not be included.
rem Taipan Trader's settings and picture library (config\settings.json, config\media.json) are kept as they are.
setlocal
cd /d "%~dp0"
git config merge.ours.driver true
git remote get-url upstream >nul 2>nul || git remote add upstream https://github.com/BuzzRacing/SeaTrader.git
git diff --quiet && git diff --cached --quiet
if errorlevel 1 (
  echo You have unsaved changes in Taipan Trader. Commit them first, then run this again.
  pause
  exit /b 1
)
echo Fetching Crimson Ledger...
git fetch upstream main || (echo Could not reach GitHub. & pause & exit /b 1)
git merge --no-edit upstream/main
if errorlevel 1 (
  echo.
  echo Crimson Ledger changed some of the same lines as Taipan Trader. These files need a look:
  git diff --name-only --diff-filter=U
  echo.
  echo Ask Claude to finish the merge, keeping Taipan Trader clean-only with its mixed cast.
  pause
  exit /b 1
)
set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
%PY% tools\taipan_admin_css.py
git add web\taipan-admin.css
git diff --cached --quiet || git commit -q -m "Rebuild Taipan Admin colours after the Crimson Ledger merge"
%PY% tests\taipan_clean_test.py
if errorlevel 1 (
  echo.
  echo The merge brought in something that breaks Taipan Trader's rules. Ask Claude to fix it before pushing.
  pause
  exit /b 1
)
echo.
echo Merged and checked. Pushing to GitHub...
git push origin main
pause
endlocal
