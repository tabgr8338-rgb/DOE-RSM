@echo off
rem DOE-RSM app launcher (double-click to start)
cd /d "%~dp0"
echo Installing / updating DOE-RSM ...
python -m pip install --quiet --disable-pip-version-check -e ".[app]"
if errorlevel 1 (
  echo.
  echo Python was not found or the installation failed.
  echo Install Python 3.10 or later from https://www.python.org/ and check "Add python.exe to PATH".
  pause
  exit /b 1
)
echo Starting DOE-RSM. Your browser will open. Close this window to stop the app.
python -m doe_rsm app
pause
