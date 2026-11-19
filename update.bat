@echo off
rem Update Zengo in place: close it, pull the latest version, sync dependencies and the
rem dictionary, then start it again. If a step fails, it goes back to the version you had.
rem   update.bat            update, restart Zengo if it was running
rem   update.bat --restart  (used by Settings -> Update) always restart, close this window after
setlocal
cd /d "%~dp0"
set "PYV=.venv\Scripts\python.exe"
set "AUTO=0"
if /i "%~1"=="--restart" set "AUTO=1"

if not exist ".git" (
  echo This copy of Zengo wasn't installed with git, so it can't update itself.
  echo Download the new version into a new folder and run setup.bat there.
  goto :end_fail
)
where git >nul 2>nul
if errorlevel 1 (
  echo Git is needed to update: https://git-scm.com/download/win
  goto :end_fail
)
if not exist "%PYV%" (
  echo Run setup.bat first.
  goto :end_fail
)

echo Closing Zengo if it's running...
"%PYV%" -m zengo --quit
set "RC=%errorlevel%"
set "WAS_RUNNING=0"
if "%RC%"=="0" set "WAS_RUNNING=1"
if "%RC%"=="2" (
  echo Zengo didn't close. Quit it from its tray icon, then run update.bat again.
  goto :end_fail
)
if "%AUTO%"=="1" set "WAS_RUNNING=1"

for /f %%h in ('git rev-parse HEAD') do set "PREV=%%h"
echo Downloading the latest version...
git pull --ff-only
if errorlevel 1 (
  echo.
  echo Couldn't update: git pull failed ^(no connection, or local edits that clash with the update^).
  echo Nothing was changed.
  call :restart
  goto :end_fail
)
for /f %%h in ('git rev-parse HEAD') do set "NEW=%%h"

"%PYV%" scripts\sync_env.py
if errorlevel 1 goto :rollback

if "%PREV%"=="%NEW%" (echo Already up to date.) else (echo.& echo Updated. What changed:& git log --format="  - %%s" %PREV%..%NEW%)
call :restart
if "%AUTO%"=="1" (timeout /t 4 >nul & exit /b 0)
pause
exit /b 0

:rollback
echo.
echo The update failed, so Zengo is going back to the version you had...
git reset --keep %PREV%
"%PYV%" scripts\sync_env.py
call :restart
goto :end_fail

:restart
if "%WAS_RUNNING%"=="1" (
  echo Starting Zengo...
  start "" ".venv\Scripts\pythonw.exe" zengo.pyw
)
exit /b 0

:end_fail
echo.
pause
exit /b 1
