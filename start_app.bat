@echo off
rem DOE-RSM app launcher (double-click to start)
cd /d "%~dp0"
rem Install only on the first run or when pyproject.toml (the list of required packages) changes.
python -c "import hashlib,pathlib,sys; h=hashlib.sha1(pathlib.Path('pyproject.toml').read_bytes()).hexdigest(); m=pathlib.Path('.installed'); sys.exit(0 if m.exists() and m.read_text()==h else 1)" 2>nul
if errorlevel 1 (
  echo First start: installing DOE-RSM. This takes a few minutes only once.
  python -m pip install --quiet --disable-pip-version-check -e ".[app]"
  if errorlevel 1 (
    echo.
    echo Python was not found or the installation failed.
    echo Install Python 3.10 or later from https://www.python.org/ and check "Add python.exe to PATH".
    pause
    exit /b 1
  )
  python -c "import hashlib,pathlib; pathlib.Path('.installed').write_text(hashlib.sha1(pathlib.Path('pyproject.toml').read_bytes()).hexdigest())"
)
echo Starting DOE-RSM. Your browser will open. Close this window to stop the app.
python -m doe_rsm app
pause
