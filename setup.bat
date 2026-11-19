@echo off
rem One-time setup on a new Windows machine: venv, dependencies, dictionaries.
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>nul
if errorlevel 1 (
  echo Zengo needs Python 3.10 or newer: https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv || goto :fail
)
rem Installs dependencies and builds (or upgrades) the dictionary. Safe to re-run as a repair.
".venv\Scripts\python.exe" scripts\sync_env.py --always-install || goto :fail

echo.
echo Done. Start Zengo with start-zengo.bat, then add your API keys in Settings.
echo Later, run update.bat (or Settings, About) to update.
pause
exit /b 0

:fail
echo.
echo Setup failed. See the error above.
pause
exit /b 1
