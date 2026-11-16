@echo off
rem Uploads SeaTrader to GitHub. Double-click it; that is all.
rem   Upload_To_GitHub.bat                     asks for a short note (Enter = automatic)
rem   Upload_To_GitHub.bat "Fixed typhoons"    uses that note, no question asked
rem
rem What it does each time:
rem   1. Sets the folder up for git the first time it runs.
rem   2. Drops anything that should not be on GitHub (saves, browser profile,
rem      Python cache) according to .gitignore, even if it was uploaded before.
rem   3. Commits every change and pushes it to the repo below.
setlocal
cd /d "%~dp0"
set "REPO=https://github.com/BuzzRacing/SeaTrader.git"
set "BRANCH=main"

where git >nul 2>nul
if errorlevel 1 goto nogit

if exist ".git" goto ready
echo Setting this folder up for git (first run only)...
git init -q
if errorlevel 1 goto failed
git symbolic-ref HEAD refs/heads/%BRANCH%

:ready
git remote get-url origin >nul 2>nul
if errorlevel 1 git remote add origin "%REPO%"
git remote set-url origin "%REPO%"

git config user.name >nul 2>nul
if errorlevel 1 goto noidentity
git config user.email >nul 2>nul
if errorlevel 1 goto noidentity

rem Take anything that is now ignored back out of the upload list.
for /f "delims=" %%F in ('git ls-files -ci --exclude-standard 2^>nul') do git rm --cached -q -- "%%F"

git add -A
if errorlevel 1 goto failed

git diff --cached --quiet
if not errorlevel 1 goto nochanges

echo.
echo Changes going up:
git status --short
echo.
set "MSG=%~1"
if not defined MSG set /p "MSG=Short note for this upload (Enter to skip): "
if not defined MSG set "MSG=Update %date% %time:~0,5%"
git commit -q -m "%MSG%"
if errorlevel 1 goto failed
goto sync

:nochanges
echo No new changes to commit.

:sync
git rev-parse --verify -q HEAD >nul 2>nul
if errorlevel 1 goto empty

echo.
echo Talking to GitHub...
git fetch -q origin
if errorlevel 1 goto nofetch

rem If GitHub has commits this folder lacks (a README made on the site, or
rem work pushed from another machine), fold them in. This folder wins ties.
git rev-parse --verify -q origin/%BRANCH% >nul 2>nul
if errorlevel 1 goto push
git merge-base --is-ancestor origin/%BRANCH% HEAD >nul 2>nul
if not errorlevel 1 goto push
echo GitHub has changes this folder does not. Merging them in...
git merge origin/%BRANCH% --allow-unrelated-histories -X ours --no-edit -q
if errorlevel 1 goto mergefailed

:push
git push -u origin HEAD:%BRANCH%
if errorlevel 1 goto pushfailed

echo.
echo ------------------------------------------------------------
echo  Uploaded. Files now on GitHub:
echo ------------------------------------------------------------
git ls-files
echo ------------------------------------------------------------
git status --short --branch
echo.
echo  https://github.com/BuzzRacing/SeaTrader
echo.
pause
exit /b 0

:empty
echo.
echo There is nothing in this folder to upload yet.
pause
exit /b 0

:nogit
echo.
echo Git was not found on this computer.
echo Install it from https://git-scm.com/download/win (the defaults are fine),
echo then run this file again.
echo.
pause
exit /b 1

:noidentity
echo.
echo Git does not know who you are yet. Run these two lines once, with your
echo own name and the email on your GitHub account, then run this file again:
echo.
echo   git config --global user.name "Your Name"
echo   git config --global user.email "you@example.com"
echo.
pause
exit /b 1

:nofetch
echo.
echo Could not reach GitHub. Check the internet connection and that you are
echo signed in to GitHub (a sign-in window opens the first time).
echo Your changes are saved in this folder; run this file again to upload them.
echo.
pause
exit /b 1

:mergefailed
git merge --abort >nul 2>nul
echo.
echo GitHub has changes that could not be combined automatically.
echo Nothing was uploaded and nothing in this folder was changed.
echo.
pause
exit /b 1

:pushfailed
echo.
echo The upload did not go through. Your changes are saved in this folder;
echo run this file again to retry.
echo.
pause
exit /b 1

:failed
echo.
echo Something went wrong before the upload. Nothing was sent to GitHub.
echo.
pause
exit /b 1
